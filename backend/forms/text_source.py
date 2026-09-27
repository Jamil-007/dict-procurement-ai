from pathlib import Path
from utils.pdf_parser import extract_text_from_pdf
from utils.storage import get_thread_upload_dir, validate_thread_id

def _pdfs(thread_id: str) -> list[Path]:
    if not validate_thread_id(thread_id):
        return []
    d = get_thread_upload_dir(thread_id)
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")

def has_source_documents(thread_id: str) -> bool:
    return bool(_pdfs(thread_id))

def get_source_text(thread_id: str) -> str:
    parts = []
    for p in _pdfs(thread_id):
        try:
            parts.append(extract_text_from_pdf(p))
        except Exception:
            continue
    return "\n\n".join(parts)
