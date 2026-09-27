from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class AnalyzeResponse(BaseModel):
    """Response from the /analyze endpoint."""

    thread_id: str
    status: Literal["processing"]


class ThinkingLog(BaseModel):
    """Real-time log of agent activity."""

    id: str
    agent: str
    message: str
    timestamp: float
    status: Literal["pending", "active", "complete"]


class Finding(BaseModel):
    """Individual finding in the analysis report."""

    category: str
    items: List[str]
    severity: Literal["high", "medium", "low"]


class VerdictData(BaseModel):
    """Final analysis verdict matching frontend TypeScript interface."""

    status: Literal["PASS", "FAIL"]
    title: str
    findings: List[Finding]
    confidence: int = Field(..., ge=0, le=100)


class ReviewRequest(BaseModel):
    """Request to review and decide next steps."""

    thread_id: str
    action: Literal["generate_gamma", "chat_only"]


class ReviewResponse(BaseModel):
    """Response from the review endpoint."""

    status: str
    gamma_link: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to chat about the analyzed document."""

    thread_id: str
    query: str = Field(..., min_length=1, max_length=5000)


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    response: str


class ErrorResponse(BaseModel):
    """Error response format."""

    error: str
    detail: Optional[str] = None


class FormDetectRequest(BaseModel):
    """Request to detect document types and recommend forms."""

    thread_id: str


class FormExtractRequest(BaseModel):
    """Request to extract fields from agents.doc_generation."""

    thread_id: str
    form_keys: List[str]


class FormGenerateRequest(BaseModel):
    """Request to generate form files."""

    thread_id: str
    form_keys: List[str]
    overrides: Optional[dict] = None


class FeedbackItemRequest(BaseModel):
    """One feedback item posted from the frontend."""

    feature: str = Field(..., min_length=1, max_length=64)
    context_key: str = Field(..., min_length=1, max_length=128)
    field_path: Optional[str] = Field(None, max_length=256)
    thread_id: str
    source_ref: Optional[str] = Field(None, max_length=512)
    signal_type: Literal["implicit", "explicit"]
    ai_value: Optional[str] = Field(None, max_length=8000)
    corrected_value: Optional[str] = Field(None, max_length=8000)
    rating: Optional[Literal["up", "down"]] = None
    note: Optional[str] = Field(None, max_length=2000)
    input_context: Optional[str] = Field(None, max_length=20000)


class FeedbackRequest(BaseModel):
    """Batch of feedback items."""

    items: List[FeedbackItemRequest] = Field(..., min_length=1, max_length=100)


class FeedbackResponse(BaseModel):
    stored: int
