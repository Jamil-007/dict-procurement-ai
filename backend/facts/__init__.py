"""Canonical document facts.

Every checker in this system reads `DocumentFacts`, never raw text. That is
what lets six different features share two engines: the rule engine and the
consistency engine both operate on the same typed record, whatever document
it came from.
"""

from facts.schema import (
    DOC_TYPE_LABELS,
    Amounts,
    DocumentFacts,
    KeyDates,
    LineItem,
    Signatory,
    SourceRef,
)

__all__ = [
    "DOC_TYPE_LABELS",
    "Amounts",
    "DocumentFacts",
    "KeyDates",
    "LineItem",
    "Signatory",
    "SourceRef",
]
