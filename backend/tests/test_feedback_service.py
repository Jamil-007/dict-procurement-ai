# backend/tests/test_feedback_service.py
import agents.feedback.service as svc
from agents.feedback.models import FeedbackItem


def _item(**kw):
    base = dict(feature="forms", context_key="ppmp", thread_id="t1",
                signal_type="implicit", input_context="ctx")
    base.update(kw)
    return FeedbackItem(**base)


def test_record_is_inert_when_disabled(monkeypatch):
    monkeypatch.setattr(svc.settings, "FEEDBACK_BANK_ENABLED", False)
    called = {"n": 0}
    monkeypatch.setattr(svc, "get_feedback_store",
                        lambda: (_ for _ in ()).throw(AssertionError("must not touch store")))
    assert svc.record_feedback([_item()]) == 0


def test_record_stores_when_enabled(monkeypatch):
    monkeypatch.setattr(svc.settings, "FEEDBACK_BANK_ENABLED", True)
    recorded = []
    monkeypatch.setattr(svc, "get_feedback_store",
                        lambda: type("S", (), {"record": lambda self, items: recorded.extend(items)})())
    assert svc.record_feedback([_item(), _item()]) == 2
    assert len(recorded) == 2


def test_retrieve_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(svc.settings, "FEEDBACK_BANK_ENABLED", False)
    assert svc.retrieve_feedback("forms", "ppmp", "ctx") == []


def test_retrieve_swallows_errors(monkeypatch):
    monkeypatch.setattr(svc.settings, "FEEDBACK_BANK_ENABLED", True)
    monkeypatch.setattr(svc, "get_feedback_store",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert svc.retrieve_feedback("forms", "ppmp", "ctx") == []


def test_build_fewshot_empty_is_blank():
    assert svc.build_fewshot_block([]) == ""


def test_build_fewshot_contains_values():
    block = svc.build_fewshot_block([
        _item(field_path="procuring_entity", ai_value="Dept ICT",
              corrected_value="Department of ICT")
    ])
    assert "procuring_entity" in block
    assert "Dept ICT" in block and "Department of ICT" in block


def test_trust_gate_blocks_single_correction():
    items = [_item(field_path="contract_price", ai_value="100", corrected_value="200")]
    assert svc.apply_trust_gate(items, min_repeats=3) == []


def test_trust_gate_trusts_repeated_correction_deduped():
    items = [_item(field_path="contract_price", ai_value="100", corrected_value="200")
             for _ in range(3)]
    out = svc.apply_trust_gate(items, min_repeats=3)
    assert len(out) == 1  # three edits, one hint
    assert out[0].corrected_value == "200"


def test_trust_gate_upvote_adds_downvote_subtracts():
    edit = _item(field_path="f", ai_value="100", corrected_value="200")
    up = _item(signal_type="explicit", field_path="f", ai_value="200", rating="up")
    # edit (+1) + up (+1) = 2 -> trusted at threshold 2
    assert len(svc.apply_trust_gate([edit, up], min_repeats=2)) == 1
    # add a downvote (-1) -> net 1 -> blocked
    down = _item(signal_type="explicit", field_path="f", ai_value="200", rating="down")
    assert svc.apply_trust_gate([edit, up, down], min_repeats=2) == []


def test_trust_gate_never_injects_raw_ratings():
    ratings = [_item(signal_type="explicit", field_path="f", ai_value="x", rating="up")
               for _ in range(5)]
    assert svc.apply_trust_gate(ratings, min_repeats=1) == []


def test_retrieve_applies_gate_and_topk(monkeypatch):
    monkeypatch.setattr(svc.settings, "FEEDBACK_BANK_ENABLED", True)
    monkeypatch.setattr(svc.settings, "FEEDBACK_MIN_REPEATS", 2)
    monkeypatch.setattr(svc.settings, "FEEDBACK_TOP_K", 5)
    candidates = [
        _item(field_path="a", ai_value="1", corrected_value="A"),
        _item(field_path="a", ai_value="1", corrected_value="A"),  # A repeated -> trusted
        _item(field_path="b", ai_value="2", corrected_value="B"),  # B once -> blocked
    ]

    class _Store:
        def retrieve(self, *a, **k):
            return candidates

    monkeypatch.setattr(svc, "get_feedback_store", lambda: _Store())
    out = svc.retrieve_feedback("forms", "ppmp", "ctx")
    assert [i.corrected_value for i in out] == ["A"]


def test_resolve_input_context_uses_provided():
    assert svc.resolve_input_context("t1", "hello world") == "hello world"


def test_resolve_input_context_falls_back_to_source(monkeypatch):
    assert svc.resolve_input_context("t1", "", source_resolver=lambda tid: "SOURCE DOC TEXT") == "SOURCE DOC TEXT"


def test_resolve_input_context_composed_fallback_when_no_source(monkeypatch):
    out = svc.resolve_input_context("t1", None, source_resolver=lambda tid: "")
    assert out.strip() != ""  # never empty
