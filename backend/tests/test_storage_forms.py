from pathlib import Path

import pytest

from utils.storage import save_generated_file, list_generated_files, generate_thread_id


@pytest.fixture(autouse=True)
def _local_disk_only(monkeypatch):
    """The real .env sets GCS_BUCKET (staging) — force it off so this local-disk
    test doesn't take the GCS branch, same pattern as test_text_source.py."""
    from config import settings
    monkeypatch.setattr(settings, "GCS_BUCKET", "")


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
