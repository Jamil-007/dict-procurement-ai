"""
Document Consistency — figures, dates, quantities and terms compared across
procurement documents.

Owner: Dev B
Replaces: nothing. This capability does not exist in agents.py today.

Findings here should almost always populate `comparison` with one entry per
document so the UI can show the two passages side by side, plus `delta`
summarising the discrepancy in plain words.

STUB — returns no findings. Fill in `run` following the pattern in
document_quality.py.
"""

from typing import List

from review.context import ReviewContext
from review.registry import register
from review.schema import ReviewFinding

DIMENSION = "document_consistency"


@register(
    key=DIMENSION,
    label="Document Consistency",
    blurb="Figures, dates, quantities and terms compared across procurement documents.",
    owner="Dev B",
)
def run(ctx: ReviewContext) -> List[ReviewFinding]:
    return []
