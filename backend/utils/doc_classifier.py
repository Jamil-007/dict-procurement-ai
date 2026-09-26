"""
Work out what an uploaded PDF actually is.

The BAC used to pick a document type by hand on upload. They no longer do, so
this infers it instead. The result is a starting point, not a verdict — the
documents table lets the user change it, and every dimension has to cope with
a document typed "Other".

Two passes. The filename first, because BAC files are usually named after what
they are and reading the name costs nothing; then the model over the opening
pages for everything the name did not settle.

Deliberately conservative: an honest "Other" the user corrects in one click
beats a confident wrong label that silently steers the review.
"""

import logging
import re

from domain import DOC_TYPES

logger = logging.getLogger(__name__)

# Only the front of the document is classified. Title pages and headers carry
# the signal; forty pages of specifications add cost and no accuracy.
CLASSIFY_PAGES = 3
CLASSIFY_CHARS = 6000

# --- the filename pass ---
#
# Patterns are matched against the filename with the extension and any
# directory removed, lowercased, and underscores, hyphens and dots folded to
# spaces — so "PROC-2026-004_technical_specs_v2.PDF" is matched as
# "proc 2026 004 technical specs v2".
#
# Every pattern must be specific enough that a filename containing it is
# almost certainly that document. Where an acronym is also an ordinary word
# — "APP" at an agency that procures applications — the phrase has to be
# spelled out instead. A missed match costs one model call; a wrong match
# quietly points a review at the wrong document.
FILENAME_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\btors?\b|terms?\s+of\s+reference", "Terms of Reference (TOR)"),
    (
        r"\bspecs?\b|specification|tech(nical)?\s+spec",
        "Technical Specifications",
    ),
    (
        r"annual\s+procurement\s+plan",
        "Annual Procurement Plan (APP)",
    ),
    (
        r"\bppmp\b|project\s+procurement\s+management\s+plan",
        "Project Procurement Management Plan (PPMP)",
    ),
    (r"market\s+(study|research|scoping|survey)", "Market Study"),
    (r"quotation|canvass", "Supplier Quotation"),
    (r"purchase\s+request", "Purchase Request"),
    (
        r"\bcaf\b|availability\s+of\s+funds",
        "Certificate of Availability of Funds",
    ),
    (r"cost\s+breakdown", "Detailed Cost Breakdown"),
    (r"bidding\s+doc|\bbid\s+docs?\b", "Bidding Documents"),
    (r"\bitb\b|invitation\s+to\s+bid", "Invitation to Bid"),
    (r"\baob\b|abstract\s+of\s+bids?", "Abstract of Bids"),
    (r"\bbac\s+res|\bresolution\b", "BAC Resolution"),
    (r"\bminutes\b", "Minutes of BAC Meeting"),
    (r"post\s*qual", "Post-Qualification Report"),
)


def _normalise(filename: str) -> str:
    """Filename to matchable words: no path, no extension, no separators."""
    stem = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = re.sub(r"\.[a-z0-9]{1,5}$", "", stem, flags=re.IGNORECASE)
    return re.sub(r"[\s_\-.()]+", " ", stem).strip().lower()


def classify_filename(filename: str) -> str | None:
    """
    The document type named by the filename, or None if it does not name one.

    None covers both "no type word in here" and "two type words in here". The
    second is the interesting case: a file called "TOR and Technical
    Specifications.pdf" really could be either, and picking one on pattern
    order would be a guess dressed up as an answer. The model sees the text,
    so it is better placed to break the tie.
    """
    name = _normalise(filename)
    if not name:
        return None

    hits = [
        doc_type for pattern, doc_type in FILENAME_PATTERNS if re.search(pattern, name)
    ]
    # De-duplicate while keeping order, in case two patterns share a type.
    unique = list(dict.fromkeys(hits))

    if len(unique) == 1:
        return unique[0]
    if unique:
        logger.info("Filename %r names %s — asking the model", filename, unique)
    return None


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


def _ask_model(filename: str, excerpt: str) -> str:
    """The model's raw reply. Separated so the parsing above stays testable."""
    from utils.llm_factory import get_llm

    options = "\n".join(f"- {option}" for option in DOC_TYPES)
    prompt = PROMPT.format(
        options=options,
        filename=filename,
        excerpt=excerpt[:CLASSIFY_CHARS],
    )

    response = get_llm().invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def classify(filename: str, text: str) -> str:
    """
    Best guess at the type of one document.

    Never raises: classification is a convenience, and a failure here must not
    stop a document being attached to the procurement.
    """
    # The filename first. When it names a type outright it is the uploader's
    # own label, which is deliberate evidence rather than an inference, and it
    # costs nothing — so a hit skips the model call. It also types the scanned
    # PDFs that the text pass below can say nothing about.
    named = classify_filename(filename)
    if named:
        logger.info("Classified %s as %s from its name", filename, named)
        return named

    excerpt = (text or "").strip()
    if len(excerpt) < 200:
        # Scanned or image-only PDFs land here. Nothing to read, so do not
        # pretend — OCR would be the fix if these turn out to be common.
        logger.info("Too little text to classify %s", filename)
        return "Other"

    try:
        result = _match(_ask_model(filename, excerpt))
        logger.info("Classified %s as %s", filename, result)
        return result
    except Exception:  # noqa: BLE001 - never block an upload on this
        logger.warning("Could not classify %s", filename, exc_info=True)
        return "Other"


async def classify_many(documents: list[tuple[str, str]]) -> list[str]:
    """
    Classify several documents at once, in parallel.

    Uploading six files should cost one classification round trip, not six in
    series — and fewer than that, since the ones the filename pass settles cost
    no call at all. `documents` is a list of (filename, text).
    """
    import asyncio

    return list(
        await asyncio.gather(
            *(asyncio.to_thread(classify, name, text) for name, text in documents)
        )
    )
