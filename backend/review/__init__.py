"""
AI Review: five independent dimensions over one set of procurement documents.

    from review import run_review, ReviewContext, ReviewDocument

    ctx = ReviewContext(procurement_ref="PROC-2026-001", documents=[...])
    result = await run_review(ctx)

Importing this package registers all dimensions.
"""

from review import dimensions  # noqa: F401  (registration side effect)
from review.context import ReviewContext, ReviewDocument
from review.registry import all_dimensions, get_dimension, register
from review.runner import run_review
from review.schema import (
    ComparedText,
    DimensionResult,
    ReviewFinding,
    ReviewResult,
    Source,
    StoredFinding,
)

__all__ = [
    "ReviewContext",
    "ReviewDocument",
    "ReviewFinding",
    "ReviewResult",
    "DimensionResult",
    "StoredFinding",
    "Source",
    "ComparedText",
    "run_review",
    "register",
    "all_dimensions",
    "get_dimension",
]
