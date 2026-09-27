"""
Saying "I could not check this" out loud.

A dimension that finds nothing to read must not return an empty list. To the
BAC an empty result looks exactly like a clean result, and under RA 12009 a
missing document is itself something the committee needs to see. Return
`cannot_assess(...)` instead.
"""

from typing import List, Sequence

from review.schema import ReviewFinding, Source


def _list(items: Sequence[str], conjunction: str) -> str:
    """'a', 'a or b', 'a, b or c'."""
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"


def cannot_assess(
    dimension: str,
    needed: Sequence[str],
    uploaded: Sequence[str],
) -> List[ReviewFinding]:
    """
    One finding saying which document types this dimension needed and what
    was uploaded instead.

    `needed` is the document types the dimension reads; `uploaded` is the
    types actually present on the record.
    """
    wanted = _list(needed, "or")
    present = _list(sorted(set(uploaded)), "and") or "no documents"

    return [
        ReviewFinding(
            dimension=dimension,
            severity="medium",
            title=f"Not assessed — no {wanted} was attached",
            analysis=(
                f"This check reads the {wanted}. The documents attached to this "
                f"procurement are: {present}. Nothing in this area has been "
                "examined, so the absence of findings here should not be read "
                "as a clean result. Every other area has still been reviewed "
                "against the documents that are present."
            ),
            recommendation=(
                f"If the {wanted} is ready, attaching it and running the review "
                "again will cover this area. If one is already here under the "
                "wrong Type, correcting it in the Documents tab has the same "
                "effect. If it does not exist yet, no action is needed now — "
                "this note simply records what was outside the review."
            ),
            source=Source(doc="", section="Documents attached to this procurement"),
        )
    ]
