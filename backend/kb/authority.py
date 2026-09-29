"""Attaching a legal citation to a finding.

Both engines need the same behaviour, and it has one rule: the citation comes
out of the indexed corpus or it is marked unverified. Nothing here composes a
section number, and nothing silently substitutes a different provision for
the one a rule named.
"""

from __future__ import annotations

from typing import Dict, Optional

from kb.retriever import get_retriever


def resolve_authority(
    doc: Optional[str] = None,
    section: Optional[str] = None,
    query: Optional[str] = None,
) -> Optional[Dict]:
    """Look up the provision a check rests on.

    A named `section` is looked up verbatim. Otherwise `query` retrieves the
    best match, optionally restricted to one document. Returns None when the
    check declares no authority at all, or when the index is unavailable.
    """
    if not doc and not query:
        return None

    retriever = get_retriever()
    if not retriever.available:
        return None

    if doc and section:
        found = retriever.find_section(doc, section)
        if found:
            return found.to_dict()
        # The named section is not in the indexed corpus. Say so, rather than
        # falling back to whatever the retriever thinks is closest -- a
        # confidently wrong citation is worse than a missing one.
        return {
            "doc": doc,
            "section": section,
            "page": None,
            "quoted_text": "",
            "citation": f"{doc}, {section}",
            "unverified": True,
        }

    if not query:
        return None

    best = retriever.best(query, docs=[doc] if doc else None)
    return best.to_dict() if best else None
