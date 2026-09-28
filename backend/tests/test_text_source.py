import pytest

from agents.doc_generation.text_source import (
    get_source_text,
    has_source_documents,
    get_source_documents,
)


@pytest.fixture(autouse=True)
def _local_disk_only(monkeypatch):
    """
    These tests exercise the local-disk path specifically. The real .env sets
    GCS_BUCKET (staging), so without this every thread-session read here
    would take the GCS branch instead — force it off, same pattern as
    test_knowledge_upload.py's isolate_index_and_uploads fixture.
    """
    from config import settings
    monkeypatch.setattr(settings, "GCS_BUCKET", "")


def test_no_docs_returns_empty(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    from utils.storage import generate_thread_id
    tid = generate_thread_id()
    assert get_source_text(tid) == ""
    assert has_source_documents(tid) is False

def test_reads_pdfs(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("agents.doc_generation.text_source.extract_text_from_pdf", lambda p: f"TEXT({p.name})")
    from utils.storage import generate_thread_id, get_thread_upload_dir
    tid = generate_thread_id()
    d = get_thread_upload_dir(tid); d.mkdir(parents=True)
    (d / "a.pdf").write_bytes(b"%PDF-1"); (d / "b.pdf").write_bytes(b"%PDF-1")
    out = get_source_text(tid)
    assert "TEXT(a.pdf)" in out and "TEXT(b.pdf)" in out
    assert has_source_documents(tid) is True


def test_get_source_documents_per_file(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("agents.doc_generation.text_source.extract_text_from_pdf", lambda p: f"TEXT({p.name})")
    from utils.storage import generate_thread_id, get_thread_upload_dir
    tid = generate_thread_id()
    d = get_thread_upload_dir(tid); d.mkdir(parents=True)
    (d / "b.pdf").write_bytes(b"%PDF-1"); (d / "a.pdf").write_bytes(b"%PDF-1")
    docs = get_source_documents(tid)
    # Sorted order (same as _pdfs): a.pdf then b.pdf
    assert [x["filename"] for x in docs] == ["a.pdf", "b.pdf"]
    assert docs[0]["text"] == "TEXT(a.pdf)"
    assert docs[1]["text"] == "TEXT(b.pdf)"


def test_get_source_documents_extract_error_empty_text(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    def _boom(p):
        raise RuntimeError("bad pdf")
    monkeypatch.setattr("agents.doc_generation.text_source.extract_text_from_pdf", _boom)
    from utils.storage import generate_thread_id, get_thread_upload_dir
    tid = generate_thread_id()
    d = get_thread_upload_dir(tid); d.mkdir(parents=True)
    (d / "a.pdf").write_bytes(b"%PDF-1")
    docs = get_source_documents(tid)
    assert docs == [{"filename": "a.pdf", "text": ""}]


def test_get_source_documents_no_docs_empty(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    from utils.storage import generate_thread_id
    tid = generate_thread_id()
    assert get_source_documents(tid) == []
