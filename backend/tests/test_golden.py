import json
import os
import pytest
from pathlib import Path
from forms.extractor import extract_fields

SAMPLE = (Path(__file__).parent / "fixtures" / "gecs_sample.txt").read_text()

# Skip live LLM tests if no API key present
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GOOGLE_CLOUD_PROJECT"))

@pytest.mark.skipif(not HAS_API_KEY, reason="No LLM API key configured")
def test_ppmp_matches_golden():
    """
    Test PPMP extraction against golden reference.

    This test requires a live LLM API key (ANTHROPIC_API_KEY or GOOGLE_CLOUD_PROJECT).
    It will be skipped if no key is present.
    """
    model, warning = extract_fields("ppmp", SAMPLE)
    golden = json.loads((Path(__file__).parent / "golden" / "ppmp.json").read_text())
    got = model.model_dump()

    # Check key fields match (allow for LLM variation in exact wording)
    assert got.get("fiscal_year") == golden.get("fiscal_year")
    assert got.get("project_type") == golden.get("project_type")
    assert "50,000,000" in str(got.get("estimated_budget", ""))
    assert warning is False

def test_golden_structure_valid():
    """
    Test that golden files have valid structure (can run without API key).
    """
    golden_path = Path(__file__).parent / "golden" / "ppmp.json"
    golden = json.loads(golden_path.read_text())

    # Check that all PPMP fields are present
    expected_fields = [
        "fiscal_year", "end_user_unit", "general_description", "project_type",
        "quantity_size", "mode_of_procurement", "pre_procurement_conference",
        "start_activity", "end_activity", "expected_delivery", "source_of_funds",
        "estimated_budget", "supporting_documents", "remarks", "prepared_by"
    ]

    for field in expected_fields:
        assert field in golden, f"Golden file missing field: {field}"
