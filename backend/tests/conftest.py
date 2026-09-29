"""
Shared test isolation that applies to every test in this directory.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_live_gcs_by_default(monkeypatch):
    """
    Default every test to local-disk storage, never a developer's real
    `GCS_BUCKET` from their local .env.

    Several code paths (store/files.py, knowledge/index.py) branch on
    `settings.GCS_BUCKET` to decide between local disk and a real GCS
    bucket. Before knowledge/index.py learned to sync the RAG index with
    GCS, an unmocked `GCS_BUCKET` in a dev's .env only affected document
    upload/download tests that already dealt with it explicitly. Now that
    `load_index()` also consults it on every call, any test that reaches
    knowledge retrieval (directly, or transitively through policy grounding
    in a review/doc-generation flow) would otherwise make live network calls
    against the real staging bucket — slow, flaky under load, and able to
    overwrite the committed local index seed with whatever is actually in
    that bucket.

    Tests that specifically want to exercise the GCS-backed code paths turn
    it back on via their own fixture after also faking the storage client
    (see test_forms_storage_gcs.py's `fake_gcs` and
    test_knowledge_index_gcs.py's `fake_gcs`) — those fixtures run after this
    autouse one and their `monkeypatch.setattr` wins.
    """
    from config import settings

    monkeypatch.setattr(settings, "GCS_BUCKET", "")
