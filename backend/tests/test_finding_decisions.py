"""
What the BAC can and cannot do to a finding.

The decision set is down to accept and reject. Rejecting hides the finding
from the review list and drops it from the final report, so these pin the two
properties that keep that safe: a rejection cannot be recorded without a
reason, and accepting a previously rejected finding clears the rejection
rather than leaving a stale one attached to a finding that is back in the
report.
"""

import pytest
from fastapi import HTTPException

from domain import Procurement
from review.schema import Source, StoredFinding
from routers import review_api
from routers.review_api import FindingPatch, patch_finding

REF = "PROC-TEST-001"


def make_finding(**overrides) -> StoredFinding:
    return StoredFinding(
        id="A4-003",
        procurement_ref=REF,
        dimension="procurement_market",
        severity="medium",
        title="Market study does not document key market-scoping elements",
        analysis="The Market Study does not adequately document key elements.",
        source=Source(doc="Market Study.pdf"),
        **overrides,
    )


class FakeStore:
    def __init__(self, finding):
        self.finding = finding

    def get_procurement(self, ref):
        return Procurement(ref=REF, title="Supply of Rack Servers")

    def get_finding(self, ref, finding_id):
        return self.finding if finding_id == self.finding.id else None

    def save_finding(self, finding):
        self.finding = finding
        return finding


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore(make_finding())
    monkeypatch.setattr(review_api, "get_store", lambda: fake)
    return fake


def test_rejecting_records_the_reason(store):
    result = patch_finding(
        REF,
        "A4-003",
        FindingPatch(
            decision="rejected",
            rejection_reason="not_applicable",
            rejection_note="Covered by the TOR instead.",
        ),
    )

    assert result.decision == "rejected"
    assert result.rejection_reason == "not_applicable"
    assert result.rejection_note == "Covered by the TOR instead."
    assert result.decided_by and result.decided_at


def test_rejecting_without_a_reason_is_refused(store):
    with pytest.raises(HTTPException) as raised:
        patch_finding(REF, "A4-003", FindingPatch(decision="rejected"))

    assert raised.value.status_code == 400
    assert store.finding.decision is None


def test_other_needs_the_note_to_say_what_it_was(store):
    with pytest.raises(HTTPException) as raised:
        patch_finding(
            REF,
            "A4-003",
            FindingPatch(decision="rejected", rejection_reason="other", rejection_note="  "),
        )

    assert raised.value.status_code == 400


def test_an_overlong_note_is_refused(store):
    with pytest.raises(HTTPException) as raised:
        patch_finding(
            REF,
            "A4-003",
            FindingPatch(
                decision="rejected",
                rejection_reason="duplicate",
                rejection_note="x" * 501,
            ),
        )

    assert raised.value.status_code == 400


def test_accepting_clears_an_earlier_rejection(monkeypatch):
    fake = FakeStore(
        make_finding(
            decision="rejected",
            rejection_reason="duplicate",
            rejection_note="Same as A4-001.",
        )
    )
    monkeypatch.setattr(review_api, "get_store", lambda: fake)

    result = patch_finding(REF, "A4-003", FindingPatch(decision="accepted"))

    assert result.decision == "accepted"
    assert result.rejection_reason is None
    assert result.rejection_note == ""


def test_editing_the_wording_is_not_itself_a_decision(store):
    """Modify is gone: an edit marks the finding edited and nothing more."""
    result = patch_finding(
        REF, "A4-003", FindingPatch(analysis="Reworded by the committee.")
    )

    assert result.edited is True
    assert result.decision is None
    assert result.decided_by is None
