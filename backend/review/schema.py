"""
The AI Review contract.

Every dimension analyzer returns a list of ReviewFinding. The frontend renders
whatever conforms to this shape, so no dimension needs its own UI.

Treat this file as frozen once agreed. Changing a field here means every
dimension owner and the frontend card have to change with it.
"""

from typing import Any, Dict, List, Literal, Optional, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

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


#: The BAC either accepts a finding or rejects it. "modified" and "further"
#: are no longer offered — editing a finding's wording no longer counts as a
#: decision — but both stay in the union so a finding decided before they were
#: dropped still loads and still renders its chip.
Decision = Literal["accepted", "modified", "further", "rejected"]

#: Why a finding was rejected. Required on rejection: a hidden finding that
#: never reaches the report has to carry a reason on the record, and a free
#: text box alone makes the reasons impossible to count across procurements.
RejectionReason = Literal[
    "not_applicable",
    "insufficient_evidence",
    "misinterpreted",
    "duplicate",
    "acceptable",
    "other",
]

Feedback = Literal["correct", "incorrect", "irrelevant", "incomplete"]

Confidence = Literal["high", "medium", "low"]

#: How sure the analyzer is of the finding, which is a separate question from
#: how serious it would be if true. A critical finding held at low confidence
#: still belongs in front of the BAC — it just has to say so.
CONFIDENCE_MEANING: Dict[Confidence, str] = {
    "high": "Rests on figures stated in the documents or on an official source",
    "medium": "Rests on indicative sources, or on a comparison needing assumptions",
    "low": "Indicative only — thin evidence, or figures that are not like-for-like",
}

#: Weakest-to-strongest ranking for evidence retrieved from the web. A price
#: on a marketplace listing and a price on a DBM circular are not the same kind
#: of fact, and a pre-posting review has to show which one it relied on.
SOURCE_TIER_MEANING: Dict[int, str] = {
    1: "Philippine government — PhilGEPS, DBM, PS-DBM, COA, GPPB",
    2: "Manufacturer or official distributor",
    3: "Philippine supplier or reseller",
    4: "Online marketplace listing",
    5: "Informational — news, blogs, reviews",
}


def _admits_none(annotation: Any) -> bool:
    """True when the field's type includes None, e.g. Optional[int]."""
    return type(None) in get_args(annotation)


