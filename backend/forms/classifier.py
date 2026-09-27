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

    # Keyword-based fallback
    text_lower = parsed_text.lower()
    types = []

    if "terms of reference" in text_lower or "tor" in text_lower[:500]:
        types.append("Terms of Reference")
    if "market study" in text_lower or "market scoping" in text_lower or "market research" in text_lower:
        types.append("Market Study")
    if "cost breakdown" in text_lower or "detailed cost estimate" in text_lower or "dce" in text_lower:
        types.append("Cost Breakdown")
    if "contract" in text_lower and "agreement" in text_lower:
        types.append("Contract")

    return types if types else ["Other"]

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
