from forms.text_source import get_source_text, has_source_documents

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
    monkeypatch.setattr("forms.text_source.extract_text_from_pdf", lambda p: f"TEXT({p.name})")
    from utils.storage import generate_thread_id, get_thread_upload_dir
    tid = generate_thread_id()
    d = get_thread_upload_dir(tid); d.mkdir(parents=True)
    (d / "a.pdf").write_bytes(b"%PDF-1"); (d / "b.pdf").write_bytes(b"%PDF-1")
    out = get_source_text(tid)
    assert "TEXT(a.pdf)" in out and "TEXT(b.pdf)" in out
    assert has_source_documents(tid) is True
