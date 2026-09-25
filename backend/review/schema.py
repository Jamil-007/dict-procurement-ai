"""
The AI Review contract.

Every dimension analyzer returns a list of ReviewFinding. The frontend renders
whatever conforms to this shape, so no dimension needs its own UI.

Treat this file as frozen once agreed. Changing a field here means every
dimension owner and the frontend card have to change with it.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["critical", "warning", "compliant"]

Decision = Literal["accepted", "modified", "further", "rejected"]

Feedback = Literal["correct", "incorrect", "irrelevant", "incomplete"]


class Source(BaseModel):
    """
    Where in the uploaded documents the finding came from.

    `page` is optional because a model cannot always place a passage — the UI
    shows the section alone when it is missing. Insert [page N] markers into
    the document text to get it filled in reliably.
    """

    doc: str = Field(..., description="File name, e.g. 'TOR.pdf'")
    page: Optional[int] = Field(None, ge=1)
    section: str = Field("", description="e.g. 'Section 4 — Technical Specifications'")


class ComparedText(BaseModel):
    """
    One side of a cross-document comparison.

    Populate `comparison` with two or more of these when a finding is about
    two documents disagreeing; the UI renders them side by side. Leave it
    empty and set `quote` instead when the finding cites a single passage.
    """

    doc: str
    page: Optional[int] = Field(None, ge=1)
    label: str = Field("", description="What is being compared, e.g. 'Quantity'")
    quote: str = Field(..., description="Exact text as it appears in the document")


class ReviewFinding(BaseModel):
    """
    What a dimension analyzer produces.

    `id` is assigned by the runner after all dimensions return — analyzers
    should leave it empty.
    """

    id: str = ""
    dimension: str
    severity: Severity
    title: str
    analysis: str
    recommendation: str = ""
    source: Source
    policy_basis: str = Field(
        "", description="RA 12009, its IRR, a GPPB or COA issuance, or a DICT policy"
    )
    quote: str = Field("", description="Cited text when there is nothing to compare")
    comparison: List[ComparedText] = Field(default_factory=list)
    delta: Optional[str] = Field(
        None, description="Plain summary of the discrepancy, e.g. 'Differs by ₱600,000.00'"
    )


class Comment(BaseModel):
    """A note left by the BAC on a finding."""

    text: str
    author: str = "BAC Admin"
    at: str


class StoredFinding(ReviewFinding):
    """A finding as persisted, carrying what the BAC did with it."""

    procurement_ref: str
    decision: Optional[Decision] = None
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    edited: bool = False
    ai_analysis: str = Field("", description="Original wording, kept when edited")
    ai_recommendation: str = ""
    comments: List[Comment] = Field(default_factory=list)
    feedback: Optional[Feedback] = None


class DimensionResult(BaseModel):
    """Outcome of one dimension. A failure here never stops the others."""

    key: str
    label: str
    status: Literal["ok", "failed", "timeout"] = "ok"
    findings: List[ReviewFinding] = Field(default_factory=list)
    error: Optional[str] = None
    duration_ms: int = 0


class ReviewResult(BaseModel):
    """Outcome of a full review across every registered dimension."""

    procurement_ref: str
    dimensions: List[DimensionResult] = Field(default_factory=list)
    findings: List[ReviewFinding] = Field(default_factory=list)

    @property
    def counts(self) -> dict:
        out = {"critical": 0, "warning": 0, "compliant": 0}
        for finding in self.findings:
            out[finding.severity] += 1
        return out
