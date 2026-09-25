"""
Requirements & Risk — deliverables, warranty, payment conditions and contract
obligations.

Owner: Mark
Replaces: sustainability_agent in agents.py
Legacy prompt to draw from: GREEN_SUSTAINABLE_PROMPT (lifecycle and
sustainability requirements belong here)

STUB — returns no findings. Fill in `run` following the pattern in
document_quality.py.
"""

from typing import List

from review.context import ReviewContext
from review.registry import register
from review.schema import ReviewFinding

DIMENSION = "requirements_risk"


@register(
    key=DIMENSION,
    label="Requirements & Risk",
    blurb="Deliverables, warranty, payment conditions and contract obligations.",
    owner="Mark",
)
def run(ctx: ReviewContext) -> List[ReviewFinding]:
    return []
