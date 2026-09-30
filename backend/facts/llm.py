"""Provider-neutral structured-output calls for the facts pipeline.

Classification and extraction both need one thing from an LLM: a JSON response
shaped by a schema. This routes through the app's configured provider
(utils.llm_factory.get_llm) so compliance fact-extraction uses the same model as
the rest of the app (Anthropic by default) and carries no hardcoded/placeholder
model ids.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from utils.llm_factory import get_llm

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _loads(text: str) -> Dict[str, Any]:
    """Parse a JSON object out of a model reply, tolerating code fences and
    surrounding prose."""
    cleaned = _FENCE.sub("", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def generate_json(
    prompt: str,
    schema: Dict[str, Any],
    model: Optional[str] = None,  # accepted for signature compatibility; ignored
    max_tokens: int = 16000,
) -> Dict[str, Any]:
    """Call the configured LLM and return schema-shaped JSON.

    Prefers native structured output (tool/function calling); falls back to a
    plain call with JSON extraction so a provider path without structured-output
    support still returns a dict. Temperature 0: reading a field off a scanned
    form is transcription, not composition, and the checkers need repeatable
    extraction.
    """
    llm = get_llm(temperature=0)
    try:
        structured = llm.with_structured_output(schema)
        result = structured.invoke(prompt)
        return result if isinstance(result, dict) else dict(result)
    except Exception:
        response = llm.invoke(
            prompt
            + "\n\nReturn ONLY a single JSON object matching the schema. "
            + "No prose, no code fences."
        )
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return _loads(content)
