"""
Work out what an uploaded PDF actually is.

The BAC used to pick a document type by hand on upload. They no longer do, so
this infers it instead. The result is a starting point, not a verdict — the
documents table lets the user change it, and every dimension has to cope with
a document typed "Other".

Deliberately conservative: an honest "Other" the user corrects in one click
beats a confident wrong label that silently steers the review.
"""

import logging
import re
from typing import List, Tuple

from domain import DOC_TYPES

logger = logging.getLogger(__name__)

# Only the front of the document is classified. Title pages and headers carry
# the signal; forty pages of specifications add cost and no accuracy.
CLASSIFY_PAGES = 3
CLASSIFY_CHARS = 6000

PROMPT = """You are filing documents for the Bids and Awards Committee of the
Philippine Department of Information and Communications Technology.

Identify what this document is. Choose exactly one label from this list:

{options}

File name: {filename}

Opening pages:
---
{excerpt}
---

Rules:
- Answer with the label alone, copied exactly as written above. No explanation.
- A document that sets out requirements, deliverables and responsibilities is
  a Terms of Reference (TOR). A document that is mostly tables of models,
  capacities, speeds or standards is Technical Specifications.
- If the document does not clearly match any label, or the text is too short
  or garbled to tell, answer exactly: Other
- Do not guess between two plausible labels. Answer Other instead.
"""


def _match(answer: str) -> str:
    """Map a model reply onto a known type, or 'Other'."""
    cleaned = re.sub(r"[`*_\"']", "", answer or "").strip()
    if not cleaned:
        return "Other"

    # Exact, then case-insensitive, then a unique substring hit — models like
    # to answer "Terms of Reference" for "Terms of Reference (TOR)".
    if cleaned in DOC_TYPES:
        return cleaned

    lowered = cleaned.lower()
    for option in DOC_TYPES:
        if option.lower() == lowered:
            return option

    # The reply must sit inside exactly one label — "Terms of Reference" and
    # "TOR" both resolve, "a TOR or maybe Technical Specifications" does not.
    # Deliberately not the other way round: mining a label out of a sentence
    # turns the model hedging into a confident answer, and hedging means Other.
    if len(lowered) >= 3:
        hits = [
            option
            for option in DOC_TYPES
            if option != "Other" and lowered in option.lower()
        ]
        if len(hits) == 1:
            return hits[0]

    logger.info("Unrecognised document type from model: %r", cleaned)
    return "Other"


def classify(filename: str, text: str) -> str:
    """
    Best guess at the type of one document.

    Never raises: classification is a convenience, and a failure here must not
    stop a document being attached to the procurement.
    """
    excerpt = (text or "").strip()
    if len(excerpt) < 200:
        # Scanned or image-only PDFs land here. Nothing to read, so do not
        # pretend — OCR would be the fix if these turn out to be common.
        logger.info("Too little text to classify %s", filename)
        return "Other"

    options = "\n".join(f"- {option}" for option in DOC_TYPES)
    prompt = PROMPT.format(
        options=options,
        filename=filename,
        excerpt=excerpt[:CLASSIFY_CHARS],
    )

    try:
        from utils.llm_factory import get_llm

        response = get_llm().invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        result = _match(str(content))
        logger.info("Classified %s as %s", filename, result)
        return result
    except Exception:  # noqa: BLE001 - never block an upload on this
        logger.warning("Could not classify %s", filename, exc_info=True)
        return "Other"


async def classify_many(documents: List[Tuple[str, str]]) -> List[str]:
    """
    Classify several documents at once, one call each, in parallel.

    Uploading six files should cost one classification round trip, not six in
    series. `documents` is a list of (filename, text).
    """
    import asyncio

    return list(
        await asyncio.gather(
            *(asyncio.to_thread(classify, name, text) for name, text in documents)
        )
    )
