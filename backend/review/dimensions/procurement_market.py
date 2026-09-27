"""
Procurement & Market — specification openness, ABC alignment, and existing
system dependencies.

Owner: Mark
Replaces: market_scoping_agent and lcca_agent in agents.py

Full brief: docs/dimension-procurement-market.md. Read it before changing this
file — it covers the boundary against the other four dimensions, the source
tiering for external evidence, and what this dimension must not assert.

Two things that are easy to get wrong:
- The Tavily search is optional. TAVILY_API_KEY is not set locally, so the
  document-only path is the default one. It runs every internal check and says
  in the findings that no external evidence was retrieved.
- Specifications that appear tailored to one product are raised as a potential
  concern requiring BAC review, never as a determination that the
  specification is restrictive.
"""

import logging
from typing import List

from prompts import RA_12009_DIRECTIVE
from review.context import ReviewContext, render
from review.gaps import cannot_assess
from review.llm import analyze
from review.market_search import MAX_QUERIES, MarketEvidence, available, search_market
from review.parsing import (
    CONFIDENCE_CONTRACT,
    EXTERNAL_EVIDENCE_CONTRACT,
    FINDING_JSON_CONTRACT,
    RECORD_IS_NOT_EVIDENCE,
    extract_json,
    strip_unretrieved_sources,
)
from review.policy import POLICY_CONTRACT, ground_policy_basis, provisions_for_queries
from review.registry import register
from review.schema import ReviewFinding
from utils.llm_factory import get_llm

logger = logging.getLogger(__name__)

DIMENSION = "procurement_market"

# Fixed queries covering this dimension's subject matter. No extra LLM call to
# build them — the dimension's concerns are stable. These are phrased as the
# provisions would be worded, not as questions.
POLICY_QUERIES = (
    "approved budget for the contract ABC market price basis",
    "brand name specifications or equivalent justification",
    "restrictive eligibility requirements technical specifications",
    "market scoping before procurement supplier identification",
    "delivery period lead time requirements",
)

# Document types this dimension reads. Names come from domain.DOC_TYPES.
# Supplier Quotation is planning evidence here — the price canvassing behind
# the market study and the ABC, not a bid received after posting.
READS = (
    "Market Study",
    "Supplier Quotation",
    "Project Procurement Management Plan (PPMP)",
    "Terms of Reference (TOR)",
    "Technical Specifications",
    "Detailed Cost Breakdown",
)

# How much document text to show the query builder. It only needs to name the
# items, so this stays small — the full text goes to the analysis call.
QUERY_EXCERPT_CHARS = 6000

QUERY_PROMPT = """From the procurement documents below, write the web search
queries that would establish whether the budget and the specification are
realistic in the Philippine market.

Write at most {max_queries} queries. Make each one narrow and specific:
- Name the brand and model where the specification names one.
- Otherwise name the item category with its distinguishing capacity or size.
- Include "Philippines" in every query, and the year for anything price-related.
- Make at least one query target Philippine government sources, for example
  PhilGEPS or PS-DBM price references.

Return ONLY a JSON array of strings. Return [] if the documents name nothing
concrete enough to search for.

PROCUREMENT: {title}
DOCUMENTS:
{excerpt}
"""

