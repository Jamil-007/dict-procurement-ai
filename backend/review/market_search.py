"""
Retrieving market evidence from the web.

Tavily is evidence retrieval, not authority. This module fetches pages and
ranks how authoritative each one is; the judgement stays with the analyzer and
the citation stays with the BAC.

Three properties matter more than search quality here:

- It must work with no API key. TAVILY_API_KEY is unset on every developer
  machine, so the no-key path is the default, not an edge case.
- It must never raise into the dimension. A search problem degrades the
  analysis; it must not fail a review.
- It must finish. The runner kills a dimension at 180 seconds and that ceiling
  also covers the LLM call, so searching runs against a hard deadline.
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Sequence, Set
from urllib.parse import urlparse

from config import settings

logger = logging.getLogger(__name__)

#: Never issue more than this many searches for one review, whatever the
#: document contains. Each one costs money and wall-clock inside the timeout.
MAX_QUERIES = 6

#: Results requested per query. Enough to rank meaningfully, few enough that
#: the prompt does not drown the documents in web snippets.
RESULTS_PER_QUERY = 4

#: Whole-search budget. The remainder of the dimension timeout belongs to the
#: LLM call, which is the part that cannot be skipped.
SEARCH_BUDGET_SECONDS = 35.0

#: Per-request ceiling, so one slow host cannot eat the whole budget.
PER_REQUEST_TIMEOUT = 12.0

#: Longest snippet carried into the prompt, per page.
SNIPPET_CHARS = 500

#: Citation dates are read by a Philippine committee and may end up in a record
#: defended years later, so they are stamped in Philippine time rather than UTC
#: or whatever the container happens to be set to.
PH_TIME = timezone(timedelta(hours=8))


# --- source tiers ---------------------------------------------------------

_GOV_HOSTS = (".gov.ph", ".gov")
_MARKETPLACES = (
    "lazada.", "shopee.", "amazon.", "alibaba.", "aliexpress.", "ebay.",
    "carousell.",
)
_MANUFACTURERS = (
    "dell.com", "hp.com", "hpe.com", "lenovo.com", "cisco.com", "apple.com",
    "microsoft.com", "ibm.com", "oracle.com", "fortinet.com", "aruba",
    "canon.", "epson.", "brother.", "ricoh.", "fujitsu.", "asus.", "acer.",
    "samsung.com", "lg.com", "schneider-electric.com", "apc.com", "vmware.com",
)


def classify_tier(url: str) -> int:
    """
    Rank a URL against SOURCE_TIER_MEANING in review/schema.py. 1 is strongest.

    Host matching is a heuristic and will misjudge sources it has no rule for.
    It is deliberately biased downward — an unrecognised host lands at tier 5,
    informational — because overstating a source's authority on a procurement
    that later gets challenged is the expensive direction to be wrong in.
    """
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if not host:
        return 5
    if host.endswith(_GOV_HOSTS):
        return 1
    if any(vendor in host for vendor in _MANUFACTURERS):
        return 2
    if any(market in host for market in _MARKETPLACES):
        return 4
    if host.endswith(".ph"):
        return 3
    return 5


def _publisher(url: str) -> str:
    """A readable name for the citation line, e.g. 'ps-philgeps.gov.ph'."""
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


# --- results --------------------------------------------------------------


@dataclass(frozen=True)
class RetrievedPage:
    """One page the search returned."""

    url: str
    title: str
    publisher: str
    tier: int
    retrieved_at: str
    snippet: str


@dataclass
class MarketEvidence:
    """
    What the search produced, plus an honest account of whether it ran.

    `note` is written into the finding when evidence is thin or absent, so the
    BAC reads an assessment that says what it rests on rather than one that
    quietly omits the market.
    """

    pages: List[RetrievedPage] = field(default_factory=list)
    searched: bool = False
    note: str = ""

    @property
    def urls(self) -> Set[str]:
        """The URLs a finding is allowed to cite. Anything else is invented."""
        return {page.url for page in self.pages}

    def render(self) -> str:
        """The retrieved pages as prompt text, strongest source first."""
        if not self.pages:
            return "(none)"
        ordered = sorted(self.pages, key=lambda p: p.tier)
        return "\n\n".join(
            f"[tier {p.tier}] {p.title or p.url}\n"
            f"url: {p.url}\n"
            f"publisher: {p.publisher}\n"
            f"retrieved_at: {p.retrieved_at}\n"
            f"{p.snippet}"
            for p in ordered
        )


# --- search ---------------------------------------------------------------


def available() -> bool:
    """Whether an external search can be attempted at all."""
    return bool(settings.TAVILY_API_KEY)


def search_market(queries: Sequence[str]) -> MarketEvidence:
    """
    Run several queries concurrently and return the pages that came back.

    Never raises. A missing key, a dead network or a slow host all produce an
    empty result with `note` explaining it, and the dimension carries on with
    the documents alone.
    """
    if not queries:
        return MarketEvidence(note="No searchable items were identified.")

    if not available():
        return MarketEvidence(
            note=(
                "No external market evidence was retrieved for this review; "
                "the assessment rests on the attached documents."
            )
        )

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    except Exception:  # noqa: BLE001 - search is optional, the review is not
        logger.warning("Could not create the search client", exc_info=True)
        return MarketEvidence(
            note=(
                "External market search was unavailable for this review; the "
                "assessment rests on the attached documents."
            )
        )

    queries = list(queries)[:MAX_QUERIES]
    deadline = time.monotonic() + SEARCH_BUDGET_SECONDS
    seen: Dict[str, RetrievedPage] = {}
    today = datetime.now(PH_TIME).date().isoformat()
    failures = 0

    def one(query: str) -> dict:
        return client.search(
            query=query,
            max_results=RESULTS_PER_QUERY,
            timeout=PER_REQUEST_TIMEOUT,
        )

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(queries))
    try:
        futures = {pool.submit(one, q): q for q in queries}
        for future in concurrent.futures.as_completed(
            futures, timeout=max(0.1, deadline - time.monotonic())
        ):
            try:
                payload = future.result()
            except Exception:  # noqa: BLE001 - one bad query, not a failed review
                failures += 1
                logger.warning("Market query failed: %s", futures[future])
                continue

            for item in payload.get("results", []) or []:
                url = (item.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen[url] = RetrievedPage(
                    url=url,
                    title=(item.get("title") or "").strip(),
                    publisher=_publisher(url),
                    tier=classify_tier(url),
                    retrieved_at=today,
                    snippet=(item.get("content") or "").strip()[:SNIPPET_CHARS],
                )
    except concurrent.futures.TimeoutError:
        # Whatever arrived before the deadline is still usable. Proceed with it.
        logger.warning(
            "Market search hit the %.0fs budget with %d page(s) retrieved",
            SEARCH_BUDGET_SECONDS,
            len(seen),
        )
    finally:
        # Do not block the review waiting on requests we have stopped needing.
        pool.shutdown(wait=False, cancel_futures=True)

    pages = list(seen.values())
    if not pages:
        return MarketEvidence(
            searched=True,
            note=(
                "An external market search was run but returned no usable "
                "results; the assessment rests on the attached documents."
            ),
        )

    note = ""
    if failures:
        note = (
            f"{failures} of {len(queries)} market searches did not complete, so "
            "the external evidence below is partial."
        )
    logger.info("Market search retrieved %d page(s)", len(pages))
    return MarketEvidence(pages=pages, searched=True, note=note)
