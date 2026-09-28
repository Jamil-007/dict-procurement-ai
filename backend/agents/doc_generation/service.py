import logging

from pydantic import ValidationError

from agents.doc_generation.text_source import (
    get_source_text,
    has_source_documents,
    get_source_documents,
    get_ref_source_text,
)
from agents.doc_generation.classifier import (
    classify_documents,
    recommendations,
    recommend_for_ref,
)
from agents.doc_generation.extractor import extract_fields, extract_header, HEADER_KEYS
from agents.doc_generation.registry import FORM_REGISTRY, GROUP_B_DISCLAIMER
from utils.storage import save_generated_file

logger = logging.getLogger(__name__)


class FormGenerationError(Exception):
    """Raised when a form cannot be generated. Server surfaces a generic 500."""


def detect(thread_id: str) -> dict:
    """
    Detect document types per uploaded file and return form recommendations.

    Classifies EACH file separately (more accurate than concatenated text) and
    returns a per-file breakdown alongside the backward-compatible ``doc_types``
    (ordered union across all files) and ``forms`` keys.

    Returns:
        {
          documents: [{filename, doc_types: [...]}],
          doc_types: [...],           # ordered union across all files
          forms: {key: {available, recommended, reason}},
        }
    """
    docs = get_source_documents(thread_id)

    documents = []
    all_types: list[str] = []
    for doc in docs:
        types = classify_documents(doc["text"]) if doc["text"].strip() else []
        documents.append({"filename": doc["filename"], "doc_types": types})
        for t in types:
            if t not in all_types:
                all_types.append(t)

    return {
        "documents": documents,
        "doc_types": all_types,
        "forms": recommendations(all_types),
    }


def detect_for_ref(ref: str) -> dict:
    """
    Recommend forms for a procurement record's own documents, combining the
    documents' already-classified doc_types with AI-Review signals, and report
    which of each recommended form's required source documents are already on
    the procurement versus still missing.

    Unlike ``detect()`` this does not re-classify each file's text — the
    procurement's documents are classified at upload (routers/procurements.py)
    and refined by AI Review, so that existing signal is reused instead.

    Returns:
        {
          doc_types: [...],
          forms: {
            key: {available, recommended, reason, source_doc_types, present, missing}
          },
        }
    """
    rec = recommend_for_ref(ref)
    doc_types = rec["doc_types"]

    forms = {}
    for key, info in rec["forms"].items():
        required = FORM_REGISTRY[key].source_doc_types
        forms[key] = {
            **info,
            "source_doc_types": required,
            "present": [t for t in required if t in doc_types],
            "missing": [t for t in required if t not in doc_types],
        }

    return {"doc_types": doc_types, "forms": forms}


def extract_all(thread_id: str, form_keys: list[str]) -> dict:
    """
    Extract fields for requested forms.

    Returns:
        {key: {"fields": {...}, "warning": bool, "group": "A_rich"|"B_annex"}}
    """
    text = get_source_text(thread_id)
    result = {}
    _header_cache = None

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
            # Group B: header-only stamp (procuring_entity/project_title/project_reference)
            if _header_cache is None:
                _header_cache = extract_header(text)
            result[key] = {
                "fields": {k: _header_cache.get(k) for k in HEADER_KEYS},
                "warning": False,
                "group": spec.group,
            }

    return result


def _build_group_a_model(spec, text: str, form_overrides: dict):
    """Reconstruct a Group A model, applying overrides. Skips LLM extraction when
    overrides already cover all fields. Tolerant of malformed overrides: fields that fail
    validation fall back to the extracted (or empty) value rather than raising."""
    field_names = set(spec.schema.model_fields.keys())

    if field_names <= set(form_overrides.keys()):
        # Overrides fully cover the form; skip redundant extraction.
        base = spec.schema()
    else:
        base, _ = extract_fields(spec.key, text)

    base_dict = base.model_dump()
    data_dict = {**base_dict, **form_overrides}

    try:
        return spec.schema(**data_dict)
    except ValidationError as e:
        # Reset only the offending top-level fields to the extracted/base value.
        for err in e.errors():
            loc = err.get("loc") or ()
            if loc:
                data_dict[loc[0]] = base_dict.get(loc[0])
        try:
            return spec.schema(**data_dict)
        except ValidationError:
            # Give up on overrides entirely rather than 500.
            return base


def _generate_from_text(text: str, form_keys: list[str], overrides: dict) -> list[tuple[str, bytes]]:
    """Shared generation body for both the thread-based and ref-based sources."""
    results = []
    _header_cache = None

    for key in form_keys:
        if key not in FORM_REGISTRY:
            continue

        spec = FORM_REGISTRY[key]
        form_overrides = overrides.get(key, {}) or {}

        try:
            if spec.group == "A_rich" and spec.schema:
                model = _build_group_a_model(spec, text, form_overrides)
                file_bytes = spec.filler(spec.template_path, model)
            else:
                # Group B: blank annex with project header stamp + disclaimer.
                if set(HEADER_KEYS) <= set(form_overrides.keys()):
                    header = {k: form_overrides.get(k) for k in HEADER_KEYS}
                else:
                    if _header_cache is None:
                        _header_cache = extract_header(text)
                    header = {k: _header_cache.get(k) for k in HEADER_KEYS}
                context = {**header, **form_overrides}
                # Pass "[TBD]" for missing/blank header values so docxtpl never renders an
                # empty placeholder (never fabricate; missing renders literally as [TBD]).
                context = {k: ("[TBD]" if v in (None, "") else v) for k, v in context.items()}
                file_bytes = spec.filler(spec.template_path, context)
        except FormGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced as a generic 500 by the server
            logger.exception("Failed to generate form %s: %s", key, exc)
            raise FormGenerationError(f"Failed to generate form: {key}") from exc

        filename = f"{spec.name}{spec.ext}"
        results.append((filename, file_bytes))

    return results


def generate(thread_id: str, form_keys: list[str], overrides: dict) -> list[tuple[str, bytes]]:
    """
    Generate form files from a thread's fresh-upload session, saving each to
    disk under that thread (so it can be re-downloaded via list_generated_files).

    Args:
        thread_id: Thread identifier
        form_keys: List of form keys to generate
        overrides: Dict of {form_key: {field: value}} for manual edits

    Returns:
        List of (filename, bytes) tuples
    """
    text = get_source_text(thread_id)
    results = _generate_from_text(text, form_keys, overrides)
    for filename, file_bytes in results:
        save_generated_file(thread_id, filename, file_bytes)
    return results


def generate_for_ref(ref: str, form_keys: list[str], overrides: dict) -> list[tuple[str, bytes]]:
    """
    Generate form files from a procurement record's own documents (Forms tab).

    Unlike ``generate()``, results are not saved to a thread's disk area — the
    procurement's documents (and therefore the generated forms, regenerated on
    demand) are already durable via store/files.py.

    Args:
        ref: Procurement ref
        form_keys: List of form keys to generate
        overrides: Dict of {form_key: {field: value}} for manual edits

    Returns:
        List of (filename, bytes) tuples
    """
    text = get_ref_source_text(ref)
    return _generate_from_text(text, form_keys, overrides)
