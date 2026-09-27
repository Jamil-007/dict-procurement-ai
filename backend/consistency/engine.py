"""The consistency engine.

Where the rule engine asks "is this document correct on its own terms", this
one asks "do these documents tell the same story". Three of the six assigned
features are configurations of it:

    T4  Contract-to-Payment Consistency   -> profiles/contract_to_payment.yaml
    T5  Document & Data Cross-Checker     -> profiles/delivery_acceptance.yaml
    T6  MS / TOR / DCB / BD alignment     -> profiles/planning_alignment.yaml

Two comparison shapes, chosen by the matcher:

  * **Symmetric** -- every document in scope should carry the same value. The
    engine picks one authoritative document as the reference and reports the
    dissenters against it, as one finding per field rather than one per pair.
    Six documents that agree and one that does not is a single observation,
    and a reviewer should read it once.
  * **Directional** -- the right-hand value is constrained by the left-hand
    one. Payment must not exceed the contract amount; delivery must not fall
    after the contractual due date. Reporting these symmetrically would flag
    every partial payment as a discrepancy.

**Standing assumption:** every document in one upload belongs to one
transaction. That is what makes a contract number appearing on six documents
and a different one on the seventh a finding rather than two unrelated
packets. The router enforces it by scoping a run to a session.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from consistency.matchers import MATCHERS, MatchResult, align_items
from facts.schema import DocumentFacts
from findings import Evidence, Finding
from kb.authority import resolve_authority
from rules.parsing import is_blank

PROFILES_DIR = Path(__file__).parent / "profiles"

# Matchers whose meaning depends on which side is which.
DIRECTIONAL_MATCHERS = frozenset(
    {"numeric_not_exceeding", "date_not_before", "date_not_after", "list_covers"}
)

# Handled by the engine rather than by a matcher: whether every line item on
# one document has a counterpart on the other at all.
ITEM_COVERAGE = "item_coverage"


@dataclass
class Comparison:
    """One field compared across documents."""

    field: str
    match: str
    severity: str = "medium"
    title: str = ""
    category: str = "Cross-Document Consistency"
    params: Dict = dataclass_field(default_factory=dict)
    left_field: str = ""
    right_field: str = ""
    action_hint: Optional[str] = None
    remediation: Optional[str] = None
    authority_doc: Optional[str] = None
    authority_section: Optional[str] = None
    authority_query: Optional[str] = None

    @property
    def is_item_field(self) -> bool:
        return self.field.startswith("items[].")

    @property
    def item_attr(self) -> str:
        return self.field.split("items[].", 1)[1]

    @property
    def directional(self) -> bool:
        return self.match in DIRECTIONAL_MATCHERS


@dataclass
class Profile:
    """A named cross-document check, corresponding to one assigned feature."""

    id: str
    task: str
    name: str
    description: str
    left: List[str]
    right: List[str]
    compare: List[Comparison]
    path: Optional[Path] = None

    def split(
        self, documents: Sequence[DocumentFacts]
    ) -> Tuple[List[DocumentFacts], List[DocumentFacts]]:
        usable = [d for d in documents if not d.error]
        return (
            [d for d in usable if d.doc_type in self.left],
            [d for d in usable if d.doc_type in self.right],
        )


# -- loading ---------------------------------------------------------------


def _parse_comparison(raw: Dict, defaults: Dict) -> Comparison:
    authority = raw.get("authority") or {}
    field_path = raw["field"]
    return Comparison(
        field=field_path,
        match=raw["match"],
        severity=raw.get("severity", defaults.get("severity", "medium")),
        title=raw.get("title", field_path),
        category=raw.get("category", defaults.get("category", "Cross-Document Consistency")),
        params=raw.get("params", {}) or {},
        left_field=raw.get("left_field", field_path),
        right_field=raw.get("right_field", field_path),
        action_hint=raw.get("action_hint"),
        remediation=raw.get("remediation"),
        authority_doc=authority.get("doc"),
        authority_section=authority.get("section"),
        authority_query=authority.get("query"),
    )


def load_profile(path: Path) -> Profile:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    defaults = raw.get("defaults", {}) or {}
    comparisons = [_parse_comparison(entry, defaults) for entry in raw.get("compare", [])]

    unknown = [
        c.match for c in comparisons if c.match not in MATCHERS and c.match != ITEM_COVERAGE
    ]
    if unknown:
        raise ValueError(
            f"{path.name} references unknown matcher(s): {sorted(set(unknown))}. "
            f"Available: {sorted(MATCHERS) + [ITEM_COVERAGE]}"
        )

    return Profile(
        id=raw.get("id", path.stem),
        task=raw.get("task", ""),
        name=raw.get("name", path.stem),
        description=raw.get("description", ""),
        left=raw.get("left", []),
        right=raw.get("right", []),
        compare=comparisons,
        path=path,
    )


_profiles: Optional[Dict[str, Profile]] = None
_lock = threading.Lock()


def load_all_profiles(profiles_dir: Path = PROFILES_DIR) -> Dict[str, Profile]:
    global _profiles
    if _profiles is not None:
        return _profiles
    with _lock:
        if _profiles is None:
            _profiles = {}
            for path in sorted(profiles_dir.glob("*.yaml")):
                profile = load_profile(path)
                _profiles[profile.id] = profile
    return _profiles


def reload_profiles() -> Dict[str, Profile]:
    global _profiles
    with _lock:
        _profiles = None
    return load_all_profiles()


# -- comparison ------------------------------------------------------------


def _evidence(doc: DocumentFacts, field_path: str, value: Any, page: Optional[int] = None) -> Evidence:
    return Evidence(
        document=doc.source.filename or doc.type_label,
        doc_type=doc.doc_type,
        page=page if page is not None else doc.page_of(field_path),
        field=field_path,
        value=None if value is None else str(value)[:160],
    )


def _render(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value[:4]) or "(empty)"
    return str(value)


@dataclass
class _Row:
    """One document's disagreement with the reference."""

    doc: DocumentFacts
    value: Any
    detail: str
    page: Optional[int] = None
    item_label: str = ""
    # What the reference document said for this same line. Only line-item
    # comparisons set it: their reference value varies per row, so it cannot
    # be carried once on the comparison the way a scalar's can.
    reference_value: Any = None


