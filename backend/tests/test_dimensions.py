"""
The four document-reading dimensions.

What is testable here is everything except the model's judgement: that each
dimension is registered, that its prompt actually composes, that it selects
the documents it claims to read, that it says something honest when it has
nothing to read, and that it stays inside its own boundary.

The boundary tests are the load-bearing ones. Five reviewers over one set of
documents will produce the same finding five times unless each is told what it
does not own, and a prompt that quietly loses that paragraph in an edit would
degrade the review in a way no unit test would otherwise notice.
"""

import json
import re

import pytest

from domain import DOC_TYPES
from review.context import ReviewContext, ReviewDocument
from review.dimensions import (
    compliance,
    document_consistency,
    document_quality,
    requirements_risk,
)
from review.registry import get_dimension
from review.schema import SEVERITY_ORDER, DimensionOutput

# Every dimension that reads documents and asks a model about them. The market
# dimension is excluded — it has its own test module, and it is the one that
# reaches the network.
MODULES = [compliance, document_consistency, document_quality, requirements_risk]

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


@pytest.fixture(autouse=True)
def no_retrieval(monkeypatch):
    """
    Keep the reference library out of these tests.

    Provision search costs an embedding round trip per query, and what it
    returns is knowledge/'s business, covered by its own tests. Compliance's
    handling of an empty retrieval is itself worth pinning down, so this
    doubles as the index-unavailable case.
    """
    from knowledge.schema import Retrieval

    monkeypatch.setattr(
        "review.dimensions.compliance.provisions_for_queries",
        lambda *a, **k: Retrieval(note="Index unavailable in tests."),
    )


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


@pytest.mark.parametrize(
    "module",
    [document_quality, requirements_risk, document_consistency],
    ids=lambda m: m.DIMENSION,
)
def test_the_document_types_it_names_are_real_types(module):
    """
    A typo here silently makes a dimension unable to find anything.

    Compliance is absent because it reads the whole record and declares no
    list. Document Consistency compares everything too, but names a preferred
    set, and a typo in that set would still mislead the model.
    """
    named = getattr(module, "READS", None) or module.PRIMARY

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
    """
    The pasted agent specs asked for severities of Critical, High, Medium, Low
    and Informational. We kept the five the schema and the UI already use, so
    a prompt must offer those and no others — a model told to return
    "Informational" produces findings the parser has to drop.

    "high" itself is not evidence of a leak: it is a legitimate *confidence*
    level. "informational" belongs to neither scale, so it is the word that
    actually distinguishes the two vocabularies.
    """
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


def test_consistency_says_so_with_only_one_document(llm):
    """One document is not a comparison, and the finding should say why."""
    output = document_consistency.run(context(doc("TOR.pdf", "Terms of Reference (TOR)")))

    assert not llm.prompts
    assert len(output.findings) == 1
    assert "only one document" in output.findings[0].title
    assert "TOR.pdf" in output.findings[0].analysis


def test_consistency_runs_with_two_documents(llm):
    output = document_consistency.run(
        context(doc("TOR.pdf", "Terms of Reference (TOR)"), doc("Scan.pdf", "Other"))
    )

    assert llm.prompts
    assert len(output.findings) == 1


def test_compliance_returns_nothing_when_there_are_no_documents(llm):
    """The router rejects this case first; the dimension must not crash on it."""
    output = compliance.run(context())

    assert not llm.prompts
    assert output.findings == []


# --- document selection ---


def test_quality_reads_only_the_types_it_declares(llm):
    document_quality.run(
        context(doc("TOR.pdf", "Terms of Reference (TOR)"), doc("Junk.pdf", "Other"))
    )

    prompt = llm.prompts[0]
    assert "TOR.pdf" in prompt
    assert "Junk.pdf" not in prompt


def test_compliance_reads_the_whole_record_including_untyped_files(llm):
    """
    Half of compliance's job is noticing what is absent, so it must see
    everything — including a file the classifier could not type.
    """
    compliance.run(
        context(doc("TOR.pdf", "Terms of Reference (TOR)"), doc("Junk.pdf", "Other"))
    )

    assert "Junk.pdf" in llm.prompts[0]


