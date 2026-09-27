from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # LLM Provider
    LLM_PROVIDER: Literal["vertex_ai", "google_genai", "anthropic"] = "anthropic"

    # Vertex AI Configuration
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Google AI Studio (Gemini API key) Configuration
    GOOGLE_API_KEY: str = ""

    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = ""

    # Tavily Configuration
    TAVILY_API_KEY: str = ""

    # Gamma Configuration (optional)
    GAMMA_API_KEY: str = ""

    # Storage Configuration
    UPLOAD_DIR: str = "./uploads"

    # State Persistence
    STATE_STORAGE: Literal["memory", "sqlite", "postgres"] = "memory"

    # Model Configuration
    VERTEX_MODEL_NAME: str = "gemini-2.0-flash-exp"  # Options: gemini-2.0-flash-exp, gemini-1.5-pro-002, gemini-1.5-flash-002
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"
    ANTHROPIC_MODEL_NAME: str = "claude-3-5-sonnet-20241022"
    TEMPERATURE: float = 0.7
    CHAT_PARSED_TEXT_LIMIT: int = 150000

    # Feedback Bank
    FEEDBACK_BANK_ENABLED: bool = False
    FEEDBACK_BACKEND: Literal["firestore", "local"] = "local"
    FIRESTORE_PROJECT: str = ""
    FIRESTORE_DATABASE: str = "(default)"
    FIRESTORE_COLLECTION: str = "feedback"
    EMBEDDING_MODEL: str = "text-embedding-004"
    FEEDBACK_TOP_K: int = 3
    FEEDBACK_OVERSAMPLE: int = 4
    FEEDBACK_LOCAL_DB: str = "./uploads/feedback.db"
    # Trust gate: a manual correction is only used as a hint once the same
    # (field, corrected value) has been recorded at least this many times.
    # 👍 on the same value adds to the count, 👎 subtracts. This stops one bad
    # edit from steering future extractions. Set to 1 to trust every correction.
    FEEDBACK_MIN_REPEATS: int = 3
    # How many similarity-ranked candidates to scan when counting repeats.
    FEEDBACK_TRUST_SCAN: int = 200

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create upload directory if it doesn't exist
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
