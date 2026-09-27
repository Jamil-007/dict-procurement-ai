"""
Market evidence retrieval.

No test here touches the network. What matters is the ranking, which decides
how much weight a citation carries in front of the BAC, and the behaviour when
there is no API key — the default on every developer machine.
"""

import pytest

from review import market_search
from review.market_search import (
    MarketEvidence,
    RetrievedPage,
    classify_tier,
    search_market,
)


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Never let a developer's real key make these tests hit the network."""
    monkeypatch.setattr(market_search.settings, "TAVILY_API_KEY", "")


# --- tier ranking ---------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "tier"),
    [
        ("https://www.philgeps.gov.ph/opportunities/1", 1),
        ("https://ps-philgeps.gov.ph/price-list", 1),
        ("https://www.dbm.gov.ph/circular", 1),
        ("https://www.dell.com/en-ph/shop/server", 2),
        ("https://www.lenovo.com/ph/en/p/x", 2),
        ("https://itsupplier.com.ph/products/server", 3),
        ("https://shop.example.ph/item", 3),
        ("https://www.lazada.com.ph/products/x", 4),
        ("https://shopee.ph/listing", 4),
        ("https://sometechblog.com/review", 5),
    ],
)
def test_ranks_a_source_by_host(url, tier):
    assert classify_tier(url) == tier


@pytest.mark.parametrize("url", ["", "not a url", "://broken"])
def test_an_unreadable_url_ranks_lowest(url):
    # Biased downward on purpose: overstating a source's authority on a
    # procurement that is later challenged is the expensive way to be wrong.
    assert classify_tier(url) == 5


def test_an_unrecognised_host_ranks_lowest():
    assert classify_tier("https://who-are-they.io/page") == 5


# --- evidence -------------------------------------------------------------


def page(url: str, tier: int, title: str = "") -> RetrievedPage:
    return RetrievedPage(
        url=url,
        title=title,
        publisher="example",
        tier=tier,
        retrieved_at="2026-09-26",
        snippet="…",
    )


def test_renders_the_strongest_source_first():
    evidence = MarketEvidence(
        pages=[
            page("https://market.example/b", 4, "Marketplace"),
            page("https://gov.example/a", 1, "Government"),
        ]
    )
    rendered = evidence.render()
    assert rendered.index("Government") < rendered.index("Marketplace")
    assert "[tier 1]" in rendered


def test_renders_nothing_as_none_rather_than_an_empty_string():
    assert MarketEvidence().render() == "(none)"


def test_urls_are_what_a_finding_may_cite():
    evidence = MarketEvidence(pages=[page("https://a.example/1", 3)])
    assert evidence.urls == {"https://a.example/1"}


# --- searching without a key ----------------------------------------------


def test_says_so_rather_than_failing_when_there_is_no_key():
    result = search_market(["rack server price philippines"])
    assert result.pages == []
    assert result.searched is False
    assert "rests on the attached documents" in result.note


def test_no_queries_means_no_search_attempt():
    result = search_market([])
    assert result.searched is False
    assert result.note


def test_never_raises_when_the_client_cannot_be_built(monkeypatch):
    monkeypatch.setattr(market_search.settings, "TAVILY_API_KEY", "set-but-broken")
    monkeypatch.setattr(market_search, "available", lambda: True, raising=True)

    import builtins

    real_import = builtins.__import__

    def explode(name, *args, **kwargs):
        if name == "tavily":
            raise ImportError("no tavily here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", explode)

    result = search_market(["anything"])
    assert result.pages == []
    assert "unavailable" in result.note
