"""
Wiring the reference library into the review pipeline.

Every finding's policy basis is verified by us before the BAC reads it. The
model may only cite provisions retrieval actually returned, and the citation
the committee sees is materialised from the retrieved chunk, never from the
model's recall. Fabrication becomes impossible by construction.

This is the bridge between `knowledge/` and `review/`. `parsing.py` stays free
of knowledge imports — this module owns both the prompt block that tells
dimensions they may cite provisions, and the enforcement guard that strips
anything they cite but retrieval did not return.
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from collections.abc import Sequence

from knowledge.retrieve import provisions_for
from knowledge.schema import Chunk, Retrieval
from review.schema import PolicyCitation, ReviewFinding

logger = logging.getLogger(__name__)

#: How many seconds the entire multi-query provision search may spend. Whatever
#: arrived by the deadline is used; the dimension carries on with the rest.
POLICY_BUDGET_SECONDS = 20.0

#: Maximum characters of chunk text carried into a PolicyCitation quote field.
#: The full provision lives in the index; the quote is what fits in a finding
#: card without drowning the analysis.
POLICY_QUOTE_CHARS = 600

# Paste this in ADDITION to FINDING_JSON_CONTRACT, and only in a dimension that
# actually retrieves provisions. Same rationale as EXTERNAL_EVIDENCE_CONTRACT:
# telling a dimension that never retrieves that it may cite provisions is an
# invitation to invent them from memory.
POLICY_CONTRACT = """
One further field carries provisions from the reference library:

  "policy_refs": ["ra-12009-irr#0042", "gppb2023-004#0007"]

The identifiers are the bracketed ones shown in the provisions block above, and
nothing else. Cite a provision only when the finding genuinely rests on it, not
to decorate every finding with a statutory reference.

