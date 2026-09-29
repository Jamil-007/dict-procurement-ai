"""
Task 9: the Knowledge Hub RAG index (chunks.jsonl, vectors.npy, manifest.json)
must survive a Cloud Run restart/redeploy, not just live in the container's
local disk. When GCS_BUCKET is set, knowledge/index.py mirrors the 3 index
files to `gs://{GCS_BUCKET}/{KNOWLEDGE_INDEX_PREFIX}/`.

This fakes the google-cloud-storage client end-to-end (no live bucket, no
network) and exercises: bootstrap (local seed -> GCS on first load), append
(local write -> GCS upload), and a fresh instance (empty local disk, cache
reset) pulling the durable copy back from GCS.

GCS_BUCKET-unset behavior is covered by test_knowledge_retrieval.py and
test_knowledge_upload.py and is untouched by this fixture.
"""

import json
from pathlib import Path

import numpy as np
import pytest

import knowledge.index as index_module
from knowledge.index import (
    append_to_index,
    load_index,
    reset_cache,
)
from knowledge.retrieve import provisions_for
from knowledge.schema import Chunk, IndexManifest, SourceDocument

TEST_BUCKET = "proc-ai-staging-files-test"


class _FakeBlob:
    def __init__(self, store, name):
        self._store = store
        self.name = name

    def upload_from_string(self, data, content_type=None):
        self._store[self.name] = data

    def download_as_bytes(self):
        return self._store[self.name]

    def exists(self):
        return self.name in self._store

    def delete(self):
        self._store.pop(self.name, None)


class _FakeBucket:
    def __init__(self, store):
        self._store = store

    def blob(self, name):
        return _FakeBlob(self._store, name)

    def list_blobs(self, prefix=""):
        return [
            _FakeBlob(self._store, name)
            for name in sorted(self._store)
            if name.startswith(prefix)
        ]


class FakeGCSClient:
    """Same shape as test_forms_storage_gcs.py's fake: an in-memory dict per
    bucket name, shared across every Client() built during a test."""

    def __init__(self, buckets, project=None):
        self._buckets = buckets

    def bucket(self, name):
        return _FakeBucket(self._buckets.setdefault(name, {}))


@pytest.fixture
def fake_gcs(tmp_path, monkeypatch):
    """
    Point the knowledge index at a scratch local directory, turn on
    GCS_BUCKET, and fake the storage client so index.py's GCS branch runs
    against an in-memory bucket instead of local disk or a real network call.
    """
    buckets: dict = {}
    index_root = tmp_path / "knowledge_index"

    monkeypatch.setattr(
        index_module, "index_dir", lambda backend_root=None: str(index_root)
    )
    monkeypatch.setattr(index_module.settings, "GCS_BUCKET", TEST_BUCKET)

    import google.cloud.storage as gcs_module

    monkeypatch.setattr(
        gcs_module, "Client", lambda project=None: FakeGCSClient(buckets, project)
    )

    reset_cache()
    yield buckets, index_root
    reset_cache()


