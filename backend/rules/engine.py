"""The rule engine.

Loads YAML rulepacks and runs them against `DocumentFacts`. Three of the six
assigned features are configurations of this one engine:

    T1  Payment Document & DV Checker        -> packs/dv_payment.yaml
    T2  AI Procurement Compliance Checker    -> packs/ra12009_planning.yaml
    T3  Procurement Doc Review & Compliance  -> packs/completeness_by_doctype.yaml

Rules are data. Adding a check means adding six lines of YAML, not writing
Python -- which matters because the people who know what COA will flag are
not the people who write the code.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import yaml

from facts.schema import DocumentFacts
from findings import Finding
from kb.authority import resolve_authority
from rules.primitives import PRIMITIVES, Outcome

PACKS_DIR = Path(__file__).parent / "packs"


@dataclass
class Rule:
    """One check, as declared in a rulepack."""

    id: str
    check: str
    applies_to: List[str]
    severity: str
    title: str
    detail: str
    category: str
    params: Dict
    authority_doc: Optional[str]
    authority_section: Optional[str]
    authority_query: Optional[str]
    action_hint: Optional[str]
    remediation: Optional[str]

    def matches(self, doc_type: str) -> bool:
        return not self.applies_to or doc_type in self.applies_to or "*" in self.applies_to


@dataclass
class Rulepack:
    """A named collection of rules, corresponding to one assigned feature."""

    id: str
    task: str
    name: str
    description: str
    rules: List[Rule]
    path: Optional[Path] = None


def _parse_rule(raw: Dict, defaults: Dict) -> Rule:
    authority = raw.get("authority") or {}
    return Rule(
        id=raw["id"],
        check=raw["check"],
        applies_to=raw.get("applies_to", defaults.get("applies_to", [])),
        severity=raw.get("severity", defaults.get("severity", "medium")),
        title=raw.get("title", raw["id"]),
        detail=raw.get("detail", ""),
        category=raw.get("category", defaults.get("category", "Compliance")),
        params=raw.get("params", {}) or {},
        authority_doc=authority.get("doc"),
        authority_section=authority.get("section"),
        authority_query=authority.get("query"),
        action_hint=raw.get("action_hint"),
        remediation=raw.get("remediation"),
    )


def load_pack(path: Path) -> Rulepack:
    """Read one rulepack from disk."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    defaults = raw.get("defaults", {}) or {}
    rules = [_parse_rule(entry, defaults) for entry in raw.get("rules", [])]

    unknown = [rule.check for rule in rules if rule.check not in PRIMITIVES]
    if unknown:
        raise ValueError(
            f"{path.name} references unknown check primitive(s): {sorted(set(unknown))}. "
            f"Available: {sorted(PRIMITIVES)}"
        )

    return Rulepack(
        id=raw.get("id", path.stem),
        task=raw.get("task", ""),
        name=raw.get("name", path.stem),
        description=raw.get("description", ""),
        rules=rules,
        path=path,
    )


_packs: Optional[Dict[str, Rulepack]] = None
_lock = threading.Lock()


def load_all_packs(packs_dir: Path = PACKS_DIR) -> Dict[str, Rulepack]:
    """Load every rulepack, once per process."""
    global _packs
    if _packs is not None:
        return _packs
    with _lock:
        if _packs is None:
            _packs = {}
            for path in sorted(packs_dir.glob("*.yaml")):
                pack = load_pack(path)
                _packs[pack.id] = pack
    return _packs


def reload_packs() -> Dict[str, Rulepack]:
    """Force a re-read. Used by tests and by rulepack authors."""
    global _packs
    with _lock:
        _packs = None
    return load_all_packs()


def _resolve_authority(rule: Rule) -> Optional[Dict]:
    """Attach a retrieved legal citation to a rule.

    The rule's title stands in as the query when it declares a document but
    no section and no explicit query.
    """
    return resolve_authority(
        doc=rule.authority_doc,
        section=rule.authority_section,
        query=rule.authority_query or (rule.title if rule.authority_doc else None),
    )


def _to_finding(rule: Rule, task: str, outcome: Outcome, facts: DocumentFacts) -> Finding:
    detail = outcome.detail
    if outcome.skipped_reason:
        detail = outcome.skipped_reason
    elif not outcome.passed and rule.remediation:
        detail = f"{detail} {rule.remediation}"

    return Finding(
        rule_id=rule.id,
        task=task,
        category=rule.category,
        severity=rule.severity,
        title=rule.title,
        detail=detail,
        passed=outcome.passed,
        evidence=outcome.evidence,
        authority=_resolve_authority(rule) if not outcome.passed else None,
        action_hint=outcome.action_hint or rule.action_hint,
        skipped_reason=outcome.skipped_reason,
    )


def run_pack(
    pack: Rulepack,
    documents: Sequence[DocumentFacts],
    include_passes: bool = False,
) -> List[Finding]:
    """Run one rulepack across a set of documents.

    Args:
        pack: The rulepack to run.
        documents: Canonical facts for every uploaded document.
        include_passes: Keep passing results too. The report shows only
            failures, but the fixture tests assert on passes as well -- a
            rule that silently stops running is worse than one that fails.
    """
    findings: List[Finding] = []

    for facts in documents:
        if facts.error:
            continue
        for rule in pack.rules:
            if not rule.matches(facts.doc_type):
                continue
            primitive = PRIMITIVES[rule.check]
            try:
                outcome = primitive(facts, rule.params)
            except Exception as exc:  # noqa: BLE001 - a bad rule must not stop the run
                outcome = Outcome.skip(
                    f"Check '{rule.id}' could not be evaluated: {exc}"
                )
            finding = _to_finding(rule, pack.task, outcome, facts)
            if include_passes or not finding.passed:
                findings.append(finding)

    return sorted(findings, key=lambda f: f.sort_key)


def run_packs(
    pack_ids: Iterable[str],
    documents: Sequence[DocumentFacts],
    include_passes: bool = False,
) -> List[Finding]:
    """Run several rulepacks and merge their findings."""
    packs = load_all_packs()
    findings: List[Finding] = []
    for pack_id in pack_ids:
        pack = packs.get(pack_id)
        if pack is None:
            continue
        findings.extend(run_pack(pack, documents, include_passes))
    return sorted(findings, key=lambda f: f.sort_key)


def applicable_packs(documents: Sequence[DocumentFacts]) -> List[str]:
    """Which rulepacks have at least one rule matching the uploaded types."""
    present = {facts.doc_type for facts in documents if not facts.error}
    selected: List[str] = []
    for pack_id, pack in load_all_packs().items():
        if any(rule.matches(doc_type) for rule in pack.rules for doc_type in present):
            selected.append(pack_id)
    return selected
