"""
Document Consistency — do the documents agree with one another on the same
procurement facts?

Owner: Dev A

A cross-document fact comparison engine, and nothing else. It extracts the
same fact from two or more documents, normalises both sides, and reports the
difference when one exists and matters.

Two things make this dimension hard, and both are in the prompt below.

The first is normalisation. "₱10,000,000.00" and "PHP 10M" are the same
number; "12 months" and "1 year" are the same duration; "At least 32GB RAM"
and "32GB RAM minimum" are the same requirement. A dimension that flags those
produces noise the committee learns to skim, which is worse than producing
nothing.

The second is time. Procurement documents legitimately change as a
procurement progresses — a PPMP written in January and a DCB approved in June
are *supposed* to be able to differ. So the finding is never "the ABC is
wrong"; it is "these two records differ, and the documents on hand do not
establish whether that was an approved revision".
"""

from typing import List

from prompts import RA_12009_DIRECTIVE
from review.context import ReviewContext, ReviewDocument, render
from review.gaps import cannot_assess
from review.llm import analyze_with_summary
from review.parsing import (
    CONFIDENCE_CONTRACT,
    FINDING_JSON_CONTRACT,
    SUMMARY_CONTRACT,
)
from review.registry import register
from review.schema import DimensionOutput

DIMENSION = "document_consistency"

# There is nothing to compare against a single document, so this is the one
# dimension with a hard floor on how much of the record it needs.
MIN_DOCUMENTS = 2

# Compared in preference order when the record is large. Everything else is
# still shown; these are named to the model as the documents whose agreement
# matters most.
PRIMARY = (
    "Project Procurement Management Plan (PPMP)",
    "Purchase Request",
    "Terms of Reference (TOR)",
    "Technical Specifications",
    "Detailed Cost Breakdown",
    "Bidding Documents",
)

PROMPT = """You are reviewing Philippine government procurement documents for
the Bids and Awards Committee of the DICT.

{ra_12009_directive}

You are a cross-document fact comparison engine. Your single question is:

  "Do the procurement documents agree with one another on the same
   procurement facts?"

PROCUREMENT RECORD
Title: {title}
Approved Budget for the Contract: {abc}
Mode: {mode}
Reference: {ref}

The ABC above is the figure on the procurement record. Where a document states
a different one, that is exactly the kind of disagreement you exist to report.

FACTS TO COMPARE
Procurement title and reference. Approved Budget for the Contract. Quantity
and unit of measure. Mode of procurement. Source of funds. End-user or
implementing unit. Delivery period. Contract duration. Technical
specifications. Product and service descriptions. Warranty. Support
requirements. Subscription duration. Payment terms. Implementation
requirements. Dates. Supplier information. Any other material procurement
fact appearing in more than one document.

HOW TO WORK
For each fact:
  1. Extract every statement of it, with the document, page and section.
  2. Normalise both sides onto the same basis before comparing.
  3. Decide whether a real difference remains.
  4. Decide whether that difference is material.
  5. Only then write a finding.

NORMALISE FIRST
These are the same value and must never be flagged:
  "₱10,000,000.00" / "PHP 10M" / "10 million pesos"
  "12 months" / "1 year"
  "100 units" / "100 pcs"
  "At least 32GB RAM" / "32GB RAM minimum" / "Minimum 32GB RAM"
Differences in capitalisation, abbreviation, formatting, number formatting or
equivalent terminology are not findings. Ever.

These are not the same value:
  "Minimum 32GB RAM" against "Minimum 16GB RAM"
  "Delivery within 60 calendar days" against "Delivery within 90 calendar days"

MATERIAL DIFFERENCES ONLY
A difference is material when it could change what is bought, what it costs,
when it arrives, or how it is evaluated. ABC, quantity, delivery period, a
technical requirement, warranty, contract duration, mode of procurement,
end-user, scope, payment terms — these are material when they genuinely
differ. A descriptive rewording is not.

DOCUMENTS CHANGE OVER TIME
A later document is allowed to supersede an earlier one. Before writing a
finding, look for evidence in the documents that a value was revised and
approved. If you find it, there is no inconsistency to report — at most an
"info" finding noting the revision.

If you find no such evidence, report the conflict without resolving it:

  "The PPMP records ₱10,000,000.00 while the Detailed Cost Breakdown records
   ₱12,000,000.00. The available records do not establish whether this
   reflects an approved revision."

Never write "the correct ABC is ₱12,000,000.00". You do not know which
document is right, and saying so would tell the committee to act on a guess.
Report both sides and explain what turns on the difference.

FINDING SHAPE
Every finding here uses "comparison", with one entry per document, and each
entry carries the value as that document states it. Set "delta" to the
difference in plain words — "₱2,000,000.00 higher", "30 calendar days longer",
"16GB less". Set "source" to the document the finding is primarily about.
Say in the analysis what could go wrong if the difference is not resolved.

STAY INSIDE THIS DIMENSION
Four other reviewers run alongside you. Do not comment on:
- whether a value is achievable, reasonable or well-priced
- whether a provision satisfies a procurement rule
- how well any single document is drafted
- two statements inside the SAME document disagreeing

That last line is the boundary people cross most. A TOR saying 30 days in
section 3 and 60 days in section 8 is an internal contradiction and another
reviewer owns it. You compare ACROSS documents, never within one.

A missing signature is another reviewer's finding, not yours — unless the
absence creates a disagreement between two documents.

RECORD WHAT AGREES
Where the documents line up on something that matters — the ABC carries
cleanly from the PPMP through to the bidding documents, say — raise a
"compliant" finding saying so and showing the matching values. A committee
reading only disagreements cannot tell what was checked.

SEVERITY, CALIBRATED FOR THIS DIMENSION
- "critical": ABC, quantity or a technical requirement differs materially, with
  nothing on the record explaining it. These change what is being bought or
  what it costs.
- "medium": delivery period, warranty, contract duration, payment terms or
  end-user differs.
- "low": a descriptive difference that is real but unlikely to change anything.
Do not inflate, and do not pad. Fewer, better-evidenced findings.

{json_contract}
{confidence_contract}
{summary_contract}
DOCUMENTS TO COMPARE:
{documents}
"""


