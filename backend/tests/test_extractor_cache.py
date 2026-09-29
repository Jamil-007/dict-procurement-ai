"""
Building a form's live preview calls /forms/generate, which reconstructs the
Group A model. Because the frontend's overrides omit composite fields, the
backend's "skip extraction when overrides cover every field" guard never fires,
so generation re-runs extract_fields — the same LLM extraction /forms/extract
already ran moments earlier, and again on every debounced field edit. Each of
those was a full LLM round trip, which is why the preview took so long to build.

extract_fields now caches a successful extraction per (form_key, source text),
so the second and later calls for the same document set return instantly instead
of re-hitting the model. Failures are not cached (a transient error must not
stick for the whole session).
"""

import agents.doc_generation.extractor as ex
from agents.doc_generation.schemas import PPMPData


class _CountingLLM:
    def __init__(self, content):
        self.calls = 0
        self._content = content

    def invoke(self, prompt):
        self.calls += 1
        return type("R", (), {"content": self._content})()


def test_repeat_extraction_hits_cache_not_llm(monkeypatch):
    llm = _CountingLLM('{"fiscal_year": "2026"}')
    monkeypatch.setattr(ex, "get_llm", lambda temperature=None: llm)

    text = "A procurement document with enough content to extract from."
    m1, w1 = ex.extract_fields("ppmp", text)
    m2, w2 = ex.extract_fields("ppmp", text)

    assert isinstance(m1, PPMPData) and m1.fiscal_year == "2026"
    assert isinstance(m2, PPMPData) and m2.fiscal_year == "2026"
    assert w1 is False and w2 is False
    assert llm.calls == 1, f"expected the second extraction to be cached, LLM called {llm.calls}x"


def test_different_text_is_extracted_separately(monkeypatch):
    llm = _CountingLLM('{"fiscal_year": "2026"}')
    monkeypatch.setattr(ex, "get_llm", lambda temperature=None: llm)

    ex.extract_fields("ppmp", "document one")
    ex.extract_fields("ppmp", "a different document")

    assert llm.calls == 2  # distinct sources → distinct extractions


def test_failed_extraction_is_not_cached(monkeypatch):
    llm = _CountingLLM("not json at all")
    monkeypatch.setattr(ex, "get_llm", lambda temperature=None: llm)

    _, w1 = ex.extract_fields("ppmp", "same text")
    assert w1 is True  # extraction failed (unparseable)

    # A later call with a working model must retry, not serve the failed result.
    good = _CountingLLM('{"fiscal_year": "2026"}')
    monkeypatch.setattr(ex, "get_llm", lambda temperature=None: good)
    m2, w2 = ex.extract_fields("ppmp", "same text")
    assert w2 is False and m2.fiscal_year == "2026"
    assert good.calls == 1
