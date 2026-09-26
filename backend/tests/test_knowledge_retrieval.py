"""
Reference provision retrieval from the knowledge index.

No test here touches the network. What matters is the tokeniser (which must
preserve legal citations), the BM25 ranking (which drives keyword-only mode),
and the degradation paths when the index is missing or the embedding client
fails — both are defaults, not edge cases.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from knowledge import retrieve as retrieve_module
from knowledge.index import load_index, reset_cache, tokenise
from knowledge.retrieve import provisions_for
from knowledge.schema import Chunk, IndexManifest


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Never let a developer's real key make these tests hit the network."""
    monkeypatch.setattr(retrieve_module.settings, "GOOGLE_API_KEY", "")


@pytest.fixture(autouse=True)
def reset_index_cache():
    """Reset the module-level cache before and after each test."""
    reset_cache()
    yield
    reset_cache()


# --- test fixtures --------------------------------------------------------


def build_fixture_index(tmp_path: Path, include_vectors: bool = True) -> Path:
    """
    Build a tiny knowledge index for testing.

    Returns the directory path where the index was written.
    """
    index_dir = tmp_path / "knowledge_index"
    index_dir.mkdir()

    # Sample chunks covering different scenarios
    chunks = [
        Chunk(
            id="ra12009_irr#0001",
            doc_id="ra12009_irr",
            doc_title="RA 12009 IRR",
            section="Section 23.1",
            page=45,
            text="Section 23.1 prohibits brand name specifications unless justified.",
        ),
        Chunk(
            id="ra12009_irr#0002",
            doc_id="ra12009_irr",
            doc_title="RA 12009 IRR",
            section="Section 23.2",
            page=46,
            text="Technical specifications must be generic and performance-based.",
        ),
        Chunk(
            id="ra12009_irr#0003",
            doc_id="ra12009_irr",
            doc_title="RA 12009 IRR",
            section="Section 12.1",
            page=30,
            text="The procurement process must be competitive and transparent.",
        ),
        Chunk(
            id="gppb2023-004#0001",
            doc_id="gppb2023-004",
            doc_title="GPPB Resolution 2023-004",
            section="Section 1",
            page=1,
            text="This resolution covers procurement of IT equipment and services.",
        ),
        Chunk(
            id="gppb2023-004#0002",
            doc_id="gppb2023-004",
            doc_title="GPPB Resolution 2023-004",
            section="Section 2",
            page=2,
            text="Alternative procurement modes may be used for specialized IT needs.",
        ),
    ]

    # Write chunks.jsonl
    chunks_file = index_dir / "chunks.jsonl"
    with chunks_file.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_json()) + "\n")

    # Write manifest.json
    manifest = IndexManifest(
        built_at="2026-09-26T10:00:00+08:00",
        embedding_model="models/gemini-embedding-001" if include_vectors else "",
        dimensions=768 if include_vectors else 0,
        chunk_count=len(chunks),
        documents=[],
    )
    manifest_file = index_dir / "manifest.json"
    with manifest_file.open("w", encoding="utf-8") as f:
        json.dump(manifest.to_json(), f)

    # Write vectors.npy if requested
    if include_vectors:
        # Generate random embeddings for testing
        rng = np.random.RandomState(42)  # Deterministic for tests
        vectors = rng.randn(len(chunks), 768).astype(np.float32)
        vectors_file = index_dir / "vectors.npy"
        np.save(str(vectors_file), vectors)

    return index_dir


# --- tokeniser ------------------------------------------------------------


def test_preserves_section_numbers():
    tokens = tokenise("Section 23.1 prohibits brand names")
    assert "23.1" in tokens
    assert "section" in tokens


def test_preserves_issuance_codes():
    tokens = tokenise("GPPB Resolution 2023-004 covers IT")
    assert "2023-004" in tokens
    assert "gppb" in tokens


def test_preserves_act_numbers():
    tokens = tokenise("RA 12009 is the Government Procurement Reform Act")
    assert "12009" in tokens
    assert "ra" in tokens


def test_tokeniser_lowercases():
    tokens = tokenise("Section 23.1")
    assert "section" in tokens
    assert "Section" not in tokens


def test_tokeniser_handles_multiple_dots():
    # Edge case: version numbers or complex section refs
    tokens = tokenise("Version 1.2.3 and Section 5.1.2")
    assert "1.2.3" in tokens
    assert "5.1.2" in tokens


# --- loading --------------------------------------------------------------


