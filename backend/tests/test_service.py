from forms import service

def test_generate_ppmp_no_docs_blank(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("forms.service.get_source_text", lambda tid: "")
    from utils.storage import generate_thread_id
    tid = generate_thread_id()
    out = service.generate(tid, ["ppmp"], overrides={})
    assert len(out) == 1 and out[0][0].endswith(".xlsx") and out[0][1][:2] == b"PK"

def test_generate_group_b_has_disclaimer(monkeypatch, tmp_path):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("forms.service.get_source_text", lambda tid: "")
    from utils.storage import generate_thread_id
    import io
    from docx import Document
    tid = generate_thread_id()
    out = service.generate(tid, ["bsd"], overrides={})
    text = "\n".join(p.text for p in Document(io.BytesIO(out[0][1])).paragraphs)
    assert "DRAFT" in text
