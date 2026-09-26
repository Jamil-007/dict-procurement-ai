"""
The AI Review contract.

Every dimension analyzer returns a list of ReviewFinding. The frontend renders
whatever conforms to this shape, so no dimension needs its own UI.

Treat this file as frozen once agreed. Changing a field here means every
dimension owner and the frontend card have to change with it.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Severity = Literal["critical", "medium", "low", "info", "compliant"]

#: Highest concern first. Drives sort order, the legend, and the count summary.
SEVERITY_ORDER: List[Severity] = ["critical", "medium", "low", "info", "compliant"]

#: What each level means, so the prompt and the UI tooltip say the same thing.
SEVERITY_MEANING: Dict[Severity, str] = {
    "critical": "Potentially material issue requiring prompt BAC attention",
    "medium": "Meaningful issue but generally does not by itself prevent continuation",
    "low": "Minor quality or completeness issue",
    "info": "Observation rather than an identified deficiency",
    "compliant": "Checked and no issue found",
}

#: Findings written under the earlier three-level scale. Coerced on load so
#: procurements reviewed before the scale changed still render.
LEGACY_SEVERITY: Dict[str, Severity] = {"warning": "medium", "high": "critical"}


def empty_counts() -> Dict[str, int]:
    """A zeroed count for every level, in display order."""
    return {level: 0 for level in SEVERITY_ORDER}


def normalize_counts(counts: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Fold a stored count onto the current scale, dropping unknown keys."""
    out = empty_counts()
    for key, value in (counts or {}).items():
        level = LEGACY_SEVERITY.get(key, key)
        if level in out:
            out[level] += int(value or 0)
    return out

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

    @field_validator("severity", mode="before")
    @classmethod
    def _accept_legacy_severity(cls, value: Any) -> Any:
        """Map a severity written under the earlier scale onto the current one."""
        if isinstance(value, str):
            level = value.strip().lower()
            return LEGACY_SEVERITY.get(level, level)
        return value


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
        out = empty_counts()
        for finding in self.findings:
            out[finding.severity] += 1
        return out
