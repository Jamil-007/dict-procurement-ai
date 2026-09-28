"""
Where uploaded procurement documents go.

GCS when GCS_BUCKET is set, local disk otherwise. Local disk is for
development only — on Cloud Run the container filesystem is wiped on every
redeploy and each instance has its own copy.
"""

import logging
from pathlib import Path
from typing import Tuple

from config import settings

logger = logging.getLogger(__name__)


def _local_path(ref: str, filename: str, prefix: str = "") -> Path:
    base = Path(settings.UPLOAD_DIR)
    directory = (base / prefix / ref) if prefix else (base / ref)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / filename


def count_pages(data: bytes) -> int:
    """Page count of a PDF, or 0 if it cannot be read."""
    try:
        import fitz

        with fitz.open(stream=data, filetype="pdf") as document:
            return document.page_count
    except Exception:  # noqa: BLE001 - a bad page count must not fail an upload
        logger.warning("Could not read page count", exc_info=True)
        return 0


def _ocr_page(page, dpi: int = 300) -> str:
    """
    Render a page to an image and read it with Tesseract.

    The fallback for a page with no embedded text layer — a scan, or a
    print-to-PDF export that never wrote real text. get_text() returns ""
    for those, silently, so a whole document can go through the review as if
    it were blank unless something else looks at the pixels.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("OCR skipped: pytesseract/Pillow not installed")
        return ""

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    try:
        pixmap = page.get_pixmap(dpi=dpi)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        return pytesseract.image_to_string(image)
    except Exception:  # noqa: BLE001 - a bad scan must not fail the whole document
        logger.warning("OCR failed on a page", exc_info=True)
        return ""


def extract_text(data: bytes, max_pages: int = 0, markers: bool = True) -> str:
    """
    Text of a PDF, empty string if it cannot be read.

    Falls back to OCR on any page whose text layer is blank. A scanned
    procurement document has no text for PyMuPDF to read at all — without
    this, every page comes back empty and a dimension has nothing to work
    with even though the document plainly has content.

    `markers` inserts a [page N] line before each page so a finding can cite a
    page instead of guessing at one — the review needs this. Pass max_pages to
    read only the front of a long document, which is all the classifier needs.
    """
    try:
        import fitz

        with fitz.open(stream=data, filetype="pdf") as document:
            pages = []
            for number, page in enumerate(document, start=1):
                if max_pages and number > max_pages:
                    break
                text = page.get_text()
                if not text.strip():
                    text = _ocr_page(page)
                pages.append(f"[page {number}]\n{text}" if markers else text)
            return "\n".join(pages)
    except Exception:  # noqa: BLE001 - an unreadable file is handled by callers
        logger.warning("Could not extract text", exc_info=True)
        return ""


def save_document(
    ref: str, filename: str, data: bytes, prefix: str = "procurements"
) -> Tuple[str, int]:
    """
    Store one document and return (path, page_count).

    The path is a gs:// URI or a local filesystem path depending on config.
    `prefix` namespaces the object key (GCS) — e.g. "procurements" (default)
    or "knowledge" for the Knowledge Hub. Local disk keeps the original
    unprefixed layout (`UPLOAD_DIR/{ref}/{filename}`) for the default
    "procurements" prefix, so existing procurement uploads are untouched; any
    other prefix gets its own subdirectory (`UPLOAD_DIR/{prefix}/{ref}/{filename}`).
    """
    pages = count_pages(data)

    if settings.GCS_BUCKET:
        from google.cloud import storage

        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        blob = client.bucket(settings.GCS_BUCKET).blob(f"{prefix}/{ref}/{filename}")
        blob.upload_from_string(data, content_type="application/pdf")
        return f"gs://{settings.GCS_BUCKET}/{blob.name}", pages

    local_prefix = "" if prefix == "procurements" else prefix
    path = _local_path(ref, filename, local_prefix)
    path.write_bytes(data)
    return str(path), pages


def document_path(ref: str, filename: str, prefix: str = "procurements") -> str:
    """
    Path (gs:// URI or local path) a document would be stored at for
    (ref, filename, prefix) — without requiring it to already exist.

    For building a read path once the filename is already known (e.g. from
    `list_documents`), mirroring the layout `save_document` writes to.
    """
    if settings.GCS_BUCKET:
        return f"gs://{settings.GCS_BUCKET}/{prefix}/{ref}/{filename}"

    local_prefix = "" if prefix == "procurements" else prefix
    return str(_local_path(ref, filename, local_prefix))


def list_documents(ref: str, prefix: str = "procurements") -> list:
    """
    Filenames already stored under (ref, prefix), sorted.

    GCS has no cheap "list a directory" — this lists by key prefix instead
    (`{prefix}/{ref}/`) and returns just the immediate filenames (no nested
    keys). Local disk lists the directory `save_document` writes to for the
    same (ref, prefix), same as before this helper existed.
    """
    if settings.GCS_BUCKET:
        from google.cloud import storage

        gcs_prefix = f"{prefix}/{ref}/"
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        blobs = client.bucket(settings.GCS_BUCKET).list_blobs(prefix=gcs_prefix)
        names = []
        for blob in blobs:
            name = blob.name[len(gcs_prefix):]
            if name and "/" not in name:
                names.append(name)
        return sorted(names)

    local_prefix = "" if prefix == "procurements" else prefix
    base = Path(settings.UPLOAD_DIR)
    directory = (base / local_prefix / ref) if local_prefix else (base / ref)
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_file())


def document_exists(path: str) -> bool:
    """Whether the stored file is actually retrievable."""
    if not path:
        return False
    if path.startswith("gs://"):
        from google.cloud import storage

        bucket_name, _, blob_name = path[5:].partition("/")
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        return client.bucket(bucket_name).blob(blob_name).exists()
    return Path(path).is_file()


def read_document(path: str) -> bytes:
    if path.startswith("gs://"):
        from google.cloud import storage

        bucket_name, _, blob_name = path[5:].partition("/")
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        return client.bucket(bucket_name).blob(blob_name).download_as_bytes()

    return Path(path).read_bytes()


def delete_document(path: str) -> None:
    """Best effort — a missing file is not an error."""
    try:
        if path.startswith("gs://"):
            from google.cloud import storage

            bucket_name, _, blob_name = path[5:].partition("/")
            client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
            client.bucket(bucket_name).blob(blob_name).delete()
        else:
            Path(path).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        logger.warning("Could not delete %s", path, exc_info=True)