def _finding(
    profile: Profile,
    comparison: Comparison,
    detail: str,
    evidence: List[Evidence],
    comparison_payload: Dict,
    action_hint: Optional[str] = None,
) -> Finding:
    if comparison.remediation:
        detail = f"{detail} {comparison.remediation}"
    return Finding(
        rule_id=f"{profile.id}.{comparison.field}",
        task=profile.task,
        category=comparison.category,
        severity=comparison.severity,
        title=comparison.title,
        detail=detail,
        passed=False,
        evidence=evidence,
        authority=resolve_authority(
            doc=comparison.authority_doc,
            section=comparison.authority_section,
            query=comparison.authority_query
            or (comparison.title if comparison.authority_doc else None),
        ),
        action_hint=action_hint or comparison.action_hint,
        field=comparison.field,
        comparison=comparison_payload,
    )


def _skipped(profile: Profile, comparison: Comparison, reason: str) -> Finding:
    return Finding(
        rule_id=f"{profile.id}.{comparison.field}",
        task=profile.task,
        category=comparison.category,
        severity=comparison.severity,
        title=comparison.title,
        detail="",
        passed=False,
        skipped_reason=reason,
        field=comparison.field,
    )


def _passed(profile: Profile, comparison: Comparison, detail: str) -> Finding:
    return Finding(
        rule_id=f"{profile.id}.{comparison.field}",
        task=profile.task,
        category=comparison.category,
        severity=comparison.severity,
        title=comparison.title,
        detail=detail,
        passed=True,
        field=comparison.field,
    )