def _peso(value: object) -> str:
    """The ABC as it appears on the record, or a plain note when it is unset."""
    try:
        amount = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "not stated on the record"
    return f"PHP {amount:,.2f}" if amount else "not stated on the record"


def _too_few(documents: List[ReviewDocument]) -> List:
    """
    The "one document is not a comparison" finding.

    Deliberately not routed through cannot_assess: the problem here is not
    that the wrong type of document was attached, it is that there is only
    one of them, and saying "attach a TOR" would be unhelpful advice.
    """
    findings = cannot_assess(DIMENSION, PRIMARY, [d.doc_type for d in documents])
    only = documents[0].name if documents else "nothing"
    findings[0].title = "Not assessed — only one document is attached"
    findings[0].analysis = (
        f"This check compares procurement facts across documents, and the "
        f"record holds only {only}. There is no second document to compare it "
        "against, so nothing in this area has been examined. The absence of "
        "findings here should not be read as the documents agreeing. Every "
        "other area has still been reviewed."
    )
    findings[0].recommendation = (
        "Attaching the other documents for this procurement and running the "
        "review again will cover this area."
    )
    return findings


@register(
    key=DIMENSION,
    label="Document Consistency",
    blurb="Agreement on quantities, budgets, dates and scope across documents.",
    owner="Dev A",
)
def run(ctx: ReviewContext) -> DimensionOutput:
    if len(ctx.documents) < MIN_DOCUMENTS:
        return DimensionOutput(findings=_too_few(ctx.documents))

    prompt = PROMPT.format(
        ra_12009_directive=RA_12009_DIRECTIVE,
        title=ctx.meta.get("title", ""),
        abc=_peso(ctx.meta.get("abc")),
        mode=ctx.meta.get("mode", "") or "not stated",
        ref=ctx.procurement_ref,
        json_contract=FINDING_JSON_CONTRACT,
        confidence_contract=CONFIDENCE_CONTRACT,
        summary_contract=SUMMARY_CONTRACT,
        # Every document, not a subset: a fact can appear anywhere, and a
        # comparison against a document that was filtered out is a comparison
        # that never happens.
        documents=render(ctx.documents),
    )
    return analyze_with_summary(prompt, DIMENSION)
