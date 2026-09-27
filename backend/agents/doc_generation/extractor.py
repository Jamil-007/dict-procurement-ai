import re
from pydantic import BaseModel
from agents.doc_generation.schemas import SCHEMAS
from prompts import FORM_EXTRACTION_PROMPTS
from utils.json_extract import extract_json_object
from utils.llm_factory import get_llm
from agents.feedback.service import inject_fewshot
from agents.feedback.models import EMBED_INPUT_LIMIT

HEADER_KEYS = ["procuring_entity", "project_title", "project_reference"]


def extract_fields(form_key: str, parsed_text: str) -> tuple[BaseModel, bool]:
    schema = SCHEMAS[form_key]
    if not parsed_text.strip():
        return schema(), True
    context = parsed_text[:EMBED_INPUT_LIMIT]
    prompt = FORM_EXTRACTION_PROMPTS[form_key].format(parsed_text=parsed_text[:20000])
    prompt = inject_fewshot(prompt, "forms", form_key, context)
    try:
        resp = get_llm(temperature=0.0).invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)
        data = extract_json_object(content)
        if data is None:
            return schema(), True
        return schema(**data), False
    except Exception:
        return schema(), True


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
