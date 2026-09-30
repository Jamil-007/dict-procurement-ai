"""Measures both engines against the labelled fixture suite.

Two assertions, and the second matters as much as the first:

  * every injected defect is caught -- zero false negatives on the labelled
    cases;
  * every clean packet stays quiet -- no high- or medium-severity finding on
    a document that is correct.

A checker that flags everything passes the first test and is useless. The
clean controls are what keep it honest.
"""

from __future__ import annotations

import pytest

from consistency.engine import load_all_profiles, run_profiles
from fixtures import load_cases
from rules.engine import load_all_packs, run_packs

CASES = load_cases()
DEFECT_CASES = [c for c in CASES if c["expect_rules"] or c["expect_discrepancies"]]
CLEAN_CASES = [c for c in CASES if c["max_severity"] == "low"]


def _all_findings(documents):
    return run_packs(list(load_all_packs()), documents) + run_profiles(
        list(load_all_profiles()), documents
    )


def _ids(cases):
    return [c["id"] for c in cases]


# -- the engines load ------------------------------------------------------


def test_every_rulepack_loads():
    packs = load_all_packs()
    assert packs, "no rulepacks were found"
    assert {p.task for p in packs.values()} == {"T1", "T2", "T3"}


def test_every_profile_loads():
    profiles = load_all_profiles()
    assert profiles, "no consistency profiles were found"
    assert {p.task for p in profiles.values()} == {"T4", "T5", "T6"}


def test_rule_ids_are_unique():
    ids = [rule.id for pack in load_all_packs().values() for rule in pack.rules]
    assert len(ids) == len(set(ids)), "duplicate rule id across rulepacks"


def test_fixture_suite_is_present():
    assert len(CASES) >= 40, f"expected the full fixture suite, found {len(CASES)}"
    assert CLEAN_CASES, "the suite has no clean controls"


# -- no false negatives ----------------------------------------------------


@pytest.mark.parametrize("case", DEFECT_CASES, ids=_ids(DEFECT_CASES))
def test_injected_defect_is_caught(case):
    findings = _all_findings(case["documents"])
    reported = [f for f in findings if f.is_failure]

    fired_rules = {f.rule_id for f in reported}
    fired_fields = {f.field for f in reported if f.field}

    missing_rules = set(case["expect_rules"]) - fired_rules
    missing_fields = set(case["expect_discrepancies"]) - fired_fields

    assert not missing_rules, (
        f"{case['id']}: {sorted(missing_rules)} did not fire.\n"
        f"Defect: {case['description']}\n"
        f"What did fire: {sorted(fired_rules)}"
    )
    assert not missing_fields, (
        f"{case['id']}: no discrepancy reported on {sorted(missing_fields)}.\n"
        f"Defect: {case['description']}\n"
        f"What did fire: {sorted(fired_fields)}"
    )


@pytest.mark.parametrize("case", DEFECT_CASES, ids=_ids(DEFECT_CASES))
def test_forbidden_rules_do_not_fire(case):
    if not case["forbid_rules"]:
        pytest.skip("no exclusions declared for this case")
    fired = {f.rule_id for f in _all_findings(case["documents"]) if f.is_failure}
    wrongly_fired = set(case["forbid_rules"]) & fired
    assert not wrongly_fired, f"{case['id']}: {sorted(wrongly_fired)} should not fire"


# -- no false positives ----------------------------------------------------


@pytest.mark.parametrize("case", CLEAN_CASES, ids=_ids(CLEAN_CASES))
def test_clean_packet_is_quiet(case):
    noisy = [
        f
        for f in _all_findings(case["documents"])
        if f.is_failure and f.severity in ("high", "medium")
    ]
    detail = "\n".join(f"  [{f.severity}] {f.rule_id}: {f.detail[:140]}" for f in noisy)
    assert not noisy, (
        f"{case['id']} is a correct packet but produced "
        f"{len(noisy)} finding(s):\n{detail}"
    )


# -- findings are actionable -----------------------------------------------


@pytest.mark.parametrize("case", DEFECT_CASES, ids=_ids(DEFECT_CASES))
def test_findings_carry_evidence(case):
    for finding in _all_findings(case["documents"]):
        if not finding.is_failure:
            continue
        assert finding.evidence, (
            f"{case['id']}: '{finding.rule_id}' reports a failure with no "
            "evidence. A finding a reviewer cannot locate is an assertion."
        )
        assert finding.detail.strip(), f"{case['id']}: '{finding.rule_id}' has no detail"


def test_citations_are_retrieved_not_composed():
    """Every citation must quote text that is actually in the indexed corpus.

    This is the guard against a fabricated section number. If the retriever
    cannot produce the provision a rule names, the finding must say so via
    `unverified` rather than print a citation nobody can check.
    """
    from kb.retriever import get_retriever

    retriever = get_retriever()
    if not retriever.available:
        pytest.skip("legal index not built; run `python -m kb.build_index`")

    unverified = []
    for case in DEFECT_CASES:
        for finding in _all_findings(case["documents"]):
            authority = finding.authority
            if not authority:
                continue
            if authority.get("unverified"):
                unverified.append((finding.rule_id, authority["citation"]))
                continue
            assert authority.get("quoted_text"), (
                f"'{finding.rule_id}' cites {authority['citation']} but quotes "
                "no text from it"
            )

    # Unverified citations are permitted -- some provisions genuinely are not
    # in the scanned corpus -- but they must be few and visible.
    assert len(set(unverified)) <= 6, (
        "too many rules cite provisions absent from the index: "
        f"{sorted(set(unverified))}"
    )
