"""
One LLM call, one list of findings.

Dimension modules should not need to know about response objects, markdown
fences or JSON repair.
"""

import logging
from typing import List

from review.parsing import findings_from_response, output_from_response
from review.schema import DimensionOutput, ReviewFinding
from utils.llm_factory import get_llm

logger = logging.getLogger(__name__)


def _reply(prompt: str) -> str:
    """Send a prompt and flatten the reply to text."""
    llm = get_llm()
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)

    if isinstance(content, list):
        # Some providers return content as a list of parts.
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )

    return content


def analyze(prompt: str, dimension: str) -> List[ReviewFinding]:
    """
    Send a prompt and parse the reply into findings.

    Raises on an unusable response so the runner can mark the dimension
    failed — returning [] here would look like a clean review that found
    nothing, which is worse than an honest failure.
    """
    findings = findings_from_response(_reply(prompt), dimension)
    logger.info("Dimension '%s' produced %d findings", dimension, len(findings))
    return findings


def analyze_with_summary(prompt: str, dimension: str) -> DimensionOutput:
    """
    As analyze(), for a prompt that also carries SUMMARY_CONTRACT.

    Returns the findings together with what the dimension says it reviewed.
    Raises on the same terms as analyze().
    """
    output = output_from_response(_reply(prompt), dimension)
    logger.info(
        "Dimension '%s' produced %d findings and %d research gap(s)",
        dimension,
        len(output.findings),
        len(output.research_gaps),
    )
    return output