def test_loads_an_index_from_disk(tmp_path):
    index_path = build_fixture_index(tmp_path)
    index = load_index(str(index_path))

    assert index is not None
    assert len(index.chunks) == 5
    assert index.manifest.chunk_count == 5
    assert index.vectors is not None
    assert index.vectors.shape == (5, 768)


def test_missing_index_directory_returns_none_without_raising(tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    index = load_index(str(nonexistent))
    assert index is None


def test_caches_the_loaded_index(tmp_path):
    index_path = build_fixture_index(tmp_path)

    first = load_index(str(index_path))
    second = load_index(str(index_path))

    assert first is second  # Same object


def test_reset_cache_forces_reload(tmp_path):
    index_path = build_fixture_index(tmp_path)

    first = load_index(str(index_path))
    reset_cache()
    second = load_index(str(index_path))

    assert first is not second  # Different objects


def test_vector_chunk_row_count_mismatch_falls_back_to_keyword_only(tmp_path):
    """
    When vectors.npy has a different row count than chunks.jsonl, fall back to
    keyword-only rather than silently misaligning results. This is the worst
    possible failure — citing the wrong provision is indefensible.
    """
    index_dir = tmp_path / "knowledge_index"
    index_dir.mkdir()

    # Write 3 chunks
    chunks = [
        Chunk(
            id="doc#0001",
            doc_id="doc",
            doc_title="Doc",
            section="Section 1",
            page=1,
            text="First chunk",
        ),
        Chunk(
            id="doc#0002",
            doc_id="doc",
            doc_title="Doc",
            section="Section 2",
            page=2,
            text="Second chunk",
        ),
        Chunk(
            id="doc#0003",
            doc_id="doc",
            doc_title="Doc",
            section="Section 3",
            page=3,
            text="Third chunk",
        ),
    ]

    chunks_file = index_dir / "chunks.jsonl"
    with chunks_file.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_json()) + "\n")

    manifest = IndexManifest(
        built_at="2026-09-26T10:00:00+08:00",
        embedding_model="models/gemini-embedding-001",
        dimensions=768,
        chunk_count=3,
        documents=[],
    )
    manifest_file = index_dir / "manifest.json"
    with manifest_file.open("w", encoding="utf-8") as f:
        json.dump(manifest.to_json(), f)

    # Write vectors.npy with WRONG row count (2 instead of 3)
    rng = np.random.RandomState(42)
    misaligned_vectors = rng.randn(2, 768).astype(np.float32)
    vectors_file = index_dir / "vectors.npy"
    np.save(str(vectors_file), misaligned_vectors)

    # Load the index
    index = load_index(str(index_dir))

    # The index should load, but vectors should be None (fallback to keyword-only)
    assert index is not None
    assert len(index.chunks) == 3
    assert index.vectors is None  # Dropped due to mismatch


def test_loads_index_without_vectors(tmp_path):
    """When vectors.npy is absent, the index still loads (keyword-only mode)."""
    index_path = build_fixture_index(tmp_path, include_vectors=False)
    index = load_index(str(index_path))

    assert index is not None
    assert len(index.chunks) == 5
    assert index.vectors is None


# --- BM25 ranking ---------------------------------------------------------


def test_bm25_ranks_exact_section_number_query_first(tmp_path, monkeypatch):
    """
    Matching "Section 23.1" should rank the chunk with that section highest,
    because exact section matches are the most valuable signal in this corpus.
    """
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    # Load the fixture index explicitly
    index = load_index(str(index_path))
    assert index is not None

    # Make provisions_for use this index by patching load_index
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    result = provisions_for("Section 23.1", k=3)

    assert len(result.provisions) > 0
    # The first result should be the chunk with Section 23.1
    assert result.provisions[0].chunk.section == "Section 23.1"
    assert result.provisions[0].chunk.id == "ra12009_irr#0001"


def test_bm25_ranks_by_term_frequency(tmp_path, monkeypatch):
    """A query with multiple matching terms should rank well."""
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    # "specifications" appears in chunks #0001 and #0002
    result = provisions_for("specifications generic", k=5)

    assert len(result.provisions) > 0
    # Both chunks with "specifications" should rank
    provision_ids = {p.chunk.id for p in result.provisions}
    assert "ra12009_irr#0002" in provision_ids  # "generic and performance-based"


# --- retrieval ------------------------------------------------------------


