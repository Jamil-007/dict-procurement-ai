# backend/tests/test_extractor_feedback.py
import forms.extractor as ex
from forms.schemas import PPMPData
from feedback.models import FeedbackItem


class _CapLLM:
    def __init__(self): self.prompt = None
    def invoke(self, p):
        self.prompt = p
        return type("R", (), {"content": '{"fiscal_year": "2026"}'})()


def _fb():
    return [FeedbackItem(feature="forms", context_key="ppmp", thread_id="t",
                         signal_type="implicit", field_path="fiscal_year",
                         ai_value="2025", corrected_value="2026",
                         input_context="ctx")]


def test_fewshot_injected_when_enabled(monkeypatch):
    cap = _CapLLM()
    monkeypatch.setattr("feedback.service.settings.FEEDBACK_BANK_ENABLED", True)
    monkeypatch.setattr("feedback.service.retrieve_feedback", lambda *a, **k: _fb())
    monkeypatch.setattr("forms.extractor.get_llm", lambda temperature=None: cap)
    model, warning = ex.extract_fields("ppmp", "some document text")
    assert isinstance(model, PPMPData) and warning is False
    assert "correct value was" in cap.prompt  # few-shot block present
    assert "some document text" in cap.prompt  # original prompt preserved


def test_no_injection_when_disabled(monkeypatch):
    cap = _CapLLM()
    monkeypatch.setattr("feedback.service.settings.FEEDBACK_BANK_ENABLED", False)
    monkeypatch.setattr("forms.extractor.get_llm", lambda temperature=None: cap)
    ex.extract_fields("ppmp", "some document text")
    assert "correct value was" not in cap.prompt


def test_retrieval_error_does_not_break_extraction(monkeypatch):
    cap = _CapLLM()
    monkeypatch.setattr("feedback.service.settings.FEEDBACK_BANK_ENABLED", True)
    def boom(*a, **k): raise RuntimeError("bank down")
    monkeypatch.setattr("feedback.service.retrieve_feedback", boom)
    monkeypatch.setattr("forms.extractor.get_llm", lambda temperature=None: cap)
    model, warning = ex.extract_fields("ppmp", "some document text")
    assert isinstance(model, PPMPData) and warning is False
