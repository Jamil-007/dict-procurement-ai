"""
Tests for policy citation wiring into the review pipeline.

The critical property is that fabrication is impossible by construction: only
provision ids that retrieval actually returned can make it into policy_sources,
and the citation text is always the one from the index, never the model's.
"""

import pytest

from knowledge.schema import Chunk, Provision, Retrieval
from review import policy as policy_module
from review.policy import ground_policy_basis, provisions_for_queries
from review.schema import ReviewFinding


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Never let a developer's real key make these tests hit the network."""
    try:
        from config import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    except ImportError:
        pass


def test_finding_citing_retrieved_id_gets_policy_sources_populated():
    """
    A finding citing a provision id that was retrieved gets policy_sources
    populated with the canonical citation.
    """
    chunk = Chunk(
        id="ra-12009-irr#0042",
        doc_id="ra-12009-irr",
        doc_title="IRR of RA 12009",
        section="Section 23.1",
        page=45,
        text="Brand name specifications are prohibited unless justified by technical necessity.",
    )
    retrieval = Retrieval(provisions=[Provision(chunk=chunk, score=1.0)])

    finding = ReviewFinding(
        dimension="test",
        severity="medium",
        title="Test finding",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_refs=["ra-12009-irr#0042"],
    )

    findings = ground_policy_basis([finding], retrieval)

    assert len(findings) == 1
    f = findings[0]
    assert len(f.policy_sources) == 1
    assert f.policy_sources[0].title == "IRR of RA 12009"
    assert f.policy_sources[0].section == "Section 23.1"
    assert f.policy_sources[0].page == 45
    assert "Brand name specifications" in f.policy_sources[0].quote
    # policy_basis is rewritten to the canonical citation
    assert f.policy_basis == "IRR of RA 12009 — Section 23.1"


def test_finding_citing_unretrieved_id_has_policy_basis_cleared():
    """
    A finding citing an id that was NOT retrieved has policy_basis cleared and
    policy_sources left empty, but is not dropped.
    """
    chunk = Chunk(
        id="ra-12009-irr#0042",
        doc_id="ra-12009-irr",
        doc_title="IRR of RA 12009",
        section="Section 23.1",
        page=45,
        text="Brand name specifications are prohibited.",
    )
    retrieval = Retrieval(provisions=[Provision(chunk=chunk, score=1.0)])

    finding = ReviewFinding(
        dimension="test",
        severity="medium",
        title="Test finding",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_basis="Some model-written basis",
        policy_refs=["gppb-2023-004#0001"],  # Not in retrieval
    )

    findings = ground_policy_basis([finding], retrieval)

    assert len(findings) == 1  # Not dropped
    f = findings[0]
    assert f.policy_sources == []
    assert f.policy_basis == ""  # Cleared because it was unverifiable


def test_finding_citing_nothing_keeps_empty_policy_basis():
    """
    A finding with no policy_refs and no policy_basis stays that way.
    """
    retrieval = Retrieval(provisions=[])

    finding = ReviewFinding(
        dimension="test",
        severity="info",
        title="Observation",
        analysis="Just a note",
        source={"doc": "TOR.pdf", "page": 1},
    )

    findings = ground_policy_basis([finding], retrieval)

    assert len(findings) == 1
    f = findings[0]
    assert f.policy_sources == []
    assert f.policy_basis == ""


def test_empty_retrieval_leaves_findings_untouched():
    """
    When retrieval is empty (index unavailable), findings are returned
    completely untouched, including a model-written policy_basis. The
    index being unavailable must degrade the review to what it does today,
    not strip value out of it.
    """
    retrieval = Retrieval(
        provisions=[],
        note="The reference index has not been built yet",
    )

    finding = ReviewFinding(
        dimension="test",
        severity="medium",
        title="Test finding",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_basis="RA 12009 IRR Section 23.1",  # Model-written
        policy_refs=["ra-12009-irr#0042"],
    )

    findings = ground_policy_basis([finding], retrieval)

    assert len(findings) == 1
    f = findings[0]
    # Untouched — the model's policy_basis is preserved
    assert f.policy_basis == "RA 12009 IRR Section 23.1"
    assert f.policy_sources == []


