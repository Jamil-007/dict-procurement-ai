import aiofiles
from pathlib import Path
from config import settings
import uuid


async def save_uploaded_file(file_content: bytes, thread_id: str) -> str:
    """
    Save uploaded PDF file to disk.

    Args:
        file_content: Binary content of the uploaded file
        thread_id: Unique thread identifier for this analysis session

    Returns:
        Path to the saved file
    """
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / f"{thread_id}.pdf"

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)

    return str(file_path)


def get_file_path(thread_id: str) -> str:
    """Get the file path for a given thread_id."""
    return str(Path(settings.UPLOAD_DIR) / f"{thread_id}.pdf")


def file_exists(thread_id: str) -> bool:
    """Check if a file exists for the given thread_id."""
    return Path(get_file_path(thread_id)).exists()


def generate_thread_id() -> str:
    """Generate a unique thread ID for a new analysis session."""
    return str(uuid.uuid4())
