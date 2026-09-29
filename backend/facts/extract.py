"""Extract canonical facts from a document transcript.

Extraction is the boundary between "text the model read" and "data the
checkers reason about". Everything after this point is deterministic, so the
quality of the whole system rests here.

Three things make it reliable:

1. **A JSON schema is enforced by the API**, so the response is always valid
   JSON of the right shape -- no fence-stripping, no repair passes.
2. **A per-doc-type field profile** tells the model which fields actually
   matter for the document in front of it, instead of asking it to fill in
   fifty fields that mostly do not apply.
3. **Page anchors are mandatory** for every value found, so a later finding
   can point at the page it came from.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from config import settings
from facts.classify import classify_document
from facts.schema import DOC_TYPE_LABELS, DocumentFacts, SourceRef
from ingest.loaders import LoadedDocument, load_document

# Which canonical fields each document type is actually expected to carry.
# The model is told to focus on these; it may still fill others if present.
FIELD_PROFILES: Dict[str, List[str]] = {
    "disbursement_voucher": [
        "dv_no", "ors_no", "payee", "amounts.gross", "amounts.tax",
        "amounts.retention", "amounts.other_deductions", "amounts.net",
        "amount_in_words", "dates.document", "dates.payment",
        "attachments_referenced", "signatories", "mode_of_procurement",
    ],
    "ors": ["ors_no", "payee", "amounts.total", "dates.document", "signatories"],
    "contract": [
        "contract_no", "supplier", "amounts.contract_amount", "items",
        "dates.contract_signed", "delivery_period", "warranty_period",
        "signatories", "project_title", "delivery_place", "personnel",
    ],
    "delivery_receipt": [
        "doc_number", "contract_no", "po_no", "supplier", "items",
        "dates.delivery", "delivery_place", "recipient", "signatories",
    ],
    "iar": [
        "doc_number", "contract_no", "po_no", "supplier", "items",
        "dates.inspection", "dates.acceptance", "signatories",
        "delivery_place", "recipient", "personnel",
    ],
    "inspection_report": [
        "doc_number", "contract_no", "supplier", "items",
        "dates.inspection", "dates.acceptance", "signatories",
        "delivery_place", "personnel",
    ],
    "par": [
        "doc_number", "items", "recipient", "end_user", "dates.received",
        "amounts.total", "signatories", "delivery_place",
    ],
    "ics": [
        "doc_number", "items", "recipient", "dates.received", "signatories",
        "delivery_place",
    ],
    "warranty_certificate": [
        "doc_number", "supplier", "items", "warranty_period",
        "dates.warranty_start", "dates.warranty_end", "contract_no",
    ],
    "invoice": [
        "invoice_no", "supplier", "items", "amounts.gross", "amounts.tax",
        "amounts.total", "dates.invoice", "po_no",
    ],
    "pr": [
        "pr_no", "project_title", "end_user", "items", "amounts.total",
        "dates.pr", "mode_of_procurement", "signatories",
    ],
    "tor": [
        "project_title", "items", "amounts.abc", "deliverables", "milestones",
        "delivery_period", "warranty_period", "eligibility_requirements",
        "delivery_place", "personnel",
    ],
    "market_study": ["project_title", "items", "amounts.abc", "supplier"],
    "dcb": ["project_title", "items", "amounts.abc", "amounts.total"],
    "bidding_docs": [
        "project_title", "items", "amounts.abc", "deliverables",
        "eligibility_requirements", "delivery_period", "warranty_period",
        "dates.bid_opening", "mode_of_procurement", "delivery_place",
        "personnel",
    ],
    "rfq": [
        "doc_number", "project_title", "items", "amounts.abc",
        "delivery_period", "eligibility_requirements",
    ],
    "ppmp": ["project_title", "items", "amounts.abc", "mode_of_procurement"],
    "app": ["project_title", "items", "amounts.abc", "mode_of_procurement"],
    "sbb": ["doc_number", "project_title", "dates.document"],
    "noa": ["doc_number", "contract_no", "supplier", "amounts.contract_amount", "dates.noa"],
    "ntp": ["doc_number", "contract_no", "supplier", "dates.ntp", "delivery_period"],
    "bac_resolution": ["doc_number", "project_title", "supplier", "amounts.contract_amount"],
    "tax_receipt": ["doc_number", "payee", "amounts.total", "dates.document"],
    "checklist": ["project_title", "attachments_referenced"],
}

_DEFAULT_PROFILE = [
    "doc_number", "project_title", "supplier", "items", "amounts.total",
    "dates.document", "signatories",
]

_EXTRACT_PROMPT = """You are extracting structured data from a Philippine government procurement document.