class Parsed(BaseModel):
    """
    Base for every model built from an LLM response.

    Treats an explicit null as an absent key, so the field's default applies.

    A model handed a JSON template fills in every key it was shown, writing
    `null` into the ones it cannot answer — that is it saying "not provided".
    Pydantic reads an explicit null as a value, and `section: str = ""` rejects
    it, where omitting the key entirely would have been fine. The two mean the
    same thing coming from a model, and the distinction costs whole findings:
    a single `"section": null` was enough to drop a finding, and a run where
    every finding carried one took out two dimensions completely.

    Fields that genuinely admit None — `page`, `confidence`, `delta` — keep
    their nulls, because there the null is an answer rather than a blank.
    Nulling a *required* field is still an error, as it should be: no default
    exists to fall back on.
    """

    @model_validator(mode="before")
    @classmethod
    def _null_means_absent(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return {
            key: value
            for key, value in data.items()
            if value is not None
            or key not in cls.model_fields
            or _admits_none(cls.model_fields[key].annotation)
        }


class Source(Parsed):
    """
    Where in the uploaded documents the finding came from.

    `page` is optional because a model cannot always place a passage — the UI
    shows the section alone when it is missing. Insert [page N] markers into
    the document text to get it filled in reliably.
    """

    doc: str = Field(..., description="File name, e.g. 'TOR.pdf'")
    page: Optional[int] = Field(None, ge=1)
    section: str = Field("", description="e.g. 'Section 4 — Technical Specifications'")


class ComparedText(Parsed):
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


class ExternalSource(Parsed):
    """
    A web page consulted during the review, as distinct from an uploaded
    document. Only dimensions that search externally populate this.

    `tier` is what makes the citation usable in a defence of the procurement:
    it records how authoritative the source is, so the BAC can see at a glance
    whether a price rests on a DBM circular or on a marketplace listing.
    """

    url: str
    title: str = Field("", description="Page title as retrieved")
    publisher: str = Field("", description="Who published it, e.g. 'PS-DBM'")
    tier: int = Field(
        5, ge=1, le=5, description="See SOURCE_TIER_MEANING; 1 is strongest"
    )
    retrieved_at: str = Field(
        "", description="ISO date the page was read — prices go stale"
    )


class PolicyCitation(Parsed):
    """
    A provision from the reference library that a finding rests on.

    Filled in by the review pipeline from the retrieved passage, never by the
    model, so the title, section, page and quote are always the real ones.
    """

    title: str = Field(..., description="Document title, e.g. 'IRR of RA 12009'")
    section: str = Field("", description="e.g. 'Section 23.1'")
    page: int = Field(0, ge=0, description="0 when unknown")
    quote: str = Field("", description="The provision as written")


class ReviewFinding(Parsed):
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
        None,
        description="Plain summary of the discrepancy, e.g. 'Differs by ₱600,000.00'",
    )
    confidence: Optional[Confidence] = Field(
        None,
        description="How sure the analyzer is. Omit when the finding rests "
        "wholly on figures stated in the documents.",
    )
    external_sources: List[ExternalSource] = Field(
        default_factory=list,
        description="Web pages the finding relies on. Every price or "
        "availability claim drawn from outside the documents needs one.",
    )
    policy_sources: List[PolicyCitation] = Field(
        default_factory=list,
        description="Provisions the finding rests on, resolved from the "
        "reference library. Analyzers never set this.",
    )
    policy_refs: List[str] = Field(
        default_factory=list,
        exclude=True,
        description="Internal: provision identifiers named by the analyzer, "
        "resolved into policy_sources and then not persisted.",
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
    #: Set only when decision is "rejected". A rejected finding is withheld
    #: from the review list and from the final report, so the reason is the
    #: only trace of it left in front of the committee.
    rejection_reason: Optional[RejectionReason] = None
    rejection_note: str = ""
    edited: bool = False
    ai_analysis: str = Field("", description="Original wording, kept when edited")
    ai_recommendation: str = ""
    comments: List[Comment] = Field(default_factory=list)
    feedback: Optional[Feedback] = None


class DimensionSummary(Parsed):
    """
    What a dimension says about its own run, as distinct from its findings.

    Exists because "I checked and found nothing" and "I had nothing to check"
    render identically as an empty list, and the difference matters a great
    deal to a committee deciding whether an area has been covered. The
    assessment is where a dimension says which ground it actually walked.
    """

    assessment: str = Field(
        "", description="Plain summary of what was reviewed and what was found"
    )
    documents_reviewed: List[str] = Field(
        default_factory=list, description="File names this dimension actually read"
    )
    confidence: Optional[Confidence] = Field(
        None, description="How sure the dimension is of the assessment overall"
    )


class DimensionOutput(Parsed):
    """
    The richer return shape available to a dimension analyzer.

    `run` may return a bare list of findings — most do, and nothing forces a
    change — or one of these when it also has an assessment or a gap to
    report. The runner accepts either.
    """

    findings: List[ReviewFinding] = Field(default_factory=list)
    summary: Optional[DimensionSummary] = None
    research_gaps: List[str] = Field(
        default_factory=list,
        description="What the dimension could not resolve and why, in plain words",
    )


class DimensionResult(BaseModel):
    """Outcome of one dimension. A failure here never stops the others."""

    key: str
    label: str
    status: Literal["ok", "failed", "timeout"] = "ok"
    findings: List[ReviewFinding] = Field(default_factory=list)
    summary: Optional[DimensionSummary] = None
    research_gaps: List[str] = Field(default_factory=list)
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
