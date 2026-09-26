"""
Turning an LLM response into findings.

Shared so that five dimension modules do not each reimplement fence-stripping
and JSON repair.
"""

import json
import logging
import re
from typing import Any, Iterable, List, Optional

from pydantic import ValidationError

from review.schema import DimensionOutput, DimensionSummary, ReviewFinding

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

# Paste this in ADDITION to FINDING_JSON_CONTRACT in a dimension that should
# also report what it reviewed. It overrides the "Return ONLY a JSON array"
# instruction above, so the two must always appear in that order.
SUMMARY_CONTRACT = """
OVERRIDE: do not return a bare array after all. Return this object instead,
with the findings array from above sitting inside it:

{
  "summary": {
    "assessment": "What you reviewed and what you concluded, in two or three sentences",
    "documents_reviewed": ["TOR.pdf", "Purchase Request.pdf"],
    "confidence": "high" | "medium" | "low"
  },
  "findings": [ ... ],
  "research_gaps": [
    "What you could not resolve, and what would have resolved it"
  ]
}

Rules for these three:
- "documents_reviewed" lists only files you were actually given below. Never
  name a document that was not provided.
- The assessment is required even when "findings" is empty — especially then.
  An empty findings list with no assessment is indistinguishable from a
  dimension that failed, and the committee has to be able to tell which areas
  were genuinely covered.
- Put a missing document in "research_gaps", not in a finding, unless its
  absence is itself the issue you are raising.
- Leave "research_gaps" as [] when nothing was missing.
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

# Paste this right after a dimension's "PROCUREMENT RECORD" block. Title, ABC,
# mode, fund and end-user there are what the BAC typed into the case when it
# was created — often before every document was even attached — not something
# verified against the documents. A dimension that treats it as ground truth
# inherits every typo and every field left at its default, and judges real
# documents against a number nobody checked. The documents are the evidence;
# the record is a label for the case.
RECORD_IS_NOT_EVIDENCE = """
The PROCUREMENT RECORD above is what the BAC typed in when the case was
created. Treat it as a label for the case, not as a verified fact, and never
use it to override what a document states. Determine every fact you report
on — budget, quantities, mode, dates, specifications — from the documents
themselves. Where a document disagrees with the record, that disagreement may
be worth a finding, but only if it also falls inside what this dimension
covers; do not let the record's figure change your assessment of what the
documents show.
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

    Logs the raw reply before raising — this is the only place that ever sees
    it. Without that, a failure here shows up as a bare "No JSON found in
    response" with the actual model output gone, and there is no way to tell
    a safety refusal from an auth error surfaced as text from a model that
    genuinely answered in prose.
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

    logger.warning("No JSON in model response, first 2000 chars:\n%s", content[:2000])
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


def _findings_from_list(payload: list, dimension: str) -> List[ReviewFinding]:
    """
    Validate a list of raw entries into findings, dropping any that does not
    fit the schema rather than failing the whole dimension.

    Raises only when everything was dropped — a response that parsed but
    yielded nothing usable is a failure, not a clean review.
    """
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


def findings_from_response(content: str, dimension: str) -> List[ReviewFinding]:
    """
    Parse a model response into findings, ignoring anything wrapped around
    them. Use output_from_response instead when the dimension also asks for
    an assessment.
    """
    payload = extract_json(content)

    if isinstance(payload, dict):
        # Accept {"findings": [...]} as well as a bare array.
        payload = payload.get("findings", [payload])
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of findings, got {type(payload).__name__}")

    return _findings_from_list(payload, dimension)


def _summary_from(payload: dict, dimension: str) -> Optional[DimensionSummary]:
    """The summary block, or None if the model omitted or mangled it."""
    raw = payload.get("summary")
    if not isinstance(raw, dict):
        return None
    try:
        return DimensionSummary(**raw)
    except ValidationError as exc:
        # The findings are the valuable part — never lose them over this.
        logger.warning("Dropped a malformed %s summary: %s", dimension, exc.errors())
        return None


def output_from_response(content: str, dimension: str) -> DimensionOutput:
    """
    Parse a model response into findings plus its summary and research gaps.

    Tolerates a bare array, so a dimension carrying SUMMARY_CONTRACT still
    parses when the model ignores it and answers in the older shape. The
    findings are what matter; the envelope around them is a bonus and is
    dropped rather than allowed to fail the dimension.
    """
    payload = extract_json(content)

    if isinstance(payload, list):
        return DimensionOutput(findings=_findings_from_list(payload, dimension))

    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected findings or an object containing them, got "
            f"{type(payload).__name__}"
        )

    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        # A single finding returned as a bare object, which models do.
        raw_findings = [payload]

    gaps = payload.get("research_gaps")
    gaps = [str(g) for g in gaps if str(g).strip()] if isinstance(gaps, list) else []

    return DimensionOutput(
        findings=_findings_from_list(raw_findings, dimension),
        summary=_summary_from(payload, dimension),
        research_gaps=gaps,
    )


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
