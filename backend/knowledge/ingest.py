"""
Turn one uploaded reference PDF into index-ready chunks and grow the live
knowledge index with them.

Wires together the pieces that already exist for the offline build
(`scripts/build_knowledge_index.py`) — `store.files.extract_text`,
`knowledge.corpus.chunk_document`, the same embedding model/width — behind a
single call an upload endpoint can use synchronously, so a reference is
searchable immediately rather than waiting for the next offline rebuild.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Protocol

from knowledge.corpus import chunk_document
from knowledge.index import IndexAppendError, append_to_index, reset_cache
from knowledge.schema import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    Chunk,
    IndexManifest,
    SourceDocument,
)
from store.files import count_pages, extract_text

logger = logging.getLogger(__name__)

# Re-exported so callers only need `from knowledge.ingest import IndexAppendError`.
__all__ = ["Embedder", "IndexAppendError", "IngestResult", "ingest_document"]


@dataclass
class IngestResult:
    """What one upload did to the live index."""

    chunks: list[Chunk]
    manifest: IndexManifest
    indexed: bool
    """
    True only when embeddings were actually computed and persisted for these
    chunks — not merely that chunks exist. A document with no extractable
    text, or one appended in keyword-only mode because no embedder was
    available, has `indexed=False` even though `chunks` may be non-empty.
    """


class Embedder(Protocol):
    """The one method both the real client and a test fake need."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


def _default_embedder() -> "Embedder | None":
    """The real embedder, or None if it cannot be built (matches build_knowledge_index.py)."""
    from config import settings

    if not settings.GOOGLE_API_KEY:
        logger.warning("No GOOGLE_API_KEY; uploaded document will be keyword-only")
        return None
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError:
        logger.warning("langchain_google_genai is not installed; skipping embeddings")
        return None
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )


def _embed(chunks: list[Chunk], embedder: "Embedder | None"):
    import numpy as np

    embedder = embedder if embedder is not None else _default_embedder()
    if embedder is None:
        return None
    try:
        vectors = embedder.embed_documents([c.text for c in chunks])
        return np.array(vectors, dtype=np.float32)
    except Exception:  # noqa: BLE001 - an upload must not fail because embedding did
        logger.warning(
            "Embedding failed for an uploaded document; keyword-only for now",
            exc_info=True,
        )
        return None


def ingest_document(
    doc_id: str,
    title: str,
    filename: str,
    data: bytes,
    embedder: "Embedder | None" = None,
) -> IngestResult:
    """
    Chunk, embed and append one uploaded PDF to the live knowledge index.

    `embedder` is injectable so tests can supply a deterministic fake instead
    of hitting the real embedding API; production callers leave it as None and
    get `GoogleGenerativeAIEmbeddings` (or a graceful keyword-only degrade if
    no API key is configured).

    Raises `IndexAppendError`, and writes nothing, when appending these
    chunks — with or without vectors — would misalign chunks.jsonl and
    vectors.npy for the whole index (see `knowledge.index.append_to_index`).
    The caller (the upload endpoint) is expected to keep the already-stored
    file and KnowledgeEntry in that case and report indexing as failed rather
    than silently degrading every other document's search quality.

    Returns an `IngestResult`. `chunks` is empty when the PDF had no
    extractable text — still a valid upload, just not retrievable by the RAG
    index. Calls `reset_cache()` after a successful append so the next
    `load_index()` (and therefore the next `provisions_for()`) sees the new
    content.
    """
    pages = count_pages(data)
    text = extract_text(data, max_pages=0, markers=True)
    chunks = chunk_document(doc_id, title, text)

    source = SourceDocument(
        doc_id=doc_id,
        title=title,
        filename=filename,
        sha256=hashlib.sha256(data).hexdigest(),
        pages=pages,
        chunks=len(chunks),
    )

    if not chunks:
        manifest = append_to_index([], None, source)
        reset_cache()
        return IngestResult(chunks=[], manifest=manifest, indexed=False)

    vectors = _embed(chunks, embedder)
    manifest = append_to_index(chunks, vectors, source)  # may raise IndexAppendError
    reset_cache()
    return IngestResult(chunks=chunks, manifest=manifest, indexed=vectors is not None)
