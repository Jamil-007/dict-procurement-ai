"""The finding record produced by every checker.

Both engines emit these, so the compiler, the API and the UI handle one
shape regardless of which of the six features produced a result.

A finding is only useful if a reviewer can act on it, which means three
things must always be present: what is wrong (`detail`), where it was seen
(`evidence`, with document and page), and what says so (`authority`, a
retrieved legal citation). A finding with no evidence is an assertion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


class Evidence(BaseModel):
    """Where a finding was observed."""

    document: str = ""  # filename as uploaded
    doc_type: str = ""
    page: Optional[int] = None
    field: Optional[str] = None
    value: Optional[str] = None

    def label(self) -> str:
        location = f"{self.document}" if self.document else "document"
        if self.page:
            location += f", p. {self.page}"
        if self.field:
            location += f" ({self.field})"
        return location


class Finding(BaseModel):
    """One check result."""

    rule_id: str
    task: str = ""  # "T1".."T6" -- which assigned feature produced this
    category: str = ""
    severity: str = "medium"  # high | medium | low | info
    title: str = ""
    detail: str = ""
    passed: bool = False
    evidence: List[Evidence] = Field(default_factory=list)
    authority: Optional[Dict[str, Any]] = None
    action_hint: Optional[str] = None
    # Set when a check could not run -- a missing document or an unparseable
    # value. Distinct from a failure: "not verified" must never be reported
    # to a reviewer as "compliant".
    skipped_reason: Optional[str] = None
    # Set by the consistency engine: the canonical field path that disagreed,
    # plus both sides of the comparison, so the UI can show them side by side
    # instead of making a reviewer parse the sentence.
    field: Optional[str] = None
    comparison: Optional[Dict[str, Any]] = None

    @property
    def is_failure(self) -> bool:
        return not self.passed and self.skipped_reason is None

    @property
    def sort_key(self) -> tuple:
        return (SEVERITY_ORDER.get(self.severity, 9), self.rule_id)

    def summary_line(self) -> str:
        """One-line rendering for the report and the chat context."""
        where = "; ".join(e.label() for e in self.evidence[:3])
        line = self.detail or self.title
        if where:
            line = f"{line} [{where}]"
        if self.authority and self.authority.get("citation"):
            line = f"{line} — {self.authority['citation']}"
        return line


def summarize(findings: List[Finding]) -> Dict[str, int]:
    """Counts by outcome, for the verdict."""
    return {
        "total": len(findings),
        "failed": sum(1 for f in findings if f.is_failure),
        "passed": sum(1 for f in findings if f.passed),
        "skipped": sum(1 for f in findings if f.skipped_reason is not None),
        "high": sum(1 for f in findings if f.is_failure and f.severity == "high"),
        "medium": sum(1 for f in findings if f.is_failure and f.severity == "medium"),
        "low": sum(1 for f in findings if f.is_failure and f.severity == "low"),
    }
