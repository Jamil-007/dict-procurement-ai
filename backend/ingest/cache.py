"""Disk cache for OCR results.

OCR is the expensive step in this pipeline: every real DICT transaction
document is a scanned image, and the bidding documents alone run to 62 pages.
Re-reading a document must be free, so results are keyed on the file's content
hash plus every parameter that can change the output.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from config import settings


def file_sha256(path: str | Path) -> str:
    """Content hash of a file, read in chunks so large PDFs stay off the heap."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_key(file_hash: str, **params: Any) -> str:
    """Build a cache key from a file hash and the parameters that shape output.

    Any change to dpi, model, page budget or prompt version produces a
    different key, so a stale result can never be served after a tweak.
    """
    parts = "|".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha256(f"{file_hash}|{parts}".encode("utf-8")).hexdigest()


def _cache_dir() -> Path:
    path = Path(settings.OCR_CACHE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def read_cache(key: str) -> Optional[Dict[str, Any]]:
    """Return the cached payload for `key`, or None on miss or corruption."""
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        # A half-written or corrupt entry is treated as a miss rather than
        # an error, so a bad cache can never block ingestion.
        return None


def write_cache(key: str, payload: Dict[str, Any]) -> None:
    """Write a cache entry atomically so a crash cannot leave a partial file."""
    path = cache_path(key)
    tmp = path.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)


def clear_cache() -> int:
    """Delete every cache entry. Returns the number of files removed."""
    removed = 0
    for entry in _cache_dir().glob("*.json"):
        entry.unlink(missing_ok=True)
        removed += 1
    return removed
