"""
What a dimension analyzer is given to work with.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ReviewDocument:
    """One uploaded procurement document, already parsed."""

    name: str
    doc_type: str
    pages: int
    text: str


@dataclass
class ReviewContext:
    """
    Read-only input to every dimension.

    Analyzers must not mutate this — the same instance is handed to all
    dimensions running in parallel.
    """

    procurement_ref: str
    documents: List[ReviewDocument] = field(default_factory=list)
    meta: Dict[str, object] = field(default_factory=dict)

    def document(self, name: str) -> Optional[ReviewDocument]:
        """Look up one document by file name."""
        for doc in self.documents:
            if doc.name == name:
                return doc
        return None

    def by_type(self, doc_type: str) -> List[ReviewDocument]:
        """All documents of a given type, e.g. 'BAC Resolution'."""
        return [d for d in self.documents if d.doc_type == doc_type]

    def of_types(self, *doc_types: str) -> List[ReviewDocument]:
        """
        All documents matching any of the given types.

        Types are inferred on upload and correctable by hand, so a document
        the BAC has not retyped may sit under "Other". Dimensions that would
        otherwise find nothing should fall back to everything and say in the
        finding which documents they actually read.
        """
        wanted = set(doc_types)
        return [d for d in self.documents if d.doc_type in wanted]

    @property
    def combined_text(self) -> str:
        """
        Every document concatenated with a header per file.

        Use this for dimensions that reason over the whole record. Dimensions
        that compare specific documents should pull them with `document()`
        so the prompt stays small.
        """
        return render(self.documents)


def render(documents: List[ReviewDocument]) -> str:
    """A subset of documents as prompt text, one header per file."""
    return "\n\n".join(
        f"===== {d.name} ({d.doc_type}, {d.pages} pages) =====\n{d.text}"
        for d in documents
    )
