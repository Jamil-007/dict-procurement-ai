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

    # Gemini via Google AI Studio (preferred when set)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"

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

    # State Persistence. SQLite by default: with MemorySaver a backend restart
    # loses every in-flight review, including any paused at the human-in-the-
    # loop interrupt, and the archive has nothing to point at. Read only by
    # persistence/checkpoint.py, which backs the checker graph; the legacy
    # analysis graph in graph.py still constructs its own MemorySaver.
    STATE_STORAGE: Literal["memory", "sqlite", "postgres"] = "sqlite"

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

    # Object prefix under GCS_BUCKET where the Knowledge Hub RAG index
    # (chunks.jsonl, vectors.npy, manifest.json) is mirrored, so a KB upload
    # survives a Cloud Run restart/redeploy instead of only living in the
    # container's local disk. Ignored when GCS_BUCKET is unset.
    KNOWLEDGE_INDEX_PREFIX: str = "knowledge_index"

    # Model Configuration
    VERTEX_MODEL_NAME: str = "gemini-2.0-flash-exp"  # Options: gemini-2.0-flash-exp, gemini-1.5-pro-002, gemini-1.5-flash-002
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"
    ANTHROPIC_MODEL_NAME: str = "claude-opus-5"
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

    # OCR / Ingestion Configuration
    # Every real DICT transaction document is a scanned image with no text layer,
    # so pages are rendered and read by Claude vision. Results are cached on disk.
    # TESSERACT_CMD is declared with the other storage settings above.
    OCR_MODEL_NAME: str = "claude-opus-5"
    OCR_DPI: int = 300
    OCR_MAX_EDGE_PX: int = 2200  # Shared render cap; Anthropic downscales >1568 anyway
    OCR_MAX_PAGES: int = 40  # Page budget per document; longer docs are sampled
    OCR_MAX_CONCURRENCY: int = 4
    OCR_CACHE_DIR: str = "./cache/ocr"
    # A page with fewer than this many extractable characters is treated as scanned.
    OCR_MIN_CHARS_PER_PAGE: int = 100

    # How long the /stream SSE connection waits for a verdict before giving
    # up. Sized for a first run over a packet of scanned documents, where
    # every page goes through vision OCR; cached re-runs finish in seconds.
    SSE_TIMEOUT_SECONDS: int = 1800

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
