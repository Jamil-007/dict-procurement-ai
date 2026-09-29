"""Retrieve legal authorities for findings.

BM25 over the pre-built index. No vector database and no embedding cost: at
this corpus size (a few thousand chunks of highly technical vocabulary where
the query terms are the statute's own terms) lexical matching is both
adequate and more predictable than a semantic search would be.

The contract with the rest of the system: a finding's `authority` is always
something this module returned. Nothing generates a citation.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)*")

# Terms that appear in nearly every chunk carry no signal here.
_STOPWORDS = frozenset(
    """a an and are as at be been by for from has have in is it its of on or
    that the this to was were will with shall may any such under which
    provided""".split()
)


def tokenize(text: str) -> List[str]:
    """Lowercase tokens, keeping dotted section numbers like `71.2.1` intact."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass
class Authority:
    """A retrieved legal citation attached to a finding."""

    doc: str
    section: str
    page: int
    quoted_text: str
    score: float = 0.0

    def citation(self) -> str:
        return f"{self.doc}, {self.section} (p. {self.page})"

    def to_dict(self) -> Dict:
        return {
            "doc": self.doc,
            "section": self.section,
            "page": self.page,
            "quoted_text": self.quoted_text,
            "citation": self.citation(),
        }


class LegalRetriever:
    """BM25 search over the legal corpus."""

    def __init__(self, index_path: str | Path):
        self.index_path = Path(index_path)
        self.chunks: List[Dict] = []
        self._bm25 = None
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        try:
            with open(self.index_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self.chunks = payload.get("chunks", [])
        except (json.JSONDecodeError, OSError):
            self.chunks = []
            return

        if not self.chunks:
            return

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            # Citations degrade to absent rather than taking the whole run
            # down; `available` is what callers check.
            self.chunks = []
            return

        corpus = [
            tokenize(f"{chunk['doc']} {chunk['section']} {chunk['text']}")
            for chunk in self.chunks
        ]
        self._bm25 = BM25Okapi(corpus)

    @property
    def available(self) -> bool:
        return self._bm25 is not None

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        docs: Optional[Sequence[str]] = None,
        quote_chars: int = 600,
    ) -> List[Authority]:
        """Return the best-matching authorities for `query`.

        Args:
            query: Free text; the rulepack's own wording works well, since it
                uses the same vocabulary as the issuances.
            top_k: How many to return. Defaults to KB_TOP_K.
            docs: Restrict to these canonical document names. Use this when a
                rule already knows which issuance governs it -- it prevents a
                GAM passage being cited for an IRR rule.
            quote_chars: Maximum length of the quoted excerpt.
        """
        if not self.available:
            return []

        top_k = top_k or settings.KB_TOP_K
        scores = self._bm25.get_scores(tokenize(query))

        allowed = set(docs) if docs else None
        ranked = sorted(
            (
                (score, index)
                for index, score in enumerate(scores)
                if score > 0
                and (allowed is None or self.chunks[index]["doc"] in allowed)
            ),
            reverse=True,
        )

        results: List[Authority] = []
        seen_sections = set()
        for score, index in ranked:
            chunk = self.chunks[index]
            # One citation per section: three chunks of the same chapter is
            # noise, not corroboration.
            key = (chunk["doc"], chunk["section"])
            if key in seen_sections:
                continue
            seen_sections.add(key)
            results.append(
                Authority(
                    doc=chunk["doc"],
                    section=chunk["section"],
                    page=chunk["page"],
                    quoted_text=_excerpt(chunk["text"], quote_chars),
                    score=round(float(score), 3),
                )
            )
            if len(results) >= top_k:
                break
        return results

    def best(
        self, query: str, docs: Optional[Sequence[str]] = None
    ) -> Optional[Authority]:
        """The single best authority for a query, or None."""
        results = self.search(query, top_k=1, docs=docs)
        return results[0] if results else None

    def find_section(self, doc: str, section_hint: str) -> Optional[Authority]:
        """Look up a specific section a rulepack names directly.

        Rulepacks declare their governing section (`IRR of RA 12009`,
        `Section 71.2.1`). This resolves that declaration to the real text so
        the citation carries a verbatim quote rather than just a number.
        """
        hint = section_hint.lower().strip()
        candidates = [c for c in self.chunks if c["doc"] == doc]
        if not candidates:
            return None

        matches = [c for c in candidates if c["section"].lower().startswith(hint)]

        if not matches:
            # Fall back to the kind + number, e.g. "Annex B" or "71.2.1",
            # appearing anywhere in the label -- a section nested under a
            # chapter reads "Chapter 8 - Disbursements, Section 12".
            #
            # The kind word is part of the needle on purpose: without it,
            # asking for "Annex S" in a circular whose scan lost that annex
            # would happily return "Section 1.2", a confident citation to the
            # wrong provision. Returning nothing is the correct answer.
            parsed = re.match(
                r"\s*(annex|appendix|chapter|section|article|rule)?\s*"
                r"([\d]+(?:\.[\d]+)*|[A-Z]{1,2})\b",
                section_hint,
                re.IGNORECASE,
            )
            if not parsed:
                return None
            kind, number = parsed.group(1), parsed.group(2)
            needle = rf"\b{re.escape(number.lower())}\b"
            if kind:
                needle = rf"\b{kind.lower()}\s+{re.escape(number.lower())}\b"
            matches = [
                c for c in candidates if re.search(needle, c["section"].lower())
            ]

        if not matches:
            return None

        chunk = matches[0]
        return Authority(
            doc=chunk["doc"],
            section=chunk["section"],
            page=chunk["page"],
            quoted_text=_excerpt(chunk["text"], 600),
            score=1.0,
        )


def _excerpt(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip() + "..."


_retriever: Optional[LegalRetriever] = None
_lock = threading.Lock()


def get_retriever(index_path: Optional[str] = None) -> LegalRetriever:
    """Process-wide retriever. The index is loaded and tokenized once."""
    global _retriever
    if _retriever is None or index_path is not None:
        with _lock:
            if _retriever is None or index_path is not None:
                _retriever = LegalRetriever(index_path or settings.KB_INDEX_PATH)
    return _retriever


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "variation order infrastructure"
    retriever = get_retriever()
    if not retriever.available:
        print("Index not built. Run: python -m kb.build_index --docs ../docs")
        raise SystemExit(1)
    print(f"{len(retriever.chunks)} chunks indexed\n")
    for authority in retriever.search(query, top_k=5):
        print(f"[{authority.score}] {authority.citation()}")
        print(f"    {authority.quoted_text[:300]}\n")
