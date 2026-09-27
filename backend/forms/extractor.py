from pydantic import BaseModel, ValidationError
from forms.schemas import SCHEMAS
from prompts import FORM_EXTRACTION_PROMPTS
from utils.json_extract import extract_json_object
from utils.llm_factory import get_llm

def extract_fields(form_key: str, parsed_text: str) -> tuple[BaseModel, bool]:
    schema = SCHEMAS[form_key]
    if not parsed_text.strip():
        return schema(), True
    prompt = FORM_EXTRACTION_PROMPTS[form_key].format(parsed_text=parsed_text[:20000])
    try:
        resp = get_llm(temperature=0.0).invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)
        data = extract_json_object(content)
        if data is None:
            return schema(), True
        return schema(**data), False
    except (ValidationError, Exception):
        return schema(), True
