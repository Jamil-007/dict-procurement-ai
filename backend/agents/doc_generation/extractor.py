import hashlib
import re
from pydantic import BaseModel
from agents.doc_generation.schemas import SCHEMAS
from prompts import FORM_EXTRACTION_PROMPTS
from utils.json_extract import extract_json_object
from utils.llm_factory import get_llm
from agents.feedback.service import inject_fewshot
from agents.feedback.models import EMBED_INPUT_LIMIT

HEADER_KEYS = ["procuring_entity", "project_title", "project_reference"]

# Extracting a form's fields is a full LLM round trip. The Forms review flow
# extracts once (/forms/extract) and then re-derives the same fields again when
# building each form's preview (/forms/generate) and on every debounced edit,
# all against the same source text — so without a cache the same extraction runs
# several times per form. Cache a *successful* extraction per (form_key, source
# text) so those repeats are instant. Failures are never cached, so a transient
# error doesn't stick for the whole session.
_extract_cache: dict[tuple[str, str], BaseModel] = {}
_EXTRACT_CACHE_MAX = 256


def clear_extract_cache() -> None:
    """Drop cached extractions (tests, or to force a fresh extraction)."""
    _extract_cache.clear()


def extract_fields(form_key: str, parsed_text: str) -> tuple[BaseModel, bool]:
    schema = SCHEMAS[form_key]
    if not parsed_text.strip():
        return schema(), True

    cache_key = (
        form_key,
        hashlib.sha256(parsed_text.encode("utf-8", "ignore")).hexdigest(),
    )
    cached = _extract_cache.get(cache_key)
    if cached is not None:
        return cached, False

    context = parsed_text[:EMBED_INPUT_LIMIT]
    prompt = FORM_EXTRACTION_PROMPTS[form_key].format(parsed_text=parsed_text[:20000])
    prompt = inject_fewshot(prompt, "forms", form_key, context)
    try:
        resp = get_llm(temperature=0.0).invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)
        data = extract_json_object(content)
        if data is None:
            return schema(), True
        model = schema(**data)
    except Exception:
        return schema(), True

    if len(_extract_cache) >= _EXTRACT_CACHE_MAX:
        _extract_cache.clear()
    _extract_cache[cache_key] = model
    return model, False


_HEADER_PROMPT = (
    "Extract ONLY the following procurement project header fields from the document as JSON "
    "with exactly these keys: procuring_entity, project_title, project_reference. "
    "procuring_entity is the government agency/office issuing the procurement. "
    "project_title is the name/title of the procurement project. "
    "project_reference is the project identification / reference / ITB number. "
    "Use null for any value not present. Return ONLY the JSON object.\n\n"
    "Document:\n{parsed_text}"
)

# Regex fallback patterns (case-insensitive) keyed by header field.
_HEADER_PATTERNS = {
    "procuring_entity": [
        r"procuring\s+entity\s*[:\-]\s*(.+)",
        r"name\s+of\s+(?:the\s+)?procuring\s+entity\s*[:\-]\s*(.+)",
        r"agency\s*[:\-]\s*(.+)",
    ],
    "project_title": [
        r"project\s+title\s*[:\-]\s*(.+)",
        r"name\s+of\s+(?:the\s+)?project\s*[:\-]\s*(.+)",
        r"procurement\s+project\s*[:\-]\s*(.+)",
    ],
    "project_reference": [
        r"project\s+identification\s+no\.?\s*[:\-]\s*(.+)",
        r"(?:project\s+)?reference\s+(?:no\.?|number)\s*[:\-]\s*(.+)",
        r"itb\s+no\.?\s*[:\-]\s*(.+)",
    ],
}


def _regex_header_fallback(parsed_text: str, result: dict) -> None:
    for field, patterns in _HEADER_PATTERNS.items():
        if result.get(field):
            continue
        for pat in patterns:
            m = re.search(pat, parsed_text, flags=re.IGNORECASE)
            if m:
                value = m.group(1).strip().splitlines()[0].strip()
                if value:
                    result[field] = value
                    break


def extract_header(parsed_text: str) -> dict:
    """Derive procuring_entity / project_title / project_reference for Group B header
    stamping. Uses a temperature-0.0 LLM call with a keyword/regex fallback so it works
    without an API key. Missing values are returned as None (rendered as [TBD])."""
    result = {k: None for k in HEADER_KEYS}
    if not parsed_text.strip():
        return result

    try:
        prompt = _HEADER_PROMPT.format(parsed_text=parsed_text[:20000])
        resp = get_llm(temperature=0.0).invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)
        data = extract_json_object(content)
        if data:
            for k in HEADER_KEYS:
                v = data.get(k)
                if v not in (None, "", "null"):
                    result[k] = str(v)
    except Exception:
        pass

    _regex_header_fallback(parsed_text, result)
    return result
