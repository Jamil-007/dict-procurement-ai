"""
Parsing a model response into findings.

These cover the ways a response goes wrong in practice rather than the happy
path: a dropped finding here is invisible to the BAC, who cannot tell a review
that found nothing from a review whose output failed to validate.
"""

import json

import pytest

from review.parsing import (
    extract_json,
    findings_from_response,
    strip_unretrieved_sources,
)
from review.schema import ExternalSource, ReviewFinding, Source


def finding(**overrides) -> dict:
    base = {
        "severity": "medium",
        "title": "A title",
        "analysis": "Some analysis",
        "source": {"doc": "TOR.pdf", "page": 3},
    }
    base.update(overrides)
    return base


# --- extract_json ---------------------------------------------------------


def test_reads_a_bare_array():
    assert extract_json('[{"a": 1}]') == [{"a": 1}]


def test_reads_through_a_markdown_fence():
    assert extract_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_reads_through_surrounding_prose():
    content = 'Here are my findings:\n[{"a": 1}]\nI hope these help.'
    assert extract_json(content) == [{"a": 1}]


@pytest.mark.parametrize("content", ["", "   ", "no json at all"])
def test_rejects_a_response_with_no_json(content):
    with pytest.raises(ValueError):
        extract_json(content)


# --- findings_from_response -----------------------------------------------


def test_stamps_the_dimension_and_discards_any_model_supplied_id():
    payload = json.dumps([finding(id="AI-99")])
    result = findings_from_response(payload, "procurement_market")
    assert result[0].dimension == "procurement_market"
    assert result[0].id == ""  # the runner assigns ids, not the model


def test_accepts_a_findings_object_as_well_as_an_array():
    payload = json.dumps({"findings": [finding()]})
    assert len(findings_from_response(payload, "d")) == 1


def test_coerces_a_severity_from_the_earlier_three_level_scale():
    payload = json.dumps([finding(severity="high"), finding(severity="warning")])
    result = findings_from_response(payload, "d")
    assert [f.severity for f in result] == ["critical", "medium"]


def test_drops_one_malformed_finding_but_keeps_the_rest():
    payload = json.dumps([finding(), {"severity": "nonsense"}, finding()])
    assert len(findings_from_response(payload, "d")) == 2


def test_raises_when_every_finding_is_malformed():
    # Returning [] here would be indistinguishable from a clean review.
    payload = json.dumps([{"severity": "nonsense"}])
    with pytest.raises(ValueError):
        findings_from_response(payload, "d")


# --- source repair --------------------------------------------------------
#
# A model that fills in `comparison` tends to treat `source` as redundant and
# omit it. `source` is required, so the finding used to be dropped — and a
# cross-document finding is usually the most valuable one in the set.


def test_recovers_a_missing_source_from_the_first_compared_document():
    payload = json.dumps(
        [
            {
                "severity": "critical",
                "title": "Required lead time is shorter than the market quotes",
                "analysis": "…",
                "comparison": [
                    {
                        "doc": "TOR.pdf",
                        "page": 4,
                        "label": "Required lead time",
                        "quote": "forty-five (45) calendar days",
                    },
                    {
                        "doc": "Market Study.pdf",
                        "page": 3,
                        "label": "Quoted lead time",
                        "quote": "90 to 120 calendar days",
                    },
                ],
            }
        ]
    )
    result = findings_from_response(payload, "procurement_market")
    assert len(result) == 1
    assert result[0].source.doc == "TOR.pdf"
    assert result[0].source.page == 4
    assert result[0].source.section == "Required lead time"
    assert len(result[0].comparison) == 2


def test_never_overwrites_a_source_the_model_supplied():
    payload = json.dumps(
        [
            finding(
                source={"doc": "PPMP.pdf", "page": 1},
                comparison=[{"doc": "TOR.pdf", "quote": "x"}],
            )
        ]
    )
    assert findings_from_response(payload, "d")[0].source.doc == "PPMP.pdf"


def test_still_rejects_a_finding_with_neither_source_nor_comparison():
    payload = json.dumps([{"severity": "low", "title": "t", "analysis": "a"}])
    with pytest.raises(ValueError):
        findings_from_response(payload, "d")


def test_does_not_repair_from_a_comparison_entry_with_no_document():
    payload = json.dumps(
        [
            {
                "severity": "low",
                "title": "t",
                "analysis": "a",
                "comparison": [{"quote": "x"}],
            }
        ]
    )
    with pytest.raises(ValueError):
        findings_from_response(payload, "d")


# --- strip_unretrieved_sources --------------------------------------------
#
# Instructing a model not to invent a URL is not the same as it not inventing
# one, and a fabricated citation on a pre-posting review is worse than none.


def built(**overrides) -> ReviewFinding:
    base = {
        "dimension": "procurement_market",
        "severity": "medium",
        "title": "t",
        "analysis": "a",
        "source": Source(doc="Market Study.pdf"),
    }
    base.update(overrides)
    return ReviewFinding(**base)


def test_keeps_a_source_the_search_returned():
    f = built(
        confidence="high",
        external_sources=[ExternalSource(url="https://real.gov.ph/a", tier=1)],
    )
    strip_unretrieved_sources([f], {"https://real.gov.ph/a"})
    assert [s.url for s in f.external_sources] == ["https://real.gov.ph/a"]
    assert f.confidence == "high"


def test_removes_only_the_sources_the_search_did_not_return():
    f = built(
        confidence="high",
        external_sources=[
            ExternalSource(url="https://real.gov.ph/a", tier=1),
            ExternalSource(url="https://invented.example/x", tier=4),
        ],
    )
    strip_unretrieved_sources([f], {"https://real.gov.ph/a"})
    assert [s.url for s in f.external_sources] == ["https://real.gov.ph/a"]
    assert f.confidence == "high"  # something verifiable survived


def test_downgrades_confidence_when_every_source_was_invented():
    f = built(
        confidence="high",
        external_sources=[ExternalSource(url="https://invented.example/x", tier=1)],
    )
    strip_unretrieved_sources([f], set())
    assert f.external_sources == []
    assert f.confidence == "low"


def test_leaves_a_document_only_finding_untouched():
    f = built(confidence="high")
    strip_unretrieved_sources([f], set())
    assert f.confidence == "high"
