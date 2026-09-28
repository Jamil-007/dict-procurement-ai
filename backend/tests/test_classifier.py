import pytest

from agents.doc_generation.classifier import classify_documents, recommendations, DOC_FORM_MAP

ALLOWED = {"Terms of Reference", "Market Study", "Cost Breakdown", "Contract", "Other"}


# ---------------------------------------------------------------------------
# Fixtures / snippets
# ---------------------------------------------------------------------------

@pytest.fixture
def force_keyword_fallback(monkeypatch):
    """Make the LLM path raise so classify_documents uses the keyword fallback."""

    def _raise(*args, **kwargs):
        raise RuntimeError("LLM disabled for keyword-fallback test")

    monkeypatch.setattr("agents.doc_generation.classifier.get_llm", _raise)


TOR_SNIPPET = (
    "TERMS OF REFERENCE\n\n"
    "1. Background and Objectives\n"
    "This TOR defines the scope of works for the project. "
    "The contractor shall provide all labor, materials, and equipment "
    "necessary to complete the deliverables within the agreed timeline."
)

MARKET_SNIPPET = (
    "MARKET STUDY REPORT\n\n"
    "This market research analyzes potential suppliers and prevailing "
    "prices for the required goods. Market scoping was conducted across "
    "several accredited vendors in the region."
)

COST_SNIPPET = (
    "DETAILED COST ESTIMATE (DCE)\n\n"
    "Cost Breakdown of items:\n"
    "Each line item shows the unit cost, quantity, and total amount for "
    "the goods and services being procured."
)

CONTRACT_SNIPPET = (
    "CONTRACT AGREEMENT\n\n"
    "This Contract is entered into by and between the Procuring Entity "
    '(hereinafter referred to as the "Client") and the Supplier. '
    "The parties agree to the following terms and conditions of engagement."
)

TOR_MENTIONS_CONTRACT = (
    "TERMS OF REFERENCE\n\n"
    "The winning bidder will later sign a contract with the agency. "
    "A service agreement shall govern the engagement. "
    "This TOR sets out the scope of works and required deliverables."
)

CONTRACTOR_NO_TOR = (
    "PROJECT NARRATIVE\n\n"
    "The main contractor and each subcontractor must monitor every factor "
    "affecting the sector. A supervisor will inspect the ventilator and "
    "generator installations regularly."
)


# ---------------------------------------------------------------------------
# classify_documents — keyword fallback
# ---------------------------------------------------------------------------

def test_tor_snippet_classifies_as_tor_only(force_keyword_fallback):
    result = classify_documents(TOR_SNIPPET)
    assert result == ["Terms of Reference"]
    assert "Contract" not in result


def test_market_study_snippet(force_keyword_fallback):
    assert classify_documents(MARKET_SNIPPET) == ["Market Study"]


def test_cost_breakdown_snippet(force_keyword_fallback):
    assert classify_documents(COST_SNIPPET) == ["Cost Breakdown"]


def test_contract_snippet(force_keyword_fallback):
    result = classify_documents(CONTRACT_SNIPPET)
    assert result == ["Contract"]
    assert "Terms of Reference" not in result


def test_tor_mentioning_contract_is_not_contract(force_keyword_fallback):
    # Regression for bug #2: "contract" + "agreement" in passing must NOT
    # classify a TOR as a Contract.
    result = classify_documents(TOR_MENTIONS_CONTRACT)
    assert result == ["Terms of Reference"]
    assert "Contract" not in result


def test_contractor_factor_not_tor(force_keyword_fallback):
    # Regression for bug #1: bare "tor" substring inside "contractor",
    # "factor", "sector", "monitor", "ventilator", "generator" must not
    # trigger a Terms of Reference detection.
    result = classify_documents(CONTRACTOR_NO_TOR)
    assert "Terms of Reference" not in result
    assert result == ["Other"]


def test_empty_text_is_other(force_keyword_fallback):
    assert classify_documents("") == ["Other"]
    assert classify_documents("   \n\t ") == ["Other"]


def test_all_fallback_results_are_constrained(force_keyword_fallback):
    for snippet in (
        TOR_SNIPPET,
        MARKET_SNIPPET,
        COST_SNIPPET,
        CONTRACT_SNIPPET,
        TOR_MENTIONS_CONTRACT,
        CONTRACTOR_NO_TOR,
    ):
        result = classify_documents(snippet)
        assert result, "result must be non-empty"
        assert set(result).issubset(ALLOWED)
        assert len(result) == len(set(result))  # no duplicates


# ---------------------------------------------------------------------------
# recommendations()
# ---------------------------------------------------------------------------

def test_tor_recommends_ppmp_and_contract():
    rec = recommendations(["Terms of Reference"])
    assert rec["ppmp"]["recommended"] is True
    assert rec["contract"]["recommended"] is True
    assert rec["market"]["recommended"] is False
    # app is not auto-recommended, but is still available
    assert rec["app"]["recommended"] is False
    assert rec["app"]["available"] is True
    assert set(rec) == set(DOC_FORM_MAP)  # all forms present


def test_market_study_recommends_market():
    rec = recommendations(["Market Study"])
    assert rec["market"]["recommended"] is True


def test_cost_breakdown_available_not_recommended():
    rec = recommendations(["Cost Breakdown"])
    # ppmp and app can be filled from a cost breakdown, but are not recommended
    for key in ("ppmp", "app"):
        assert rec[key]["available"] is True
        assert rec[key]["recommended"] is False


def test_group_b_always_available_never_recommended():
    rec = recommendations(["Terms of Reference"])
    for key in ("bidform", "price_local", "price_abroad", "bsd", "oss", "psd"):
        assert rec[key]["available"] is True
        assert rec[key]["recommended"] is False


def test_no_doc_types_recommends_nothing():
    for doc_types in ([], ["Other"]):
        rec = recommendations(doc_types)
        assert all(v["recommended"] is False for v in rec.values())
        assert all(v["available"] is True for v in rec.values())


# ---------------------------------------------------------------------------
# Real-LLM sanity check (skips if no credentials)
# ---------------------------------------------------------------------------

def test_real_llm_sanity_tor():
    try:
        from utils.llm_factory import get_llm

        get_llm(temperature=0.0)
    except Exception:
        pytest.skip("No LLM credentials configured")

    result = classify_documents(TOR_SNIPPET)
    assert isinstance(result, list)
    assert result
    assert set(result).issubset(ALLOWED)
