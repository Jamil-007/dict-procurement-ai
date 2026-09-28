"""
Loading the reference index from disk.

The index is text-based (chunks.jsonl, manifest.json) plus binary vectors, built
once and cached. Building is separate — this module only reads what someone
already wrote.

Read the module docstring in schema.py for the on-disk contract.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from knowledge.schema import (
    CHUNKS_FILE,
    EMBEDDING_MODEL,
    MANIFEST_FILE,
    VECTORS_FILE,
    Chunk,
    IndexManifest,
    SourceDocument,
    index_dir,
)

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


def tokenise(text: str) -> list[str]:
    """
    Split text into searchable tokens, preserving legal citation patterns.

    Philippine Government Procurement references are full of section numbers like
    "23.1", act numbers like "12009", and issuance codes like "2023-004". These
    must survive tokenisation as single tokens because matching an exact section
    number is the single most valuable signal in this corpus.

    Standard word-splitting would turn "Section 23.1" into ["section", "23", "1"],
    losing the structure. This tokeniser keeps them whole.
    """
    # Lowercase first
    text = text.lower()

    # Pattern: alphanumeric sequences, with internal dots or hyphens allowed.
    # [a-z0-9]+ matches one or more letters/digits
    # (?:[.-][a-z0-9]+)* matches zero or more groups of (dot or hyphen followed by letters/digits)
    # Examples: "23.1", "12009", "2023-004", "section", "ra", "1.2.3"
    pattern = r"[a-z0-9]+(?:[.-][a-z0-9]+)*"
    tokens = re.findall(pattern, text)

    return tokens


@dataclass
class LoadedIndex:
    """
    An index loaded into memory, ready to search.

    BM25 statistics are computed at load time because they depend only on the
    corpus, not the query, so recomputing them for every search is waste.
    """

    chunks: list[Chunk]
    manifest: IndexManifest
    vectors: np.ndarray | None = None

    # BM25 statistics, precomputed from the chunks
    doc_freqs: dict[str, int] = None  # token -> how many chunks contain it
    doc_lengths: list[int] = None  # token count per chunk
    avg_doc_length: float = 0.0

    def __post_init__(self):
        if self.doc_freqs is None:
            self.doc_freqs = {}
        if self.doc_lengths is None:
            self.doc_lengths = []


# Module-level cache. The index is read-only data loaded once per process.
_cached: LoadedIndex | None = None


def reset_cache() -> None:
    """Clear the cached index. Tests need this; production does not."""
    global _cached
    _cached = None


def load_index(path: str | None = None) -> LoadedIndex | None:
    """
    Load the reference index from disk, or return None if unavailable.

    The returned index is cached in a module singleton; subsequent calls return
    the same instance immediately unless reset_cache() was called. The cache is
    process-local, so multiple workers each load their own copy.

    Missing directory, unreadable files, and a vectors/chunks row-count mismatch
    all degrade rather than raising — the caller gets either a working index or
    None, never an exception.
    """
    global _cached
    if _cached is not None:
        return _cached

    root = Path(path) if path else Path(index_dir())
    if not root.exists():
        logger.warning("Knowledge index directory does not exist: %s", root)
        return None

    chunks_file = root / CHUNKS_FILE
    manifest_file = root / MANIFEST_FILE
    vectors_file = root / VECTORS_FILE

    # Load manifest
    manifest = _load_manifest(manifest_file)
    if manifest is None:
        return None

    # Load chunks
    chunks = _load_chunks(chunks_file)
    if chunks is None:
        return None

    if len(chunks) != manifest.chunk_count:
        logger.warning(
            "Chunk count mismatch: manifest says %d, loaded %d from %s",
            manifest.chunk_count,
            len(chunks),
            chunks_file,
        )

    # Load vectors if they exist
    vectors = None
    if vectors_file.exists():
        vectors = _load_vectors(vectors_file, expected_rows=len(chunks))

    # Build BM25 statistics
    doc_freqs, doc_lengths, avg_doc_length = _build_bm25_stats(chunks)

    loaded = LoadedIndex(
        chunks=chunks,
        manifest=manifest,
        vectors=vectors,
        doc_freqs=doc_freqs,
        doc_lengths=doc_lengths,
        avg_doc_length=avg_doc_length,
    )

    _cached = loaded
    logger.info(
        "Loaded knowledge index: %d chunks, vectors=%s",
        len(chunks),
        vectors is not None,
    )
    return loaded


def append_to_index(
    chunks: list[Chunk],
    vectors: "np.ndarray | None",
    source: SourceDocument,
    root: str | None = None,
) -> IndexManifest:
    """
    Grow the on-disk index with one newly-processed document, creating the
    index directory if it does not exist yet.

    This is the incremental counterpart to `scripts/build_knowledge_index.py`
    (which rewrites the whole index from scratch): a user upload should not
    have to wait for that offline rebuild to become searchable. Chunks are
    appended to chunks.jsonl in order — row i of vectors.npy must keep
    matching line i, so vectors (when given) are stacked onto the existing
    array rather than merged any other way. The manifest gets an updated
    chunk_count and a new SourceDocument entry.

    `vectors` may be None (e.g. no embedding client available) — the chunks
    are still appended so keyword search finds them, but vectors.npy is left
    untouched. If the index already has vectors, this creates a chunk/vector
    row-count mismatch that `load_index` detects and safely degrades to
    keyword-only for the *whole* index until it is backfilled or rebuilt with
    embeddings — a known, deliberate trade-off documented in the caller
    (`knowledge/ingest.py`).

    Callers must call `reset_cache()` afterwards so the next `load_index()`
    call picks up the change; this function only writes to disk.
    """
    import numpy as np

    index_root = Path(root) if root else Path(index_dir())
    index_root.mkdir(parents=True, exist_ok=True)

    chunks_path = index_root / CHUNKS_FILE
    manifest_path = index_root / MANIFEST_FILE
    vectors_path = index_root / VECTORS_FILE

    manifest = _load_manifest(manifest_path) or IndexManifest()

    if chunks:
        with chunks_path.open("a", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")

    if vectors is not None and len(vectors):
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors_path.exists():
            existing = np.load(str(vectors_path))
            combined = np.vstack([existing, vectors])
        else:
            combined = vectors
        np.save(str(vectors_path), combined)
        manifest.dimensions = combined.shape[1]
        manifest.embedding_model = EMBEDDING_MODEL

    manifest.chunk_count += len(chunks)
    manifest.documents.append(source)
    manifest.built_at = datetime.now(timezone.utc).isoformat()

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest.to_json(), f, indent=2, ensure_ascii=False)

    return manifest


def _load_manifest(path: Path) -> IndexManifest | None:
    """Load and parse the manifest, or None if it cannot be read."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return IndexManifest.from_json(data)
    except FileNotFoundError:
        logger.warning("Manifest file not found: %s", path)
        return None
    except Exception:
        logger.warning("Could not read manifest from %s", path, exc_info=True)
        return None