def _write_local_seed(index_root: Path) -> None:
    """A tiny committed-seed-style index: one chunk, no vectors (keyword-only)."""
    index_root.mkdir(parents=True, exist_ok=True)

    chunk = Chunk(
        id="seed#0001",
        doc_id="seed",
        doc_title="Seed Doc",
        section="Section 1",
        page=1,
        text="This is the original seeded provision about procurement modalities.",
    )
    with (index_root / "chunks.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(chunk.to_json()) + "\n")

    manifest = IndexManifest(
        built_at="2026-01-01T00:00:00+00:00",
        embedding_model="",
        dimensions=0,
        chunk_count=1,
        documents=[],
    )
    with (index_root / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest.to_json(), f)


def test_load_index_bootstraps_local_seed_to_gcs(fake_gcs):
    buckets, index_root = fake_gcs
    _write_local_seed(index_root)

    loaded = load_index(str(index_root))

    assert loaded is not None
    assert len(loaded.chunks) == 1

    bucket = buckets[TEST_BUCKET]
    assert "knowledge_index/chunks.jsonl" in bucket
    assert "knowledge_index/manifest.json" in bucket
    # The uploaded manifest is the seed's, byte for byte.
    assert bucket["knowledge_index/manifest.json"] == (
        index_root / "manifest.json"
    ).read_bytes()


def test_append_uploads_updated_index_to_gcs(fake_gcs):
    buckets, index_root = fake_gcs
    _write_local_seed(index_root)
    load_index(str(index_root))  # bootstraps GCS from the seed
    reset_cache()

    new_chunk = Chunk(
        id="new#0001",
        doc_id="new",
        doc_title="New Doc",
        section="Section 2",
        page=1,
        text="A freshly uploaded provision that must become durable in GCS.",
    )
    source = SourceDocument(
        doc_id="new", title="New Doc", filename="new.pdf", sha256="abc", pages=1, chunks=1
    )

    append_to_index([new_chunk], None, source, root=str(index_root))

    bucket = buckets[TEST_BUCKET]
    uploaded_chunks = bucket["knowledge_index/chunks.jsonl"].decode("utf-8")
    assert "new freshly uploaded" not in uploaded_chunks  # sanity: not a substring fluke
    assert "freshly uploaded provision" in uploaded_chunks
    assert "seeded provision" in uploaded_chunks  # the original seed row is still there

    uploaded_manifest = json.loads(bucket["knowledge_index/manifest.json"])
    assert uploaded_manifest["chunk_count"] == 2


def test_fresh_instance_pulls_index_from_gcs_and_can_retrieve_new_content(fake_gcs):
    """
    Simulates instance A appending and instance B starting cold: clear the
    local directory entirely, reset the cache, and load again — the content
    must come back from GCS, including the appended document.
    """
    buckets, index_root = fake_gcs
    _write_local_seed(index_root)
    load_index(str(index_root))
    reset_cache()

    new_chunk = Chunk(
        id="new#0001",
        doc_id="new",
        doc_title="New Doc",
        section="Section 2",
        page=1,
        text="A freshly uploaded provision that must survive an instance restart.",
    )
    source = SourceDocument(
        doc_id="new", title="New Doc", filename="new.pdf", sha256="abc", pages=1, chunks=1
    )
    append_to_index([new_chunk], None, source, root=str(index_root))
    reset_cache()

    # Simulate a brand-new instance: no local files at all.
    for name in ("chunks.jsonl", "vectors.npy", "manifest.json"):
        path = index_root / name
        if path.exists():
            path.unlink()

    loaded = load_index(str(index_root))
    assert loaded is not None
    assert len(loaded.chunks) == 2
    assert any(c.doc_id == "new" for c in loaded.chunks)

    result = provisions_for("freshly uploaded provision", k=5)
    assert any("freshly uploaded" in p.chunk.text for p in result.provisions)


def test_append_from_stale_instance_does_not_overwrite_prior_append(fake_gcs):
    """
    Multi-instance safety: instance B appending after instance A must pull A's
    durable append down from GCS first, not overwrite it from a stale local copy.
    Without the sync-before-append, B (which never saw A's doc) would upload
    seed+B and silently drop A's document from the durable index.
    """
    buckets, index_root = fake_gcs
    _write_local_seed(index_root)
    load_index(str(index_root))  # bootstrap GCS from the seed
    reset_cache()

    # Instance A appends doc A.
    chunk_a = Chunk(
        id="a#0001", doc_id="doca", doc_title="Doc A", section="S", page=1,
        text="Provision A from the first instance.",
    )
    src_a = SourceDocument(
        doc_id="doca", title="Doc A", filename="a.pdf", sha256="a", pages=1, chunks=1
    )
    append_to_index([chunk_a], None, src_a, root=str(index_root))
    reset_cache()

    # Simulate a different instance B that never saw doc A: wipe local files so
    # its local copy is stale/empty before it appends.
    for name in ("chunks.jsonl", "vectors.npy", "manifest.json"):
        p = index_root / name
        if p.exists():
            p.unlink()

    chunk_b = Chunk(
        id="b#0001", doc_id="docb", doc_title="Doc B", section="S", page=1,
        text="Provision B from the second instance.",
    )
    src_b = SourceDocument(
        doc_id="docb", title="Doc B", filename="b.pdf", sha256="b", pages=1, chunks=1
    )
    append_to_index([chunk_b], None, src_b, root=str(index_root))

    bucket = buckets[TEST_BUCKET]
    uploaded = bucket["knowledge_index/chunks.jsonl"].decode("utf-8")
    assert "seeded provision" in uploaded  # original seed survived
    assert "Provision A from the first instance." in uploaded  # A's append NOT lost
    assert "Provision B from the second instance." in uploaded  # B's append present
    manifest = json.loads(bucket["knowledge_index/manifest.json"])
    assert manifest["chunk_count"] == 3


def test_gcs_bucket_unset_behaves_exactly_as_local_only(tmp_path, monkeypatch):
    """No GCS_BUCKET: no storage client is even touched, local disk is the
    whole story — the existing (pre-Task-9) behavior."""
    index_root = tmp_path / "knowledge_index"
    monkeypatch.setattr(
        index_module, "index_dir", lambda backend_root=None: str(index_root)
    )
    monkeypatch.setattr(index_module.settings, "GCS_BUCKET", "")

    def _boom(*args, **kwargs):
        raise AssertionError("GCS must not be touched when GCS_BUCKET is unset")

    import google.cloud.storage as gcs_module

    monkeypatch.setattr(gcs_module, "Client", _boom)

    reset_cache()
    _write_local_seed(index_root)

    loaded = load_index(str(index_root))
    assert loaded is not None
    assert len(loaded.chunks) == 1
    reset_cache()
