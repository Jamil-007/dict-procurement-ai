"""The router, the compiler and the archive.

The engines are covered by `test_checkers.py`. What is tested here is the
wiring around them: that the right checkers get selected for a given packet,
that the verdict reports what actually ran, and that a session survives being
written to disk and read back.

Nothing here calls a model. Ingestion, classification and extraction are the
only parts of the pipeline that need one, and they are exercised separately;
everything downstream reads `DocumentFacts` and is deterministic.
"""

from __future__ import annotations

import json

import pytest

from fixtures import load_case, load_cases
from pipeline import (
    ADVISORY_NODES,
    CHECKER_NODES,
    compile_node,
    consistency_checks_node,
    plan_route,
    route,
    route_node,
    rule_checks_node,
)


def _run(case_id: str):
    """Everything from routing to the compiled verdict, without a graph."""
    case = load_case(case_id)
    state = {
        "documents": [d.model_dump(mode="json") for d in case["documents"]],
        "findings": [],
        "analysis_results": {},
    }
    state.update(route_node(state))
    if "rule_checks" in state["routed_checkers"]:
        state["findings"] += rule_checks_node(state).get("findings", [])
    if "consistency_checks" in state["routed_checkers"]:
        state["findings"] += consistency_checks_node(state).get("findings", [])
    return state, json.loads(compile_node(state)["compiled_report"])


# -- the graph is wired the way the router thinks it is -------------------


def test_graph_has_a_node_for_every_routable_checker():
    from graph import graph as compiled

    nodes = set(compiled.get_graph().nodes)
    missing = set(CHECKER_NODES) - nodes
    assert not missing, f"router can return {sorted(missing)} but the graph has no such node"


def test_route_always_reaches_the_compiler():
    """An empty route must still produce a report, not a silent dead end."""
    assert route({"routed_checkers": []}) == ["report_compiler"]
    assert route({}) == ["report_compiler"]


# -- routing ---------------------------------------------------------------


def test_payment_packet_skips_the_planning_advisory():
    """The six advisory agents know nothing about a disbursement voucher.

    Running them anyway would cost six model calls and produce commentary on
    documents they were never written for.
    """
    state, _ = _run("clean_payment_packet")
    fired = set(state["routed_checkers"])
    assert "rule_checks" in fired
    assert "consistency_checks" in fired
    assert not fired & set(ADVISORY_NODES)


def test_planning_packet_fires_the_advisory_agents():
    """The original demo must not regress: planning docs still get all six."""
    state, _ = _run("clean_planning_packet")
    assert set(ADVISORY_NODES) <= set(state["routed_checkers"])


def test_nothing_readable_routes_nowhere():
    assert plan_route([]) == []


# -- the verdict reports what actually happened ---------------------------


CLEAN_IDS = [c["id"] for c in load_cases() if c["max_severity"] == "low"]
DEFECT_IDS = [
    c["id"] for c in load_cases() if c["expect_rules"] or c["expect_discrepancies"]
]


@pytest.mark.parametrize("case_id", CLEAN_IDS)
def test_clean_packet_passes_and_says_how_much_was_checked(case_id):
    _, verdict = _run(case_id)
    assert verdict["status"] == "PASS"
    # A PASS over zero checks is not a PASS. The count is what separates
    # "we looked and it was fine" from "we did not look".
    assert verdict["summary"]["passed"] > 0, "passed with no checks actually run"
    assert verdict["summary"]["high"] == 0


@pytest.mark.parametrize("case_id", DEFECT_IDS)
def test_defect_packet_surfaces_the_finding_in_the_verdict(case_id):
    """A finding the engine produced but the compiler dropped is invisible."""
    state, verdict = _run(case_id)
    engine_failures = [
        f
        for f in state["findings"]
        if not f.get("passed") and not f.get("skipped_reason")
    ]
    if not engine_failures:
        pytest.skip("this case is covered by the engine tests, not the compiler")

    reported = sum(len(g["items"]) for g in verdict["findings"])
    assert reported >= len(engine_failures), (
        f"{len(engine_failures)} failure(s) from the engines but only "
        f"{reported} reached the report"
    )


def test_high_severity_fails_the_verdict():
    high_case = next(
        (
            cid
            for cid in DEFECT_IDS
            if any(
                f.get("severity") == "high"
                and not f.get("passed")
                and not f.get("skipped_reason")
                for f in _run(cid)[0]["findings"]
            )
        ),
        None,
    )
    assert high_case, "the fixture suite has no high-severity defect"
    _, verdict = _run(high_case)
    assert verdict["status"] == "FAIL"


def test_verdict_lists_the_documents_it_reviewed():
    _, verdict = _run("clean_full_packet")
    assert verdict["documents"], "the verdict does not say what it reviewed"
    assert all(d["doc_type"] for d in verdict["documents"])


def test_unverified_checks_are_not_reported_as_compliant():
    """`skipped_reason` must survive all the way to the report.

    If a check could not run, saying nothing is the same as saying it passed,
    and that is the one thing a compliance tool must never do.
    """
    for case_id in CLEAN_IDS:
        state, verdict = _run(case_id)
        skipped = [f for f in state["findings"] if f.get("skipped_reason")]
        if not skipped:
            continue
        categories = {g["category"] for g in verdict["findings"]}
        assert "Not Verified" in categories
        assert "not verified" in verdict["title"]
        return


# -- the archive -----------------------------------------------------------


def test_session_round_trips_through_the_archive(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    import persistence.db as db

    monkeypatch.setattr(db, "_connection", None)

    state, verdict = _run("serial_numbers_differ_dr_vs_par")
    state["compiled_report"] = json.dumps(verdict)
    thread_id = "11111111-2222-3333-4444-555555555555"

    db.save_session(thread_id, state)

    listed = db.list_sessions()
    assert [s["thread_id"] for s in listed] == [thread_id]
    assert listed[0]["status"] == verdict["status"]
    assert listed[0]["file_count"] == len(state["documents"])

    # Every check is stored, but reading a session back returns only the ones
    # that did not pass -- reopening a review should surface what needs
    # attention, not 169 rows of "fine".
    unresolved = [f for f in state["findings"] if not f.get("passed")]
    assert unresolved, "the fixture should produce at least one open finding"

    loaded = db.get_session(thread_id)
    assert loaded["report"]["title"] == verdict["title"]
    assert len(loaded["documents"]) == len(state["documents"])
    assert len(loaded["findings"]) == len(unresolved)
    assert not any(f.get("passed") for f in loaded["findings"])

    # Re-saving the same thread replaces its results rather than duplicating.
    db.save_session(thread_id, state)
    assert len(db.get_session(thread_id)["findings"]) == len(unresolved)

    assert db.delete_session(thread_id) is True
    assert db.get_session(thread_id) is None
    assert db.list_sessions() == []
