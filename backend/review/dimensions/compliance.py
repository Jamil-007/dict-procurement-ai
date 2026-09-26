"""
Compliance — RA 12009, its IRR, GPPB and COA issuances, and documentary
completeness.

Owner: Dev B
Replaces: modality_advisor_agent and domestic_preference_agent in agents.py

The question this dimension owns is narrow and worth stating exactly: "does
the procurement documentation appear aligned with applicable procurement
requirements?" Not whether the price is sensible (Procurement & Market), not
whether the documents agree with each other (Document Consistency), not
whether any one of them is well drafted (Document Quality).

This is the only dimension whose subject matter *is* the rules, so it is the
one that leans hardest on the reference library. Everything it says about a
requirement has to trace to a retrieved provision — `ground_policy_basis`
below is what enforces that, by discarding any citation retrieval did not
actually return. A compliance finding resting on the model's recollection of
RA 12009 is the single most dangerous thing this tool could produce, because
it is the kind of claim a reader is least equipped to check.
"""


from prompts import RA_12009_DIRECTIVE
from review.context import ReviewContext, render
from review.llm import analyze_with_summary
from review.parsing import (
    CONFIDENCE_CONTRACT,
    FINDING_JSON_CONTRACT,
    SUMMARY_CONTRACT,
)
from review.policy import POLICY_CONTRACT, ground_policy_basis, provisions_for_queries
from review.registry import register
from review.schema import DimensionOutput

DIMENSION = "compliance"

# Compliance reads the whole record rather than a subset. Its own subject
# matter includes which documents are absent, so narrowing the input would
# blind it to half its job.
READS = ("every document attached to the procurement",)

# Fixed queries covering this dimension's subject matter. No extra LLM call to
# build them — the concerns are stable. Phrased as the provisions would be
# worded, not as questions.
POLICY_QUERIES = (
    (
        "procurement planning annual procurement plan project procurement "
        "management plan requirements"
    ),
    "certificate of availability of funds appropriation before procurement",
    "modes of procurement competitive bidding alternative methods conditions",
    "approved budget for the contract determination and approval",
    "bids and awards committee composition functions resolution quorum",
    "posting and publication requirements PhilGEPS notices",
    "terms of reference technical specifications mandatory contents",
    "domestic preference Filipino preference Tatak Pinoy requirement",
    "documentary requirements eligibility submission bidding documents",
    "approvals signatures certification required on procurement documents",
)