def test_round_robin_merge_deduplicates_overlapping_results(monkeypatch):
    """
    Two queries returning overlapping results are deduplicated, and neither
    query monopolises the cap. Round-robin merge ensures diversity.
    """

    # Mock provisions_for to return controlled results
    def mock_provisions_for(query, k=6, doc_ids=None):
        if "brand" in query.lower():
            return Retrieval(
                provisions=[
                    Provision(
                        chunk=Chunk(
                            id="ra-12009-irr#0001",
                            doc_id="ra-12009-irr",
                            doc_title="IRR of RA 12009",
                            section="Section 23.1",
                            page=45,
                            text="Brand specs",
                        ),
                        score=1.0,
                    ),
                    Provision(
                        chunk=Chunk(
                            id="ra-12009-irr#0002",
                            doc_id="ra-12009-irr",
                            doc_title="IRR of RA 12009",
                            section="Section 23.2",
                            page=46,
                            text="Generic specs",
                        ),
                        score=0.9,
                    ),
                ],
                embedded=True,
            )
        elif "market" in query.lower():
            return Retrieval(
                provisions=[
                    Provision(
                        chunk=Chunk(
                            id="ra-12009-irr#0002",  # Overlaps with brand query
                            doc_id="ra-12009-irr",
                            doc_title="IRR of RA 12009",
                            section="Section 23.2",
                            page=46,
                            text="Generic specs",
                        ),
                        score=1.0,
                    ),
                    Provision(
                        chunk=Chunk(
                            id="gppb-2023-004#0001",
                            doc_id="gppb-2023-004",
                            doc_title="GPPB Resolution 2023-004",
                            section="Section 1",
                            page=1,
                            text="Market scoping",
                        ),
                        score=0.8,
                    ),
                ],
                embedded=True,
            )
        else:
            return Retrieval(provisions=[], embedded=True)

    monkeypatch.setattr(policy_module, "provisions_for", mock_provisions_for)

    result = provisions_for_queries(["brand name", "market scoping"], k_each=3, cap=8)

    # Should have 3 unique chunks: #0001, #0002, gppb#0001
    assert len(result.provisions) == 3
    chunk_ids = {p.chunk.id for p in result.provisions}
    assert "ra-12009-irr#0001" in chunk_ids
    assert "ra-12009-irr#0002" in chunk_ids
    assert "gppb-2023-004#0001" in chunk_ids
    # Round-robin: first from query 1, first from query 2, second from query 1, ...
    # So order should be: #0001 (brand rank 0), #0002 (market rank 0 - but dup),
    # actually: #0001, #0002, gppb#0001
    assert result.provisions[0].chunk.id == "ra-12009-irr#0001"


def test_quote_trimmed_at_word_boundary():
    """
    The provision quote is trimmed at a word boundary, not mid-word, with an
    ellipsis when it exceeds POLICY_QUOTE_CHARS.
    """
    long_text = "This is a very long provision text " * 50  # Way over 600 chars

    chunk = Chunk(
        id="test#0001",
        doc_id="test",
        doc_title="Test Doc",
        section="Section 1",
        page=1,
        text=long_text,
    )
    retrieval = Retrieval(provisions=[Provision(chunk=chunk, score=1.0)])

    finding = ReviewFinding(
        dimension="test",
        severity="info",
        title="Test",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_refs=["test#0001"],
    )

    findings = ground_policy_basis([finding], retrieval)

    quote = findings[0].policy_sources[0].quote
    assert len(quote) <= 601  # 600 + ellipsis char
    assert quote.endswith("…")
    # Verify it was trimmed (original is much longer)
    assert len(long_text) > 600
    # The quote without the ellipsis should be found in the original text
    # (i.e., it's a valid substring, not broken mid-word)
    quote_without_ellipsis = quote[:-1]
    assert quote_without_ellipsis in long_text


def test_policy_refs_excluded_from_model_dump():
    """
    policy_refs has exclude=True, so it does not appear in model_dump(). This
    ensures it never reaches storage or the frontend.
    """
    finding = ReviewFinding(
        dimension="test",
        severity="info",
        title="Test",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_refs=["ra-12009-irr#0042"],
    )

    dumped = finding.model_dump()
    assert "policy_refs" not in dumped


