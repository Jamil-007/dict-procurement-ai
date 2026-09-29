"""
Compliance Checks endpoints — the six assigned features (T1-T6) run against
a procurement record.

Runs the same `checks_graph` LangGraph the Analyst page runs, over the same
ingest and fact extraction. The only differences are where the documents come
from — the record's bucket rather than a session upload — and that the six
advisory agents are left out, because the AI Review tab beside this one
already reads the documents with an LLM.

Findings are stored against the procurement under `engine="checks"`, so the
BAC can accept, reject and comment on them exactly as they do a review
finding, and the accepted ones reach the final report the same way.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from checks import CheckerInfo, all_checkers, to_review_findings
from domain import Procurement
from findings import Finding
from review.schema import StoredFinding, empty_counts
from store import get_store
from store.files import read_document
from utils.storage import sanitize_filename

logger = logging.getLogger(__name__)

router = APIRouter(tags=["checks"])


def _require(ref: str) -> Procurement:
    procurement = get_store().get_procurement(ref)
    if not procurement:
        raise HTTPException(status_code=404, detail=f"Unknown procurement: {ref}")
    return procurement


# --- the catalogue ---


@router.get("/checks/checkers", response_model=List[CheckerInfo])
def list_checkers():
    """
    The six checkers, read from the rulepacks and consistency profiles.

    Served rather than hardcoded in the frontend for the same reason the AI
    Review serves its dimensions: a seventh checker should be a seventh YAML
    file and nothing else.
    """
    return all_checkers()


# --- running the checks ---


class CheckerOutcome(BaseModel):
    """What one checker did on this run."""

    key: str
    task: str
    label: str
    owner: str
    engine: str
    #: "ran" when the router selected it, "skipped" when the uploaded
    #: documents cannot support it. A checker that ran and found nothing is
    #: not the same as one that never ran, and the tab says which.
    status: str
    findings: int
    failed: int
    passed: int
    not_verified: int
    reason: str = ""


class RunChecksResponse(BaseModel):
    ref: str
    checkers: List[CheckerOutcome]
    findings: List[StoredFinding]
    counts: Dict[str, int]
    detected_types: List[str]
    #: The router's own narration, so the tab can show what was decided and
    #: why without re-deriving it.
    log: List[Dict] = []


def _materialize(procurement: Procurement, into: Path) -> List[str]:
    """
    Write the record's documents to a local directory and return the paths.

    The ingest layer reads files, not bytes: a scanned PDF is rendered page by
    page for vision OCR, and the OCR cache is keyed on the file's hash. Giving
    it real paths is what lets a re-run of an unchanged packet cost nothing.

    The original filename is preserved, because it is what every finding cites
    as its evidence and what the reviewer sees in the documents list.
    """
    paths: List[str] = []
    for doc in procurement.documents or []:
        if not doc.gcs_path:
            continue
        try:
            data = read_document(doc.gcs_path)
        except Exception:  # noqa: BLE001 - one unreadable file must not stop the run
            logger.warning("Could not read %s", doc.name, exc_info=True)
            continue
        target = into / sanitize_filename(doc.name)
        target.write_bytes(data)
        paths.append(str(target))
    return paths


def _run_graph(paths: List[str]) -> dict:
    """
    Invoke the checker graph and return the state it stopped at.

    Blocking from end to end — OCR, extraction and the rule engine are all
    synchronous — so callers run it in a thread.

    Imported here rather than at module scope: building the graph loads the
    checkpointer and both engines' YAML, and an endpoint that is never called
    should not make the server slower to start.
    """
    from checks_graph import create_initial_state, graph

    thread_id = str(uuid.uuid4())
    state = create_initial_state(thread_id, paths)
    # The advisory agents are the AI Review tab's job; see pipeline.plan_route.
    state["run_advisory"] = False

    config = {"configurable": {"thread_id": thread_id}}
    # The graph interrupts after report_compiler, so invoke returns the state
    # as it stands there — which is after every checker has written.
    return graph.invoke(state, config)


def _outcomes(
    findings: List[Finding], routed: List[str], detected: List[str]
) -> List[CheckerOutcome]:
    """Per-checker tallies, including the ones that did not run."""
    # A routed node is a graph node ("rule_checks"), whereas a finding names
    # the pack or profile that produced it. Map through the task, which both
    # sides carry.
    ran_rule = "rule_checks" in routed
    ran_consistency = "consistency_checks" in routed

    out: List[CheckerOutcome] = []
    for checker in all_checkers():
        mine = [f for f in findings if f.rule_id.split(".")[0] == checker.key]
        ran = ran_rule if checker.engine == "rule" else ran_consistency
        # A checker whose engine ran but which produced nothing was not
        # applicable to these documents, and should say so rather than
        # reporting a clean bill of health.
        selected = ran and bool(mine)

        reason = ""
        if not selected:
            if not detected:
                reason = "No document could be read."
            elif checker.engine == "consistency":
                reason = (
                    "Needs documents on both sides of the comparison; "
                    "the uploaded set has only one."
                )
            else:
                reason = "No uploaded document is of a type this checker covers."

        out.append(
            CheckerOutcome(
                key=checker.key,
                task=checker.task,
                label=checker.label,
                owner=checker.owner,
                engine=checker.engine,
                status="ran" if selected else "skipped",
                findings=len(mine),
                failed=sum(1 for f in mine if f.is_failure),
                passed=sum(1 for f in mine if f.passed),
                not_verified=sum(1 for f in mine if f.skipped_reason is not None),
                reason=reason,
            )
        )
    return out


@router.post("/procurements/{ref}/checks", response_model=RunChecksResponse)
async def run_checks(ref: str):
    """
    Run every applicable checker over this record's documents.

    Re-running discards the previous checker findings, including any BAC
    decisions recorded against them. The AI Review's findings are untouched.
    """
    procurement = _require(ref)
    if not procurement.documents:
        raise HTTPException(status_code=400, detail="No documents to check")

    store = get_store()
    procurement.check_status = "processing"
    store.save_procurement(procurement)

    workspace = Path(tempfile.mkdtemp(prefix=f"checks-{ref}-"))
    try:
        # Off the event loop: downloads, OCR and extraction are all blocking,
        # and a packet of scanned documents holds it for minutes.
        paths = await asyncio.to_thread(_materialize, procurement, workspace)
        if not paths:
            raise HTTPException(status_code=400, detail="No readable documents")
        state = await asyncio.to_thread(_run_graph, paths)
    except HTTPException:
        procurement.check_status = "none"
        store.save_procurement(procurement)
        raise
    except Exception as exc:  # noqa: BLE001
        procurement.check_status = "none"
        store.save_procurement(procurement)
        logger.exception("Checks failed for %s", ref)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    raw = [Finding(**row) for row in state.get("findings") or []]
    documents = state.get("documents") or []
    detected = sorted(
        {doc.get("doc_type", "") for doc in documents if doc.get("doc_type")}
    )

    stored = [
        StoredFinding(
            **finding.model_dump(),
            procurement_ref=ref,
            engine="checks",
            ai_analysis=finding.analysis,
            ai_recommendation=finding.recommendation,
        )
        for finding in to_review_findings(raw)
    ]
    store.replace_findings(ref, stored, engine="checks")

    procurement.check_status = "done"
    store.save_procurement(procurement)

    counts = empty_counts()
    for finding in stored:
        counts[finding.severity] += 1

    return RunChecksResponse(
        ref=ref,
        checkers=_outcomes(raw, state.get("routed_checkers") or [], detected),
        findings=stored,
        counts=counts,
        detected_types=detected,
        log=state.get("thinking_logs") or [],
    )


@router.get("/procurements/{ref}/checks", response_model=List[StoredFinding])
def list_check_findings(ref: str):
    """This record's checker findings. The AI Review's are served separately."""
    _require(ref)
    return get_store().list_findings(ref, engine="checks")
