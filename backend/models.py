from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from datetime import datetime


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
    query: str


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    response: str


class ErrorResponse(BaseModel):
    """Error response format."""
    error: str
    detail: Optional[str] = None
