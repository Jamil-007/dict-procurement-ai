"""Provider-neutral structured-output calls for the facts pipeline.

Classification and extraction both need one thing from an LLM: a JSON
response shaped by a schema. Gemini (via GOOGLE_API_KEY) is preferred when
configured; Anthropic is the alternative.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from config import settings


def _gemini_json(
    prompt: str,
    schema: Dict[str, Any],
    model: Optional[str],
    max_tokens: int,
) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    # No max_output_tokens: Gemini 2.5 counts thinking tokens against the cap,
    # which silently truncates large JSON responses.
    response = client.models.generate_content(
        model=model or settings.GEMINI_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
            # Reading a field off a scanned form is transcription, not
            # composition. Left at the default, two runs over the same packet
            # disagreed about which fields were legible at all -- one found a
            # recipient and a delivery date where the next found neither --
            # and the consistency checkers turned that into eleven "could not
            # be confirmed" rows that had been real comparisons a minute
            # earlier. A checker whose answer changes when nothing changed is
            # not one a committee can act on.
            temperature=0.0,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as exc:
        finish = getattr(response.candidates[0], "finish_reason", None) if response.candidates else None
        # Keep JSONDecodeError type so callers can retry malformed responses.
        raise json.JSONDecodeError(
            f"{exc.msg} (finish_reason={finish})", exc.doc, exc.pos
        ) from exc


def _anthropic_json(
    prompt: str,
    schema: Dict[str, Any],
    model: Optional[str],
    max_tokens: int,
) -> Dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model or settings.ANTHROPIC_MODEL_NAME,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        # Same reason as the Gemini path above: extraction must be repeatable.
        temperature=0.0,
    )
    body = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return json.loads(body)


def generate_json(
    prompt: str,
    schema: Dict[str, Any],
    model: Optional[str] = None,
    max_tokens: int = 16000,
) -> Dict[str, Any]:
    """Call the configured LLM and return schema-shaped JSON."""
    if settings.GOOGLE_API_KEY:
        return _gemini_json(prompt, schema, model, max_tokens)
    if settings.ANTHROPIC_API_KEY:
        return _anthropic_json(prompt, schema, model, max_tokens)
    raise RuntimeError(
        "No LLM credentials: set GOOGLE_API_KEY (Gemini) or ANTHROPIC_API_KEY in .env"
    )
