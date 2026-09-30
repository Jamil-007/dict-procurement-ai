"""
What the six checkers are, for the tab that lists them.

Read from the rulepacks and consistency profiles rather than written out
here, for the same reason the rules themselves are YAML: adding a seventh
checker should mean adding a seventh file, not editing Python in three
places and the frontend in a fourth.
"""

from __future__ import annotations

from typing import List, Literal, Sequence

from pydantic import BaseModel

from consistency.engine import load_all_profiles
from facts.schema import DocumentFacts
from rules.engine import load_all_packs

Engine = Literal["rule", "consistency"]


class CheckerInfo(BaseModel):
    """One checker, as the tab lists it before anything has run."""

    key: str
    task: str
    label: str
    blurb: str
    owner: str
    engine: Engine
    #: The document types this checker needs. Shown so a reviewer who uploads
    #: a planning packet understands why the payment checks did not run.
    doc_types: List[str] = []


def _rule_doc_types(pack) -> List[str]:
    types: List[str] = []
    for rule in pack.rules:
        for doc_type in rule.applies_to or []:
            if doc_type not in types:
                types.append(doc_type)
    return types


def all_checkers() -> List[CheckerInfo]:
    """Every checker, rule packs first, in task order within each engine."""
    out: List[CheckerInfo] = []

    for pack in load_all_packs().values():
        out.append(
            CheckerInfo(
                key=pack.id,
                task=pack.task,
                label=pack.name,
                blurb=" ".join((pack.description or "").split()),
                owner=pack.owner,
                engine="rule",
                doc_types=_rule_doc_types(pack),
            )
        )

    for profile in load_all_profiles().values():
        out.append(
            CheckerInfo(
                key=profile.id,
                task=profile.task,
                label=profile.name,
                blurb=" ".join((profile.description or "").split()),
                owner=profile.owner,
                engine="consistency",
                # Both sides, because a consistency profile needs documents
                # from each to have anything to compare.
                doc_types=sorted(set(profile.left) | set(profile.right)),
            )
        )

    return sorted(out, key=lambda c: (c.engine != "rule", c.task))


def selected_checkers(documents: Sequence[DocumentFacts]) -> List[str]:
    """
    Which checkers the router would fire for these documents.

    Delegates to the engines' own `applicable_*` so the tab cannot disagree
    with what the graph actually runs.
    """
    from consistency.engine import applicable_profiles
    from rules.engine import applicable_packs

    return list(applicable_packs(documents)) + list(applicable_profiles(documents))
