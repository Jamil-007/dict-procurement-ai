from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # LLM Provider
    LLM_PROVIDER: Literal["vertex_ai", "anthropic"] = "anthropic"

    # Vertex AI Configuration
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = ""

    # Gemini via Google AI Studio (preferred when set)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"

    # Tavily Configuration
    TAVILY_API_KEY: str = ""

    # Gamma Configuration (optional)
    GAMMA_API_KEY: str = ""

    # Storage Configuration
    UPLOAD_DIR: str = "./uploads"

    # State Persistence. SQLite by default: with MemorySaver a backend restart
    # loses every in-flight review, including any paused at the human-in-the-
    # loop interrupt, and the archive has nothing to point at.
    STATE_STORAGE: Literal["memory", "sqlite", "postgres"] = "sqlite"

    # Model Configuration
    VERTEX_MODEL_NAME: str = "gemini-2.0-flash-exp"  # Options: gemini-2.0-flash-exp, gemini-1.5-pro-002, gemini-1.5-flash-002
    ANTHROPIC_MODEL_NAME: str = "claude-opus-5"
    TEMPERATURE: float = 0.7
    CHAT_PARSED_TEXT_LIMIT: int = 150000

    # OCR / Ingestion Configuration
    # Every real DICT transaction document is a scanned image with no text layer,
    # so pages are rendered and read by Claude vision. Results are cached on disk.
    OCR_MODEL_NAME: str = "claude-opus-5"
    OCR_DPI: int = 300
    OCR_MAX_EDGE_PX: int = 2200  # Shared render cap; Anthropic downscales >1568 anyway
    OCR_MAX_PAGES: int = 40  # Page budget per document; longer docs are sampled
    OCR_MAX_CONCURRENCY: int = 4
    OCR_CACHE_DIR: str = "./cache/ocr"
    TESSERACT_CMD: str = ""  # Optional full path to tesseract.exe if not on PATH
    # A page with fewer than this many extractable characters is treated as scanned.
    OCR_MIN_CHARS_PER_PAGE: int = 100

    # Fact extraction
    EXTRACT_TEXT_LIMIT: int = 200000

    # Legal knowledge base (retrieved citations)
    KB_INDEX_PATH: str = "./kb/index.json"
    KB_TOP_K: int = 4

    # Application database (sessions, documents, findings, checkpoints)
    DB_PATH: str = "./data/procurement.db"

    # Upload budget. The 3-file cap is gone -- a payment packet is 10+ files --
    # but a total budget still bounds cost and latency.
    MAX_UPLOAD_FILES: int = 50
    MAX_UPLOAD_TOTAL_MB: int = 300
    MAX_UPLOAD_FILE_MB: int = 50

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create upload directory if it doesn't exist
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