def _compare_scalar_symmetric(
    profile: Profile,
    comparison: Comparison,
    left_docs: List[DocumentFacts],
    right_docs: List[DocumentFacts],
) -> Optional[Finding]:
    matcher = MATCHERS[comparison.match]
    scope = left_docs + right_docs

    present = [
        (doc, doc.get_path(comparison.field))
        for doc in scope
        if not is_blank(doc.get_path(comparison.field))
    ]
    if len(present) < 2:
        return _skipped(
            profile,
            comparison,
            f"Only {len(present)} document(s) in this set state "
            f"'{comparison.field}'; there is nothing to compare it against.",
        )

    # The left-hand side is the authoritative one -- the contract, not the
    # voucher; the TOR, not the bidding documents.
    reference_doc, reference_value = present[0]
    for doc, value in present:
        if doc in left_docs:
            reference_doc, reference_value = doc, value
            break

    rows: List[_Row] = []
    checked = 0
    for doc, value in present:
        if doc is reference_doc:
            continue
        result = matcher(reference_value, value, comparison.params)
        if not result.comparable:
            continue
        checked += 1
        if not result.agree:
            rows.append(_Row(doc, value, result.detail))

    if not checked:
        return _skipped(
            profile, comparison, f"'{comparison.field}' could not be compared."
        )
    if not rows:
        return _passed(
            profile,
            comparison,
            f"{comparison.field} agrees across {checked + 1} document(s) "
            f"({_render(reference_value)}).",
        )

    names = "; ".join(
        f"{row.doc.type_label} states {_render(row.value)}" for row in rows
    )
    return _finding(
        profile,
        comparison,
        detail=(
            f"{comparison.field} does not agree across the packet. "
            f"{reference_doc.type_label} states {_render(reference_value)}; "
            f"{names}."
        ),
        evidence=[
            _evidence(reference_doc, comparison.field, reference_value),
            *[_evidence(row.doc, comparison.field, row.value) for row in rows],
        ],
        comparison_payload={
            "kind": "scalar",
            "reference": {
                "document": reference_doc.source.filename or reference_doc.type_label,
                "doc_type": reference_doc.doc_type,
                "value": _render(reference_value),
            },
            "rows": [
                {
                    "document": row.doc.source.filename or row.doc.type_label,
                    "doc_type": row.doc.doc_type,
                    "value": _render(row.value),
                    "detail": row.detail,
                }
                for row in rows
            ],
        },
    )


def _compare_scalar_directional(
    profile: Profile,
    comparison: Comparison,
    left_docs: List[DocumentFacts],
    right_docs: List[DocumentFacts],
) -> Optional[Finding]:
    matcher = MATCHERS[comparison.match]
    rows: List[_Row] = []
    evidence: List[Evidence] = []
    checked = 0
    reference: Optional[Tuple[DocumentFacts, Any]] = None

    for left in left_docs:
        left_value = left.get_path(comparison.left_field)
        if is_blank(left_value):
            continue
        for right in right_docs:
            right_value = right.get_path(comparison.right_field)
            if is_blank(right_value):
                continue
            result = matcher(left_value, right_value, comparison.params)
            if not result.comparable:
                continue
            checked += 1
            if reference is None:
                reference = (left, left_value)
            if not result.agree:
                rows.append(_Row(right, right_value, result.detail))
                evidence.append(
                    _evidence(right, comparison.right_field, right_value)
                )

    if not checked or reference is None:
        return _skipped(
            profile,
            comparison,
            f"'{comparison.left_field}' and '{comparison.right_field}' are not "
            "both present in this set; the comparison was not made.",
        )
    if not rows:
        return _passed(
            profile,
            comparison,
            f"{comparison.right_field} is consistent with "
            f"{comparison.left_field} across {checked} comparison(s).",
        )

    reference_doc, reference_value = reference
    detail = "; ".join(f"{row.doc.type_label}: {row.detail}" for row in rows)
    return _finding(
        profile,
        comparison,
        detail=(
            f"Measured against {reference_doc.type_label} "
            f"({comparison.left_field} = {_render(reference_value)}) - {detail}."
        ),
        evidence=[
            _evidence(reference_doc, comparison.left_field, reference_value),
            *evidence,
        ],
        comparison_payload={
            "kind": "directional",
            "reference": {
                "document": reference_doc.source.filename or reference_doc.type_label,
                "doc_type": reference_doc.doc_type,
                "field": comparison.left_field,
                "value": _render(reference_value),
            },
            "rows": [
                {
                    "document": row.doc.source.filename or row.doc.type_label,
                    "doc_type": row.doc.doc_type,
                    "field": comparison.right_field,
                    "value": _render(row.value),
                    "detail": row.detail,
                }
                for row in rows
            ],
        },
    )