def _load_chunks(path: Path) -> list[Chunk] | None:
    """Load chunks from JSONL, or None if the file cannot be read."""
    try:
        chunks = []
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    chunks.append(Chunk.from_json(row))
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Skipping malformed chunk at line %d: %s", line_no, e
                    )
        return chunks
    except FileNotFoundError:
        logger.warning("Chunks file not found: %s", path)
        return None
    except Exception:
        logger.warning("Could not read chunks from %s", path, exc_info=True)
        return None


def _load_vectors(path: Path, expected_rows: int) -> np.ndarray | None:
    """
    Load the vector matrix, or None if it cannot be loaded or is misaligned.

    A mismatch between vectors.npy row count and the chunk count is the worst
    possible failure here — it would cite the wrong provision in a finding,
    which is indefensible in front of the BAC. Fall back to keyword-only rather
    than silently returning misaligned results.
    """
    try:
        import numpy as np

        arr = np.load(str(path))
        if arr.shape[0] != expected_rows:
            logger.error(
                "Vector/chunk row count mismatch: vectors have %d rows, chunks have %d. "
                "Falling back to keyword-only retrieval to avoid citing the wrong provision.",
                arr.shape[0],
                expected_rows,
            )
            return None
        return arr
    except ImportError:
        logger.warning("numpy is not installed; vector search is unavailable")
        return None
    except Exception:
        logger.warning("Could not load vectors from %s", path, exc_info=True)
        return None


def _build_bm25_stats(
    chunks: list[Chunk],
) -> tuple[dict[str, int], list[int], float]:
    """
    Compute BM25 statistics from the chunk texts.

    Returns (doc_freqs, doc_lengths, avg_doc_length).
    """
    doc_freqs: Counter = Counter()
    doc_lengths = []

    for chunk in chunks:
        tokens = tokenise(chunk.searchable())
        doc_lengths.append(len(tokens))
        # Count unique tokens per document for document frequency
        unique_tokens = set(tokens)
        for token in unique_tokens:
            doc_freqs[token] += 1

    avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0

    return dict(doc_freqs), doc_lengths, avg_doc_length