Document type: {doc_label} (`{doc_type}`)
Source file: {filename}

Fields that matter most for this document type:
{focus_fields}

Rules:

1. Transcribe values EXACTLY as printed. Never correct, complete or infer.
   If a total is arithmetically wrong on the page, report the wrong figure --
   detecting that error is a downstream check's job, not yours.
2. Use null for any field not present on the document. Never guess, and never
   copy a value from a different field because it looks similar.
3. Amounts: digits only, no currency symbol, no thousands separators
   (1,250,000.00 becomes 1250000.00). Parenthesised figures are negative.
4. Dates: copy the date string exactly as printed. Do not reformat.
5. Line items: one entry per printed row, in order. Split a combined
   "5 units @ 1,200.00" into qty=5, unit="units", unit_price=1200.00.
   Capture every serial number, IMEI or asset tag into `serial_numbers`.
6. Signatories: one entry per signature block, including UNSIGNED blocks.
   `signed` is true only when an actual signature mark is present, not merely
   a printed name. An unsigned block with a printed name is signed=false.
7. `attachments_referenced`: documents this one names as attached or supporting.
7a. `personnel`: individuals the supplier is committed to assign to the work --
   a project manager, team leader, engineer or technician named in the body of
   the document or in a manning schedule. Record the name, and the role in
   parentheses after it when the document states one. These are NOT the
   signatories: a person who only signs the form does not belong here.
8. `page_refs`: for each field you filled, add an entry mapping the field's
   dotted path (e.g. "amounts.net", "dv_no", "items", "signatories") to the
   page number it was read from. Use the `--- Page N ---` markers.
9. `extraction_confidence`: 0.0-1.0, lowered when the transcript is marked
   [ILLEGIBLE] in places that matter.
10. `notes`: anything a reviewer should know -- illegible figures, pages that
   were not transcribed, contradictory values on the same page.

