import time
import uuid
from typing import Literal, Optional
from pydantic import BaseModel, Field

EMBED_INPUT_LIMIT = 20000
EMBEDDING_DIM = 768


class FeedbackItem(BaseModel):
    """A single captured correction or rating, stored in the feedback bank."""

    feature: str
    context_key: str
    field_path: Optional[str] = None
    thread_id: str
    source_ref: Optional[str] = None
    signal_type: Literal["implicit", "explicit"]
    ai_value: Optional[str] = None
    corrected_value: Optional[str] = None
    rating: Optional[Literal["up", "down"]] = None
    note: Optional[str] = None
    input_context: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = Field(default_factory=lambda: time.time())
    metadata: dict = Field(default_factory=dict)
