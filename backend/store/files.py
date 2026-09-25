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


def _local_path(ref: str, filename: str) -> Path:
    directory = Path(settings.UPLOAD_DIR) / ref
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


def save_document(ref: str, filename: str, data: bytes) -> Tuple[str, int]:
    """
    Store one document and return (path, page_count).

    The path is a gs:// URI or a local filesystem path depending on config.
    """
    pages = count_pages(data)

    if settings.GCS_BUCKET:
        from google.cloud import storage

        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        blob = client.bucket(settings.GCS_BUCKET).blob(
            f"procurements/{ref}/{filename}"
        )
        blob.upload_from_string(data, content_type="application/pdf")
        return f"gs://{settings.GCS_BUCKET}/{blob.name}", pages

    path = _local_path(ref, filename)
    path.write_bytes(data)
    return str(path), pages


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
