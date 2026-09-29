"""Build the legal knowledge base index.

Run offline, once, whenever the corpus changes:

    python -m kb.build_index --docs ../docs

The source PDFs stay gitignored (they are 158 MB); the resulting
`kb/index.json` is small enough to commit, so a fresh checkout can cite
authorities without re-downloading the corpus.

Chunking follows section headings rather than a fixed window, because a
citation is only useful if it names the section a reader can look up.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pymupdf

# Filename fragment -> the canonical name used in citations, plus the kind of
# issuance. Anything not listed here is skipped: the index must contain only
# authorities we are willing to cite.
#
# Matching is by substring, so more specific fragments must come first --
# "GAM Volume I" would otherwise also match "GAM Volume II.pdf".
CORPUS: List[Tuple[str, str, str]] = [
    ("Implementing-Rules-and-Regulations-of-RA-12009", "IRR of RA 12009", "irr"),
    ("RA 12009", "RA 12009 (New Government Procurement Act)", "statute"),
    ("GAM Volume II", "Government Accounting Manual, Volume II", "gam"),
    ("GAM Volume I", "Government Accounting Manual, Volume I", "gam"),
    ("COA-CIRCULAR-NO.-2009-001", "COA Circular No. 2009-001", "coa"),
    ("COA-CIRCULAR-NO.-2023-004", "COA Circular No. 2023-004", "coa"),
    ("Volume 1 – Procurement Systems", "GPPB Generic Procurement Manual, Volume 1", "gppb"),
    ("Volume 2 – Procurement of Goods", "GPPB Generic Procurement Manual, Volume 2", "gppb"),
    ("Volume 3 – Procurement of Infrastructure", "GPPB Generic Procurement Manual, Volume 3", "gppb"),
    ("Volume 4 – Procurement of Consulting", "GPPB Generic Procurement Manual, Volume 4", "gppb"),
    ("Documentary Requirements for Specific Modes", "GPPB Documentary Requirements for Specific Modes of Procurement", "gppb"),
    ("Circular-No.-06-2026", "GPPB Circular No. 06-2026", "gppb"),
    ("GPPB-Resolution-No.-12-2026", "GPPB Resolution No. 12-2026", "gppb"),
    ("Circular-Bid-Docs-Fees", "GPPB Circular on Bidding Documents Fees", "gppb"),
    ("Circular-Tie-Break", "GPPB Circular on Tie-Breaking", "gppb"),
    ("GPPB-Resolution-No.-08-2026", "GPPB Resolution No. 08-2026", "gppb"),
    ("CIRCULAR-NO.-01-2026", "GPPB Circular No. 01-2026", "gppb"),
    ("GPPB-Resolution-No.-17-2026", "GPPB Resolution No. 17-2026", "gppb"),
]

# Heading forms that appear across the corpus, most specific first.
_HEADING_PATTERNS = [
    # IRR subsections: "71.1.1 Amendment to Order"
    re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){1,3})\.?\s+([A-Z][^\n]{2,90})$"),
    # "Section 71. Contract Implementation" / "SECTION 71."
    re.compile(r"^\s*(?:SECTION|Section|SEC\.|Sec\.)\s+(\d{1,3}[A-Za-z]?)\.?\s*[-–—]?\s*([^\n]{0,90})$"),
    # "Rule XII" / "ARTICLE V"
    re.compile(r"^\s*(?:RULE|Rule|ARTICLE|Article)\s+([IVXLC]{1,6}|\d{1,2})\.?\s*[-–—]?\s*([^\n]{0,90})$"),
    # "Annex B - Variation Orders" / 'Annex "B"' / "APPENDIX 59".
    # COA circulars quote the letter and the scans introduce stray dots and
    # spaces, so the quoting and punctuation are all optional here.
    re.compile(
        r"^\s*(?:ANNEX|Annex|APPENDIX|Appendix)[\s.]*[\"'“”‘’]?\s*"
        r"([A-Z]{1,2}|\d{1,3})\s*[\"'“”‘’]?\s*[-–—:.]?\s*([^\n]{0,90})$"
    ),
]

# Chapters are tracked as a *scope* rather than as a section, because GAM
# Volume I restarts section numbering inside every chapter -- "Section 12" is
# meaningless on its own, "Chapter 8, Section 12" is a citation a reader can
# follow. The chapter title usually sits on the line after the number.
_CHAPTER_RE = re.compile(
    r"^\s*(?:CHAPTER|Chapter)\s+(\d{1,2})\s*[-–—:.]?\s*([^,\n]{0,60})$"
)
# Phrases that mark a cross-reference rather than a heading
# ("...as provided in Chapter 19-Financial Reporting of this Manual.").
_CHAPTER_REJECT = re.compile(r"of this (?:Manual|Chapter)|respectively|Book [IVX]")

# The scanned legal PDFs encode curly quotes and dashes in a code page
# PyMuPDF cannot resolve, leaving U+FFFD in otherwise clean text. Quoted
# statutory text has to read correctly, so these are repaired on the way in.
_MOJIBAKE = {
    "�": "'",
    "–": "-",
    "—": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "\xa0": " ",
}


def clean_text(text: str) -> str:
    for bad, good in _MOJIBAKE.items():
        text = text.replace(bad, good)
    return re.sub(r"[ \t]{2,}", " ", text)

MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 2400


@dataclass
class Chunk:
    """One citable passage."""

    doc: str
    kind: str
    section: str
    page: int
    text: str


def _canonical_name(path: Path) -> Optional[Tuple[str, str]]:
    """Map a file to its canonical citation name, or None if not in the corpus."""
    name = path.name
    for fragment, canonical, kind in CORPUS:
        if fragment.lower() in name.lower():
            return canonical, kind
    return None


def _tidy_title(title: str) -> str:
    """Trim a captured heading title back to the heading itself.

    The patterns capture up to 90 characters, which on a run-in heading like
    "Section 8. Disbursements by Check. Checks shall be drawn only on..."
    swallows the first sentence of the body. Cutting at the first sentence
    end keeps the section label readable in a citation.
    """
    title = clean_text(title).strip(" .:-")
    # Cut at the first sentence end. Run-in headings are common in the IRR
    # ("Amendment to Order. - Amendments to Order for procurement of goods
    # may be issued...") and without this the label swallows the body.
    sentence_end = re.search(r"(?<=\w{3})\.\s", title)
    if sentence_end:
        title = title[: sentence_end.start()]
    return title.strip(" .:-")


def _match_heading(line: str) -> Optional[str]:
    """Return a normalised section label if `line` is a heading."""
    stripped = clean_text(line).strip()
    if not stripped or len(stripped) > 120:
        return None

    for pattern in _HEADING_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        number = match.group(1)
        title = _tidy_title(match.group(2) or "")

        # The prefix comes from the line's own leading word, not from which
        # pattern matched -- reordering the pattern list must not silently
        # relabel every annex in the corpus.
        upper = stripped.upper()
        if upper.startswith("ANNEX"):
            prefix = "Annex "
        elif upper.startswith("APPENDIX"):
            prefix = "Appendix "
        elif upper.startswith("RULE"):
            prefix = "Rule "
        elif upper.startswith("ARTICLE"):
            prefix = "Article "
        else:
            prefix = "Section "

        label = f"{prefix}{number}"
        return f"{label} - {title}" if title else label
    return None


def _flush(
    chunks: List[Chunk],
    doc: str,
    kind: str,
    section: str,
    page: int,
    buffer: List[str],
) -> None:
    text = clean_text("\n".join(buffer)).strip()
    if len(text) < MIN_CHUNK_CHARS:
        return
    # A long section is split rather than truncated: BM25 scores short
    # passages better, and a 20-page chapter quoted whole is not a citation.
    while text:
        piece, text = text[:MAX_CHUNK_CHARS], text[MAX_CHUNK_CHARS:]
        if text:
            # Break on a sentence boundary where one is nearby.
            cut = piece.rfind(". ")
            if cut > MAX_CHUNK_CHARS // 2:
                text = piece[cut + 1 :] + text
                piece = piece[: cut + 1]
        if len(piece.strip()) >= MIN_CHUNK_CHARS:
            chunks.append(Chunk(doc, kind, section, page, piece.strip()))


def _match_chapter(line: str) -> Optional[Tuple[str, str]]:
    """Return (number, title) if `line` opens a chapter, else None."""
    stripped = clean_text(line).strip()
    if not stripped or len(stripped) > 70 or _CHAPTER_REJECT.search(stripped):
        return None
    match = _CHAPTER_RE.match(stripped)
    if not match:
        return None
    return match.group(1), _tidy_title(match.group(2) or "")


def _is_chapter_title_line(line: str) -> bool:
    """Whether a line looks like the title that follows a bare `Chapter N`."""
    stripped = clean_text(line).strip()
    if not (3 < len(stripped) <= 70):
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    # Chapter titles in GAM are set in title case or caps and never end in
    # a period.
    return not stripped.endswith(".") and sum(c.isupper() for c in letters) / len(
        letters
    ) > 0.5


def chunk_pdf(path: Path, doc: str, kind: str) -> List[Chunk]:
    """Split one legal PDF into citable, section-labelled chunks."""
    chunks: List[Chunk] = []
    chapter: Optional[str] = None
    section = "Preliminary"
    section_page = 1
    buffer: List[str] = []
    awaiting_chapter_title: Optional[str] = None

    def label(raw_section: str) -> str:
        return f"{chapter}, {raw_section}" if chapter else raw_section

    with pymupdf.open(path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            for line in page.get_text().splitlines():
                # A bare "Chapter 8" is followed by its title on the next line.
                if awaiting_chapter_title is not None:
                    if _is_chapter_title_line(line):
                        chapter = f"{awaiting_chapter_title} - {clean_text(line).strip()}"
                        awaiting_chapter_title = None
                        continue
                    chapter = awaiting_chapter_title
                    awaiting_chapter_title = None

                chapter_hit = _match_chapter(line)
                if chapter_hit:
                    number, title = chapter_hit
                    _flush(chunks, doc, kind, label(section), section_page, buffer)
                    buffer, section, section_page = [], "Preliminary", page_index
                    if title:
                        chapter = f"Chapter {number} - {title}"
                    else:
                        awaiting_chapter_title = f"Chapter {number}"
                    continue

                heading = _match_heading(line)
                if heading:
                    _flush(chunks, doc, kind, label(section), section_page, buffer)
                    section, section_page, buffer = heading, page_index, []
                    continue

                if line.strip():
                    buffer.append(line.strip())

            # Long sections that run across many pages are flushed as they go,
            # so the recorded page stays close to where the text actually is.
            if sum(len(line) for line in buffer) > MAX_CHUNK_CHARS * 2:
                _flush(chunks, doc, kind, label(section), section_page, buffer)
                buffer = []
                section_page = page_index

    _flush(chunks, doc, kind, label(section), section_page, buffer)
    return chunks


def iter_corpus_files(docs_root: Path) -> Iterable[Tuple[Path, str, str]]:
    """Yield every PDF in `docs_root` that belongs to the legal corpus."""
    seen: Dict[str, Path] = {}
    for path in sorted(docs_root.rglob("*.pdf")):
        canonical = _canonical_name(path)
        if not canonical:
            continue
        name, kind = canonical
        if name in seen:
            continue
        seen[name] = path
        yield path, name, kind


def build_index(docs_root: Path, output: Path) -> Dict:
    """Build and write the index. Returns a summary for the caller to print."""
    all_chunks: List[Chunk] = []
    per_doc: Dict[str, int] = {}
    skipped: List[str] = []

    for path, name, kind in iter_corpus_files(docs_root):
        chunks = chunk_pdf(path, name, kind)
        if not chunks:
            # A scanned legal PDF would land here. None currently do, but the
            # index must not silently claim coverage it does not have.
            skipped.append(f"{name} (no extractable text)")
            continue
        all_chunks.extend(chunks)
        per_doc[name] = len(chunks)
        print(f"  {name}: {len(chunks)} chunks", file=sys.stderr)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(
            {"version": 1, "chunks": [asdict(chunk) for chunk in all_chunks]},
            fh,
            ensure_ascii=False,
        )

    return {
        "documents": len(per_doc),
        "chunks": len(all_chunks),
        "per_doc": per_doc,
        "skipped": skipped,
        "output": str(output),
        "size_kb": output.stat().st_size // 1024,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the legal KB index.")
    parser.add_argument(
        "--docs",
        default="../docs",
        help="Root directory containing the legal corpus PDFs.",
    )
    parser.add_argument("--out", default="kb/index.json", help="Output index path.")
    args = parser.parse_args()

    docs_root = Path(args.docs)
    if not docs_root.exists():
        print(f"docs directory not found: {docs_root}", file=sys.stderr)
        return 1

    print(f"Indexing legal corpus from {docs_root}", file=sys.stderr)
    summary = build_index(docs_root, Path(args.out))
    print(
        f"\nIndexed {summary['chunks']} chunks from {summary['documents']} "
        f"document(s) -> {summary['output']} ({summary['size_kb']} KB)",
        file=sys.stderr,
    )
    for note in summary["skipped"]:
        print(f"  SKIPPED: {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
