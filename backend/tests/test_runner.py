"""
The runner's contract with a dimension.

Two things are being protected here. One is isolation: a dimension that
raises, hangs or returns nonsense must come back as a failure beside four
healthy ones, never take the run down with it. The other is that a dimension
may answer with a bare list of findings or with the richer DimensionOutput,
and both have to work — the second shape was added later, and adding it was
only acceptable because it did not force the existing analyzers to change.
"""

import asyncio

from review.context import ReviewContext
from review.registry import DimensionSpec
from review.runner import _run_one
from review.schema import DimensionOutput, DimensionSummary, ReviewFinding, Source


def finding(title: str = "Something to check") -> ReviewFinding:
    return ReviewFinding(
        dimension="wrong_on_purpose",
        severity="medium",
        title=title,
        analysis="...",
        source=Source(doc="TOR.pdf", page=2),
    )


def spec_for(run) -> DimensionSpec:
    return DimensionSpec(
        key="compliance", label="Compliance", blurb="", owner="", run=run
    )


def run_dimension(run, timeout: int = 5):
    ctx = ReviewContext(procurement_ref="PROC-2026-001", documents=[])
    return asyncio.run(_run_one(spec_for(run), ctx, timeout))


def test_a_bare_list_of_findings_is_accepted():
    result = run_dimension(lambda ctx: [finding()])

    assert result.status == "ok"
    assert len(result.findings) == 1
    assert result.summary is None
    assert result.research_gaps == []


def test_a_dimension_output_carries_its_summary_through():
    output = DimensionOutput(
        findings=[finding()],
        summary=DimensionSummary(
            assessment="Read the TOR.", documents_reviewed=["TOR.pdf"]
        ),
        research_gaps=["No market study."],
    )

    result = run_dimension(lambda ctx: output)

    assert result.status == "ok"
    assert result.summary.assessment == "Read the TOR."
    assert result.research_gaps == ["No market study."]


def test_an_assessment_with_no_findings_is_still_a_success():
    """"Checked it, nothing to raise" must not read as "did not run"."""
    result = run_dimension(
        lambda ctx: DimensionOutput(
            summary=DimensionSummary(assessment="Nothing of concern.")
        )
    )

    assert result.status == "ok"
    assert result.findings == []
    assert result.summary.assessment == "Nothing of concern."


def test_returning_nothing_is_an_empty_success():
    result = run_dimension(lambda ctx: None)

    assert result.status == "ok"
    assert result.findings == []


def test_an_async_dimension_is_awaited():
    async def run(ctx):
        await asyncio.sleep(0)
        return [finding()]

    assert len(run_dimension(run).findings) == 1


def test_the_runner_stamps_its_own_key_on_every_finding():
    """An analyzer must not be able to mislabel its output as another's."""
    result = run_dimension(lambda ctx: [finding()])

    assert result.findings[0].dimension == "compliance"


def test_a_nonsense_return_fails_the_dimension_not_the_run():
    result = run_dimension(lambda ctx: "all good!")

    assert result.status == "failed"
    assert "str" in result.error


def test_a_raising_dimension_comes_back_failed():
    def run(ctx):
        raise RuntimeError("the model refused")

    result = run_dimension(run)

    assert result.status == "failed"
    assert "the model refused" in result.error


def test_a_slow_dimension_times_out():
    async def run(ctx):
        await asyncio.sleep(5)
        return []

    result = run_dimension(run, timeout=1)

    assert result.status == "timeout"
    assert result.findings == []
