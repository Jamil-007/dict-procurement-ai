import aiofiles
from pathlib import Path
from config import settings
import uuid
from typing import List, Tuple


async def save_uploaded_files(file_payloads: List[Tuple[str, bytes]], thread_id: str) -> List[str]:
    """
    Save uploaded PDF files to disk.

    Args:
        file_payloads: List of tuples (filename, file_content)
        thread_id: Unique thread identifier for this analysis session

    Returns:
        Paths to the saved files
    """
    thread_dir = Path(settings.UPLOAD_DIR) / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    used_names = set()

    for idx, (filename, file_content) in enumerate(file_payloads, start=1):
        original_name = Path(filename or f"document_{idx}.pdf").name
        base_name = Path(original_name).stem or f"document_{idx}"
        suffix = Path(original_name).suffix or ".pdf"

        safe_name = f"{base_name}{suffix}"
        counter = 1
        while safe_name in used_names:
            safe_name = f"{base_name}_{counter}{suffix}"
            counter += 1
        used_names.add(safe_name)

        file_path = thread_dir / safe_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        saved_paths.append(str(file_path))

    return saved_paths


def get_thread_upload_dir(thread_id: str) -> Path:
    """Get the upload directory path for a given thread_id."""
    return Path(settings.UPLOAD_DIR) / thread_id


def file_exists(thread_id: str) -> bool:
    """Check if at least one PDF file exists for the given thread_id."""
    thread_dir = get_thread_upload_dir(thread_id)
    if not thread_dir.exists() or not thread_dir.is_dir():
        return False
    return any(path.is_file() and path.suffix.lower() == ".pdf" for path in thread_dir.iterdir())


def generate_thread_id() -> str:
    """Generate a unique thread ID for a new analysis session."""
    return str(uuid.uuid4())
