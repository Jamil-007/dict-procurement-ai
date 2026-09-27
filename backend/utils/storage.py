import aiofiles
from pathlib import Path
from config import settings
import uuid
import re
from typing import List, Tuple

from ingest.loaders import SUPPORTED_EXTENSIONS

# A magic-byte check per accepted extension. The point is not to be clever
# about content sniffing -- it is that a file claiming to be a PDF and
# starting with something else should be rejected at the door rather than
# failing three layers down inside the parser.
#
# `.docx`/`.xlsx` are ZIP containers, so they share the PK signature. Plain
# text has no signature and is accepted on extension alone; it cannot be
# anything more dangerous than text.
_MAGIC_BYTES = {
    ".pdf": (b"%PDF",),
    ".docx": (b"PK", b"PK", b"PK"),
    ".xlsx": (b"PK", b"PK", b"PK"),
    ".xlsm": (b"PK", b"PK", b"PK"),
}


def is_supported_upload(filename: str) -> bool:
    """Whether this filename carries an extension the ingest layer can read."""
    return Path(filename or "").suffix.lower() in SUPPORTED_EXTENSIONS


def validate_thread_id(thread_id: str) -> bool:
    """Validate that thread_id is a valid UUID to prevent path traversal."""
    try:
        uuid.UUID(thread_id)
        return True
    except ValueError:
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other security issues."""
    # Remove any path components
    filename = Path(filename).name
    # Remove dangerous characters, keep only alphanumeric, dash, underscore, dot
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip(".")
    # Limit length, keeping the extension -- which is now what decides how the
    # file is parsed, so truncating it away would break ingestion.
    if len(filename) > 255:
        suffix = Path(filename).suffix[:16]
        filename = filename[: 255 - len(suffix)] + suffix
    return filename or "document.pdf"


async def save_uploaded_files(
    file_payloads: List[Tuple[str, bytes]], thread_id: str
) -> List[str]:
    """
    Save uploaded documents to disk.

    Accepts every format the ingest layer can read -- PDF, DOCX, XLSX/XLSM,
    TXT and MD -- because a procurement packet is not all PDFs: the PPMP, APP
    and readiness checklists in circulation are Word and Excel files.

    Args:
        file_payloads: List of tuples (filename, file_content)
        thread_id: Unique thread identifier for this analysis session

    Returns:
        Paths to the saved files

    Raises:
        ValueError: If thread_id is invalid, or a file is the wrong type,
            too large, or too small
    """
    # Validate thread_id to prevent path traversal
    if not validate_thread_id(thread_id):
        raise ValueError("Invalid thread_id format")

    thread_dir = Path(settings.UPLOAD_DIR) / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    used_names = set()

    max_file_size = settings.MAX_UPLOAD_FILE_MB * 1024 * 1024
    max_total_size = settings.MAX_UPLOAD_TOTAL_MB * 1024 * 1024
    total_size = 0

    if len(file_payloads) > settings.MAX_UPLOAD_FILES:
        raise ValueError(
            f"Too many files: {len(file_payloads)} "
            f"(limit {settings.MAX_UPLOAD_FILES})"
        )

    for idx, (filename, file_content) in enumerate(file_payloads, start=1):
        safe_filename = sanitize_filename(filename or f"document_{idx}.pdf")
        base_name = Path(safe_filename).stem or f"document_{idx}"
        suffix = Path(safe_filename).suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"File {filename} has unsupported type '{suffix or 'none'}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        if len(file_content) > max_file_size:
            raise ValueError(
                f"File {filename} exceeds the "
                f"{settings.MAX_UPLOAD_FILE_MB}MB per-file limit"
            )
        if len(file_content) < 100:
            raise ValueError(f"File {filename} is too small to contain a document")

        total_size += len(file_content)
        if total_size > max_total_size:
            raise ValueError(
                f"Upload exceeds the {settings.MAX_UPLOAD_TOTAL_MB}MB total limit"
            )

        expected = _MAGIC_BYTES.get(suffix)
        if expected and not any(file_content.startswith(sig) for sig in expected):
            raise ValueError(f"File {filename} is not a valid {suffix[1:].upper()} file")

        safe_name = f"{base_name}{suffix}"
        counter = 1
        while safe_name in used_names:
            safe_name = f"{base_name}_{counter}{suffix}"
            counter += 1
        used_names.add(safe_name)

        file_path = thread_dir / safe_name

        # Ensure file path is within upload directory (prevent path traversal)
        if not str(file_path.resolve()).startswith(str(thread_dir.resolve())):
            raise ValueError("Invalid file path detected")

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        saved_paths.append(str(file_path))

    return saved_paths


def get_thread_upload_dir(thread_id: str) -> Path:
    """Get the upload directory path for a given thread_id.

    Args:
        thread_id: Thread identifier

    Returns:
        Path to thread upload directory

    Raises:
        ValueError: If thread_id is invalid
    """
    if not validate_thread_id(thread_id):
        raise ValueError("Invalid thread_id format")
    return Path(settings.UPLOAD_DIR) / thread_id


def file_exists(thread_id: str) -> bool:
    """Check if at least one readable document exists for the given thread_id.

    Args:
        thread_id: Thread identifier

    Returns:
        True if any supported file exists, False otherwise
    """
    if not validate_thread_id(thread_id):
        return False

    thread_dir = get_thread_upload_dir(thread_id)
    if not thread_dir.exists() or not thread_dir.is_dir():
        return False
    return any(
        path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        for path in thread_dir.iterdir()
    )


def delete_thread_files(thread_id: str) -> bool:
    """Remove a session's uploaded files. Used when a session is deleted.

    Deleting the archive row while leaving the scanned documents on disk
    would be the wrong half of the operation -- these are real procurement
    records, and "deleted" has to mean deleted.
    """
    if not validate_thread_id(thread_id):
        return False

    thread_dir = get_thread_upload_dir(thread_id)
    if not thread_dir.exists():
        return False

    import shutil

    shutil.rmtree(thread_dir, ignore_errors=True)
    return not thread_dir.exists()


def generate_thread_id() -> str:
    """Generate a unique thread ID for a new analysis session."""
    return str(uuid.uuid4())