def test_compliance_states_the_record_as_a_list(llm):
    """
    The manifest is separate from the document text on purpose: a model
    inferring the boundaries of the record from concatenated text is likelier
    to hallucinate a document into it.
    """
    compliance.run(context(*FULL_RECORD))

    prompt = llm.prompts[0]
    assert "DOCUMENTS ATTACHED TO THIS PROCUREMENT" in prompt
    assert "- DCB.pdf — Detailed Cost Breakdown" in prompt


def test_consistency_compares_across_every_document(llm):
    """A fact can appear anywhere, so filtering by type would lose comparisons."""
    document_consistency.run(
        context(doc("TOR.pdf", "Terms of Reference (TOR)"), doc("Junk.pdf", "Other"))
    )

    assert "Junk.pdf" in llm.prompts[0]


# --- compliance and the reference library ---


def test_compliance_withholds_the_policy_contract_when_nothing_was_retrieved(llm):
    """
    Telling the dimension it may cite provisions when none are in front of it
    is an invitation to cite them from memory — which is the one failure this
    dimension cannot afford.
    """
    compliance.run(context(*FULL_RECORD))

    assert "policy_refs" not in llm.prompts[0]


def test_compliance_offers_the_policy_contract_when_provisions_came_back(
    llm, monkeypatch
):
    from knowledge.schema import Chunk, Provision, Retrieval

    chunk = Chunk(
        id="ra-12009-irr#0042",
        doc_id="ra-12009-irr",
        doc_title="IRR of RA 12009",
        section="Section 23.1",
        page=88,
        text="The BAC shall determine the eligibility of prospective bidders.",
    )
    monkeypatch.setattr(
        "review.dimensions.compliance.provisions_for_queries",
        lambda *a, **k: Retrieval(provisions=[Provision(chunk=chunk, score=1.0)]),
    )

    compliance.run(context(*FULL_RECORD))

    prompt = llm.prompts[0]
    assert "policy_refs" in prompt
    assert "ra-12009-irr#0042" in prompt


def test_compliance_drops_a_citation_retrieval_did_not_return(llm, monkeypatch):
    """The anti-fabrication guard, end to end through the dimension."""
    from knowledge.schema import Chunk, Provision, Retrieval

    chunk = Chunk(
        id="ra-12009-irr#0042",
        doc_id="ra-12009-irr",
        doc_title="IRR of RA 12009",
        section="Section 23.1",
        page=88,
        text="The BAC shall determine the eligibility of prospective bidders.",
    )
    monkeypatch.setattr(
        "review.dimensions.compliance.provisions_for_queries",
        lambda *a, **k: Retrieval(provisions=[Provision(chunk=chunk, score=1.0)]),
    )
    llm.reply = json.dumps(
        [
            {
                "severity": "critical",
                "title": "Eligibility check is not evidenced",
                "analysis": "...",
                "source": {"doc": "TOR.pdf", "page": 2},
                "policy_basis": "Section 99 of some act I remember",
                "policy_refs": ["invented-provision#9999"],
            }
        ]
    )

    output = compliance.run(context(*FULL_RECORD))

    finding = output.findings[0]
    assert finding.policy_sources == []
    assert finding.policy_basis == ""


def test_compliance_materialises_a_citation_it_did_retrieve(llm, monkeypatch):
    from knowledge.schema import Chunk, Provision, Retrieval

    chunk = Chunk(
        id="ra-12009-irr#0042",
        doc_id="ra-12009-irr",
        doc_title="IRR of RA 12009",
        section="Section 23.1",
        page=88,
        text="The BAC shall determine the eligibility of prospective bidders.",
    )
    monkeypatch.setattr(
        "review.dimensions.compliance.provisions_for_queries",
        lambda *a, **k: Retrieval(provisions=[Provision(chunk=chunk, score=1.0)]),
    )
    llm.reply = json.dumps(
        [
            {
                "severity": "medium",
                "title": "Eligibility check is not evidenced",
                "analysis": "...",
                "source": {"doc": "TOR.pdf", "page": 2},
                "policy_refs": ["ra-12009-irr#0042"],
            }
        ]
    )

    output = compliance.run(context(*FULL_RECORD))

    citation = output.findings[0].policy_sources[0]
    assert citation.title == "IRR of RA 12009"
    assert citation.section == "Section 23.1"
    assert citation.page == 88
    assert "eligibility of prospective bidders" in citation.quote
