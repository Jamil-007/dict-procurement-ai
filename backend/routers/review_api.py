"""
AI Review endpoints.

The dimension list is served from the registry rather than hardcoded in the
frontend, so adding or renaming a dimension needs no frontend change.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from domain import Procurement
from review import ReviewContext, ReviewDocument, all_dimensions, run_review
from review.schema import (
    Comment,
    Decision,
    DimensionSummary,
    Feedback,
    RejectionReason,
    Severity,
    StoredFinding,
)
from store import get_store
from store.files import extract_text, read_document

logger = logging.getLogger(__name__)

router = APIRouter(tags=["review"])

ACTOR = "BAC Admin"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require(ref: str) -> Procurement:
    procurement = get_store().get_procurement(ref)
    if not procurement:
        raise HTTPException(status_code=404, detail=f"Unknown procurement: {ref}")
    return procurement


#: How many documents to fetch at once. The work is a GCS download followed by
#: a PyMuPDF parse — waiting on the network for most of it — so more threads
#: than cores is the right shape. Capped so a procurement with thirty
#: attachments does not open thirty connections at once.
MAX_DOCUMENT_WORKERS = 8


def _read_for_review(doc) -> Optional[ReviewDocument]:
    """One document, or None if it cannot contribute to the review."""
    if not doc.gcs_path:
        return None
    try:
        # Markers on: findings cite a page rather than guessing at one.
        text = extract_text(read_document(doc.gcs_path))
    except Exception:  # noqa: BLE001 - one unreadable file must not stop the review
        logger.warning("Could not read %s", doc.name, exc_info=True)
        return None
    if not text.strip():
        logger.warning("No readable text in %s", doc.name)
        return None
    return ReviewDocument(
        name=doc.name, doc_type=doc.doc_type, pages=doc.pages, text=text
    )


def _build_context(procurement: Procurement) -> ReviewContext:
    """
    Fetch and parse every attached document.

    Blocking throughout, so call it from a thread. The documents are fetched
    concurrently: read one at a time, five attachments meant five round trips
    to the bucket end to end, and that latency is most of what the reviewer
    waits through before the first model call.
    """
    attachments = procurement.documents or []
    documents: List[ReviewDocument] = []

    if attachments:
        workers = min(len(attachments), MAX_DOCUMENT_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # .map keeps the results in the order given, so the reviewer sees
            # the documents in the order they were attached however the
            # downloads happen to finish.
            documents = [
                parsed
                for parsed in pool.map(_read_for_review, attachments)
                if parsed is not None
            ]

    return ReviewContext(
        procurement_ref=procurement.ref,
        documents=documents,
        meta={
            "title": procurement.title,
            "abc": procurement.abc,
            "mode": procurement.mode,
            "category": procurement.category,
        },
    )


# --- dimensions ---


class DimensionInfo(BaseModel):
    key: str
    label: str
    blurb: str
    owner: str


@router.get("/review/dimensions", response_model=List[DimensionInfo])
def list_dimensions():
    return [
        DimensionInfo(key=d.key, label=d.label, blurb=d.blurb, owner=d.owner)
        for d in all_dimensions()
    ]


# --- running a review ---


class DimensionOutcome(BaseModel):
    key: str
    label: str
    status: str
    findings: int
    # What the dimension says about its own run. Carried through because a
    # count of zero findings is ambiguous on its own — it reads the same
    # whether the dimension checked and found nothing or had nothing to check.
    summary: Optional[DimensionSummary] = None
    research_gaps: List[str] = []
    error: Optional[str] = None
    duration_ms: int


class RunReviewResponse(BaseModel):
    ref: str
    dimensions: List[DimensionOutcome]
    findings: List[StoredFinding]
    counts: dict


@router.post("/procurements/{ref}/review", response_model=RunReviewResponse)
async def run_procurement_review(
    ref: str,
    keys: Optional[List[str]] = Query(
        None, description="Run only these dimensions. Repeat the parameter."
    ),
):
    """
    Review every document attached to this procurement.

    Re-running discards the previous findings, including any BAC decisions
    recorded against them.

    `Query(...)` is load-bearing: FastAPI reads a bare `List[str]` parameter
    as a request body, which silently ignored ?keys= and ran all five.
    """
    procurement = _require(ref)
    if not procurement.documents:
        raise HTTPException(status_code=400, detail="No documents to review")

    store = get_store()
    procurement.review_status = "processing"
    store.save_procurement(procurement)

    try:
        # Off the event loop: _build_context downloads every document from GCS
        # and parses it with PyMuPDF, both synchronous. Run here, it holds the
        # only loop for the whole download — /health stopped answering for over
        # a minute during a review, and the procurement page queued behind it.
        # The store writes around this call block too, but they are one small
        # round trip each rather than tens of seconds.
        context = await asyncio.to_thread(_build_context, procurement)
        if not context.documents:
            raise HTTPException(status_code=400, detail="No readable documents")
        result = await run_review(context, keys=keys)
    except HTTPException:
        procurement.review_status = "none"
        store.save_procurement(procurement)
        raise
    except Exception as exc:  # noqa: BLE001
        procurement.review_status = "none"
        store.save_procurement(procurement)
        logger.exception("Review failed for %s", ref)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    stored = [
        StoredFinding(
            **finding.model_dump(),
            procurement_ref=ref,
            ai_analysis=finding.analysis,
            ai_recommendation=finding.recommendation,
        )
        for finding in result.findings
    ]
    store.replace_findings(ref, stored)

    procurement.review_status = "done"
    store.save_procurement(procurement)

    return RunReviewResponse(
        ref=ref,
        dimensions=[
            DimensionOutcome(
                key=d.key,
                label=d.label,
                status=d.status,
                findings=len(d.findings),
                summary=d.summary,
                research_gaps=d.research_gaps,
                error=d.error,
                duration_ms=d.duration_ms,
            )
            for d in result.dimensions
        ],
        findings=stored,
        counts=result.counts,
    )


# --- findings ---


@router.get("/procurements/{ref}/findings", response_model=List[StoredFinding])
def list_findings(ref: str):
    _require(ref)
    return get_store().list_findings(ref)


class FindingPatch(BaseModel):
    """
    What the BAC can change on a finding.

    Editing any of severity/title/analysis/recommendation marks the finding
    edited and keeps the original AI wording in ai_analysis. Editing is not
    itself a decision — the committee still has to accept or reject.

    Rejecting requires a reason, and "other" requires the note to say what it
    was: the finding disappears from the review and the report, so the record
    of why has to be more than a bare flag.
    """

    severity: Optional[Severity] = None
    title: Optional[str] = None
    analysis: Optional[str] = None
    recommendation: Optional[str] = None
    decision: Optional[Decision] = None
    rejection_reason: Optional[RejectionReason] = None
    rejection_note: Optional[str] = None
    feedback: Optional[Feedback] = None


EDIT_FIELDS = ("severity", "title", "analysis", "recommendation")

REJECTION_NOTE_LIMIT = 500


@router.patch("/procurements/{ref}/findings/{finding_id}", response_model=StoredFinding)
def patch_finding(ref: str, finding_id: str, patch: FindingPatch):
    _require(ref)
    store = get_store()
    finding = store.get_finding(ref, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Unknown finding")

    changes = patch.model_dump(exclude_none=True)

    note = (changes.get("rejection_note") or "").strip()
    if len(note) > REJECTION_NOTE_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Comments cannot exceed {REJECTION_NOTE_LIMIT} characters",
        )
    if "rejection_note" in changes:
        changes["rejection_note"] = note

    if changes.get("decision") == "rejected":
        reason = changes.get("rejection_reason")
        if not reason:
            raise HTTPException(
                status_code=400, detail="A reason is required to reject a finding"
            )
        if reason == "other" and not note:
            raise HTTPException(
                status_code=400,
                detail="Describe the reason when rejecting as “Other”",
            )

    edited = any(field in changes for field in EDIT_FIELDS)

    for key, value in changes.items():
        setattr(finding, key, value)

    # Accepting after a rejection clears the rejection, so a finding brought
    # back into the report does not carry a stale reason with it.
    if changes.get("decision") and changes["decision"] != "rejected":
        finding.rejection_reason = None
        finding.rejection_note = ""

    if edited:
        finding.edited = True

    # Only a decision is attributed. Editing wording or leaving feedback must
    # not re-stamp who decided and when.
    if changes.get("decision"):
        finding.decided_by = ACTOR
        finding.decided_at = _now()

    return store.save_finding(finding)


class CommentCreate(BaseModel):
    text: str


@router.post(
    "/procurements/{ref}/findings/{finding_id}/comments", response_model=StoredFinding
)
def add_comment(ref: str, finding_id: str, body: CommentCreate):
    _require(ref)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    finding = get_store().add_comment(
        ref, finding_id, Comment(text=text, author=ACTOR, at=_now())
    )
    if not finding:
        raise HTTPException(status_code=404, detail="Unknown finding")
    return finding
