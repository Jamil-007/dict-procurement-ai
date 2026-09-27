"""
Explicit nulls from the model.

A model handed a JSON template fills every key in it, and writes `null` into
the ones it cannot answer. That is the model saying "not provided" — but
pydantic reads an explicit null as a value, and a `str` field rejects it, where
an absent key would have quietly taken its default.

Left alone this drops findings wholesale. It took out every finding from two
dimensions in one run: five from compliance, eight from requirements_risk, all
of them on `"section": null` or `"recommendation": null`, and because nothing
survived, both dimensions were reported to the committee as failed rather than
as clean.
"""

import json

import pytest
from pydantic import ValidationError

from review.parsing import findings_from_response, output_from_response
from review.schema import ComparedText, ReviewFinding, Source


def finding(**overrides) -> dict:
    base = {
        "severity": "medium",
        "title": "A title",
        "analysis": "Some analysis",
        "source": {"doc": "TOR.pdf", "page": 3},
    }
    base.update(overrides)
    return base


# --- the models themselves ---


def test_a_null_section_is_read_as_no_section():
    assert Source(doc="TOR.pdf", page=3, section=None).section == ""


def test_a_null_page_is_still_a_null_page():
    """`page` genuinely admits None, and must keep doing so."""
    assert Source(doc="TOR.pdf", page=None).page is None


def test_null_optional_strings_on_a_finding_become_empty():
    result = ReviewFinding(
        dimension="compliance",
        severity="medium",
        title="A title",
        analysis="Some analysis",
        source=Source(doc="TOR.pdf"),
        recommendation=None,
        policy_basis=None,
        quote=None,
    )

    assert result.recommendation == ""
    assert result.policy_basis == ""
    assert result.quote == ""


def test_null_lists_become_empty_lists():
    result = ReviewFinding(
        dimension="compliance",
        severity="medium",
        title="A title",
        analysis="Some analysis",
        source=Source(doc="TOR.pdf"),
        comparison=None,
        external_sources=None,
        policy_refs=None,
    )

    assert result.comparison == []
    assert result.external_sources == []
    assert result.policy_refs == []


def test_a_null_confidence_stays_null():
    """`confidence` admits None and means something by it."""
    result = ReviewFinding(
        dimension="compliance",
        severity="medium",
        title="A title",
        analysis="Some analysis",
        source=Source(doc="TOR.pdf"),
        confidence=None,
    )

    assert result.confidence is None


def test_a_null_label_on_a_comparison_becomes_empty():
    assert ComparedText(doc="TOR.pdf", label=None, quote="text").label == ""


def test_a_null_title_is_still_a_failure():
    """Nulling a required field is not the same as omitting a defaulted one."""
    with pytest.raises(ValidationError):
        ReviewFinding(
            dimension="compliance",
            severity="medium",
            title=None,
            analysis="Some analysis",
            source=Source(doc="TOR.pdf"),
        )


# --- through the parser, which is where it actually bit ---


def test_the_exact_response_that_failed_in_production():
    content = json.dumps(
        [
            finding(
                recommendation=None,
                source={"doc": "TOR.pdf", "page": 12, "section": None},
            )
        ]
    )

    findings = findings_from_response(content, "compliance")

    assert len(findings) == 1
    assert findings[0].recommendation == ""
    assert findings[0].source.section == ""


def test_a_whole_dimension_is_not_lost_to_nulls():
    """
    The failure mode this guards. Eight findings, every one carrying a null
    section, and the dimension reported as failed because nothing survived.
    """
    content = json.dumps(
        {
            "summary": {
                "assessment": "Reviewed the TOR.",
                "documents_reviewed": ["TOR.pdf"],
                "confidence": "medium",
            },
            "findings": [
                finding(
                    title=f"Finding {i}",
                    recommendation=None,
                    source={"doc": "TOR.pdf", "page": i, "section": None},
                )
                for i in range(1, 9)
            ],
            "research_gaps": [],
        }
    )

    output = output_from_response(content, "requirements_risk")

    assert len(output.findings) == 8
    assert output.summary is not None


def test_a_null_summary_field_does_not_cost_the_summary():
    content = json.dumps(
        {
            "summary": {
                "assessment": "Reviewed the TOR.",
                "documents_reviewed": None,
                "confidence": None,
            },
            "findings": [finding()],
            "research_gaps": None,
        }
    )

    output = output_from_response(content, "compliance")

    assert output.summary.documents_reviewed == []
    assert output.summary.confidence is None
    assert output.research_gaps == []
