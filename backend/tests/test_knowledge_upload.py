"""
POST /knowledge/upload — the one path that makes the Knowledge Hub writable.

Today the RAG index is read-only, built offline by
scripts/build_knowledge_index.py. This endpoint has to do three things in one
request without ever touching the network (no live GOOGLE_API_KEY in CI):
store the PDF, persist a KnowledgeEntry, and grow the *existing* on-disk index
in place so the very next retrieval sees the new content.

The embedder is faked throughout — never call the real embedding API here.
"""

import threading

import fitz
import numpy as np
import pytest
from fastapi.testclient import TestClient

import server
import knowledge.index as index_module
from knowledge import ingest as ingest_module
from knowledge.index import IndexAppendError, append_to_index, load_index, reset_cache
from knowledge.retrieve import provisions_for
from knowledge.schema import EMBEDDING_DIMENSIONS, Chunk, SourceDocument
from store import files as files_module
from store import get_store

client = TestClient(server.app)


class FakeEmbedder:
    """Deterministic vectors of the right width — no network call."""

    def embed_documents(self, texts):
        rng = np.random.RandomState(len(texts))
        return rng.randn(len(texts), EMBEDDING_DIMENSIONS).astype(np.float32).tolist()


def _pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


SAMPLE_TEXT = (
    "Section 99.1 Sample Provision\n"
    "This clause exists only for the upload test and is long enough to clear "
    "the minimum chunk size so the chunker actually emits a chunk for it."
)


