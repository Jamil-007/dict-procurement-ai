"""
Document Quality — structure, clarity and completeness of the TOR and
technical specifications.

Owner: Mark
Replaces: specification_validator_agent in agents.py

This is the worked example for the other four dimensions. The shape is always
the same: build a prompt, call analyze(), return the findings. Everything else
— parallelism, timeouts, ids, error isolation — is the runner's job.
"""

from typing import List

from prompts import RA_12009_DIRECTIVE
from review.context import ReviewContext, render
from review.gaps import cannot_assess
from review.llm import analyze
from review.parsing import FINDING_JSON_CONTRACT
from review.registry import register
from review.schema import ReviewFinding

DIMENSION = "document_quality"

# Document types this dimension reads. Names come from domain.DOC_TYPES.
READS = ("Terms of Reference (TOR)", "Technical Specifications")

PROMPT = """You are reviewing Philippine government procurement documents for
the Bids and Awards Committee of the DICT.

{ra_12009_directive}

Examine the documents below for quality of drafting only. Look for:
- requirements that cannot be measured or objectively evaluated
- content placed under the wrong heading, for example post-qualification
  requirements sitting inside the technical specifications
- the same clause repeated in two places, especially where the two copies
  differ
- sections that are referenced but missing, or left blank
- terms used inconsistently within a single document

Raise a "compliant" finding where the drafting is sound and worth recording,
so the committee can see what was checked and passed. Use "info" for an
observation that is neither a deficiency nor a clean pass.

Do not comment on pricing, market conditions, legal compliance or
cross-document contradictions. Other reviewers cover those.

{json_contract}

DOCUMENTS:
{documents}
"""


@register(
    key=DIMENSION,
    label="Document Quality",
    blurb="Structure, clarity and completeness of the TOR and technical specifications.",
    owner="Mark",
)
def run(ctx: ReviewContext) -> List[ReviewFinding]:
    targets = ctx.of_types(*READS)
    if not targets:
        return cannot_assess(
            DIMENSION, READS, [doc.doc_type for doc in ctx.documents]
        )

    prompt = PROMPT.format(
        ra_12009_directive=RA_12009_DIRECTIVE,
        json_contract=FINDING_JSON_CONTRACT,
        documents=render(targets),
    )
    return analyze(prompt, DIMENSION)
