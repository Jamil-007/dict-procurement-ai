"""
The summary envelope: findings plus what the dimension says it reviewed.

The envelope is a bonus on top of the findings, and these tests are mostly
about that asymmetry — a mangled summary must never cost us the findings it
was wrapped around.
"""

import json

import pytest

from review.parsing import output_from_response

FINDING = {
    "severity": "medium",
    "title": "Delivery period is not stated",
    "analysis": "The TOR lists deliverables without a delivery schedule.",
    "source": {"doc": "TOR.pdf", "page": 4},
}


def envelope(**overrides) -> str:
    payload = {
        "summary": {
            "assessment": "Reviewed the TOR against the purchase request.",
            "documents_reviewed": ["TOR.pdf", "Purchase Request.pdf"],
            "confidence": "high",
        },
        "findings": [FINDING],
        "research_gaps": ["No market study was uploaded."],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_the_whole_envelope_is_read():
    output = output_from_response(envelope(), "compliance")

    assert len(output.findings) == 1
    assert output.summary.assessment.startswith("Reviewed the TOR")
    assert output.summary.documents_reviewed == ["TOR.pdf", "Purchase Request.pdf"]
    assert output.summary.confidence == "high"
    assert output.research_gaps == ["No market study was uploaded."]


def test_the_dimension_is_stamped_on_the_findings():
    output = output_from_response(envelope(), "document_quality")

    assert output.findings[0].dimension == "document_quality"


def test_a_bare_array_still_parses():
    """A model that ignores the override must not fail the dimension."""
    output = output_from_response(json.dumps([FINDING]), "compliance")

    assert len(output.findings) == 1
    assert output.summary is None
    assert output.research_gaps == []


def test_an_assessment_with_no_findings_survives():
    """The case the envelope exists for: checked, and found nothing."""
    output = output_from_response(envelope(findings=[]), "compliance")

    assert output.findings == []
    assert output.summary.assessment


def test_a_malformed_summary_does_not_cost_us_the_findings():
    output = output_from_response(
        envelope(summary={"confidence": "extremely high"}), "compliance"
    )

    assert len(output.findings) == 1
    assert output.summary is None


def test_a_summary_returned_as_a_string_is_dropped():
    output = output_from_response(envelope(summary="looks fine to me"), "compliance")

    assert len(output.findings) == 1
    assert output.summary is None


def test_research_gaps_of_the_wrong_shape_are_dropped():
    output = output_from_response(envelope(research_gaps="the market study"), "x")

    assert output.research_gaps == []


def test_blank_research_gaps_are_discarded():
    output = output_from_response(envelope(research_gaps=["", "   ", "real gap"]), "x")

    assert output.research_gaps == ["real gap"]


def test_a_single_finding_returned_bare_is_accepted():
    """Models sometimes answer with one finding object and no array."""
    output = output_from_response(json.dumps(FINDING), "compliance")

    assert len(output.findings) == 1
    assert output.findings[0].title == FINDING["title"]


def test_a_fenced_envelope_parses():
    content = f"Here you go:\n```json\n{envelope()}\n```\nHope that helps."

    output = output_from_response(content, "compliance")

    assert len(output.findings) == 1
    assert output.summary is not None


def test_a_response_that_is_neither_raises():
    with pytest.raises(ValueError):
        output_from_response("42", "compliance")


def test_findings_that_all_fail_validation_raise():
    """An unusable response must fail loudly, not look like a clean review."""
    with pytest.raises(ValueError):
        output_from_response(envelope(findings=[{"title": "no severity"}]), "x")
