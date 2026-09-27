"""
The Procurement & Market dimension.

No LLM is called. These pin the decisions the module makes before and after
the model call: which documents it reads, what the prompt is told, and what
happens to a citation the search never returned.
"""

import pytest

from review.context import ReviewContext, ReviewDocument
from review.dimensions import procurement_market as pm
from review.market_search import MarketEvidence, RetrievedPage
from review.schema import ExternalSource, ReviewFinding, Source


def doc(
    name: str, doc_type: str, text: str = "[page 1] Some content."
) -> ReviewDocument:
    return ReviewDocument(name=name, doc_type=doc_type, pages=1, text=text)


def context(*documents: ReviewDocument, **meta) -> ReviewContext:
    base = {
        "title": "Supply of Rack Servers",
        "abc": 2560000.0,
        "mode": "Competitive Bidding",
        "category": "Goods",
    }
    base.update(meta)
    return ReviewContext(
        procurement_ref="PROC-2026-009", documents=list(documents), meta=base
    )


@pytest.fixture
def captured(monkeypatch):
    """Capture the prompt and return one finding, without calling a model."""
    seen = {}

    def fake_analyze(prompt: str, dimension: str):
        seen["prompt"] = prompt
        return [
            ReviewFinding(
                dimension=dimension,
                severity="compliant",
                title="t",
                analysis="a",
                source=Source(doc="Market Study.pdf"),
            )
        ]

    monkeypatch.setattr(pm, "analyze", fake_analyze)
    return seen


# --- the ABC on the record ------------------------------------------------


def test_formats_the_abc_as_pesos():
    assert pm._peso(2560000.0) == "PHP 2,560,000.00"


@pytest.mark.parametrize("value", [None, 0, "", "not a number"])
def test_says_so_when_no_abc_is_on_the_record(value):
    assert pm._peso(value) == "not stated on the record"


# --- document selection ---------------------------------------------------


def test_reports_that_it_could_not_assess_when_nothing_it_reads_is_attached():
    result = pm.run(context(doc("Bid.pdf", "Invitation to Bid")))
    assert len(result) == 1
    assert result[0].severity == "medium"
    assert "Not assessed" in result[0].title


def test_reports_that_it_could_not_assess_an_empty_record():
    result = pm.run(context())
    assert len(result) == 1
    assert "Not assessed" in result[0].title


def test_reads_planning_documents_and_ignores_bidding_ones(monkeypatch, captured):
    monkeypatch.setattr(pm, "available", lambda: False)
    pm.run(
        context(
            doc(
                "Market Study.pdf",
                "Market Study",
                "[page 1] Canvassed three suppliers.",
            ),
            doc("Quote.pdf", "Supplier Quotation", "[page 1] PHP 512,000 per unit."),
            doc("Abstract.pdf", "Abstract of Bids", "[page 1] Should not be read."),
        )
    )
    prompt = captured["prompt"]
    assert "Canvassed three suppliers" in prompt
    assert "PHP 512,000 per unit" in prompt
    assert "Should not be read" not in prompt


def test_a_supplier_quotation_alone_is_enough_to_run(monkeypatch, captured):
    # No document set is ever required — users attach what they have.
    monkeypatch.setattr(pm, "available", lambda: False)
    result = pm.run(context(doc("Quote.pdf", "Supplier Quotation")))
    assert "Not assessed" not in result[0].title


# --- the prompt -----------------------------------------------------------


def test_the_prompt_carries_the_abc_from_the_record(monkeypatch, captured):
    monkeypatch.setattr(pm, "available", lambda: False)
    pm.run(context(doc("Market Study.pdf", "Market Study")))
    assert "PHP 2,560,000.00" in captured["prompt"]


def test_confidence_is_always_requested(monkeypatch, captured):
    # Confidence applies with or without web evidence: a comparison drawn
    # purely from the documents can still rest on an assumption.
    monkeypatch.setattr(pm, "available", lambda: False)
    pm.run(context(doc("Market Study.pdf", "Market Study")))
    assert '"confidence"' in captured["prompt"]


def test_url_citations_are_not_offered_when_nothing_was_retrieved(
    monkeypatch, captured
):
    monkeypatch.setattr(pm, "available", lambda: False)
    pm.run(context(doc("Market Study.pdf", "Market Study")))
    prompt = captured["prompt"]
    assert "external_sources" not in prompt
    assert "rests on the attached documents" in prompt


def test_url_citations_are_offered_once_pages_are_retrieved(monkeypatch, captured):
    evidence = MarketEvidence(
        pages=[
            RetrievedPage(
                url="https://ps-philgeps.gov.ph/x",
                title="Price reference",
                publisher="ps-philgeps.gov.ph",
                tier=1,
                retrieved_at="2026-09-26",
                snippet="PHP 500,000 per unit",
            )
        ],
        searched=True,
    )
    monkeypatch.setattr(pm, "available", lambda: True)
    monkeypatch.setattr(pm, "_search_queries", lambda ctx, docs: ["q"])
    monkeypatch.setattr(pm, "search_market", lambda queries: evidence)

    pm.run(context(doc("Market Study.pdf", "Market Study")))
    prompt = captured["prompt"]
    assert "external_sources" in prompt
    assert "https://ps-philgeps.gov.ph/x" in prompt
    assert "[tier 1]" in prompt


def test_no_query_building_call_is_made_without_a_key(monkeypatch, captured):
    """Building queries nothing can run would waste a model round trip."""
    monkeypatch.setattr(pm, "available", lambda: False)
    monkeypatch.setattr(
        pm,
        "_search_queries",
        lambda ctx, docs: pytest.fail("queries built with no way to search"),
    )
    pm.run(context(doc("Market Study.pdf", "Market Study")))


# --- citations ------------------------------------------------------------


def test_a_citation_the_search_never_returned_is_removed(monkeypatch):
    def fake_analyze(prompt: str, dimension: str):
        return [
            ReviewFinding(
                dimension=dimension,
                severity="critical",
                title="Priced above market",
                analysis="a",
                source=Source(doc="Market Study.pdf"),
                confidence="high",
                external_sources=[
                    ExternalSource(url="https://invented.example/x", tier=1)
                ],
            )
        ]

    monkeypatch.setattr(pm, "analyze", fake_analyze)
    monkeypatch.setattr(pm, "available", lambda: False)

    result = pm.run(context(doc("Market Study.pdf", "Market Study")))
    assert result[0].external_sources == []
    assert result[0].confidence == "low"
