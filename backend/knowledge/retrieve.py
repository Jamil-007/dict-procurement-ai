"""
Retrieving relevant provisions from the reference index.

This is the query half: load_index built the statistics, this module searches
them. BM25 is hand-written (no new dependency), and vector search degrades to
keyword-only when there is no API key or the embedding call fails — a reference
library that cannot embed still beats no reference library.

Never raises. A missing index or a broken embedding client produces an empty
Retrieval with `note` explaining it, and the dimension carries on with the
documents alone.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Iterable

from config import settings
from knowledge.index import LoadedIndex, load_index, tokenise
from knowledge.schema import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    Chunk,
    Provision,
    Retrieval,
)

logger = logging.getLogger(__name__)

# BM25 hyperparameters. These are the standard values from Robertson & Zaragoza.
BM25_K1 = 1.5
BM25_B = 0.75

# Reciprocal Rank Fusion parameter. Higher k gives more weight to lower ranks.
RRF_K = 60

# EMBEDDING_MODEL and EMBEDDING_DIMENSIONS come from knowledge/schema.py, the
# one place both halves read them: a query embedded by a different model than
# the index would still rank confidently, just meaninglessly.

# Embedding timeout in seconds. The LLM call is what cannot be skipped.
EMBEDDING_TIMEOUT = 10.0

# Maximum chunks from the same document to return, unless there is nothing else.
MAX_PER_DOC = 2


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    doc_idx: int,
    index: LoadedIndex,
) -> float:
    """
    Compute BM25 score for a document against a query.

    BM25 is a probabilistic ranking function balancing term frequency (how often
    the query words appear) against document frequency (how common those words
    are in the corpus). The result is not bounded, but higher is more relevant.
    """
    N = len(index.chunks)
    avgdl = index.avg_doc_length
    doc_length = index.doc_lengths[doc_idx]
    doc_freqs = index.doc_freqs

    # Count query term frequencies in the document
    doc_term_counts = Counter(doc_tokens)
    query_term_counts = Counter(query_tokens)

    score = 0.0
    for term in query_term_counts:
        if term not in doc_term_counts:
            continue

        # Term frequency in this document
        tf = doc_term_counts[term]

        # Document frequency: how many documents contain this term
        df = doc_freqs.get(term, 0)
        if df == 0:
            continue

        # IDF: log((N - df + 0.5) / (df + 0.5))
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        # BM25 formula
        numerator = tf * (BM25_K1 + 1)
        denominator = tf + BM25_K1 * (1 - BM25_B + BM25_B * (doc_length / avgdl))

        score += idf * (numerator / denominator)

    return score


def _keyword_rank(
    query: str, index: LoadedIndex, doc_ids: set[str] | None = None
) -> list[tuple[int, float]]:
    """
    Rank chunks by BM25 score against the query.

    Returns list of (chunk_index, score) tuples, sorted descending by score.
    """
    query_tokens = tokenise(query)
    if not query_tokens:
        return []

    scores = []
    for idx, chunk in enumerate(index.chunks):
        if doc_ids and chunk.doc_id not in doc_ids:
            continue

        doc_tokens = tokenise(chunk.searchable())
        score = _bm25_score(query_tokens, doc_tokens, idx, index)
        if score > 0:
            scores.append((idx, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _vector_rank(
    query: str,
    index: LoadedIndex,
    doc_ids: set[str] | None = None,
) -> tuple[list[tuple[int, float]], bool]:
    """
    Rank chunks by cosine similarity against the query embedding.

    Returns (list of (chunk_index, score) tuples, embedded_successfully).

    The second element is False when embedding failed or there are no vectors,
    so the caller knows to set Retrieval.embedded = False.
    """
    if index.vectors is None:
        return [], False

    if not settings.GOOGLE_API_KEY:
        logger.debug("No GOOGLE_API_KEY; vector search is unavailable")
        return [], False

    # Embed the query
    try:
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as FutTimeout

        import numpy as np
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embedder = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )

        # Run the embedding in a thread with timeout
        def embed():
            return embedder.embed_query(query)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(embed)
            try:
                query_vec = future.result(timeout=EMBEDDING_TIMEOUT)
            except FutTimeout:
                logger.warning(
                    "Query embedding timed out after %.0fs", EMBEDDING_TIMEOUT
                )
                return [], False

        query_vec = np.array(query_vec, dtype=np.float32)

        # Cosine similarity: dot(query, doc) / (||query|| * ||doc||)
        # Precompute query norm
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return [], True  # Embedded, but got a zero vector

        scores = []
        for idx, chunk in enumerate(index.chunks):
            if doc_ids and chunk.doc_id not in doc_ids:
                continue

            doc_vec = index.vectors[idx]
            doc_norm = np.linalg.norm(doc_vec)
            if doc_norm == 0:
                continue

            similarity = np.dot(query_vec, doc_vec) / (query_norm * doc_norm)
            scores.append((idx, float(similarity)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores, True

    except ImportError:
        logger.warning("langchain_google_genai is not installed")
        return [], False
    except Exception:
        logger.warning("Vector search failed", exc_info=True)
        return [], False


def _reciprocal_rank_fusion(
    keyword_ranks: list[tuple[int, float]],
    vector_ranks: list[tuple[int, float]],
    k: int = RRF_K,
) -> list[tuple[int, float, float, float]]:
    """
    Fuse keyword and vector rankings using Reciprocal Rank Fusion.

    RRF score for document d: sum over rankers r of 1 / (k + rank_r(d)).

    Returns list of (chunk_index, fused_score, keyword_score, vector_score).
    """
    # Build rank maps: chunk_index -> rank (0-based)
    keyword_rank_map = {idx: rank for rank, (idx, _) in enumerate(keyword_ranks)}
    vector_rank_map = {idx: rank for rank, (idx, _) in enumerate(vector_ranks)}

    # Build score maps for preserving original scores
    keyword_score_map = {idx: score for idx, score in keyword_ranks}
    vector_score_map = {idx: score for idx, score in vector_ranks}

    # All candidate chunk indices
    all_indices = set(keyword_rank_map.keys()) | set(vector_rank_map.keys())

    fused = []
    for idx in all_indices:
        rrf_score = 0.0

        # Keyword contribution
        if idx in keyword_rank_map:
            rrf_score += 1.0 / (k + keyword_rank_map[idx])

        # Vector contribution
        if idx in vector_rank_map:
            rrf_score += 1.0 / (k + vector_rank_map[idx])

        kw_score = keyword_score_map.get(idx, 0.0)
        vec_score = vector_score_map.get(idx, 0.0)

        fused.append((idx, rrf_score, kw_score, vec_score))

    fused.sort(key=lambda x: x[1], reverse=True)
    return fused


def _deduplicate_and_diversify(
    ranked: list[tuple[int, float, float, float]],
    chunks: list[Chunk],
    k: int,
) -> list[tuple[int, float, float, float]]:
    """
    Remove duplicates and cap per-document diversity.

    Never return two chunks with the same id. Prefer not to return more than
    MAX_PER_DOC chunks from the same doc_id unless there is nothing else
    (diversity matters more than piling up one section).

    Returns up to k results.
    """
    seen_ids: set[str] = set()
    doc_counts: dict[str, int] = {}
    results = []
    deferred = []

    for idx, fused_score, kw_score, vec_score in ranked:
        chunk = chunks[idx]

        # Skip duplicates
        if chunk.id in seen_ids:
            continue

        seen_ids.add(chunk.id)
        doc_id = chunk.doc_id
        count = doc_counts.get(doc_id, 0)

        # If we haven't hit the per-doc limit, take it
        if count < MAX_PER_DOC:
            results.append((idx, fused_score, kw_score, vec_score))
            doc_counts[doc_id] = count + 1
        else:
            # Defer it in case we need to backfill
            deferred.append((idx, fused_score, kw_score, vec_score))

        if len(results) >= k:
            break

    # Backfill from deferred if we don't have k results yet
    while len(results) < k and deferred:
        results.append(deferred.pop(0))

    return results[:k]


def provisions_for(
    query: str, k: int = 6, doc_ids: Iterable[str] | None = None
) -> Retrieval:
    """
    Find the k most relevant provisions for a query.

    Hybrid ranking: BM25 (keyword) + cosine similarity (vector) fused with
    Reciprocal Rank Fusion. Degrades gracefully when the index is missing or
    the embedding call fails — in both cases the caller gets a result, not an
    exception.

    Args:
        query: Natural language question or citation to search for.
        k: How many provisions to return.
        doc_ids: If given, restrict search to these source documents.

    Returns:
        A Retrieval with up to k provisions, or an empty one with `note`
        explaining why nothing came back.
    """
    index = load_index()
    if index is None:
        return Retrieval(
            note="The reference index has not been built yet; "
            "the review rests on the attached documents alone."
        )

    if not query.strip():
        return Retrieval(note="No query provided.")

    # Convert doc_ids to a set for O(1) lookup
    doc_id_set = set(doc_ids) if doc_ids else None

    # Keyword ranking (always runs)
    keyword_ranks = _keyword_rank(query, index, doc_id_set)

    # Vector ranking (degrades to empty list if unavailable)
    vector_ranks, embedded = _vector_rank(query, index, doc_id_set)

    # Decide on fusion strategy
    if not keyword_ranks and not vector_ranks:
        return Retrieval(
            note="No provisions matched the query.",
            embedded=embedded,
        )

    if vector_ranks:
        # Hybrid: fuse both
        fused = _reciprocal_rank_fusion(keyword_ranks, vector_ranks)
    else:
        # Keyword-only fallback
        fused = [(idx, score, score, 0.0) for idx, score in keyword_ranks]

    # Deduplicate and diversify
    final = _deduplicate_and_diversify(fused, index.chunks, k)

    # Build Provision objects
    provisions = [
        Provision(
            chunk=index.chunks[idx],
            score=fused_score,
            keyword_score=kw_score,
            vector_score=vec_score,
        )
        for idx, fused_score, kw_score, vec_score in final
    ]

    note = ""
    if not embedded and index.vectors is not None:
        note = (
            "Keyword-only retrieval was used (vector embeddings were unavailable); "
            "results may be less precise than usual."
        )

    return Retrieval(provisions=provisions, embedded=embedded, note=note)