PROMPT = """You are reviewing Philippine government procurement documents for
the Bids and Awards Committee of the DICT.

{ra_12009_directive}

This review runs immediately before the procurement is posted to PhilGEPS. The
question is not whether the paperwork is complete but whether it would stand
up: if the budget is challenged after award, is there a defensible basis for it
on the record?

PROCUREMENT RECORD
Title: {title}
Approved Budget for the Contract: {abc}
Mode: {mode}
Category: {category}
{record_caveat}
The figure above is what was typed into the case, not a verified budget.
Establish the actual ABC from the documents on file — the PPMP, the Purchase
Request, the Detailed Cost Breakdown — and judge the market evidence against
that documented figure, not the one above. If the documents disagree with each
other, or with the figure above, that disagreement is a cross-document
inconsistency and another reviewer covers it — use whichever figure the
documents themselves support for your own assessment below.

ASSESS THESE SIX AREAS
1. Project cost estimate — is the documented ABC supported by the market
   evidence on file? Is there a traceable basis for it? Are the supplier
   quotations numerous and varied enough to establish a market price, or too
   few and too alike?
2. Design and specifications — is the specification open enough to attract more
   than one offer? Name the parameters that narrow the field.
3. Technical criteria — are eligibility and technical requirements proportionate
   to what is being bought?
4. Delivery lead time — is the required schedule achievable in this market?
5. Storage and warehousing — are delivery and holding assumptions stated and
   feasible?
6. Market risks — single-source dependency, thin local supply, volatile pricing,
   end-of-life or superseded products, import dependency.

Also check the market study itself: whether it defines the relevant market,
identifies how many capable suppliers exist, states where its prices came from
and how current they are, shows availability and lead time evidence, considers
alternatives, and reflects recurring costs such as licences, support,
consumables and disposal rather than acquisition cost alone. Where one of these
is absent, an "info" or "low" finding naming what is missing is appropriate.
Absence of evidence is not evidence of a defect.

COMPARING PRICES
Two prices are not comparable until they describe the same thing. Before any
comparison, bring both sides onto the same basis and state that basis in the
analysis: currency and conversion date, VAT inclusive or exclusive, unit of
sale, quantity and delivery terms. Say whether a figure was observed on the
source or derived by you. Derived figures are fine; undeclared ones are not.
State any assumption a comparison depends on.

STAY INSIDE THIS DIMENSION
Four other reviewers run alongside you. Do not comment on:
- drafting quality, ambiguity, wrong headings or blank sections
- two documents disagreeing with each other
- legal or procedural compliance, procurement mode, thresholds or approvals
- what the procurement should do about a risk

The second line catches people out. If the market study says prices are
ex-warehouse and the TOR requires delivery to site, that is two documents
disagreeing and another reviewer raises it — even though it is about delivery.
Your version of that question is whether the market can deliver to site at all,
and at what cost. Before raising anything, check whether your evidence is one
document contradicting another. If it is, drop it.

The last line is the finer distinction: you own the market condition, another
reviewer owns the procurement's response to it. "Only two suppliers in the
Philippines carry this module" is yours. "The procurement carries no
contingency for a single-source dependency" is not.

RECORD WHAT PASSES
Where the ABC is supported by the evidence, or the specification is genuinely
open, raise a "compliant" finding saying so and citing what you checked. The
committee needs to see what held, not only what failed. Use "info" for an
observation that is neither a deficiency nor a clean pass.

A specification that names a brand, or whose combination of parameters only one
product can satisfy, is a potential concern requiring BAC review. Never write
that a specification is restrictive, tailored or rigged — that determination
belongs to the committee.

Do not inflate severity, and be careful with "critical" in particular. A named
brand carrying "or equivalent" is ordinarily "medium" — reserve "critical" for
where the surrounding parameters make an equivalent unattainable in practice,
and say which parameters those are. Reserve "critical" generally for something
that would be hard to defend if the award were challenged.

ONE OBSERVATION, ONE FINDING
The committee reads these as a list of things to act on, so the same point
appearing twice costs them time and makes the review look padded. A narrow
specification and the single-source exposure it creates are one observation,
not two — file it once, at the severity the whole point deserves, and cover
both halves in the analysis. Before you return, read your findings back and
merge any that a reader would recognise as the same issue restated. Prefer
fewer, better-evidenced findings.

REFERENCE PROVISIONS
{provisions}
{provisions_note}
The provisions above are from the reference library and are authoritative over
your own recollection of RA 12009 and its IRR. The retrieval is not exhaustive,
so the absence of a provision here is not evidence that none exists — but when
one is shown, it is correct.

{json_contract}
{confidence_contract}
{external_contract}
{policy_contract}
EXTERNAL MARKET EVIDENCE RETRIEVED:
{evidence}
{evidence_note}
DOCUMENTS:
{documents}
"""


