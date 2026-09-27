from pathlib import Path
from utils.storage import save_generated_file, list_generated_files, generate_thread_id

def test_save_and_list_generated(tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    tid = generate_thread_id()
    p = save_generated_file(tid, "PPMP.xlsx", b"PK\x03\x04data")
    assert p.exists() and p.suffix == ".xlsx"
    assert p.parent.name == "forms"
    assert [f.name for f in list_generated_files(tid)] == ["PPMP.xlsx"]

def test_save_generated_rejects_bad_thread_id():
    import pytest
    with pytest.raises(ValueError):
        save_generated_file("../etc", "x.docx", b"x")
