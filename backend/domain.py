"""
Records that outlive a single request: procurements, their documents, and the
Knowledge Hub.

Distinct from models.py, which describes the Procurement Analyst's request and
response bodies.
"""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ProcurementStatus = Literal["ongoing", "finalized"]
ReviewStatus = Literal["none", "processing", "done"]

DOC_TYPES = [
    "Market Study",
    "TOR",
    "Technical Specifications",
    "DCB",
    "Bidding Documents",
    "BAC Resolution",
    "Purchase Request",
    "Contract",
    "Supplier Quotation",
    "Payment Document",
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
    finding_counts: Dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "warning": 0, "compliant": 0}
    )
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
