"""
Uploads got slow after moving procurement storage off local disk onto GCS.
Measured on a dev machine: constructing a google.cloud.storage.Client() runs
Application Default Credentials discovery + auth setup and costs ~10-15s EACH
time, while a warm client uploads a 50KB file in ~0.2s. store/files.py used to
build a fresh Client() on every call (save_document, read_document,
list_documents, document_exists, delete_document), so every uploaded file paid
that ~10s auth cost again — the regression users felt as "uploads take too long".

The fix is to construct the client once and reuse it. These tests pin that: a
single Client() is built no matter how many storage operations run.
"""

import pytest

from config import settings
from store import files


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


TEST_BUCKET = "proc-ai-staging-files-test"


@pytest.fixture
def counting_gcs(monkeypatch):
    """Fake storage client that counts how many times Client() is constructed,
    so a test can assert the client is reused rather than rebuilt per call."""
    buckets: dict = {}
    counter = {"n": 0}

    class CountingClient:
        def __init__(self, project=None):
            counter["n"] += 1
            self._buckets = buckets

        def bucket(self, name):
            return _FakeBucket(buckets.setdefault(name, {}))

        def list_blobs(self, bucket_or_name=None, prefix=""):
            store = buckets.setdefault(bucket_or_name, {})
            return [
                _FakeBlob(store, name)
                for name in sorted(store)
                if name.startswith(prefix)
            ]

    monkeypatch.setattr(settings, "GCS_BUCKET", TEST_BUCKET)

    import google.cloud.storage as gcs_module

    monkeypatch.setattr(gcs_module, "Client", CountingClient)

    yield buckets, counter


def test_single_client_reused_across_many_operations(counting_gcs):
    buckets, counter = counting_gcs

    # A mix of operations that each used to build their own client.
    path1, _ = files.save_document("REF-1", "a.pdf", b"%PDF-1.4 a", prefix="procurements")
    path2, _ = files.save_document("REF-1", "b.pdf", b"%PDF-1.4 b", prefix="procurements")
    assert files.list_documents("REF-1") == ["a.pdf", "b.pdf"]
    assert files.document_exists(path1) is True
    assert files.read_document(path2) == b"%PDF-1.4 b"
    files.delete_document(path1)

    # Before the fix each of those calls constructed a new client (>= 6).
    assert counter["n"] == 1, f"expected client built once, was built {counter['n']} times"


def test_repeated_saves_build_client_once(counting_gcs):
    buckets, counter = counting_gcs

    for i in range(5):
        files.save_document("REF-2", f"f{i}.pdf", b"%PDF-1.4 x", prefix="procurements")

    assert counter["n"] == 1, f"expected 1 client for 5 uploads, got {counter['n']}"
