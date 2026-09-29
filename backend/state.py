"""The graph state, and the reducers that let parallel nodes write to it.

This lives apart from `agents.py` so that both the legacy advisory agents and
the new checker nodes in `pipeline.py` can import it without either importing
the other.

Everything stored here is plain JSON -- dicts, lists, strings. Pydantic models
are dumped on the way in and revalidated on the way out. That is what lets the
checkpointer be swapped from `MemorySaver` to `SqliteSaver` without the state
becoming unserialisable.
"""

from typing import Annotated, Any, Dict, List, TypedDict


def merge_analysis_results(left: dict, right: dict) -> dict:
    """Deep merge analysis results from parallel agents."""
    if not isinstance(left, dict):
        left = {}
    if not isinstance(right, dict):
        right = {}
    # Deep merge for nested dictionaries
    result = left.copy()
    for key, value in right.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = {**result[key], **value}
        else:
            result[key] = value
    return result


def append_thinking_logs(left: list, right: list) -> list:
    """Concatenate thinking logs from parallel agents."""
    if not isinstance(left, list):
        left = []
    if not isinstance(right, list):
        right = []
    return left + right


def append_findings(left: list, right: list) -> list:
    """Concatenate findings from the rule and consistency checkers.

    Both checker nodes run in the same superstep, so without a reducer one
    would silently overwrite the other and half the findings would vanish.
    Duplicates are dropped on `(rule_id, detail)`: re-running a checker after
    a state update should not double-report the same defect.
    """
    if not isinstance(left, list):
        left = []
    if not isinstance(right, list):
        right = []
    seen = set()
    merged = []
    for finding in left + right:
        if not isinstance(finding, dict):
            continue
        key = (finding.get("rule_id"), finding.get("field"), finding.get("detail"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    return merged


class AgentState(TypedDict, total=False):
    """State structure for the LangGraph workflow."""

    # -- input -------------------------------------------------------------
    original_pdf_paths: List[str]
    thread_id: str

    # -- ingestion ---------------------------------------------------------
    # One entry per uploaded file: the loaded markdown plus provenance
    # (text layer vs vision OCR, pages read, pages skipped).
    loaded_documents: List[Dict[str, Any]]
    # Every document concatenated. Kept because the six advisory agents and
    # the /chat endpoint both read it.
    parsed_text: str

    # -- canonical facts ---------------------------------------------------
    # DocumentFacts dumped to JSON, one per file. The checkers read these and
    # never touch raw text.
    documents: List[Dict[str, Any]]

    # -- routing -----------------------------------------------------------
    routed_checkers: List[str]

    # -- results -----------------------------------------------------------
    findings: Annotated[list, append_findings]
    analysis_results: Annotated[dict, merge_analysis_results]
    compiled_report: str

    # -- human in the loop -------------------------------------------------
    human_feedback: str
    generate_gamma: bool
    gamma_link: str
    thinking_logs: Annotated[list, append_thinking_logs]