PROMPT = """You are reviewing Philippine government procurement documents for
the Bids and Awards Committee of the DICT.

{ra_12009_directive}

This review runs immediately before the procurement is posted to PhilGEPS.
Your single question is:

  "Does the procurement documentation appear aligned with applicable
   procurement requirements?"

PROCUREMENT RECORD
Title: {title}
Approved Budget for the Contract: {abc}
Mode: {mode}
Category: {category}
Reference: {ref}

DOCUMENTS ATTACHED TO THIS PROCUREMENT
{manifest}

That list is the whole record. Nothing else was submitted.

WHAT TO LOOK FOR
1. Deviations from an applicable procurement requirement.
2. Mandatory provisions that are absent from a document that should carry them.
3. Required supporting documents that are absent from the record.
4. Steps of the applicable procedure with no evidence on the record.
5. Prescribed forms that are incomplete — missing required fields, signatures,
   dates, certifications, declarations, references or attachments.
6. Provisions that may conflict with an applicable rule.
7. Approvals that the record does not show were obtained.

For a prescribed form, do not raise a stylistic difference from the template.
Raise it only where the difference touches a substantive requirement.

HOW TO BUILD A FINDING
Work in this order, and do not skip a step:
  a. Name the requirement that applies.
  b. Name where that requirement comes from — cite a retrieved provision.
  c. Say what the document states, or what the record does not show.
  d. Say why the difference matters to this procurement.
A finding missing any of those four is not ready and should not be returned.

ABSENCE IS NOT PROOF OF OMISSION
This is the mistake to avoid above all others. You are looking at what was
uploaded, not at the procuring entity's files. When something is not here:

  Write: "The Market Study was not included in the submitted procurement
          records."
  Never: "The procuring entity failed to conduct a Market Study."

The second sentence is a finding of fact about conduct, and you have no
evidence for it. Only write something in that register when the record itself
shows it — for example, where a document states that a step was skipped.

Where a document you would have needed is simply absent, put it in
"research_gaps" rather than inventing a finding, unless its absence is itself
a requirement issue — in which case the finding is about the requirement, and
must cite the provision that requires it.

LANGUAGE
Write "potential compliance concern", "the document does not appear to
contain", "the submitted record does not provide evidence of", "this provision
may require review against", "further verification is recommended".

Do not write "this is illegal", "this is non-compliant", "this violates the
law" or "the procurement is invalid" — unless a retrieved provision clearly
establishes the requirement AND the document clearly shows the deviation. Even
then, prefer the careful phrasing. The determination is the committee's.

MARKET SCOPING
Where a Market Scoping Checklist is on the record, your question about it is
whether the required process was documented — cost estimate, design and
specification, technical criteria, delivery lead time, storage and warehousing,
identified market risks. Whether those answers are commercially sensible is
another reviewer's question, not yours.

STAY INSIDE THIS DIMENSION
Four other reviewers run alongside you. Do not comment on:
- whether the budget or specification is commercially reasonable, or what the
  market looks like
- two documents disagreeing with each other on a fact
- drafting quality, ambiguity, structure or internal coherence within one
  document
- whether a requirement is sufficiently defined, or whether a risk is mitigated

The fourth line is the closest boundary and the easiest to cross. "The TOR does
not define a warranty period" is a requirements gap and belongs to another
reviewer. It becomes yours only when a retrieved provision requires the
provision to be there — and then the finding is about the provision, and cites
it.

RECORD WHAT PASSES
Where a requirement is clearly met on the record, raise a "compliant" finding
saying so and citing both the provision and the document that satisfies it.
The committee needs to see which ground was covered, not only where it gave
way. Use "info" for an observation that is neither a deficiency nor a pass.

SEVERITY, CALIBRATED FOR THIS DIMENSION
- "critical": a requirement that goes to the validity of the process, with the
  deviation clear on the record — an absent Certificate of Availability of
  Funds, a mode of procurement used outside its stated conditions, an award
  step with no BAC resolution behind it.
- "medium": a real requirement issue that does not by itself stop the
  procurement — an incomplete prescribed form, a missing declaration.
- "low": a minor documentary completeness point.
Do not inflate. A requirement you cannot tie to a retrieved provision is at
most "low", and is usually better written as an "info" finding or a research
gap.

ONE OBSERVATION, ONE FINDING
The same requirement raised twice costs the committee time and makes the
review look padded. Before returning, read your findings back and merge any a
reader would recognise as the same point restated.

REFERENCE PROVISIONS
{provisions}
{provisions_note}
The provisions above are from the reference library and are authoritative over
your own recollection of RA 12009 and its IRR. The retrieval is not exhaustive,
so the absence of a provision here is not evidence that none exists — but when
one is shown, it is correct.

{json_contract}
{confidence_contract}
{policy_contract}
{summary_contract}
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


def manifest(ctx: ReviewContext) -> str:
    """
    Every attached document by name and type, one per line.

    Compliance needs this separately from the document text. Half its job is
    noticing what is not on the record, and a model reading only concatenated
    text has to infer the boundaries of the record from the text itself — it
    is much likelier to hallucinate a document into existence, or to miss that
    one is absent, than when the record is stated as a list.
    """
    if not ctx.documents:
        return "(none)"
    return "\n".join(f"- {d.name} — {d.doc_type}" for d in ctx.documents)


@register(
    key=DIMENSION,
    label="Compliance",
    blurb="RA 12009, its IRR, GPPB and COA issuances, and documentary completeness.",
    owner="Dev B",
)
def run(ctx: ReviewContext) -> DimensionOutput:
    if not ctx.documents:
        return DimensionOutput()

    # Add the procurement title as one further query so category-specific
    # provisions surface alongside the standing ones.
    queries = list(POLICY_QUERIES)
    title = str(ctx.meta.get("title", "")).strip()
    if title:
        queries.append(title)

    # A wider cap than the other dimensions use: this one reasons about the
    # rules themselves, so it needs more of them in front of it.
    retrieval = provisions_for_queries(queries, k_each=3, cap=14)

    prompt = PROMPT.format(
        ra_12009_directive=RA_12009_DIRECTIVE,
        title=title,
        abc=_peso(ctx.meta.get("abc")),
        mode=ctx.meta.get("mode", "") or "not stated",
        category=ctx.meta.get("category", "") or "not stated",
        ref=ctx.procurement_ref,
        manifest=manifest(ctx),
        provisions=retrieval.render(),
        provisions_note=f"\nNote: {retrieval.note}\n" if retrieval.note else "",
        json_contract=FINDING_JSON_CONTRACT,
        confidence_contract=CONFIDENCE_CONTRACT,
        # Only pasted when provisions came back. Telling a dimension it may
        # cite provisions when none are available invites it to invent them,
        # and this is the dimension where that would do the most damage.
        policy_contract=POLICY_CONTRACT if retrieval.provisions else "",
        summary_contract=SUMMARY_CONTRACT,
        documents=render(ctx.documents),
    )

    output = analyze_with_summary(prompt, DIMENSION)

    # Ground policy_refs against what retrieval actually returned. Only
    # verifiable citations survive.
    output.findings = ground_policy_basis(output.findings, retrieval)

    return output
