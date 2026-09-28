"""
Task 8: forms-session storage (POST /forms/upload -> /forms/detect and the
generated-file bookkeeping in utils/storage.py) must go through the
GCS-aware path in store/files.py when GCS_BUCKET is set, not silently stay on
local disk. This fakes the google-cloud-storage client end-to-end (no live
bucket, no network) and exercises upload -> read -> generate.

The local-disk path (GCS_BUCKET unset) is covered by test_forms_api.py and
test_storage_forms.py and is untouched by this fixture.
"""

import fitz
import pytest
from fastapi.testclient import TestClient

import server
from config import settings
from agents.doc_generation import text_source
from utils.storage import save_generated_file, list_generated_files

client = TestClient(server.app)


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
    """Stands in for google.cloud.storage.Client — an in-memory dict per bucket
    name, shared across every Client() constructed during a test so successive
    store/files.py calls (upload, then list, then read) see the same data."""

    def __init__(self, buckets, project=None):
        self._buckets = buckets

    def bucket(self, name):
        return _FakeBucket(self._buckets.setdefault(name, {}))


TEST_BUCKET = "proc-ai-staging-files-test"


@pytest.fixture
def fake_gcs(monkeypatch):
    """Turn GCS_BUCKET on and fake the storage client so store/files.py takes
    its GCS branch against an in-memory bucket instead of local disk or a
    real network call."""
    buckets: dict = {}
    monkeypatch.setattr(settings, "GCS_BUCKET", TEST_BUCKET)

    import google.cloud.storage as gcs_module

    monkeypatch.setattr(
        gcs_module, "Client", lambda project=None: FakeGCSClient(buckets, project)
    )

    yield buckets


def _pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def test_forms_upload_read_and_generate_round_trip_through_gcs(fake_gcs):
    pdf_bytes = _pdf_with_text("Detailed Cost Breakdown of items for testing.")

    upload_resp = client.post(
        "/forms/upload",
        files=[("files", ("cost.pdf", pdf_bytes, "application/pdf"))],
    )
    assert upload_resp.status_code == 200, upload_resp.text
    body = upload_resp.json()
    thread_id = body["thread_id"]
    assert body["has_docs"] is True
    assert body["filenames"] == ["cost.pdf"]

    # The upload landed in the fake bucket under forms/{thread_id}/, not on
    # local disk.
    assert f"forms/{thread_id}/cost.pdf" in fake_gcs[TEST_BUCKET]

    # text_source resolves the session's PDF back out of GCS.
    assert text_source.has_source_documents(thread_id) is True
    docs = text_source.get_source_documents(thread_id)
    assert [d["filename"] for d in docs] == ["cost.pdf"]
    assert "Detailed Cost Breakdown" in docs[0]["text"]
    assert "Detailed Cost Breakdown" in text_source.get_source_text(thread_id)

    # /forms/detect reads the same GCS-backed source end to end.
    detect_resp = client.post("/forms/detect", json={"thread_id": thread_id})
    assert detect_resp.status_code == 200, detect_resp.text
    assert detect_resp.json()["documents"] == [
        {"filename": "cost.pdf", "doc_types": ["Cost Breakdown"]}
    ]

    # Generated forms are also persisted via the GCS-aware path.
    saved_path = save_generated_file(thread_id, "PPMP.xlsx", b"PK\x03\x04data")
    assert saved_path == f"gs://{TEST_BUCKET}/forms_generated/{thread_id}/PPMP.xlsx"
    assert f"forms_generated/{thread_id}/PPMP.xlsx" in fake_gcs[TEST_BUCKET]
    assert list_generated_files(thread_id) == ["PPMP.xlsx"]


def test_forms_upload_empty_session_has_no_gcs_writes(fake_gcs):
    """No files: a session is still created, but nothing is written to the
    bucket (mirrors the local-disk empty-session behavior)."""
    resp = client.post("/forms/upload")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_docs"] is False
    assert body["filenames"] == []
    assert not text_source.has_source_documents(body["thread_id"])
    assert all(not blobs for blobs in fake_gcs.values())
