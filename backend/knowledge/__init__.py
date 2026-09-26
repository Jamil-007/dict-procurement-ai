"""
The reference library the review reasons against.

Laws, issuances and manuals — the same documents the Knowledge Hub lists for
people to read — chunked and indexed so a dimension can be shown the actual
provision instead of relying on the model's memory of it.

    from knowledge import provisions_for

    hits = provisions_for("brand name in technical specifications")
    prompt = PROMPT.format(provisions=hits.render(), ...)

Deliberately separate from `review/`: dimensions consume retrieval, they do
not own it.
"""

from knowledge.schema import (
    Chunk,
    IndexManifest,
    Provision,
    Retrieval,
    SourceDocument,
)

__all__ = [
    "Chunk",
    "IndexManifest",
    "Provision",
    "Retrieval",
    "SourceDocument",
]