def _compare_items(
    profile: Profile,
    comparison: Comparison,
    left_docs: List[DocumentFacts],
    right_docs: List[DocumentFacts],
) -> Optional[Finding]:
    """Compare one line-item attribute after aligning the schedules."""
    matcher = MATCHERS[comparison.match]
    attr = comparison.item_attr
    threshold = float(comparison.params.get("align_threshold", 0.70))

    scope = [doc for doc in left_docs + right_docs if doc.items]
    if len(scope) < 2:
        return _skipped(
            profile,
            comparison,
            f"Only {len(scope)} document(s) in this set carry line items.",
        )

    reference_doc = next((doc for doc in scope if doc in left_docs), scope[0])

    rows: List[_Row] = []
    evidence: List[Evidence] = []
    checked = 0

    for doc in scope:
        if doc is reference_doc:
            continue
        pairs, _, _ = align_items(reference_doc.items, doc.items, threshold)
        for pair in pairs:
            left_value = getattr(pair.left, attr, None)
            right_value = getattr(pair.right, attr, None)
            result = matcher(left_value, right_value, comparison.params)
            if not result.comparable:
                continue
            checked += 1
            if not result.agree:
                label = pair.left.label()[:60]
                rows.append(
                    _Row(
                        doc,
                        right_value,
                        result.detail,
                        pair.right.page,
                        label,
                        reference_value=left_value,
                    )
                )
                evidence.append(
                    Evidence(
                        document=doc.source.filename or doc.type_label,
                        doc_type=doc.doc_type,
                        page=pair.right.page,
                        field=f"items[{pair.right_index + 1}].{attr}",
                        value=_render(right_value)[:160],
                    )
                )

    if not checked:
        return _skipped(
            profile,
            comparison,
            f"No aligned line item carried '{attr}' on both sides.",
        )
    if not rows:
        return _passed(
            profile,
            comparison,
            f"items[].{attr} agrees across {len(scope)} document(s) "
            f"({checked} line comparison(s)).",
        )

    detail = "; ".join(f'"{row.item_label}" - {row.detail} ({row.doc.type_label})' for row in rows[:5])
    more = f"; and {len(rows) - 5} more" if len(rows) > 5 else ""
    return _finding(
        profile,
        comparison,
        detail=(
            f"Line items disagree with the {reference_doc.type_label}: "
            f"{detail}{more}."
        ),
        evidence=evidence[:8],
        comparison_payload={
            "kind": "line_items",
            "reference": {
                "document": reference_doc.source.filename or reference_doc.type_label,
                "doc_type": reference_doc.doc_type,
            },
            "rows": [
                {
                    "document": row.doc.source.filename or row.doc.type_label,
                    "doc_type": row.doc.doc_type,
                    "item": row.item_label,
                    "value": _render(row.value),
                    "reference_value": _render(row.reference_value),
                    "detail": row.detail,
                    "page": row.page,
                }
                for row in rows
            ],
        },
    )


