"""The canonical fact record extracted from every procurement document.

One `DocumentFacts` per uploaded file. The checkers never see raw text, so a
Delivery Receipt and a Disbursement Voucher are compared through the same
typed fields regardless of how differently they are laid out on paper.

Every extracted value can be traced back to a page through `page_refs`, so a
finding can always cite where it came from.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The document types the router and the rulepacks dispatch on.
DOC_TYPE_LABELS: Dict[str, str] = {
    "ppmp": "Project Procurement Management Plan",
    "app": "Annual Procurement Plan",
    "pr": "Purchase Request",
    "tor": "Terms of Reference",
    "market_study": "Market Research / Market Scoping",
    "dcb": "Detailed Cost Breakdown",
    "bidding_docs": "Bidding Documents",
    "rfq": "Request for Quotation",
    "sbb": "Supplemental Bid Bulletin",
    "bac_resolution": "BAC Resolution",
    "abstract_of_bids": "Abstract of Bids",
    "contract": "Contract Agreement / Purchase Order",
    "noa": "Notice of Award",
    "ntp": "Notice to Proceed",
    "disbursement_voucher": "Disbursement Voucher",
    "ors": "Obligation Request and Status",
    "invoice": "Sales Invoice / Billing Statement",
    "delivery_receipt": "Delivery Receipt",
    "iar": "Inspection and Acceptance Report",
    "inspection_report": "Technical Inspection Report",
    "par": "Property Acknowledgement Receipt",
    "ics": "Inventory Custodian Slip",
    "warranty_certificate": "Warranty Certificate",
    "tax_receipt": "Tax Receipt / BIR Document",
    "checklist": "Procurement Readiness Checklist",
    "other": "Unclassified document",
}

DOC_TYPES = tuple(DOC_TYPE_LABELS)

# Document types that belong to the payment/delivery side of a transaction.
TRANSACTION_DOC_TYPES = frozenset(
    {
        "disbursement_voucher",
        "ors",
        "invoice",
        "delivery_receipt",
        "iar",
        "inspection_report",
        "par",
        "ics",
        "warranty_certificate",
        "tax_receipt",
    }
)

# Document types produced during planning and bidding.
PLANNING_DOC_TYPES = frozenset(
    {
        "ppmp",
        "app",
        "pr",
        "tor",
        "market_study",
        "dcb",
        "bidding_docs",
        "rfq",
        "sbb",
        "checklist",
    }
)


class LineItem(BaseModel):
    """One row of a procurement line-item table."""

    line_no: Optional[str] = None
    description: str = ""
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    brand_model: Optional[str] = None
    serial_numbers: List[str] = Field(default_factory=list)
    page: Optional[int] = None

    def label(self) -> str:
        prefix = f"Item {self.line_no}: " if self.line_no else ""
        return f"{prefix}{self.description}".strip()


class Signatory(BaseModel):
    """A signature block, whether or not it was actually signed.

    `signed=False` with a printed name is the common COA deficiency: the block
    exists on the form but nobody signed it.
    """

    role: str = ""  # "Prepared by", "Certified by", "Approved by", "Received by", ...
    name: Optional[str] = None
    position: Optional[str] = None
    signed: bool = False
    date: Optional[str] = None
    page: Optional[int] = None


class Amounts(BaseModel):
    """Monetary figures, in pesos. `None` means the field is absent."""

    abc: Optional[float] = None  # Approved Budget for the Contract
    contract_amount: Optional[float] = None
    gross: Optional[float] = None
    tax: Optional[float] = None  # withholding tax
    retention: Optional[float] = None
    discount: Optional[float] = None
    other_deductions: Optional[float] = None
    net: Optional[float] = None  # net amount due
    total: Optional[float] = None  # document total


class KeyDates(BaseModel):
    """Dates that drive sequencing rules, as written on the document.

    Kept as raw strings; `rules.primitives` parses them. The documents use a
    mix of 12/04/2024, December 4 2024 and 04-DEC-24, and normalising on
    extraction would discard what was actually printed.
    """

    document: Optional[str] = None
    pr: Optional[str] = None
    contract_signed: Optional[str] = None
    noa: Optional[str] = None
    ntp: Optional[str] = None
    delivery: Optional[str] = None
    delivery_due: Optional[str] = None
    inspection: Optional[str] = None
    acceptance: Optional[str] = None
    invoice: Optional[str] = None
    received: Optional[str] = None
    payment: Optional[str] = None
    posting: Optional[str] = None
    bid_opening: Optional[str] = None
    warranty_start: Optional[str] = None
    warranty_end: Optional[str] = None


class SourceRef(BaseModel):
    """Where a fact record came from, for evidence citation."""

    file: str = ""
    filename: str = ""
    total_pages: int = 0
    pages_read: int = 0
    skipped_pages: List[int] = Field(default_factory=list)
    ingest_source: str = ""  # text_layer | vision | mixed | docx | xlsx


class DocumentFacts(BaseModel):
    """The canonical record for one document."""

    # Identity
    doc_type: str = "other"
    doc_type_confidence: float = 0.0
    doc_number: Optional[str] = None
    project_title: Optional[str] = None
    entity_name: Optional[str] = None  # procuring entity / agency

    # Cross-document reference numbers. These are the join keys the
    # consistency engine uses to decide that two documents describe the same
    # transaction, so they matter more than almost anything else here.
    contract_no: Optional[str] = None
    pr_no: Optional[str] = None
    po_no: Optional[str] = None
    ors_no: Optional[str] = None
    dv_no: Optional[str] = None
    invoice_no: Optional[str] = None
    reference_nos: List[str] = Field(default_factory=list)

    # Parties
    supplier: Optional[str] = None
    payee: Optional[str] = None
    end_user: Optional[str] = None
    recipient: Optional[str] = None  # who signed for receipt (PAR/ICS/DR)
    delivery_place: Optional[str] = None
    # Named individuals the supplier committed to assign, for contracts where
    # the people are the deliverable. Distinct from `signatories`, who sign
    # the document: these are named in the body of the contract or the TOR
    # and are supposed to be the same ones who later appear on the
    # accomplishment reports the payment is drawn against.
    personnel: List[str] = Field(default_factory=list)

    # Content
    amounts: Amounts = Field(default_factory=Amounts)
    amount_in_words: Optional[str] = None
    items: List[LineItem] = Field(default_factory=list)
    signatories: List[Signatory] = Field(default_factory=list)
    dates: KeyDates = Field(default_factory=KeyDates)
    attachments_referenced: List[str] = Field(default_factory=list)
    mode_of_procurement: Optional[str] = None
    delivery_period: Optional[str] = None
    warranty_period: Optional[str] = None
    eligibility_requirements: List[str] = Field(default_factory=list)
    deliverables: List[str] = Field(default_factory=list)
    milestones: List[str] = Field(default_factory=list)

    # Anything type-specific that does not fit the canonical fields.
    raw_fields: Dict[str, Any] = Field(default_factory=dict)

    # Provenance
    page_refs: Dict[str, int] = Field(default_factory=dict)
    source: SourceRef = Field(default_factory=SourceRef)
    extraction_confidence: float = 0.0
    notes: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    # -- helpers -----------------------------------------------------------

    @property
    def type_label(self) -> str:
        return DOC_TYPE_LABELS.get(self.doc_type, self.doc_type)

    @property
    def display_name(self) -> str:
        return self.source.filename or self.doc_number or self.type_label

    def page_of(self, field_path: str) -> Optional[int]:
        """The page a given field was read from, if the extractor recorded one."""
        return self.page_refs.get(field_path)

    def get_path(self, path: str) -> Any:
        """Resolve a dotted path like `amounts.net` or `dates.delivery`.

        `items[].qty` returns the list of that field across all line items.
        Returns None for any path that does not resolve, so rulepacks can
        reference fields that a given document type simply does not have.
        """
        if "[]" in path:
            head, _, tail = path.partition("[].")
            collection = self.get_path(head) if head else None
            if not isinstance(collection, list):
                return None
            return [getattr(entry, tail, None) for entry in collection]

        current: Any = self
        for part in path.split("."):
            if isinstance(current, BaseModel):
                if not hasattr(current, part):
                    return None
                current = getattr(current, part)
            elif isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            else:
                return None
        return current

    def signatory_for(self, role_keyword: str) -> Optional[Signatory]:
        """Find a signature block whose role mentions `role_keyword`."""
        needle = role_keyword.lower()
        for signatory in self.signatories:
            if needle in (signatory.role or "").lower():
                return signatory
        return None
