from pathlib import Path
from utils.pdf_parser import extract_text_from_pdf
from utils.storage import get_thread_upload_dir, validate_thread_id
from store import get_store
from store.files import extract_text as _extract_document_text, read_document

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

def get_source_documents(thread_id: str) -> list[dict]:
    """Return per-file extracted text for each PDF in the thread directory.

    Same sorted order as ``_pdfs``. On extract error, ``text`` is "".

    Returns:
        [{"filename": <saved pdf name>, "text": <extracted text>}]
    """
    docs = []
    for p in _pdfs(thread_id):
        try:
            text = extract_text_from_pdf(p)
        except Exception:
            text = ""
        docs.append({"filename": p.name, "text": text})
    return docs


# --- ref-based (a procurement record's own documents) ---
#
# Mirrors the thread-based helpers above but reads a procurement's attached
# documents by ref, via the storage-agnostic store/files.py (GCS-or-local),
# instead of a fresh-upload thread directory. Used by the Forms-in-the-record
# flow so recommendation/generation can work from documents already on the
# procurement, without a separate upload. Storage-agnostic: classify_documents/
# extract_fields/extract_header consume plain text regardless of source.


def _ref_documents(ref: str) -> list:
    procurement = get_store().get_procurement(ref)
    if not procurement:
        return []
    return list(procurement.documents or [])


def has_ref_source_documents(ref: str) -> bool:
    return bool(_ref_documents(ref))


def get_ref_source_documents(ref: str) -> list[dict]:
    """Return per-file extracted text for each document attached to the
    procurement ``ref``. Same shape as ``get_source_documents``.

    Returns:
        [{"filename": <document name>, "text": <extracted text>}]
    """
    docs = []
    for doc in _ref_documents(ref):
        text = ""
        if doc.gcs_path:
            try:
                text = _extract_document_text(read_document(doc.gcs_path), markers=False)
            except Exception:
                text = ""
        docs.append({"filename": doc.name, "text": text})
    return docs


def get_ref_source_text(ref: str) -> str:
    parts = [d["text"] for d in get_ref_source_documents(ref) if d["text"].strip()]
    return "\n\n".join(parts)