def test_missing_index_returns_empty_retrieval_with_note(monkeypatch):
    """
    When the index directory does not exist, provisions_for returns an empty
    Retrieval with a note, not an exception. The review degrades to documents-
    only rather than failing.
    """
    # Make load_index return None (simulating missing index)
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: None)

    result = provisions_for("brand name")

    assert result.provisions == []
    assert "has not been built yet" in result.note
    assert result.embedded is False


def test_keyword_only_when_no_api_key(tmp_path, monkeypatch):
    """
    With no GOOGLE_API_KEY, retrieval falls back to keyword-only and sets
    embedded=False.
    """
    index_path = build_fixture_index(tmp_path, include_vectors=True)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)
    monkeypatch.setattr(retrieve_module.settings, "GOOGLE_API_KEY", "")

    result = provisions_for("brand name", k=3)

    assert result.embedded is False
    assert len(result.provisions) > 0  # Keyword-only still works
    # Note should mention keyword-only
    assert "keyword-only" in result.note.lower() or result.note == ""


def test_respects_k_limit(tmp_path, monkeypatch):
    """The result should contain at most k provisions."""
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    result = provisions_for("procurement", k=2)

    assert len(result.provisions) <= 2


def test_doc_ids_filtering(tmp_path, monkeypatch):
    """When doc_ids is given, only chunks from those documents are returned."""
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    # Only search in GPPB resolution
    result = provisions_for("procurement", k=10, doc_ids=["gppb2023-004"])

    assert len(result.provisions) > 0
    # All results should be from gppb2023-004
    for provision in result.provisions:
        assert provision.chunk.doc_id == "gppb2023-004"


def test_same_document_diversity_capping(tmp_path, monkeypatch):
    """
    Prefer not to return more than 2 chunks from the same doc_id unless there
    is nothing else. Diversity matters more than piling up one section.
    """
    # Build an index with many chunks from one document
    index_dir = tmp_path / "knowledge_index"
    index_dir.mkdir()

    chunks = []
    for i in range(10):
        chunks.append(
            Chunk(
                id=f"same_doc#{i:04d}",
                doc_id="same_doc",
                doc_title="Same Doc",
                section=f"Section {i}",
                page=i,
                text=f"procurement procurement procurement {i}",  # All match "procurement"
            )
        )

    # Add one chunk from a different document
    chunks.append(
        Chunk(
            id="other_doc#0001",
            doc_id="other_doc",
            doc_title="Other Doc",
            section="Section 1",
            page=1,
            text="procurement is important",
        )
    )

    chunks_file = index_dir / "chunks.jsonl"
    with chunks_file.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_json()) + "\n")

    manifest = IndexManifest(
        built_at="2026-09-26T10:00:00+08:00",
        embedding_model="",
        dimensions=0,
        chunk_count=len(chunks),
        documents=[],
    )
    manifest_file = index_dir / "manifest.json"
    with manifest_file.open("w", encoding="utf-8") as f:
        json.dump(manifest.to_json(), f)

    index = load_index(str(index_dir))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    # Ask for 5 results
    result = provisions_for("procurement", k=5)

    assert len(result.provisions) <= 5

    # With diversity working, we should see the other_doc chunk included
    # (not just chunks from same_doc piled up)
    other_doc_count = sum(1 for p in result.provisions if p.chunk.doc_id == "other_doc")
    assert other_doc_count >= 1


def test_deduplicates_chunk_ids(tmp_path, monkeypatch):
    """Never return two chunks with the same id."""
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    result = provisions_for("procurement", k=10)

    # Extract all chunk ids
    chunk_ids = [p.chunk.id for p in result.provisions]

    # No duplicates
    assert len(chunk_ids) == len(set(chunk_ids))


def test_empty_query_returns_empty_result(tmp_path, monkeypatch):
    """An empty query should return an empty Retrieval with a note."""
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    result = provisions_for("", k=10)

    assert result.provisions == []
    assert "no query" in result.note.lower()


def test_keyword_and_vector_scores_are_populated(tmp_path, monkeypatch):
    """
    Each Provision should carry both keyword_score and vector_score so a
    developer can see why something ranked.
    """
    index_path = build_fixture_index(tmp_path, include_vectors=False)

    index = load_index(str(index_path))
    assert index is not None
    monkeypatch.setattr(retrieve_module, "load_index", lambda path=None: index)

    result = provisions_for("brand name", k=3)

    assert len(result.provisions) > 0
    for provision in result.provisions:
        # In keyword-only mode, keyword_score should be set
        assert provision.keyword_score >= 0
        # vector_score should be 0 (no vectors)
        assert provision.vector_score == 0.0
        # Overall score should be set
        assert provision.score >= 0
