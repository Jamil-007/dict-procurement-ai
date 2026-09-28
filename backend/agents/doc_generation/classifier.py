import re

from utils.json_extract import extract_json_object
from utils.llm_factory import get_llm

# Document type to form mapping (ETG deliverable)
DOC_FORM_MAP = {
    "ppmp": {
        "source_doc_types": ["Terms of Reference", "Cost Breakdown"],
        "recommended_when": ["Terms of Reference"],
    },
    "market": {
        "source_doc_types": ["Market Study"],
        "recommended_when": ["Market Study"],
    },
    "app": {
        "source_doc_types": ["Terms of Reference", "Cost Breakdown"],
        "recommended_when": [],  # Not auto-recommended (use if no TOR for ppmp)
    },
    "contract": {
        "source_doc_types": ["Terms of Reference", "Contract"],
        "recommended_when": ["Terms of Reference"],
    },
    # Group B: blank annexes, never auto-recommended
    "bidform": {
        "source_doc_types": [],
        "recommended_when": [],
    },
    "price_local": {
        "source_doc_types": [],
        "recommended_when": [],
    },
    "price_abroad": {
        "source_doc_types": [],
        "recommended_when": [],
    },
    "bsd": {
        "source_doc_types": [],
        "recommended_when": [],
    },
    "oss": {
        "source_doc_types": [],
        "recommended_when": [],
    },
    "psd": {
        "source_doc_types": [],
        "recommended_when": [],
    },
}

ALLOWED_DOC_TYPES = {
    "Terms of Reference",
    "Market Study",
    "Cost Breakdown",
    "Contract",
    "Other",
}

# Maps the procurement record's document vocabulary (domain.DOC_TYPES, set at
# upload by utils/doc_classifier.py) onto this module's coarser vocabulary
# (ALLOWED_DOC_TYPES), so a procurement's already-classified documents can
# feed straight into recommendations() without re-classifying their text.
DOMAIN_TO_ALLOWED: dict[str, str] = {
    "Annual Procurement Plan (APP)": "Other",
    "Project Procurement Management Plan (PPMP)": "Other",
    "Market Study": "Market Study",
    "Market Scoping Checklist": "Market Study",
    "Supplier Quotation": "Cost Breakdown",
    "Purchase Request": "Other",
    "Certificate of Availability of Funds": "Other",
    "Terms of Reference (TOR)": "Terms of Reference",
    "Technical Specifications": "Terms of Reference",
    "Detailed Cost Breakdown": "Cost Breakdown",
    "Bidding Documents": "Other",
    "Invitation to Bid": "Other",
    "Abstract of Bids": "Other",
    "BAC Resolution": "Other",
    "Minutes of BAC Meeting": "Other",
    "Post-Qualification Report": "Other",
    "Notice of Award": "Other",
    "Contract": "Contract",
    "Other": "Other",
}

# Weak signal from which AI-Review dimension raised a finding: a dimension
# that reviewed a given kind of document at all is some evidence that kind of
# document is present and relevant, even when the finding's source filename
# does not line up with anything already on the procurement record (e.g. a
# cross-document comparison finding).
DIMENSION_DOC_HINTS: dict[str, list[str]] = {
    "compliance": ["Terms of Reference"],
    "requirements_risk": ["Terms of Reference"],
    "procurement_market": ["Market Study", "Cost Breakdown"],
    "document_consistency": [],
    "document_quality": [],
}


def _constrain(types: list) -> list[str]:
    """Keep only allowed labels, preserving order and dropping duplicates/unknowns."""
    seen = []
    for t in types:
        if isinstance(t, str) and t in ALLOWED_DOC_TYPES and t not in seen:
            seen.append(t)
    return seen


