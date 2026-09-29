"""
Shared test isolation that applies to every test in this directory.
"""

import pytest


@pytest.fixture(autouse=True)
def _hermetic_storage_by_default(monkeypatch):
    """
    Default every test to local-disk storage and the local (offline) feedback
    embedder, never a developer's real `GCS_BUCKET` or live-Vertex feedback
    backend from their local .env.

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
    from store import files
    from agents.doc_generation import extractor

    monkeypatch.setattr(settings, "GCS_BUCKET", "")
    # store/files.py caches one storage client per process; drop it so a test
    # that fakes the GCS client doesn't inherit a real (or another test's)
    # client, and vice versa.
    files._reset_client_cache()
    # extract_fields caches successful extractions per (form_key, source text);
    # clear it so a test's captured/mocked LLM is actually invoked instead of a
    # prior test's cached result being served.
    extractor.clear_extract_cache()
    # Keep feedback tests hermetic and fast: the local embedder is a deterministic
    # offline hash (no network), whereas FEEDBACK_BACKEND=firestore calls live
    # Vertex embeddings. A dev .env that enables the bank against proc-ai-staging
    # would otherwise make the whole suite slow and flaky. Tests exercising the
    # firestore backend set these themselves after faking the client.
    monkeypatch.setattr(settings, "FEEDBACK_BANK_ENABLED", False)
    monkeypatch.setattr(settings, "FEEDBACK_BACKEND", "local")
