"""
Records that outlive a single request: procurements, their documents, and the
Knowledge Hub.

Distinct from models.py, which describes the Procurement Analyst's request and
response bodies.
"""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from review.schema import empty_counts

ProcurementStatus = Literal["ongoing", "finalized"]
ReviewStatus = Literal["none", "processing", "done"]

# Pre-award documents, in process order. Post-award records (contracts,
# payment documents) are deliberately absent — this system reviews a
# procurement before award.
#
# Kept in step with frontend/types/records.ts DOC_TYPES. The classifier in
# utils/doc_classifier.py picks from this list, so adding a type here is
# enough to make it selectable and inferable.
DOC_TYPES = [
    # Planning
    "Annual Procurement Plan (APP)",
    "Project Procurement Management Plan (PPMP)",
    "Market Study",
    "Market Scoping Checklist",
    # Price canvassing evidence gathered for the market study and the ABC, so
    # this is a planning input, not a bid received after posting.
    "Supplier Quotation",
    "Purchase Request",
    "Certificate of Availability of Funds",
    # Requirements
    "Terms of Reference (TOR)",
    "Technical Specifications",
    "Detailed Cost Breakdown",
    # Bidding
    "Bidding Documents",
    "Invitation to Bid",
    "Abstract of Bids",
    # BAC action
    "BAC Resolution",
    "Minutes of BAC Meeting",
    "Post-Qualification Report",
    # Award. The tool reviews before posting, so these arrive only when a
    # procurement is uploaded after the fact — but the dimensions cite them
    # when they are there, so they need to be nameable.
    "Notice of Award",
    "Contract",
    "Other",
]


def today() -> str:
    return date.today().isoformat()


class ProcurementDocument(BaseModel):
    id: str
    name: str
    doc_type: str = "Other"
    pages: int = 0
    uploaded: str = Field(default_factory=today)
    gcs_path: str = ""
    status: str = "Ready"


class Procurement(BaseModel):
    ref: str
    title: str
    abc: float = 0
    mode: str = "Competitive Bidding"
    fund: str = "GAA"
    category: str = ""
    end_user: str = ""
    status: ProcurementStatus = "ongoing"
    created: str = Field(default_factory=today)
    updated: str = Field(default_factory=today)
    documents: List[ProcurementDocument] = Field(default_factory=list)
    review_status: ReviewStatus = "none"
    report_notes: str = ""
    finalized_at: Optional[str] = None
    finalized_by: Optional[str] = None
    # Filled in by the API so the list page can summarise a record without
    # fetching every finding. Not persisted — derived from the findings store.
    finding_counts: Dict[str, int] = Field(default_factory=empty_counts)
    # How many findings the BAC has recorded an action against. Also derived.
    decided_count: int = 0


class ProcurementCreate(BaseModel):
    title: str = Field(..., min_length=1)
    abc: float = 0
    mode: str = "Competitive Bidding"
    fund: str = "GAA"
    category: str = ""
    end_user: str = ""


class ProcurementPatch(BaseModel):
    """Every field optional — only what is sent gets written."""

    title: Optional[str] = None
    abc: Optional[float] = None
    mode: Optional[str] = None
    fund: Optional[str] = None
    category: Optional[str] = None
    end_user: Optional[str] = None
    report_notes: Optional[str] = None


class KnowledgeEntry(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    category: str
    doc_type: str = ""
    date: str = ""
    pages: int = 0
    excerpt: str = ""
    gcs_path: str = ""


KNOWLEDGE_CATEGORIES = [
    "Laws & Regulations",
    "GPPB Issuances",
    "COA Issuances",
    "DICT Policies",
    "Standard Forms",
    "Jurisprudence & Cases",
]