def classify_documents(parsed_text: str) -> list[str]:
    """
    Classify documents into types using LLM with keyword fallback.

    Returns list of document types constrained to the allowed set:
    Terms of Reference, Market Study, Cost Breakdown, Contract, Other
    """
    if not parsed_text.strip():
        return ["Other"]

    # Try LLM classification first
    try:
        prompt = (
            "Classify this procurement document into one or more of these types: "
            "Terms of Reference, Market Study, Cost Breakdown, Contract, Other. "
            "Return ONLY a JSON array of the matching types.\n\n"
            f"Document:\n{parsed_text[:5000]}"
        )
        resp = get_llm(temperature=0.0).invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)

        # Try to extract JSON array
        if "[" in content and "]" in content:
            start = content.find("[")
            end = content.rfind("]") + 1
            import json
            types = json.loads(content[start:end])
            if isinstance(types, list):
                constrained = _constrain(types)
                if constrained:
                    return constrained
    except Exception:
        pass

    # Keyword-based fallback.
    # Acronym markers (TOR, DCE) are matched case-sensitively with word
    # boundaries on the ORIGINAL text so that substrings inside ordinary words
    # (e.g. "contractor", "factor", "sector", "monitor") do NOT match.
    text_lower = parsed_text.lower()
    types = []

    # --- Terms of Reference ---
    # Bug #1 fix: require the full phrase or a standalone uppercase "TOR"
    # acronym, never a bare "tor" substring.
    if "terms of reference" in text_lower or re.search(r"\bTOR\b", parsed_text):
        types.append("Terms of Reference")

    # --- Market Study ---
    if (
        "market study" in text_lower
        or "market scoping" in text_lower
        or "market research" in text_lower
    ):
        types.append("Market Study")

    # --- Cost Breakdown ---
    if (
        "cost breakdown" in text_lower
        or "detailed cost estimate" in text_lower
        or re.search(r"\bDCE\b", parsed_text)
    ):
        types.append("Cost Breakdown")

    # --- Contract ---
    # Bug #2 fix: only classify as a Contract when an actual contract
    # instrument marker is present. Merely mentioning the words "contract"
    # and "agreement" (as a TOR often does) must NOT trigger this.
    contract_markers = (
        "contract agreement",
        "by and between",
        "hereinafter referred to as",
        "hereinafter called",
        "this contract",
        "this agreement",
    )
    if any(marker in text_lower for marker in contract_markers):
        types.append("Contract")

    return _constrain(types) if types else ["Other"]

def recommendations(doc_types: list[str]) -> dict[str, dict]:
    """
    Returns availability and recommendation status for all forms.

    Returns:
        {form_key: {"available": bool, "recommended": bool, "reason": str}}
    """
    result = {}

    for form_key, mapping in DOC_FORM_MAP.items():
        source_types = mapping["source_doc_types"]
        recommended_types = mapping["recommended_when"]

        # Group B forms
        if not source_types:
            result[form_key] = {
                "available": True,
                "recommended": False,
                "reason": "Blank annex — header stamped when a TOR is present.",
            }
        else:
            # Group A forms
            has_source = any(dt in doc_types for dt in source_types)
            is_recommended = any(dt in doc_types for dt in recommended_types)

            if is_recommended:
                reason = f"Recommended based on uploaded document type."
            elif has_source:
                reason = f"Can be filled from uploaded documents."
            else:
                reason = f"No matching document type detected."

            result[form_key] = {
                "available": True,  # All forms always available
                "recommended": is_recommended,
                "reason": reason,
            }

    return result


def doc_types_from_procurement_documents(domain_doc_types: list[str]) -> list[str]:
    """
    Map a procurement's already-classified ``ProcurementDocument.doc_type``
    values (domain.DOC_TYPES vocabulary) onto ALLOWED_DOC_TYPES.

    Order-preserving, de-duplicated.
    """
    seen: list[str] = []
    for dt in domain_doc_types:
        mapped = DOMAIN_TO_ALLOWED.get(dt, "Other")
        if mapped not in seen:
            seen.append(mapped)
    return seen


def doc_types_from_findings(findings: list, name_to_allowed: dict[str, str]) -> list[str]:
    """
    AI-Review signal: for each stored finding, resolve its ``source.doc``
    filename against the procurement's own documents (``name_to_allowed`` maps
    a document name to its ALLOWED_DOC_TYPES-mapped type) and, failing that,
    fall back to a weak hint from which dimension raised it.

    Order-preserving, de-duplicated.
    """
    seen: list[str] = []

    def _add(t: str) -> None:
        if t and t not in seen:
            seen.append(t)

    for finding in findings:
        source = getattr(finding, "source", None)
        doc_name = getattr(source, "doc", "") if source is not None else ""
        matched = name_to_allowed.get(doc_name)
        if matched:
            _add(matched)
            continue
        dimension = getattr(finding, "dimension", "")
        for hint in DIMENSION_DOC_HINTS.get(dimension, []):
            _add(hint)

    return seen


def recommend_for_ref(ref: str) -> dict:
    """
    Recommend forms for a procurement record, combining:
      (a) the procurement's already-classified ``documents[*].doc_type``, and
      (b) AI-Review signals from ``store.list_findings(ref)``.

    Returns:
        {"doc_types": [...], "forms": {form_key: {available, recommended, reason}}}
    """
    from store import get_store  # local import: avoids a store<->classifier cycle at import time

    store = get_store()
    procurement = store.get_procurement(ref)
    if not procurement:
        return {"doc_types": [], "forms": recommendations([])}

    documents = procurement.documents or []
    doc_types = doc_types_from_procurement_documents([d.doc_type for d in documents])
    name_to_allowed = {d.name: DOMAIN_TO_ALLOWED.get(d.doc_type, "Other") for d in documents}

    findings = store.list_findings(ref)
    for t in doc_types_from_findings(findings, name_to_allowed):
        if t not in doc_types:
            doc_types.append(t)

    return {"doc_types": doc_types, "forms": recommendations(doc_types)}
