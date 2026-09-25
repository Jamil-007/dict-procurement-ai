"""
Procurement & Market — specification openness, ABC alignment, and existing
system dependencies.

Owner: Mark
Replaces: market_scoping_agent and lcca_agent in agents.py
Legacy prompts to draw from: MARKET_SCOPING_PROMPT, LCCA_PROMPT
Note: the Tavily search in market_scoping_agent is optional — TAVILY_API_KEY
is not set locally, so `run` must work without it.

Specifications that appear tailored to one product are raised as a potential
concern requiring BAC review, never as a determination that the specification
is restrictive.

STUB — returns no findings. Fill in `run` following the pattern in
document_quality.py.
"""

from typing import List

from review.context import ReviewContext
from review.registry import register
from review.schema import ReviewFinding

DIMENSION = "procurement_market"


@register(
    key=DIMENSION,
    label="Procurement & Market",
    blurb="Specification openness, ABC alignment, and existing system dependencies.",
    owner="Mark",
)
def run(ctx: ReviewContext) -> List[ReviewFinding]:
    return []
