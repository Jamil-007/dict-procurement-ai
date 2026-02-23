import aiofiles
from pathlib import Path
from config import settings
import uuid
import re
from typing import List, Tuple


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
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip('.')
    # Limit length
    if len(filename) > 255:
        name_part = filename[:200]
        ext_part = filename[-50:] if '.' in filename[-50:] else '.pdf'
        filename = name_part + ext_part
    return filename or 'document.pdf'


async def save_uploaded_files(file_payloads: List[Tuple[str, bytes]], thread_id: str) -> List[str]:
    """
    Save uploaded PDF files to disk.

    Args:
        file_payloads: List of tuples (filename, file_content)
        thread_id: Unique thread identifier for this analysis session

    Returns:
        Paths to the saved files

    Raises:
        ValueError: If thread_id is invalid or file size exceeds limit
    """
    # Validate thread_id to prevent path traversal
    if not validate_thread_id(thread_id):
        raise ValueError("Invalid thread_id format")

    thread_dir = Path(settings.UPLOAD_DIR) / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    used_names = set()
    
    # File size limit: 50MB per file
    MAX_FILE_SIZE = 50 * 1024 * 1024

    for idx, (filename, file_content) in enumerate(file_payloads, start=1):
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(f"File {filename} exceeds maximum size of 50MB")
        
        # Check minimum file size (100 bytes)
        if len(file_content) < 100:
            raise ValueError(f"File {filename} is too small to be a valid PDF")
        
        # Validate PDF magic bytes
        if not file_content.startswith(b'%PDF'):
            raise ValueError(f"File {filename} is not a valid PDF file")
        
        # Sanitize filename
        safe_filename = sanitize_filename(filename or f"document_{idx}.pdf")
        base_name = Path(safe_filename).stem or f"document_{idx}"
        suffix = Path(safe_filename).suffix or ".pdf"
        
        # Ensure .pdf extension
        if suffix.lower() != '.pdf':
            suffix = '.pdf'

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
    """Check if at least one PDF file exists for the given thread_id.
    
    Args:
        thread_id: Thread identifier
        
    Returns:
        True if PDF files exist, False otherwise
    """
    if not validate_thread_id(thread_id):
        return False
    
    thread_dir = get_thread_upload_dir(thread_id)
    if not thread_dir.exists() or not thread_dir.is_dir():
        return False
    return any(path.is_file() and path.suffix.lower() == ".pdf" for path in thread_dir.iterdir())


def generate_thread_id() -> str:
    """Generate a unique thread ID for a new analysis session."""
    return str(uuid.uuid4())