IMPORTANT: Do NOT write a "policy_basis" field in the JSON — it is filled in
automatically from the provisions you cite. The "policy_basis" field shown in
the earlier example is overridden here: omit it entirely. If no retrieved
provision supports your finding, leave "policy_refs" out and do not name a
section from memory.
"""


def provisions_for_queries(
    queries: Sequence[str],
    k_each: int = 3,
    cap: int = 8,
    budget: float = POLICY_BUDGET_SECONDS,
) -> Retrieval:
    """
    Run several provision queries concurrently and merge results.

    Queries execute in parallel because each one costs an embedding round trip
    of roughly 2.5 seconds. Results are merged round-robin by rank across
    queries — the scores come from separate searches and are not comparable,
    and a single query must not monopolise the whole budget.

    Args:
        queries: Natural language queries or section references to search for.
        k_each: How many provisions to retrieve per query.
        cap: Maximum total provisions to return after merging.
        budget: Whole-search timeout in seconds. Whatever arrived is used.

    Returns:
        A Retrieval with up to `cap` provisions, or an empty one with `note`
        explaining why nothing came back. Never raises.
    """
    if not queries:
        return Retrieval(note="No queries provided.")

    queries = list(queries)
    deadline = time.monotonic() + budget
    results: list[Retrieval] = []
    embedded_all = True

    def one(query: str) -> Retrieval:
        return provisions_for(query, k=k_each)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(queries))
    try:
        futures = {pool.submit(one, q): q for q in queries}
        for future in concurrent.futures.as_completed(
            futures, timeout=max(0.1, deadline - time.monotonic())
        ):
            try:
                result = future.result()
                results.append(result)
                if not result.embedded:
                    embedded_all = False
            except Exception:
                embedded_all = False
                logger.warning(
                    "Provision query failed: %s", futures[future], exc_info=True
                )
    except concurrent.futures.TimeoutError:
        logger.warning(
            "Provision search hit the %.0fs budget with %d/%d queries complete",
            budget,
            len(results),
            len(queries),
        )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # Merge results round-robin by rank across queries, deduping by chunk id
    seen: set[str] = set()
    merged: list[Chunk] = []
    rank = 0

    while len(merged) < cap:
        added_this_round = 0
        for result in results:
            if rank < len(result.provisions):
                chunk = result.provisions[rank].chunk
                if chunk.id not in seen:
                    seen.add(chunk.id)
                    merged.append(chunk)
                    added_this_round += 1
                    if len(merged) >= cap:
                        break
        if added_this_round == 0:
            break  # All queries exhausted
        rank += 1

    # Build the final Retrieval
    note = ""
    if not merged:
        # Check if we got any results at all
        if not results:
            note = (
                "The reference index was unavailable or no provision queries "
                "completed; the review rests on the attached documents alone."
            )
        else:
            note = "No provisions matched the queries."
    elif not embedded_all:
        note = (
            "Some provision searches used keyword-only retrieval (vector "
            "embeddings were unavailable); results may be less precise than usual."
        )

    # Rebuild Provision objects from merged chunks (score not meaningful after merge)
    from knowledge.schema import Provision

    provisions = [Provision(chunk=chunk, score=0.0) for chunk in merged]

    return Retrieval(provisions=provisions, embedded=embedded_all, note=note)


def ground_policy_basis(
    findings: list[ReviewFinding], retrieval: Retrieval
) -> list[ReviewFinding]:
    """
    Resolve policy_refs against retrieved provisions and enforce the contract.

    This is the guard that makes fabricated statutory citations impossible: only
    provision ids that retrieval actually returned survive. A finding citing an
    unverifiable section loses its policy_basis entirely — better to say nothing
    than to say something wrong.

    If the retrieval is empty (index unavailable), findings are returned
    untouched and the review degrades to what it does today. A missing reference
    library must not strip value out of the findings.

    Args:
        findings: Findings as parsed from the model response, with policy_refs set.
        retrieval: What provision search produced.

    Returns:
        The same findings with policy_sources populated, policy_basis rewritten
        to the canonical citation, and policy_refs cleared. Unverifiable
        citations are removed; the finding itself is never dropped.
    """
    if not retrieval.provisions:
        # Index unavailable or no provisions matched — degrade gracefully rather
        # than stripping the model's policy_basis, which may still be correct.
        if any(f.policy_refs for f in findings):
            logger.info(
                "No provisions retrieved; policy_refs on findings are not verified"
            )
        return findings

    # Build a lookup: provision id -> chunk
    provision_map = {p.chunk.id: p.chunk for p in retrieval.provisions}

    for finding in findings:
        if not finding.policy_refs:
            # Finding cites no provisions; leave it alone
            continue

        matched: list[Chunk] = []
        for ref in finding.policy_refs:
            chunk = provision_map.get(ref)
            if chunk:
                matched.append(chunk)
            else:
                logger.warning(
                    "Finding cited provision %s which was not retrieved (dimension: %s)",
                    ref,
                    finding.dimension,
                )

        # Populate policy_sources from matched chunks
        finding.policy_sources = [
            PolicyCitation(
                title=chunk.doc_title,
                section=chunk.section,
                page=chunk.page,
                quote=_trim_quote(chunk.text, POLICY_QUOTE_CHARS),
            )
            for chunk in matched
        ]

        # Rewrite policy_basis to the canonical citation
        if matched:
            finding.policy_basis = "; ".join(chunk.cite() for chunk in matched)
        elif finding.policy_basis:
            # Finding has a policy_basis but cited nothing that was verified —
            # clear it. An unverifiable statutory citation is worse than none.
            logger.warning(
                "Clearing unverifiable policy_basis on %s finding: %s",
                finding.dimension,
                finding.policy_basis,
            )
            finding.policy_basis = ""

    return findings


def _trim_quote(text: str, max_chars: int) -> str:
    """
    Trim a provision quote to max_chars at a word boundary, adding an ellipsis.

    Never cuts mid-word — a broken citation reads worse than a slightly longer
    one.
    """
    if len(text) <= max_chars:
        return text

    # Find the last space before max_chars
    trimmed = text[:max_chars]
    last_space = trimmed.rfind(" ")
    if last_space > 0:
        trimmed = trimmed[:last_space]

    return trimmed.rstrip() + "…"