def _peso(value: object) -> str:
    """The ABC as it appears on the record, or a plain note when it is unset."""
    try:
        amount = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "not stated on the record"
    return f"PHP {amount:,.2f}" if amount else "not stated on the record"


def _search_queries(ctx: ReviewContext, documents: List) -> List[str]:
    """
    Ask the model what is worth searching for.

    One generic query returns nothing usable, so the items are pulled out of
    the documents first. Failing here is not fatal — no queries simply means
    the review proceeds on the documents alone.
    """
    prompt = QUERY_PROMPT.format(
        max_queries=MAX_QUERIES,
        title=ctx.meta.get("title", ""),
        excerpt=render(documents)[:QUERY_EXCERPT_CHARS],
    )
    try:
        response = get_llm().invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        payload = extract_json(str(content))
    except Exception:  # noqa: BLE001 - search is optional, the review is not
        logger.warning("Could not build market search queries", exc_info=True)
        return []

    if not isinstance(payload, list):
        return []
    return [q.strip() for q in payload if isinstance(q, str) and q.strip()]


@register(
    key=DIMENSION,
    label="Procurement & Market",
    blurb="Specification openness, ABC alignment, and existing system dependencies.",
    owner="Mark",
)
def run(ctx: ReviewContext) -> List[ReviewFinding]:
    targets = ctx.of_types(*READS)
    if not targets:
        return cannot_assess(
            DIMENSION, READS, [doc.doc_type for doc in ctx.documents]
        )

    # Retrieve provisions from the reference library. Add the procurement title
    # as one further query so category-specific provisions surface.
    title_query = ctx.meta.get("title", "").strip()
    policy_queries = list(POLICY_QUERIES)
    if title_query:
        policy_queries.append(title_query)

    retrieval = provisions_for_queries(policy_queries, k_each=3, cap=8)

    # Skip the query-building call entirely when there is no way to search —
    # it would cost a round trip to produce queries nothing can run.
    evidence = (
        search_market(_search_queries(ctx, targets))
        if available()
        else MarketEvidence(
            note=(
                "No external market evidence was retrieved for this review; "
                "the assessment rests on the attached documents."
            )
        )
    )

    prompt = PROMPT.format(
        ra_12009_directive=RA_12009_DIRECTIVE,
        title=ctx.meta.get("title", ""),
        abc=_peso(ctx.meta.get("abc")),
        mode=ctx.meta.get("mode", "") or "not stated",
        category=ctx.meta.get("category", "") or "not stated",
        record_caveat=RECORD_IS_NOT_EVIDENCE,
        provisions=retrieval.render(),
        provisions_note=(
            f"\nNote: {retrieval.note}\n" if retrieval.note else ""
        ),
        json_contract=FINDING_JSON_CONTRACT,
        # Confidence applies either way — a comparison drawn purely from the
        # documents can still rest on an assumption. Only the URL-citing block
        # is withheld when there was nothing to cite.
        confidence_contract=CONFIDENCE_CONTRACT,
        external_contract=EXTERNAL_EVIDENCE_CONTRACT if evidence.pages else "",
        # POLICY_CONTRACT is only pasted when provisions came back — same
        # rationale as EXTERNAL_EVIDENCE_CONTRACT: telling the model it may
        # cite provisions when none are available is an invitation to invent.
        policy_contract=POLICY_CONTRACT if retrieval.provisions else "",
        evidence=evidence.render(),
        evidence_note=(
            f"\nNote: {evidence.note}\nSay this in any finding that would "
            'otherwise rest on market prices, and use "medium" confidence at '
            "most for those findings.\n"
            if evidence.note
            else ""
        ),
        documents=render(targets),
    )

    findings = analyze(prompt, DIMENSION)

    # Enforcement, not trust: anything citing a page the search did not return
    # loses the citation. A fabricated source on a pre-posting review is worse
    # than no source at all.
    findings = strip_unretrieved_sources(findings, evidence.urls)

    # Ground policy_refs against what retrieval actually returned. Only
    # verifiable citations survive.
    findings = ground_policy_basis(findings, retrieval)

    return findings
