"""
The document-reading LLM dimensions that remain under AI Review.

Compliance and cross-document consistency moved to the deterministic Compliance
Review engine (backend/rules, backend/consistency) and are no longer registered
as LLM dimensions, so this module now covers Document Quality and
Requirements & Risk. The market dimension is excluded — it has its own test
module, and it is the one that reaches the network.

What is testable here is everything except the model's judgement: that each
dimension is registered, that its prompt actually composes, that it selects the
documents it claims to read, that it says something honest when it has nothing
to read, and that it stays inside its own boundary.
"""

import json
import re

import pytest

from domain import DOC_TYPES
from review.context import ReviewContext, ReviewDocument
from review.dimensions import document_quality, requirements_risk
from review.registry import get_dimension
from review.schema import SEVERITY_ORDER, DimensionOutput

MODULES = [document_quality, requirements_risk]

REPLY = json.dumps(
    {
        "summary": {
            "assessment": "Reviewed what was attached.",
            "documents_reviewed": ["TOR.pdf"],
            "confidence": "medium",
        },
        "findings": [
            {
                "severity": "medium",
                "title": "Delivery period is not stated",
                "analysis": "The TOR lists deliverables without a schedule.",
                "recommendation": "Ask the end-user to state a delivery period.",
                "source": {"doc": "TOR.pdf", "page": 4, "section": "Deliverables"},
            }
        ],
        "research_gaps": ["No market study was attached."],
    }
)


class FakeLLM:
    """Records the prompt it was given and returns a fixed reply."""

    def __init__(self, reply: str = REPLY):
        self.reply = reply
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return type("Response", (), {"content": self.reply})()


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr("review.llm.get_llm", lambda: fake)
    return fake


def doc(name: str, doc_type: str, text: str = "Section 1. Scope.") -> ReviewDocument:
    return ReviewDocument(name=name, doc_type=doc_type, pages=3, text=text)


def context(*documents: ReviewDocument, **meta) -> ReviewContext:
    return ReviewContext(
        procurement_ref="PROC-2026-001",
        documents=list(documents),
        meta={"title": "Supply of laptops", "abc": 5_000_000, **meta},
    )


FULL_RECORD = (
    doc("TOR.pdf", "Terms of Reference (TOR)"),
    doc("Specs.pdf", "Technical Specifications"),
    doc("PPMP.pdf", "Project Procurement Management Plan (PPMP)"),
    doc("DCB.pdf", "Detailed Cost Breakdown"),
)


# --- registration ---


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_the_dimension_is_registered_under_its_own_key(module):
    spec = get_dimension(module.DIMENSION)

    assert spec.run is module.run
    assert spec.label
    assert spec.blurb


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_the_document_types_it_names_are_real_types(module):
    """A typo here silently makes a dimension unable to find anything."""
    named = getattr(module, "READS", None) or getattr(module, "PRIMARY", None)

    assert named, "a document-reading dimension must declare what it reads"
    for doc_type in named:
        assert doc_type in DOC_TYPES, doc_type


# --- the happy path ---


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_it_returns_an_output_carrying_findings_and_a_summary(module, llm):
    output = module.run(context(*FULL_RECORD))

    assert isinstance(output, DimensionOutput)
    assert len(output.findings) == 1
    assert output.summary.assessment == "Reviewed what was attached."
    assert output.research_gaps == ["No market study was attached."]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_the_prompt_composes_and_carries_the_documents(module, llm):
    module.run(context(*FULL_RECORD))

    prompt = llm.prompts[0]
    # The contracts carry literal JSON, so a bare "{" proves nothing. An
    # unsubstituted placeholder is the specific thing worth catching.
    assert not re.search(r"\{[a-z_]+\}", prompt), "an unfilled placeholder remains"
    assert "TOR.pdf" in prompt
    assert "Supply of laptops" in prompt


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_the_prompt_asks_for_the_summary_envelope(module, llm):
    module.run(context(*FULL_RECORD))

    assert "research_gaps" in llm.prompts[0]
    assert "documents_reviewed" in llm.prompts[0]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_the_prompt_uses_our_severity_vocabulary_only(module, llm):
    """The prompt must offer the five schema severities and no others — a model
    told to return "Informational" produces findings the parser has to drop."""
    module.run(context(*FULL_RECORD))
    prompt = llm.prompts[0]

    for level in SEVERITY_ORDER:
        assert f'"{level}"' in prompt

    assert "informational" not in prompt.lower()


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.DIMENSION)
def test_the_prompt_tells_the_dimension_what_it_does_not_own(module, llm):
    module.run(context(*FULL_RECORD))

    assert "STAY INSIDE THIS DIMENSION" in llm.prompts[0]


# --- nothing to read ---


def test_document_quality_says_so_when_it_has_nothing_to_read(llm):
    output = document_quality.run(context(doc("Scan.pdf", "Other")))

    assert not llm.prompts, "the model should not be called with nothing to read"
    assert len(output.findings) == 1
    assert "Not assessed" in output.findings[0].title


def test_requirements_risk_says_so_when_it_has_nothing_to_read(llm):
    output = requirements_risk.run(context(doc("Scan.pdf", "Other")))

    assert not llm.prompts
    assert "Not assessed" in output.findings[0].title


# --- document selection ---


def test_quality_reads_only_the_types_it_declares(llm):
    document_quality.run(
        context(doc("TOR.pdf", "Terms of Reference (TOR)"), doc("Junk.pdf", "Other"))
    )

    prompt = llm.prompts[0]
    assert "TOR.pdf" in prompt
    assert "Junk.pdf" not in prompt
