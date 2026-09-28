import os
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

    # Path to the tesseract binary, for OCR on scanned PDFs (no embedded text
    # layer). Empty means "on PATH", which is true in the Docker image but
    # rarely true on Windows — set this to the .exe path after installing
    # Tesseract locally.
    TESSERACT_CMD: str = ""

    # State Persistence (LangGraph checkpointer — currently MemorySaver only;
    # the sqlite/postgres options are not implemented)
    STATE_STORAGE: Literal["memory", "sqlite", "postgres"] = "memory"

    # Record storage for procurements, findings and the Knowledge Hub.
    # "memory" is per-process and dies with the container — use "firestore"
    # on Cloud Run.
    STORE_BACKEND: Literal["memory", "firestore"] = "memory"
    FIRESTORE_PREFIX: str = ""  # e.g. "staging_" to share a database
    FIRESTORE_DATABASE: str = ""  # named database id; empty means "(default)"

    # Point the Firestore client at a local emulator, e.g. "127.0.0.1:8098".
    # Declared here only so it can be set in .env; the client library reads it
    # from the real process environment, so __init__ exports it. See below.
    FIRESTORE_EMULATOR_HOST: str = ""

    # Uploaded document storage. Empty bucket name keeps files on local disk.
    GCS_BUCKET: str = ""

    # Model Configuration
    VERTEX_MODEL_NAME: str = "gemini-2.0-flash-exp"  # Options: gemini-2.0-flash-exp, gemini-1.5-pro-002, gemini-1.5-flash-002
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"
    ANTHROPIC_MODEL_NAME: str = "claude-3-5-sonnet-20241022"
    TEMPERATURE: float = 0.7

    # How many tokens Gemini may spend thinking before it answers. The 2.5
    # models think by default with a dynamic budget, which on the review
    # prompts measured at ~2,900 reasoning tokens and 17.7s against 4.5s with
    # thinking off — invisible tokens you are billed for and wait on.
    #   0   thinking off, fastest
    #   -1  the model's own dynamic budget (what it did before this setting)
    #   n   cap it at n tokens
    # 1024 keeps real reasoning for the analysis while bounding the tail.
    GEMINI_THINKING_BUDGET: int = 1024
    CHAT_PARSED_TEXT_LIMIT: int = 150000

    # Upper bound on tokens any single LLM call may generate. Unbounded output
    # is what let the Requirements & Risk dimension run 3+ minutes, close to
    # the 180s review timeout, on documents that invite a long answer. 8192 is
    # generous relative to normal review output (a few dozen findings plus a
    # summary) while giving every provider path a hard ceiling.
    MAX_OUTPUT_TOKENS: int = 8192

    # Feedback Bank
    FEEDBACK_BANK_ENABLED: bool = False
    FEEDBACK_BACKEND: Literal["firestore", "local"] = "local"
    FIRESTORE_PROJECT: str = ""
    # Separate from the Knowledge Hub's FIRESTORE_DATABASE (above): the feedback
    # bank lives in its own database (proc-feedback-bank), the Knowledge Hub in
    # procurement-agent-db. Kept distinct so the two subsystems never share data.
    FEEDBACK_FIRESTORE_DATABASE: str = "(default)"
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

        # pydantic-settings reads .env into this object, not into os.environ.
        # google-cloud-firestore only looks at os.environ, so without this an
        # emulator host set in .env is silently ignored and the client connects
        # to the real database instead. Export it before any client is built.
        # A value already in the real environment wins, so
        #   FIRESTORE_EMULATOR_HOST=... uvicorn server:app
        # still overrides .env.
        if self.FIRESTORE_EMULATOR_HOST:
            os.environ.setdefault(
                "FIRESTORE_EMULATOR_HOST", self.FIRESTORE_EMULATOR_HOST
            )
        else:
            self.FIRESTORE_EMULATOR_HOST = os.environ.get(
                "FIRESTORE_EMULATOR_HOST", ""
            )


# Global settings instance
settings = Settings()
