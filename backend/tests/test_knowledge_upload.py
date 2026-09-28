"""
POST /knowledge/upload — the one path that makes the Knowledge Hub writable.

Today the RAG index is read-only, built offline by
scripts/build_knowledge_index.py. This endpoint has to do three things in one
request without ever touching the network (no live GOOGLE_API_KEY in CI):
store the PDF, persist a KnowledgeEntry, and grow the *existing* on-disk index
in place so the very next retrieval sees the new content.

The embedder is faked throughout — never call the real embedding API here.
"""

import fitz
import numpy as np
import pytest
from fastapi.testclient import TestClient

import server
from knowledge import ingest as ingest_module
from knowledge.index import load_index, reset_cache
from knowledge.retrieve import provisions_for
from knowledge.schema import EMBEDDING_DIMENSIONS
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
    import knowledge.index as index_module

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
