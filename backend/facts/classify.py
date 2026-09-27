"""Document type classification.

Classification drives routing: which rulepacks and consistency profiles apply
to an upload is decided entirely by the mix of types detected. It runs on the
first two pages only, because a procurement document announces what it is in
its title block and nowhere else.

A cheap keyword pass runs first. Most DICT documents carry an unambiguous
title ("PROPERTY ACKNOWLEDGEMENT RECEIPT", "DISBURSEMENT VOUCHER"), so the
majority are settled without an API call; the model is asked only when the
keywords are ambiguous.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from config import settings
from facts.schema import DOC_TYPE_LABELS, DOC_TYPES

# Distinctive title-block phrases, most specific first. Order matters: a
# Technical Inspection Report also contains the word "inspection", so the
# longer phrase must win.
_KEYWORD_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("disbursement_voucher", ("disbursement voucher", "dv no", "dv no.")),
    ("ors", ("obligation request and status", "obligation request", "ors no")),
    ("par", ("property acknowledgement receipt", "property acknowledgment receipt")),
    ("ics", ("inventory custodian slip",)),
    ("iar", ("inspection and acceptance report",)),
    ("inspection_report", ("technical inspection report", "inspection report")),
    ("delivery_receipt", ("delivery receipt", "delivery note")),
    ("warranty_certificate", ("warranty certificate", "certificate of warranty")),
    ("tax_receipt", ("bureau of internal revenue", "official receipt", "bir form")),
    ("invoice", ("sales invoice", "billing statement", "charge invoice")),
    ("noa", ("notice of award",)),
    ("ntp", ("notice to proceed",)),
    ("sbb", ("supplemental bid bulletin", "bid bulletin")),
    ("bac_resolution", ("bac resolution", "resolution of the bids and awards")),
    ("abstract_of_bids", ("abstract of bids", "abstract of quotations")),
    ("contract", ("contract agreement", "purchase order", "this agreement made")),
    ("rfq", ("request for quotation", "request for proposal")),
    ("bidding_docs", ("bidding documents", "invitation to bid", "philippine bidding")),
    ("dcb", ("detailed cost breakdown", "cost breakdown")),
    ("market_study", ("market research", "market scoping", "market study")),
    ("tor", ("terms of reference", "scope of work and deliverables")),
    ("pr", ("purchase request",)),
    ("ppmp", ("project procurement management plan", "ppmp")),
    ("app", ("annual procurement plan", "indicative app", "updated app")),
    ("checklist", ("readiness checklist", "procurement checklist")),
]

_CLASSIFY_PROMPT = """You are identifying a Philippine government procurement document.

Below is the beginning of one document. Identify which single type it is.

Allowed types (use the identifier on the left, exactly):
{type_list}

Judge by the title block and the form's structure, not by passing mentions.
A Purchase Request that mentions a contract number is still a `pr`.
Use `other` when nothing fits.

Document beginning:
---
{excerpt}
---"""

_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
        "confidence": {"type": "number"},
        "title_found": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["doc_type", "confidence", "title_found", "reason"],
    "additionalProperties": False,
}


def first_pages(text: str, count: int = 2) -> str:
    """Return the first `count` page blocks of a page-anchored transcript."""
    chunks = re.split(r"\n*--- Page \d+ ---\n", text)
    chunks = [c for c in chunks if c.strip()]
    if not chunks:
        return text[:6000]
    return "\n\n".join(chunks[:count])[:6000]


def classify_by_keywords(text: str) -> Optional[Tuple[str, float, str]]:
    """Cheap title-block match.

    Returns (doc_type, confidence, matched_phrase), or None when the excerpt
    matches several unrelated types and only the model can settle it.
    """
    haystack = first_pages(text).lower()
    if not haystack.strip():
        return None

    matches: List[Tuple[str, str, int]] = []
    for doc_type, phrases in _KEYWORD_RULES:
        for phrase in phrases:
            position = haystack.find(phrase)
            if position != -1:
                matches.append((doc_type, phrase, position))
                break

    if not matches:
        return None

    # A single match, or one that appears in the title block (the first 600
    # characters), is trusted outright.
    if len(matches) == 1:
        doc_type, phrase, _ = matches[0]
        return doc_type, 0.9, phrase

    in_title = [m for m in matches if m[2] < 600]
    if len(in_title) == 1:
        doc_type, phrase, _ = in_title[0]
        return doc_type, 0.85, phrase

    # Ambiguous: several plausible titles. Defer to the model.
    return None


def _classify_with_model(text: str, model: Optional[str] = None) -> Dict:
    import anthropic

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    type_list = "\n".join(f"- {key}: {label}" for key, label in DOC_TYPE_LABELS.items())
    prompt = _CLASSIFY_PROMPT.format(type_list=type_list, excerpt=first_pages(text))

    response = client.messages.create(
        model=model or settings.ANTHROPIC_MODEL_NAME,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _CLASSIFY_SCHEMA}},
    )
    body = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return json.loads(body)


def classify_document(
    text: str,
    filename: str = "",
    model: Optional[str] = None,
    allow_model: bool = True,
) -> Tuple[str, float]:
    """Determine a document's type.

    Args:
        text: The document transcript (page-anchored markdown).
        filename: Used as a weak tiebreaker; DICT names files informatively
            ("3-Delivery Receipt.pdf", "B. PR - MISS IP Phone.pdf").
        model: Override the classification model.
        allow_model: When False, never call the API -- used by offline tests.

    Returns:
        (doc_type, confidence).
    """
    keyword_hit = classify_by_keywords(text)
    if keyword_hit:
        return keyword_hit[0], keyword_hit[1]

    # Try the filename before spending a request.
    if filename:
        name_hit = classify_by_keywords(filename.replace("_", " ").replace("-", " "))
        if name_hit:
            return name_hit[0], 0.7

    if not allow_model:
        return "other", 0.0

    try:
        result = _classify_with_model(text, model=model)
        doc_type = result.get("doc_type", "other")
        if doc_type not in DOC_TYPE_LABELS:
            doc_type = "other"
        return doc_type, float(result.get("confidence", 0.5))
    except Exception:  # noqa: BLE001 - classification must never abort ingestion
        return "other", 0.0
