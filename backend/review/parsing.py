"""
Turning an LLM response into findings.

Shared so that five dimension modules do not each reimplement fence-stripping
and JSON repair.
"""

import json
import logging
import re
from typing import Any, Iterable, List

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
    "severity": "critical" | "medium" | "low" | "info" | "compliant",
    "title": "One sentence naming the issue, neutrally phrased",
    "analysis": "What you observed in the documents and why it matters",
    "recommendation": "What the BAC should do. Omit for info and compliant findings.",
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

Severity — pick the one that fits, and do not inflate:
- "critical": potentially material issue requiring prompt BAC attention.
- "medium": meaningful issue, but it does not by itself prevent continuation.
- "low": minor quality or completeness issue.
- "info": an observation, not an identified deficiency.
- "compliant": you checked this point and found no issue. Worth recording.

Rules:
- Document text carries [page N] markers. Use the marker preceding a passage
  as its page number. Omit "page" entirely if you cannot place the passage —
  never guess, and never write null.
- "source" is required on every finding without exception, including findings
  that use "comparison". Where you are comparing documents, set "source" to the
  one the finding is primarily about.
- Use "comparison" only when two or more documents disagree. Otherwise use "quote".
- Quote text exactly as it appears. Never paraphrase inside a quote.
- Write findings as points for the BAC to verify, not as legal conclusions.
  Say "potential issue", "requires BAC review", "suggested action".
- Never state that something is illegal or non-compliant. That is the
  committee's determination, not yours.
- Return [] if you find nothing worth raising.
"""

# Paste this in ADDITION to FINDING_JSON_CONTRACT in any dimension that reasons
# about figures rather than only about drafting. Separate from the external
# evidence block below because confidence applies whether or not anything was
# retrieved from the web — a comparison drawn purely from the documents can
# still rest on an assumption.
CONFIDENCE_CONTRACT = """
One further field is available on a finding:

  "confidence": "high" | "medium" | "low"

Confidence is how sure you are, which is a separate question from how serious
the issue would be if true. A critical finding may be held at low confidence.
- "high": rests on figures stated in the documents, or on an official source.
- "medium": rests on indicative sources, or on a comparison needing assumptions.
- "low": indicative only — thin evidence, or figures that are not like-for-like.

Set it on every finding that involves a figure, a price or a comparison.
"""

# Paste this in ADDITION to the two blocks above, and only in a dimension that
# actually retrieves web pages. Kept separate deliberately: telling a dimension
# that never searches that it may cite URLs is an open invitation to invent them.
EXTERNAL_EVIDENCE_CONTRACT = """
One further field carries evidence found outside the uploaded documents:

  "external_sources": [
    {
      "url": "https://...",
      "title": "Page title as retrieved",
      "publisher": "PS-DBM",
      "tier": 1,
      "retrieved_at": "2026-09-26"
    }
  ]

Tier — how authoritative the source is. 1 is strongest:
  1  Philippine government — PhilGEPS, DBM, PS-DBM, COA, GPPB
  2  Manufacturer or official distributor
  3  Philippine supplier or reseller
  4  Online marketplace listing
  5  Informational — news, blogs, reviews

Rules:
- Every url you cite must be one that was supplied to you in the retrieved
  results below. Never write a URL from memory, and never construct one.
- Any figure that did not come from the uploaded documents needs at least one
  entry in "external_sources". A price with no source is not a finding.
- Say in the analysis whether a figure was observed on the source or derived
  by you, and state any assumption a comparison depends on.
- Leave "external_sources" out entirely when the finding rests wholly on the
  uploaded documents.
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


def _repair_source(entry: dict) -> None:
    """
    Fill in a missing `source` from the first compared document.

    A model that populates `comparison` often treats `source` as redundant and
    leaves it out, and `source` is required — so the finding is dropped. That
    is the wrong trade: a cross-document finding is usually the most valuable
    one in the set, and the citation it needs is already sitting in
    `comparison[0]`. Recover it rather than lose the finding.
    """
    source = entry.get("source")
    if isinstance(source, dict) and str(source.get("doc", "")).strip():
        return

    comparison = entry.get("comparison")
    if not isinstance(comparison, list) or not comparison:
        return

    first = comparison[0]
    if not isinstance(first, dict) or not str(first.get("doc", "")).strip():
        return

    entry["source"] = {
        "doc": first["doc"],
        "page": first.get("page"),
        "section": str(first.get("label", "")),
    }


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
        _repair_source(entry)
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


def strip_unretrieved_sources(
    findings: List[ReviewFinding], retrieved: Iterable[str]
) -> List[ReviewFinding]:
    """
    Remove any external source the search did not actually return.

    Telling a model not to invent URLs is not the same as it not inventing
    them, and a fabricated citation on a pre-posting review is worse than no
    citation at all. This is the enforcement: only URLs that came back from
    the search survive.

    A finding left with no sources keeps its text but is downgraded to "low"
    confidence, because whatever it rested on could not be verified.
    """
    allowed = set(retrieved)

    for finding in findings:
        if not finding.external_sources:
            continue
        kept = [s for s in finding.external_sources if s.url in allowed]
        if len(kept) != len(finding.external_sources):
            logger.warning(
                "Dropped %d unretrieved source(s) from a %s finding",
                len(finding.external_sources) - len(kept),
                finding.dimension,
            )
            finding.external_sources = kept
            if not kept:
                finding.confidence = "low"

    return findings