def _check_item_coverage(
    profile: Profile,
    comparison: Comparison,
    left_docs: List[DocumentFacts],
    right_docs: List[DocumentFacts],
) -> Optional[Finding]:
    """Every item on the authoritative document must appear on the others.

    An item contracted for and never delivered leaves no trace in a
    field-by-field comparison, because there is no counterpart row to compare
    it against. This is the check that notices the absence.
    """
    threshold = float(comparison.params.get("align_threshold", 0.70))
    left_with_items = [doc for doc in left_docs if doc.items]
    right_with_items = [doc for doc in right_docs if doc.items]
    if not left_with_items or not right_with_items:
        return _skipped(
            profile, comparison, "Line items are not present on both sides."
        )

    reference_doc = left_with_items[0]
    gaps: List[str] = []
    evidence: List[Evidence] = []

    for doc in right_with_items:
        _, unmatched_left, unmatched_right = align_items(
            reference_doc.items, doc.items, threshold
        )
        for index in unmatched_left:
            item = reference_doc.items[index]
            gaps.append(
                f'"{item.label()[:60]}" appears on the '
                f"{reference_doc.type_label} but not on the {doc.type_label}"
            )
            evidence.append(
                Evidence(
                    document=reference_doc.source.filename or reference_doc.type_label,
                    doc_type=reference_doc.doc_type,
                    page=item.page,
                    field=f"items[{index + 1}]",
                    value=item.label()[:160],
                )
            )
        for index in unmatched_right:
            item = doc.items[index]
            gaps.append(
                f'"{item.label()[:60]}" appears on the {doc.type_label} but '
                f"has no counterpart on the {reference_doc.type_label}"
            )
            evidence.append(
                Evidence(
                    document=doc.source.filename or doc.type_label,
                    doc_type=doc.doc_type,
                    page=item.page,
                    field=f"items[{index + 1}]",
                    value=item.label()[:160],
                )
            )

    if not gaps:
        return _passed(
            profile,
            comparison,
            f"Every line item on the {reference_doc.type_label} has a "
            f"counterpart on all {len(right_with_items)} related document(s).",
        )

    shown = "; ".join(gaps[:4])
    more = f"; and {len(gaps) - 4} more" if len(gaps) > 4 else ""
    return _finding(
        profile,
        comparison,
        detail=f"Line items do not correspond - {shown}{more}.",
        evidence=evidence[:8],
        comparison_payload={
            "kind": "coverage",
            "reference": {
                "document": reference_doc.source.filename or reference_doc.type_label,
                "doc_type": reference_doc.doc_type,
            },
            "rows": [{"detail": gap} for gap in gaps],
        },
    )


# -- running ---------------------------------------------------------------


def run_profile(
    profile: Profile,
    documents: Sequence[DocumentFacts],
    include_passes: bool = False,
) -> List[Finding]:
    """Run one consistency profile over a set of documents."""
    left_docs, right_docs = profile.split(documents)

    if not left_docs or not right_docs:
        missing = "left" if not left_docs else "right"
        expected = profile.left if missing == "left" else profile.right
        return [
            Finding(
                rule_id=f"{profile.id}.not_run",
                task=profile.task,
                category="Cross-Document Consistency",
                severity="info",
                title=f"{profile.name} was not run",
                detail="",
                passed=False,
                skipped_reason=(
                    f"This cross-check needs at least one of "
                    f"{', '.join(expected)} in the upload, and none were found. "
                    "The comparison was not made -- this is not a statement "
                    "that the documents agree."
                ),
            )
        ]

    findings: List[Finding] = []
    for comparison in profile.compare:
        try:
            if comparison.match == ITEM_COVERAGE:
                result = _check_item_coverage(profile, comparison, left_docs, right_docs)
            elif comparison.is_item_field:
                result = _compare_items(profile, comparison, left_docs, right_docs)
            elif comparison.directional:
                result = _compare_scalar_directional(
                    profile, comparison, left_docs, right_docs
                )
            else:
                result = _compare_scalar_symmetric(
                    profile, comparison, left_docs, right_docs
                )
        except Exception as exc:  # noqa: BLE001 - one bad comparison must not stop the run
            result = _skipped(
                profile,
                comparison,
                f"Comparison of '{comparison.field}' could not be completed: {exc}",
            )

        if result is None:
            continue
        if include_passes or not result.passed:
            findings.append(result)

    return sorted(findings, key=lambda f: f.sort_key)


def run_profiles(
    profile_ids: Iterable[str],
    documents: Sequence[DocumentFacts],
    include_passes: bool = False,
) -> List[Finding]:
    profiles = load_all_profiles()
    findings: List[Finding] = []
    for profile_id in profile_ids:
        profile = profiles.get(profile_id)
        if profile is None:
            continue
        findings.extend(run_profile(profile, documents, include_passes))
    return sorted(findings, key=lambda f: f.sort_key)


def applicable_profiles(documents: Sequence[DocumentFacts]) -> List[str]:
    """Which profiles have documents on both sides of the comparison."""
    selected: List[str] = []
    for profile_id, profile in load_all_profiles().items():
        left_docs, right_docs = profile.split(documents)
        if left_docs and right_docs:
            selected.append(profile_id)
    return selected