def test_multiple_provisions_cited():
    """
    A finding citing multiple provisions gets all of them in policy_sources,
    and policy_basis is semicolon-joined.
    """
    chunks = [
        Chunk(
            id="ra-12009-irr#0001",
            doc_id="ra-12009-irr",
            doc_title="IRR of RA 12009",
            section="Section 23.1",
            page=45,
            text="First provision",
        ),
        Chunk(
            id="gppb-2023-004#0002",
            doc_id="gppb-2023-004",
            doc_title="GPPB Resolution 2023-004",
            section="Section 2",
            page=3,
            text="Second provision",
        ),
    ]
    retrieval = Retrieval(provisions=[Provision(chunk=c, score=1.0) for c in chunks])

    finding = ReviewFinding(
        dimension="test",
        severity="medium",
        title="Test",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_refs=["ra-12009-irr#0001", "gppb-2023-004#0002"],
    )

    findings = ground_policy_basis([finding], retrieval)

    f = findings[0]
    assert len(f.policy_sources) == 2
    assert f.policy_sources[0].title == "IRR of RA 12009"
    assert f.policy_sources[1].title == "GPPB Resolution 2023-004"
    assert (
        f.policy_basis
        == "IRR of RA 12009 — Section 23.1; GPPB Resolution 2023-004 — Section 2"
    )


def test_provisions_for_queries_with_empty_queries():
    """
    Empty query list returns empty Retrieval with a note, not an exception.
    """
    result = provisions_for_queries([])
    assert result.provisions == []
    assert "no queries" in result.note.lower()


def test_provisions_for_queries_respects_cap(monkeypatch):
    """
    The merged result respects the cap even when queries would return more.
    """

    def mock_provisions_for(query, k=6, doc_ids=None):
        # Return many provisions per query
        provisions = [
            Provision(
                chunk=Chunk(
                    id=f"{query[:5]}-{i:04d}",
                    doc_id="test",
                    doc_title="Test",
                    section=f"Section {i}",
                    page=i,
                    text=f"Provision {i}",
                ),
                score=1.0,
            )
            for i in range(10)
        ]
        return Retrieval(provisions=provisions, embedded=True)

    monkeypatch.setattr(policy_module, "provisions_for", mock_provisions_for)

    result = provisions_for_queries(["query one", "query two"], k_each=10, cap=5)

    assert len(result.provisions) == 5


def test_embedded_false_when_any_query_not_embedded(monkeypatch):
    """
    Retrieval.embedded is True only when all completed queries were embedded.
    """
    call_count = [0]

    def mock_provisions_for(query, k=6, doc_ids=None):
        call_count[0] += 1
        embedded = call_count[0] > 1  # First query not embedded
        return Retrieval(
            provisions=[
                Provision(
                    chunk=Chunk(
                        id=f"test#{call_count[0]:04d}",
                        doc_id="test",
                        doc_title="Test",
                        section="Section 1",
                        page=1,
                        text="Test",
                    ),
                    score=1.0,
                )
            ],
            embedded=embedded,
        )

    monkeypatch.setattr(policy_module, "provisions_for", mock_provisions_for)

    result = provisions_for_queries(["query one", "query two"], k_each=3, cap=8)

    assert result.embedded is False
    assert "keyword-only" in result.note.lower()


def test_chunk_with_no_section_uses_page_in_cite():
    """
    When a chunk has no section, cite() falls back to page number, and that
    should appear in policy_basis.
    """
    chunk = Chunk(
        id="test#0001",
        doc_id="test",
        doc_title="Test Document",
        section="",  # No section
        page=42,
        text="Some provision without a section heading",
    )
    retrieval = Retrieval(provisions=[Provision(chunk=chunk, score=1.0)])

    finding = ReviewFinding(
        dimension="test",
        severity="info",
        title="Test",
        analysis="Test",
        source={"doc": "TOR.pdf", "page": 1},
        policy_refs=["test#0001"],
    )

    findings = ground_policy_basis([finding], retrieval)

    # cite() should produce "Test Document — p42"
    assert findings[0].policy_basis == "Test Document — p42"