Document transcript:
---
{transcript}
---"""


def _extraction_schema() -> Dict[str, Any]:
    """The JSON schema the API enforces on the extraction response.

    Hand-written rather than derived from Pydantic: the model needs a flat,
    explicit shape with no `$ref` indirection, and nullable-everywhere
    semantics that Pydantic's generated schema does not express cleanly.
    """
    nullable_str = {"type": ["string", "null"]}
    nullable_num = {"type": ["number", "null"]}
    str_array = {"type": "array", "items": {"type": "string"}}

    return {
        "type": "object",
        "properties": {
            "doc_number": nullable_str,
            "project_title": nullable_str,
            "entity_name": nullable_str,
            "contract_no": nullable_str,
            "pr_no": nullable_str,
            "po_no": nullable_str,
            "ors_no": nullable_str,
            "dv_no": nullable_str,
            "invoice_no": nullable_str,
            "reference_nos": str_array,
            "supplier": nullable_str,
            "payee": nullable_str,
            "end_user": nullable_str,
            "recipient": nullable_str,
            "delivery_place": nullable_str,
            "amount_in_words": nullable_str,
            "mode_of_procurement": nullable_str,
            "delivery_period": nullable_str,
            "warranty_period": nullable_str,
            "amounts": {
                "type": "object",
                "properties": {
                    key: nullable_num
                    for key in (
                        "abc", "contract_amount", "gross", "tax", "retention",
                        "discount", "other_deductions", "net", "total",
                    )
                },
                "required": [
                    "abc", "contract_amount", "gross", "tax", "retention",
                    "discount", "other_deductions", "net", "total",
                ],
                "additionalProperties": False,
            },
            "dates": {
                "type": "object",
                "properties": {
                    key: nullable_str
                    for key in (
                        "document", "pr", "contract_signed", "noa", "ntp",
                        "delivery", "delivery_due", "inspection", "acceptance",
                        "invoice", "received", "payment", "posting",
                        "bid_opening", "warranty_start", "warranty_end",
                    )
                },
                "required": [
                    "document", "pr", "contract_signed", "noa", "ntp",
                    "delivery", "delivery_due", "inspection", "acceptance",
                    "invoice", "received", "payment", "posting",
                    "bid_opening", "warranty_start", "warranty_end",
                ],
                "additionalProperties": False,
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line_no": nullable_str,
                        "description": {"type": "string"},
                        "qty": nullable_num,
                        "unit": nullable_str,
                        "unit_price": nullable_num,
                        "amount": nullable_num,
                        "brand_model": nullable_str,
                        "serial_numbers": str_array,
                        "page": {"type": ["integer", "null"]},
                    },
                    "required": [
                        "line_no", "description", "qty", "unit", "unit_price",
                        "amount", "brand_model", "serial_numbers", "page",
                    ],
                    "additionalProperties": False,
                },
            },
            "signatories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "name": nullable_str,
                        "position": nullable_str,
                        "signed": {"type": "boolean"},
                        "date": nullable_str,
                        "page": {"type": ["integer", "null"]},
                    },
                    "required": ["role", "name", "position", "signed", "date", "page"],
                    "additionalProperties": False,
                },
            },
            "attachments_referenced": str_array,
            "eligibility_requirements": str_array,
            "deliverables": str_array,
            "milestones": str_array,
            "personnel": str_array,
            "page_refs": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
            },
            "extraction_confidence": {"type": "number"},
            "notes": str_array,
        },
        "required": [
            "doc_number", "project_title", "entity_name", "contract_no",
            "pr_no", "po_no", "ors_no", "dv_no", "invoice_no", "reference_nos",
            "supplier", "payee", "end_user", "recipient", "delivery_place",
            "amount_in_words", "mode_of_procurement", "delivery_period",
            "warranty_period", "amounts", "dates", "items", "signatories",
            "attachments_referenced", "eligibility_requirements",
            "deliverables", "milestones", "personnel", "page_refs",
            "extraction_confidence", "notes",
        ],
        "additionalProperties": False,
    }


def _call_extractor(
    transcript: str,
    doc_type: str,
    filename: str,
    model: Optional[str],
) -> Dict[str, Any]:
    from facts.llm import generate_json

    profile = FIELD_PROFILES.get(doc_type, _DEFAULT_PROFILE)
    prompt = _EXTRACT_PROMPT.format(
        doc_label=DOC_TYPE_LABELS.get(doc_type, doc_type),
        doc_type=doc_type,
        filename=filename,
        focus_fields="\n".join(f"- {field}" for field in profile),
        transcript=transcript[: settings.EXTRACT_TEXT_LIMIT],
    )

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            return generate_json(
                prompt, _extraction_schema(), model=model, max_tokens=16000
            )
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt == 1:
                raise
    raise RuntimeError(f"Extraction failed: {last_error}")


def facts_from_payload(
    payload: Dict[str, Any],
    doc_type: str,
    doc_type_confidence: float,
    source: SourceRef,
) -> DocumentFacts:
    """Validate a raw extraction payload into a DocumentFacts record.

    Kept separate from the API call so fixtures and tests can build fact
    records without touching the network.
    """
    payload = dict(payload)
    payload["doc_type"] = doc_type
    payload["doc_type_confidence"] = doc_type_confidence
    try:
        facts = DocumentFacts.model_validate(payload)
    except ValidationError as exc:
        facts = DocumentFacts(
            doc_type=doc_type,
            doc_type_confidence=doc_type_confidence,
            error=f"Extraction did not match the canonical schema: {exc.error_count()} field error(s)",
        )
    facts.source = source
    return facts


def extract_facts(
    document: LoadedDocument,
    doc_type: Optional[str] = None,
    model: Optional[str] = None,
) -> DocumentFacts:
    """Turn a loaded document into a canonical fact record."""
    source = SourceRef(
        file=document.path,
        filename=document.filename,
        total_pages=document.total_pages,
        pages_read=document.pages_read,
        skipped_pages=document.skipped_pages,
        ingest_source=document.source,
    )

    if document.error or document.is_empty:
        return DocumentFacts(
            source=source,
            error=document.error or "No readable text could be extracted.",
        )

    if doc_type is None:
        doc_type, confidence = classify_document(document.text, document.filename, model)
    else:
        confidence = 1.0

    try:
        payload = _call_extractor(document.text, doc_type, document.filename, model)
    except Exception as exc:  # noqa: BLE001 - one bad document must not kill a batch
        detail = str(exc)
        if "authentication" in detail.lower() or "401" in detail:
            detail = "the AI service rejected the API key (check GOOGLE_API_KEY / ANTHROPIC_API_KEY and restart the server)"
        return DocumentFacts(
            doc_type=doc_type,
            doc_type_confidence=confidence,
            source=source,
            error=f"Extraction failed: {detail}",
        )

    facts = facts_from_payload(payload, doc_type, confidence, source)
    if document.skipped_pages:
        facts.notes.append(
            f"{len(document.skipped_pages)} page(s) were not transcribed because "
            f"the page budget was reached; some fields may be incomplete."
        )
    return facts


def extract_from_path(
    file_path: str,
    doc_type: Optional[str] = None,
    model: Optional[str] = None,
    progress=None,
) -> DocumentFacts:
    """Load a file and extract its facts in one step."""
    return extract_facts(load_document(file_path, progress=progress), doc_type, model)
