# backend/tests/test_feedback_service.py
import feedback.service as svc
from feedback.models import FeedbackItem


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


def test_resolve_input_context_uses_provided():
    assert svc.resolve_input_context("t1", "hello world") == "hello world"


def test_resolve_input_context_falls_back_to_source(monkeypatch):
    assert svc.resolve_input_context("t1", "", source_resolver=lambda tid: "SOURCE DOC TEXT") == "SOURCE DOC TEXT"


def test_resolve_input_context_composed_fallback_when_no_source(monkeypatch):
    out = svc.resolve_input_context("t1", None, source_resolver=lambda tid: "")
    assert out.strip() != ""  # never empty
