from forms.text_source import get_source_text, has_source_documents
from forms.classifier import classify_documents, recommendations
from forms.extractor import extract_fields
from forms.registry import FORM_REGISTRY
from utils.storage import save_generated_file

def detect(thread_id: str) -> dict:
    """
    Detect document types and return form recommendations.

    Returns:
        {doc_types: [...], forms: {key: {available, recommended, reason}}}
    """
    text = get_source_text(thread_id)
    doc_types = classify_documents(text) if text.strip() else []
    form_recs = recommendations(doc_types)

    return {
        "doc_types": doc_types,
        "forms": form_recs,
    }

def extract_all(thread_id: str, form_keys: list[str]) -> dict:
    """
    Extract fields for requested forms.

    Returns:
        {key: {"fields": {...}, "warning": bool, "group": "A_rich"|"B_annex"}}
    """
    text = get_source_text(thread_id)
    result = {}

    for key in form_keys:
        if key not in FORM_REGISTRY:
            continue

        spec = FORM_REGISTRY[key]

        if spec.group == "A_rich" and spec.schema:
            # Group A: extract using LLM
            model, warning = extract_fields(key, text)
            result[key] = {
                "fields": model.model_dump(),
                "warning": warning,
                "group": spec.group,
            }
        else:
            # Group B: header-only (blank for now, real implementation would extract entity/project)
            result[key] = {
                "fields": {},  # No fields for blank annexes
                "warning": False,
                "group": spec.group,
            }

    return result

def generate(thread_id: str, form_keys: list[str], overrides: dict) -> list[tuple[str, bytes]]:
    """
    Generate form files.

    Args:
        thread_id: Thread identifier
        form_keys: List of form keys to generate
        overrides: Dict of {form_key: {field: value}} for manual edits

    Returns:
        List of (filename, bytes) tuples
    """
    text = get_source_text(thread_id)
    results = []

    for key in form_keys:
        if key not in FORM_REGISTRY:
            continue

        spec = FORM_REGISTRY[key]
        form_overrides = overrides.get(key, {})

        if spec.group == "A_rich" and spec.schema:
            # Group A: extract + apply overrides
            model, _ = extract_fields(key, text)
            data_dict = model.model_dump()

            # Apply overrides
            data_dict.update(form_overrides)

            # Recreate model with overrides
            model = spec.schema(**data_dict)

            # Generate file
            file_bytes = spec.filler(spec.template_path, model)
        else:
            # Group B: blank annex with header stamp
            context = form_overrides.copy()  # Only user-provided header fields
            file_bytes = spec.filler(spec.template_path, context)

        # Save to disk
        filename = f"{spec.name}{spec.ext}"
        save_generated_file(thread_id, filename, file_bytes)

        results.append((filename, file_bytes))

    return results