@pytest.fixture(autouse=True)
def isolate_index_and_uploads(tmp_path, monkeypatch):
    """
    Point the index and the upload directory at a scratch directory so this
    test never reads or writes the real backend/data/knowledge_index or
    backend/uploads.
    """
    index_root = tmp_path / "knowledge_index"

    monkeypatch.setattr(
        "knowledge.index.index_dir", lambda backend_root=None: str(index_root)
    )
    monkeypatch.setattr(files_module.settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(files_module.settings, "GCS_BUCKET", "")

    # Never let a real embedder be constructed.
    monkeypatch.setattr(ingest_module, "_default_embedder", lambda: FakeEmbedder())

    reset_cache()
    yield
    reset_cache()


def test_upload_persists_entry_grows_index_and_is_retrievable():
    data = _pdf_with_text(SAMPLE_TEXT)

    response = client.post(
        "/knowledge/upload",
        files={"file": ("sample.pdf", data, "application/pdf")},
        data={"title": "Sample Provision Test Doc", "category": "GPPB Issuances"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chunks_indexed"] >= 1
    assert body["searchable"] is True
    entry = body["entry"]
    assert entry["title"] == "Sample Provision Test Doc"
    assert entry["category"] == "GPPB Issuances"
    assert entry["gcs_path"]

    # A new KnowledgeEntry was persisted and is fetchable via the store.
    stored = get_store().get_knowledge(entry["id"])
    assert stored is not None
    assert stored.title == "Sample Provision Test Doc"


def test_index_chunk_count_grows_and_new_content_is_retrievable():
    # The autouse fixture pointed knowledge.index.index_dir() at a scratch dir.
    index_root = index_module.index_dir()

    before = load_index(index_root)
    before_count = len(before.chunks) if before else 0

    data = _pdf_with_text(SAMPLE_TEXT)
    response = client.post(
        "/knowledge/upload",
        files={"file": ("sample2.pdf", data, "application/pdf")},
        data={"title": "Sample Provision Test Doc Two", "category": "GPPB Issuances"},
    )
    assert response.status_code == 200, response.text

    reset_cache()
    after = load_index(index_root)
    assert after is not None
    assert len(after.chunks) == before_count + response.json()["chunks_indexed"]

    result = provisions_for("Sample Provision", k=5)
    assert any("Sample Provision" in p.chunk.text for p in result.provisions)


# --- fix round: atomic vector/chunk alignment -----------------------------


class FailingEmbedder:
    """Simulates a quota error / network failure during embedding."""

    def embed_documents(self, texts):
        raise RuntimeError("embedding quota exceeded")


def test_failed_embedding_after_index_has_vectors_is_refused_not_silently_degraded(
    monkeypatch,
):
    """
    Once the index has an aligned set of embeddings, an upload whose embedder
    fails must NOT be appended in keyword-only mode — that would misalign
    vectors.npy against chunks.jsonl and silently drop vector search for
    every previously-embedded document (the bug this fix round closes).

    The endpoint must reject the upload (non-2xx) and the index must be left
    exactly as it was: same chunk/vector counts, still fully searchable by
    vector as well as keyword.
    """
    # First upload succeeds and gives the index its first aligned embeddings.
    first = client.post(
        "/knowledge/upload",
        files={"file": ("a.pdf", _pdf_with_text(SAMPLE_TEXT), "application/pdf")},
        data={"title": "Doc A", "category": "GPPB Issuances"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["searchable"] is True
    assert first.json()["message"] == ""

    index_root = index_module.index_dir()
    reset_cache()
    before = load_index(index_root)
    assert before is not None and before.vectors is not None
    before_chunk_count = len(before.chunks)
    before_vector_rows = before.vectors.shape[0]

    # Second upload: embedding fails.
    monkeypatch.setattr(ingest_module, "_default_embedder", lambda: FailingEmbedder())
    second_text = SAMPLE_TEXT.replace("99.1", "99.2")
    second = client.post(
        "/knowledge/upload",
        files={"file": ("b.pdf", _pdf_with_text(second_text), "application/pdf")},
        data={"title": "Doc B", "category": "GPPB Issuances"},
    )

    # A clear non-success, not a 200 claiming success.
    assert second.status_code == 502, second.text
    detail = second.json()["detail"]
    assert "Doc B" in detail
    assert "not" in detail.lower() and "index" in detail.lower()

    # The file + KnowledgeEntry were still saved, per spec, even though
    # indexing was refused.
    entries = get_store().list_knowledge()
    assert any(e.title == "Doc B" for e in entries)

    # The index itself is untouched by the refused append: no partial write,
    # no row-count mismatch, previously-embedded content still fully
    # searchable by vector.
    reset_cache()
    after = load_index(index_root)
    assert after is not None
    assert len(after.chunks) == before_chunk_count
    assert after.vectors is not None
    assert after.vectors.shape[0] == before_vector_rows == len(after.chunks)

    result = provisions_for("Sample Provision", k=5)
    assert any("Sample Provision" in p.chunk.text for p in result.provisions)
    assert result.embedded is False or result.embedded is True  # never raises either way


def test_upload_response_searchable_reflects_vectors_not_just_chunks(monkeypatch):
    """
    `searchable` must mean "vectors were actually written for this upload",
    not merely "chunks exist" — the exact confusion the review flagged.

    Simulated by a *fresh* index (nothing to misalign yet) whose embedder
    fails: the chunks append safely in keyword-only mode, but the response
    must say searchable=False and explain why, not silently claim success.
    """
    monkeypatch.setattr(ingest_module, "_default_embedder", lambda: FailingEmbedder())

    response = client.post(
        "/knowledge/upload",
        files={"file": ("c.pdf", _pdf_with_text(SAMPLE_TEXT), "application/pdf")},
        data={"title": "Doc C", "category": "GPPB Issuances"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chunks_indexed"] >= 1  # the chunks did get appended (safe: fresh index)
    assert body["searchable"] is False  # but no vectors were written
    assert "keyword" in body["message"].lower() or "embed" in body["message"].lower()


def test_append_to_index_refuses_before_writing_anything(tmp_path):
    """
    Unit-level check of the guard itself: given an aligned index, a second
    append with mismatched/absent vectors raises IndexAppendError and leaves
    chunks.jsonl, vectors.npy and manifest.json byte-for-byte unchanged.
    """
    root = tmp_path / "idx"
    chunk1 = Chunk(id="d#0000", doc_id="d", doc_title="D", section="", page=1, text="first")
    vec1 = np.ones((1, 8), dtype=np.float32)
    source1 = SourceDocument(
        doc_id="d", title="D", filename="d.pdf", sha256="s1", pages=1, chunks=1
    )
    append_to_index([chunk1], vec1, source1, root=str(root))

    chunks_before = (root / "chunks.jsonl").read_bytes()
    manifest_before = (root / "manifest.json").read_bytes()
    vectors_before = (root / "vectors.npy").read_bytes()

    chunk2 = Chunk(id="e#0000", doc_id="e", doc_title="E", section="", page=1, text="second")
    source2 = SourceDocument(
        doc_id="e", title="E", filename="e.pdf", sha256="s2", pages=1, chunks=1
    )

    with pytest.raises(IndexAppendError):
        append_to_index([chunk2], None, source2, root=str(root))

    assert (root / "chunks.jsonl").read_bytes() == chunks_before
    assert (root / "manifest.json").read_bytes() == manifest_before
    assert (root / "vectors.npy").read_bytes() == vectors_before


def test_concurrent_appends_stay_row_aligned(monkeypatch):
    """
    Two uploads appending at the same time must not race on the
    read-modify-write of vectors.npy/manifest.json: either everything from
    both lands, or the alignment guard rejects one, but there is never a
    torn write that leaves vectors.npy short of chunks.jsonl.
    """
    root = index_module.index_dir()

    # Widen the race window: pause briefly right after vectors.npy is read
    # (or found absent) and before it is saved, so two threads' critical
    # sections would overlap if the lock were not there.
    real_load = np.load

    def slow_load(*args, **kwargs):
        result = real_load(*args, **kwargs)
        threading.Event().wait(0.02)
        return result

    monkeypatch.setattr(np, "load", slow_load)

    def worker(i: int, errors: list):
        chunk = Chunk(
            id=f"race{i}#0000",
            doc_id=f"race{i}",
            doc_title="Race",
            section="",
            page=1,
            text=f"race chunk {i}",
        )
        vector = np.full((1, EMBEDDING_DIMENSIONS), float(i), dtype=np.float32)
        source = SourceDocument(
            doc_id=f"race{i}",
            title="Race",
            filename=f"race{i}.pdf",
            sha256=f"race{i}",
            pages=1,
            chunks=1,
        )
        try:
            append_to_index([chunk], vector, source, root=root)
        except IndexAppendError as exc:  # acceptable — refusal is safe, not a race loss
            errors.append(exc)

    errors: list = []
    threads = [
        threading.Thread(target=worker, args=(i, errors)) for i in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    reset_cache()
    after = load_index(root)
    assert after is not None
    # Whatever mix of successes/refusals happened, the on-disk index is
    # internally consistent: vectors, chunks and the manifest all agree.
    assert after.vectors is not None
    assert after.vectors.shape[0] == len(after.chunks) == after.manifest.chunk_count
