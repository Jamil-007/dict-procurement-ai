"""Synthesising the six advisory agents into a single narrative verdict.

Lifted out of the old top-level `agents.py` when the integration branch turned
that module into the `agents/` package. It lives here rather than in
`agents/analysis.py` because only the checker pipeline calls it: the legacy
analysis graph still uses `compiler_agent`, which writes the whole report,
while this returns just the advisory half for `pipeline.compile_node` to fold
in alongside the deterministic findings.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from prompts import COMPILER_PROMPT, RA_12009_DIRECTIVE
from utils.llm_factory import get_llm


def advisory_verdict(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """Ask the LLM to synthesise the six advisory agents into one verdict.

    This is the original compiler, reduced to a pure function. The graph's
    compiler node now builds the verdict from deterministic findings and
    folds this in as advisory commentary, so a failure here degrades the
    narrative rather than the whole report -- hence the dict return with an
    `error` key instead of an exception.
    """
    if not analysis_results:
        return {"error": "No advisory analysis was produced."}

    try:
        llm = get_llm()
        analysis_summary = json.dumps(analysis_results, indent=2)
        prompt = COMPILER_PROMPT.format(
            analysis_results=analysis_summary,
            ra_12009_directive=RA_12009_DIRECTIVE,
        )
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
    except Exception as e:  # network, credentials, rate limit
        return {"error": f"Advisory analysis unavailable: {e}"}

    # The model is asked for JSON but does not always send only JSON.
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    content = content.strip()
    if not content.startswith("{"):
        start_idx = content.find("{")
        if start_idx != -1:
            content = content[start_idx:]
    if not content.endswith("}"):
        end_idx = content.rfind("}")
        if end_idx != -1:
            content = content[: end_idx + 1]

    try:
        verdict = json.loads(content)
    except json.JSONDecodeError as e:
        return {"error": f"Advisory verdict was not valid JSON: {e}"}

    if not isinstance(verdict, dict) or "findings" not in verdict:
        return {"error": "Advisory verdict had an unexpected shape."}
    return verdict


