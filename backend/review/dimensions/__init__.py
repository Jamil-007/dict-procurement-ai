"""
Importing this package registers every dimension.

Add a module here and import it below — that is the only shared file a new
dimension touches.
"""

from review.dimensions import (  # noqa: F401
    compliance,
    document_consistency,
    document_quality,
    procurement_market,
    requirements_risk,
)
