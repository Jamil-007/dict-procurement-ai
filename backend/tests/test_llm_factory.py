"""
The thinking budget reaches the model.

gemini-2.5-flash thinks by default with a dynamic budget. On the review
prompts that was measured at 2,930 reasoning tokens and 17.7s for a call that
takes 4.5s with thinking off — so the budget is the difference between a
review that feels interactive and one that looks hung. These tests exist
because the setting is invisible: nothing fails if it silently stops being
passed, the reviews just get slow again.

Constructing a chat model does not open a connection, so no key and no network
are needed here.
"""

import pytest

from utils import llm_factory


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    """Keys the factory checks for, so construction gets as far as the model."""
    monkeypatch.setattr(llm_factory.settings, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(llm_factory.settings, "ANTHROPIC_API_KEY", "test-key")


def test_thinking_budget_is_passed_to_gemini(monkeypatch):
    monkeypatch.setattr(llm_factory.settings, "LLM_PROVIDER", "google_genai")
    monkeypatch.setattr(llm_factory.settings, "GEMINI_THINKING_BUDGET", 1024)

    llm = llm_factory.get_llm()

    assert llm.thinking_budget == 1024


def test_thinking_can_be_disabled(monkeypatch):
    """0 is a meaningful value, not "unset" — it turns thinking off entirely."""
    monkeypatch.setattr(llm_factory.settings, "LLM_PROVIDER", "google_genai")
    monkeypatch.setattr(llm_factory.settings, "GEMINI_THINKING_BUDGET", 0)

    llm = llm_factory.get_llm()

    assert llm.thinking_budget == 0


def test_negative_budget_leaves_the_model_default(monkeypatch):
    """-1 hands the decision back to the model's own dynamic budget."""
    monkeypatch.setattr(llm_factory.settings, "LLM_PROVIDER", "google_genai")
    monkeypatch.setattr(llm_factory.settings, "GEMINI_THINKING_BUDGET", -1)

    llm = llm_factory.get_llm()

    assert llm.thinking_budget is None


def test_anthropic_is_unaffected(monkeypatch):
    """The budget is a Gemini parameter; passing it to Anthropic would raise."""
    monkeypatch.setattr(llm_factory.settings, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(llm_factory.settings, "GEMINI_THINKING_BUDGET", 1024)

    llm = llm_factory.get_llm()

    assert not hasattr(llm, "thinking_budget")


def test_info_reports_the_budget(monkeypatch):
    """get_llm_info feeds /health, which is where this gets checked in prod."""
    monkeypatch.setattr(llm_factory.settings, "LLM_PROVIDER", "google_genai")
    monkeypatch.setattr(llm_factory.settings, "GEMINI_THINKING_BUDGET", 1024)

    assert llm_factory.get_llm_info()["thinking_budget"] == 1024


def test_info_omits_the_budget_for_other_providers(monkeypatch):
    monkeypatch.setattr(llm_factory.settings, "LLM_PROVIDER", "anthropic")

    assert "thinking_budget" not in llm_factory.get_llm_info()
