"""
Runs every registered dimension in parallel and collects the findings.

Isolation is the point of this module: one dimension raising, timing out or
returning nonsense must not stop the other four. A failed dimension comes back
with status "failed" and the report renders without it.
"""

import asyncio
import inspect
import logging
import time
from typing import Callable, List, Optional

from review.context import ReviewContext
from review.registry import DimensionSpec, all_dimensions
from review.schema import DimensionResult, ReviewFinding, ReviewResult

logger = logging.getLogger(__name__)

# A dimension that has not answered by now is treated as failed. Generous
# because some dimensions make several LLM calls.
DIMENSION_TIMEOUT_SECONDS = 180

ProgressHook = Callable[[DimensionResult], None]


async def _invoke(spec: DimensionSpec, ctx: ReviewContext) -> List[ReviewFinding]:
    """Call a dimension, whether it was written sync or async."""
    if inspect.iscoroutinefunction(spec.run):
        return await spec.run(ctx)
    # Sync analyzers block on llm.invoke(), so keep them off the event loop.
    return await asyncio.to_thread(spec.run, ctx)


async def _run_one(
    spec: DimensionSpec, ctx: ReviewContext, timeout: int
) -> DimensionResult:
    started = time.monotonic()

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    try:
        findings = await asyncio.wait_for(_invoke(spec, ctx), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Dimension '%s' timed out after %ss", spec.key, timeout)
        return DimensionResult(
            key=spec.key,
            label=spec.label,
            status="timeout",
            error=f"No result within {timeout}s",
            duration_ms=elapsed(),
        )
    except Exception as exc:  # noqa: BLE001 - one dimension must not sink the run
        logger.exception("Dimension '%s' failed", spec.key)
        return DimensionResult(
            key=spec.key,
            label=spec.label,
            status="failed",
            error=str(exc),
            duration_ms=elapsed(),
        )

    if findings is None:
        findings = []
    if not isinstance(findings, list):
        return DimensionResult(
            key=spec.key,
            label=spec.label,
            status="failed",
            error=f"Expected a list of findings, got {type(findings).__name__}",
            duration_ms=elapsed(),
        )

    # Stamp the dimension key so an analyzer cannot mislabel its own output.
    for finding in findings:
        finding.dimension = spec.key

    return DimensionResult(
        key=spec.key,
        label=spec.label,
        status="ok",
        findings=findings,
        duration_ms=elapsed(),
    )


async def run_review(
    ctx: ReviewContext,
    keys: Optional[List[str]] = None,
    timeout: int = DIMENSION_TIMEOUT_SECONDS,
    on_dimension: Optional[ProgressHook] = None,
) -> ReviewResult:
    """
    Review a procurement across every registered dimension.

    Pass `keys` to run a subset — useful while developing one dimension.
    `on_dimension` fires as each finishes, for streaming progress to the UI.
    """
    specs = all_dimensions()
    if keys:
        wanted = set(keys)
        specs = [s for s in specs if s.key in wanted]

    tasks = [asyncio.create_task(_run_one(spec, ctx, timeout)) for spec in specs]
    results: List[DimensionResult] = []

    for task in asyncio.as_completed(tasks):
        result = await task
        if on_dimension:
            try:
                on_dimension(result)
            except Exception:  # noqa: BLE001 - progress reporting is best-effort
                logger.exception("Progress hook failed for '%s'", result.key)
        results.append(result)

    # as_completed returns in finish order; restore the display order.
    order = {spec.key: i for i, spec in enumerate(specs)}
    results.sort(key=lambda r: order.get(r.key, len(order)))

    findings: List[ReviewFinding] = []
    for result in results:
        findings.extend(result.findings)

    # Ids are assigned here, once, so they are stable across the card list and
    # the final report regardless of which dimension finished first.
    for index, finding in enumerate(findings, start=1):
        finding.id = f"AI-{index:02d}"

    return ReviewResult(
        procurement_ref=ctx.procurement_ref, dimensions=results, findings=findings
    )
