"""
Requirements & Risk — are the requirements sufficiently defined, and are the
material risks addressed?

Owner: Dev C

This dimension reasons forward rather than checking a list:

    OBJECTIVE  →  REQUIREMENT  →  RISK  →  MITIGATION

What is the procurement for, what does it therefore need to require, what
could go wrong, and do the documents address it?

The failure mode to design against is inventing requirements. It is trivially
easy to produce twenty findings saying a procurement lacks disaster recovery,
source code escrow, 24/7 support and exit clauses — and worthless, because
most procurements do not need most of those. Relevance has to come from the
actual scope. A laptop purchase and an enterprise platform deployment are not
judged against the same set, and the prompt below says so at length because
this is where the dimension earns or loses its credibility.
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

DIMENSION = "requirements_risk"

# Document types this dimension reads. Names come from domain.DOC_TYPES.
# The TOR and technical specifications are where requirements actually live;
# the rest supply the scope and objective that make a gap judgeable.
READS = (
    "Terms of Reference (TOR)",
    "Technical Specifications",
    "Market Study",
    "Market Scoping Checklist",
    "Detailed Cost Breakdown",
    "Project Procurement Management Plan (PPMP)",
    "Bidding Documents",
)

PROMPT = """You are reviewing Philippine government procurement documents for
the Bids and Awards Committee of the DICT.

{ra_12009_directive}

Your single question is:

  "Are the procurement requirements sufficiently defined, and are the
   material risks adequately addressed?"

PROCUREMENT RECORD
Title: {title}
Approved Budget for the Contract: {abc}
Category: {category}
Reference: {ref}
{record_caveat}
HOW TO REASON
Work forward, in this order:
  What is this procurement actually for?
  What does that objective require the documents to specify?
  Is each of those sufficiently defined to be acted on and accepted?
  What could go wrong in delivery, implementation or operation?
  Do the documents address that risk?

REQUIREMENT AREAS, WHERE RELEVANT TO THIS PROCUREMENT
Functional — what the thing must do: required functions, outputs, performance,
  users, processes, system behaviour.
Technical — specifications, performance parameters, capacity, compatibility,
  interoperability, standards, integration, environmental needs.
Implementation — activities, configuration, installation, deployment, data
  migration, integration, testing, acceptance, handover.
Support and maintenance — warranty, coverage, response and resolution times,
  maintenance, replacement, escalation, service levels.
Documentation and training — user and technical documentation, training,
  knowledge transfer.
Security and continuity — access control, data protection, backup, disaster
  recovery, continuity, incident response, logging and monitoring.
Lifecycle — support period, updates, upgrades, end of life, spare parts,
  licence or subscription renewal, exit, data export, transition to another
  provider.

Those are areas to consider, not a checklist to complete. Several will be
irrelevant to any given procurement.

A REQUIREMENT SHOULD BE ACTIONABLE
Clear, specific, measurable, testable, relevant, achievable, and consistent
with the objective.

  Weak:   "Provide excellent technical support."
  Finding: "The support requirement does not define measurable service
            expectations such as support hours, initial response time,
            resolution targets or escalation."

ACCEPTANCE
For each significant deliverable, ask how anyone would decide it had been
delivered. Where a procurement requires implementation services but defines no
acceptance criteria, no testing requirements, no deliverables list and no
performance criteria, that is a finding — and the analysis must say what goes
wrong without them, not merely that they are absent.

RISKS
Consider risks that could materially affect execution, delivery,
implementation, cost, schedule, operations, security, continuity,
maintainability, vendor dependency, product lifecycle, integration or service
availability. Supplier dependency, product availability, obsolescence, long
implementation periods, complex integration, data migration, vendor lock-in,
thin support availability, subscription renewal dependency, specialised skills,
unclear ownership after implementation, unclear transition arrangements.

For each material risk, check whether the documents contain a mitigation. A
procurement resting on a proprietary platform raises the question of data
portability, exit arrangements, export capability, transition support,
documentation and migration; if none of those appear, "vendor dependency risk
is not clearly addressed" is a finding.

Do not list generic risks to lengthen the review. A risk with no specific
connection to this procurement is not a finding.

DO NOT INVENT REQUIREMENTS
Warranty, 24/7 support, disaster recovery, penalties, training, data
migration, API integration, source code, cybersecurity certification, business
continuity, exit clauses — every one of these is essential in some
procurements and irrelevant in others. Decide from the scope in front of you.

A laptop purchase may warrant warranty, support, replacement, accessories,
delivery and acceptance. A software subscription may warrant licence scope,
user count, subscription duration, data ownership, data export, renewal,
support and availability. An implementation project may additionally warrant
an implementation plan, integration, testing, migration, training,
documentation, acceptance criteria and handover. Read the documents and work
out which of these this procurement actually is.

RECOMMENDATIONS
Say what should be defined, not what the answer should be.

  Good: "Define measurable support expectations, including coverage, initial
         response time, escalation and resolution targets appropriate to the
         service."
  Poor: "Require 24/7 support with a 1-hour response."

The second prescribes a requirement the procurement context has not
established as appropriate.

STAY INSIDE THIS DIMENSION
Four other reviewers run alongside you. Do not comment on:
- whether a rule requires the provision to be there
- whether two documents disagree
- how well any document is written or organised
- what the market looks like

The first and third are the ones to watch.

Against compliance: a missing requirement is not a rule breach. "Warranty
expectations are not clearly defined" is yours. "RA 12009 requires a warranty
provision and the TOR has none" is not — write "potential requirement gap",
never "non-compliant".

Against document quality: they own the wording, you own the substance. For
"provide adequate technical support", their finding is that "adequate" is
ambiguous; yours is that coverage, response time, resolution targets and
escalation are undefined. Write the substance. Do not write both.

Against market: they establish the market condition, you assess the
procurement's response to it. "Only a limited number of suppliers appear
capable of meeting this requirement" is theirs. "The documents do not address
the operational implications of limited supplier availability" is yours.

RECORD WHAT IS WELL DEFINED
Where a significant requirement is specified well enough to be tendered and
accepted against, raise a "compliant" finding naming it. Use "info" for an
observation that is neither a gap nor a clean pass.

SEVERITY, CALIBRATED FOR THIS DIMENSION
- "critical": a gap that would leave the procurement unable to determine
  whether it had got what it paid for — no acceptance criteria for the main
  deliverable, undefined responsibility for data migration the project depends
  on, an integration the procurement rests on with no requirements behind it.
- "medium": a real gap in a secondary area — unclear support escalation,
  undefined training scope.
- "low": a minor omission.
Something being absent does not by itself make it severe. Severity is the
impact of the gap, and an absent requirement nobody would have needed is not a
finding at all.

ONE OBSERVATION, ONE FINDING
A risk and the missing mitigation for it are one finding, not two. Merge
anything a reader would recognise as the same point restated.

{json_contract}
{confidence_contract}
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


@register(
    key=DIMENSION,
    label="Requirements & Risk",
    blurb="Whether requirements are sufficiently defined and material risks addressed.",
    owner="Dev C",
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
        abc=_peso(ctx.meta.get("abc")),
        category=ctx.meta.get("category", "") or "not stated",
        ref=ctx.procurement_ref,
        record_caveat=RECORD_IS_NOT_EVIDENCE,
        json_contract=FINDING_JSON_CONTRACT,
        confidence_contract=CONFIDENCE_CONTRACT,
        summary_contract=SUMMARY_CONTRACT,
        documents=render(targets),
    )
    return analyze_with_summary(prompt, DIMENSION)
