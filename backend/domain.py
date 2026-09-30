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

# Documents in process order, pre-award first.
#
# Post-award records used to be deliberately absent, on the grounds that this
# system reviews a procurement before award. The Compliance Checks tab changed
# that: T1 checks a disbursement voucher, T4 compares a contract against the
# payment packet, and T5 cross-checks delivery against acceptance. None of
# those can run against documents the record has no name for.
#
# The AI Review dimensions are unaffected — they select the pre-award types
# they always did and simply ignore the rest.
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
    "Notice to Proceed",
    "Contract",
    "Purchase Order",
    # Delivery and acceptance — what T5 cross-checks against the contract.
    "Delivery Receipt",
    "Sales Invoice",
    "Inspection and Acceptance Report",
    "Property Acknowledgement Receipt",
    "Inventory Custodian Slip",
    "Warranty Certificate",
    # Payment — what T1 checks and T4 compares back to the contract.
    "Obligation Request and Status",
    "Disbursement Voucher",
    "Official Receipt",
    "Certificate of Tax Withheld",
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
    #: The Compliance Checks tab runs independently of the AI Review, so it
    #: tracks its own progress rather than sharing review_status.
    check_status: ReviewStatus = "none"
    report_notes: str = ""
    finalized_at: Optional[str] = None
    finalized_by: Optional[str] = None
    # Filled in by the API so the list page can summarise a record without
    # fetching every finding. Not persisted — derived from the findings store.
    #
    # Counted per engine, because the two tabs each badge their own total and
    # a combined number would be wrong on both.
    finding_counts: Dict[str, int] = Field(default_factory=empty_counts)
    check_counts: Dict[str, int] = Field(default_factory=empty_counts)
    # How many findings the BAC has recorded an action against, across both.
    # Also derived.
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
    "Manuals",
    "Jurisprudence & Cases",
]
