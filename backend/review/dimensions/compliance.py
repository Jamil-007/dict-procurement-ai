"""
Compliance — RA 12009, its IRR, GPPB and COA issuances, and documentary
completeness.

Owner: Dev B
Replaces: modality_advisor_agent and domestic_preference_agent in agents.py
Legacy prompts to draw from: COMPLIANCE_MODALITY_PROMPT, TATAK_PINOY_PROMPT

STUB — returns no findings. Fill in `run` following the pattern in
document_quality.py. Nothing outside this file needs to change.
"""

from typing import List

from review.context import ReviewContext
from review.registry import register
from review.schema import ReviewFinding

DIMENSION = "compliance"


@register(
    key=DIMENSION,
    label="Compliance",
    blurb="RA 12009, its IRR, GPPB and COA issuances, and documentary completeness.",
    owner="Dev B",
)
def run(ctx: ReviewContext) -> List[ReviewFinding]:
    return []
