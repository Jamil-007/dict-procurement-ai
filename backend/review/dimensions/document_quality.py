"""
Document Quality — is each individual document complete, clear, properly
structured and internally coherent?

Owner: Mark
Replaces: specification_validator_agent in agents.py

One document at a time. That is the whole discipline of this dimension, and
it is what separates it from Document Consistency: a TOR saying 30 days in
section 3 and 60 days in section 8 is this dimension's finding, while a TOR
saying 30 days and bidding documents saying 60 is the other one's.

The second discipline is that the expectations are per document type. A
Detailed Cost Breakdown is not judged by whether it has objectives, and a BAC
Resolution is not judged by whether it has acceptance criteria. Running one
checklist over everything produces findings that are technically true and
practically useless.
"""


from prompts import RA_12009_DIRECTIVE
from review.context import ReviewContext, render
from review.gaps import cannot_assess
from review.llm import analyze_with_summary
from review.parsing import (
    CONFIDENCE_CONTRACT,
    FINDING_JSON_CONTRACT,
    RECORD_IS_NOT_EVIDENCE,
    SUMMARY_CONTRACT,
)
from review.registry import register
from review.schema import DimensionOutput

DIMENSION = "document_quality"

# Document types this dimension reads. Names come from domain.DOC_TYPES.
READS = (
    "Project Procurement Management Plan (PPMP)",
    "Purchase Request",
    "Market Scoping Checklist",
    "Market Study",
    "Terms of Reference (TOR)",
    "Technical Specifications",
    "Detailed Cost Breakdown",
    "Bidding Documents",
    "BAC Resolution",
)

PROMPT = """You are reviewing Philippine government procurement documents for
the Bids and Awards Committee of the DICT.

{ra_12009_directive}

Your single question, asked separately of each document below, is:

  "Is this document complete, clear, properly structured, and internally
   coherent?"

PROCUREMENT RECORD
Title: {title}
Reference: {ref}
{record_caveat}
SIX DIMENSIONS OF QUALITY
Completeness — are the expected sections, fields, tables and information there?
Clarity — can the intended reader tell what is being stated or required?
Structure — is information under the heading where a reader would look for it?
Internal coherence — do statements within the SAME document agree?
Specificity — are important requirements defined well enough to act on?
Usability — could procurement staff, bidders, evaluators or implementers
  actually use this document for its purpose?

JUDGE EACH DOCUMENT BY ITS OWN TYPE
Do not run one checklist over everything.

Terms of Reference and Technical Specifications — scope, objectives,
deliverables, functional and technical requirements, quantities, units,
acceptance criteria, implementation requirements, warranty and support,
timelines, responsibilities. Look for requirements that cannot be objectively
evaluated: "provide adequate technical support" is a quality concern because
"adequate" has no response time, coverage, channel or service level attached.
"High-performance server" is a quality concern because no measurable parameter
follows it.

Market Scoping Checklist — whether the expected fields are populated: procuring
entity, end-user or implementing unit, representative, project name, estimated
budget, period of market scoping, expected date of delivery, market scoping
activities, market scoping results with their parameters and recommendations,
project cost estimate, project design and specification, technical criteria,
delivery lead time, storage and warehousing requirements, identified risks,
prepared by, approved by. Do not invent a field the document's own template
does not have.

Detailed Cost Breakdown — line items, quantities, units, unit costs, extended
costs, whether the arithmetic on the face of the document is self-consistent,
whether a total is stated.

BAC Resolution — what was resolved, on what date, in what proceeding, by whom,
and whether the resolution's own recitals support its operative part.

PPMP and Purchase Request — the identifying and planning fields the form
provides for, and whether they are filled.

INTERNAL CONTRADICTIONS ARE YOURS
Within one document:
  Section 3 says "Delivery: 30 days", section 8 says "Delivery: 60 days".
  A quantity of 100 units in the narrative, 50 units in the cost table.
  Subscription period of 12 months in section 4, 24 months in section 7.
Each of these is a finding, and a strong one. Cite both passages using
"comparison", with both entries naming the SAME document and different pages
or sections.

Across two documents: not yours. Another reviewer owns that entirely, and a
duplicate costs the committee time.

QUALITY IS NOT COMPLIANCE
A TOR that puts payment terms inside the technical specifications section is
badly organised. Say that. Do not say it breaches a rule — you have not been
given the rule, and another reviewer has.

A TOR missing a provision that RA 12009 requires is a compliance finding, not
yours. A TOR saying "delivery should be fast" is yours, because the problem is
that "fast" cannot be measured.

A specification that only one product could satisfy is a market question and
belongs to another reviewer. Your version of that observation is only that the
specification is vague or unmeasurable — never that it is restrictive.

STAY INSIDE THIS DIMENSION
Do not comment on pricing or market conditions, on legal or procedural
compliance, on two documents contradicting each other, or on whether a missing
requirement creates a procurement risk.

The last one is the finest distinction here. "The support requirement uses
'adequate' without defining it" is a clarity problem and it is yours. "The
procurement does not define measurable support expectations such as coverage,
response time and escalation" is a substantive requirements gap and belongs to
another reviewer. When the same sentence could produce both, write yours about
the wording and leave the substance alone.

RECORD WHAT PASSES
Where a document is well structured and its requirements are measurable, raise
a "compliant" finding naming what you checked. Use "info" for an observation
that is neither a deficiency nor a pass.

SEVERITY, CALIBRATED FOR THIS DIMENSION
- "critical": a whole expected section is absent, or a requirement central to
  the procurement is ambiguous enough that bidders would price it differently
  from each other.
- "medium": a descriptive field is missing, or a secondary requirement is
  vague, or content sits under clearly the wrong heading.
- "low": a minor completeness or organisation point.
Do not raise findings for cosmetic formatting unless it genuinely changes how
the document reads. Do not inflate.

ONE OBSERVATION, ONE FINDING
Three vague phrases in the same support section are one finding about that
section, not three findings. Merge before you return.

{json_contract}
{confidence_contract}
{summary_contract}
DOCUMENTS:
{documents}
"""


@register(
    key=DIMENSION,
    label="Document Quality",
    blurb="Completeness, clarity, structure and internal coherence of each document.",
    owner="Mark",
)
def run(ctx: ReviewContext) -> DimensionOutput:
    targets = ctx.of_types(*READS)
    if not targets:
        return DimensionOutput(
            findings=cannot_assess(
                DIMENSION, READS, [doc.doc_type for doc in ctx.documents]
            )
        )

    prompt = PROMPT.format(
        ra_12009_directive=RA_12009_DIRECTIVE,
        title=ctx.meta.get("title", ""),
        ref=ctx.procurement_ref,
        record_caveat=RECORD_IS_NOT_EVIDENCE,
        json_contract=FINDING_JSON_CONTRACT,
        confidence_contract=CONFIDENCE_CONTRACT,
        summary_contract=SUMMARY_CONTRACT,
        documents=render(targets),
    )
    return analyze_with_summary(prompt, DIMENSION)
