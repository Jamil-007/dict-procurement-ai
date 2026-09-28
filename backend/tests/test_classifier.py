import pytest

from agents.doc_generation.classifier import (
    classify_documents,
    recommendations,
    DOC_FORM_MAP,
    DOMAIN_TO_ALLOWED,
    doc_types_from_procurement_documents,
    doc_types_from_findings,
    recommend_for_ref,
)
from domain import Procurement, ProcurementDocument
from review.schema import ReviewFinding, Source, StoredFinding

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


# ---------------------------------------------------------------------------
# doc_types_from_procurement_documents / doc_types_from_findings / recommend_for_ref
# ---------------------------------------------------------------------------

REF = "PROC-FORMS-002"


def make_finding(**overrides) -> ReviewFinding:
    defaults = dict(
        id="F1",
        dimension="compliance",
        severity="medium",
        title="x",
        analysis="x",
        source=Source(doc="TOR.pdf"),
    )
    defaults.update(overrides)
    return ReviewFinding(**defaults)


def test_domain_to_allowed_covers_every_domain_doc_type():
    from domain import DOC_TYPES

    for dt in DOC_TYPES:
        assert dt in DOMAIN_TO_ALLOWED
        assert DOMAIN_TO_ALLOWED[dt] in ALLOWED


def test_doc_types_from_procurement_documents_maps_and_dedupes():
    result = doc_types_from_procurement_documents(
        ["Terms of Reference (TOR)", "Technical Specifications", "Detailed Cost Breakdown"]
    )
    assert result == ["Terms of Reference", "Cost Breakdown"]


def test_doc_types_from_procurement_documents_unknown_is_other():
    assert doc_types_from_procurement_documents(["Some Unlisted Type"]) == ["Other"]


def test_doc_types_from_findings_matches_by_source_doc_name():
    findings = [make_finding(source=Source(doc="Market.pdf"))]
    name_to_allowed = {"Market.pdf": "Market Study"}
    assert doc_types_from_findings(findings, name_to_allowed) == ["Market Study"]


def test_doc_types_from_findings_falls_back_to_dimension_hint():
    # source.doc does not match anything on the procurement record.
    findings = [make_finding(dimension="procurement_market", source=Source(doc="unknown.pdf"))]
    result = doc_types_from_findings(findings, name_to_allowed={})
    assert set(result) == {"Market Study", "Cost Breakdown"}


def test_doc_types_from_findings_dedupes():
    findings = [
        make_finding(source=Source(doc="TOR.pdf")),
        make_finding(source=Source(doc="TOR.pdf")),
    ]
    name_to_allowed = {"TOR.pdf": "Terms of Reference"}
    assert doc_types_from_findings(findings, name_to_allowed) == ["Terms of Reference"]


class FakeStore:
    def __init__(self, procurement, findings=None):
        self._procurement = procurement
        self._findings = findings or []

    def get_procurement(self, ref):
        return self._procurement if ref == REF else None

    def list_findings(self, ref):
        return self._findings


def test_recommend_for_ref_unknown_procurement_is_empty(monkeypatch):
    import store as store_module

    monkeypatch.setattr(store_module, "get_store", lambda: FakeStore(None))
    result = recommend_for_ref("does-not-exist")
    assert result == {"doc_types": [], "forms": recommendations([])}


def test_recommend_for_ref_combines_documents_and_findings(monkeypatch):
    import store as store_module

    procurement = Procurement(
        ref=REF,
        title="Supply of Rack Servers",
        documents=[
            ProcurementDocument(id="d1", name="TOR.pdf", doc_type="Terms of Reference (TOR)")
        ],
    )
    # AI Review flagged a second document (Market Study) not otherwise on record
    # under that exact filename — the procurement_market dimension hint should
    # still surface "Market Study" as a signal.
    findings = [
        StoredFinding(
            id="F1",
            procurement_ref=REF,
            dimension="procurement_market",
            severity="medium",
            title="x",
            analysis="x",
            source=Source(doc="Market Study.pdf"),
        )
    ]
    monkeypatch.setattr(store_module, "get_store", lambda: FakeStore(procurement, findings))

    result = recommend_for_ref(REF)

    assert result["doc_types"][0] == "Terms of Reference"
    assert "Market Study" in result["doc_types"]
    assert result["forms"]["ppmp"]["recommended"] is True
    assert result["forms"]["market"]["recommended"] is True
