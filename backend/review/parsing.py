"""
Turning an LLM response into findings.

Shared so that five dimension modules do not each reimplement fence-stripping
and JSON repair.
"""

import json
import logging
import re
from typing import Any, List

from pydantic import ValidationError

from review.schema import ReviewFinding

logger = logging.getLogger(__name__)

# Paste this into a dimension prompt so the model returns something the
# parser can read. Keep it in one place: if the schema changes, the
# instruction changes with it.
FINDING_JSON_CONTRACT = """
Return ONLY a JSON array. Each element is one finding:

[
  {
    "severity": "critical" | "warning" | "compliant",
    "title": "One sentence naming the issue, neutrally phrased",
    "analysis": "What you observed in the documents and why it matters",
    "recommendation": "What the BAC should do. Omit for compliant findings.",
    "source": {"doc": "TOR.pdf", "page": 11, "section": "Section 4"},
    "policy_basis": "RA 12009 IRR",
    "quote": "Exact text from the document, copied verbatim",
    "comparison": [
      {"doc": "Market Study.pdf", "page": 7, "label": "Quantity", "quote": "fifty (50) seats"},
      {"doc": "Purchase Request.pdf", "page": 3, "label": "Quantity", "quote": "Qty: 45 seats"}
    ],
    "delta": "5 seats unaccounted for"
  }
]

Rules:
- Document text carries [page N] markers. Use the marker preceding a passage
  as its page number. Omit "page" entirely if you cannot place the passage —
  never guess, and never write null.
- Use "comparison" only when two or more documents disagree. Otherwise use "quote".
- Quote text exactly as it appears. Never paraphrase inside a quote.
- Write findings as points for the BAC to verify, not as legal conclusions.
  Say "potential issue", "requires BAC review", "suggested action".
- Never state that something is illegal or non-compliant. That is the
  committee's determination, not yours.
- Return [] if you find nothing worth raising.
"""


def extract_json(content: str) -> Any:
    """
    Pull JSON out of a model response, tolerating markdown fences and prose
    either side of it. Raises ValueError if nothing parses.
    """
    if not content or not content.strip():
        raise ValueError("Empty response")

    text = content.strip()

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost array or object in the response.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError("No JSON found in response")


def findings_from_response(content: str, dimension: str) -> List[ReviewFinding]:
    """
    Parse a model response into findings, dropping any element that does not
    fit the schema rather than failing the whole dimension.
    """
    payload = extract_json(content)

    if isinstance(payload, dict):
        # Accept {"findings": [...]} as well as a bare array.
        payload = payload.get("findings", [payload])
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of findings, got {type(payload).__name__}")

    findings: List[ReviewFinding] = []
    dropped = 0

    for entry in payload:
        if not isinstance(entry, dict):
            dropped += 1
            continue
        entry.pop("id", None)  # ids are assigned by the runner
        entry["dimension"] = dimension
        try:
            findings.append(ReviewFinding(**entry))
        except ValidationError as exc:
            # Never silent: a schema mismatch here looks exactly like a clean
            # review that found nothing.
            dropped += 1
            logger.warning(
                "Dropped a malformed %s finding: %s", dimension, exc.errors()
            )

    if dropped and not findings:
        raise ValueError(
            f"All {dropped} findings returned by '{dimension}' failed validation"
        )

    return findings
