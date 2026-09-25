"""
Procurement records and their documents.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from domain import (
    DOC_TYPES,
    Procurement,
    ProcurementCreate,
    ProcurementDocument,
    ProcurementPatch,
    today,
)
from store import get_store
from store.files import delete_document, save_document

router = APIRouter(prefix="/procurements", tags=["procurements"])

# No auth in the MVP. Every action is attributed to the one BAC account.
ACTOR = "BAC Admin"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require(ref: str) -> Procurement:
    procurement = get_store().get_procurement(ref)
    if not procurement:
        raise HTTPException(status_code=404, detail=f"Unknown procurement: {ref}")
    return procurement


class FinalizeResponse(BaseModel):
    ref: str
    status: str
    finalized_at: Optional[str]
    finalized_by: Optional[str]


def _with_counts(procurement: Procurement) -> Procurement:
    """
    Attach the finding tally the list page shows beside each record.

    Always recomputed on read, so a stale copy written to the store is never
    what the client sees.
    """
    counts = {"critical": 0, "warning": 0, "compliant": 0}
    decided = 0
    for finding in get_store().list_findings(procurement.ref):
        if finding.severity in counts:
            counts[finding.severity] += 1
        if finding.decision:
            decided += 1
    procurement.finding_counts = counts
    procurement.decided_count = decided
    return procurement


@router.get("", response_model=List[Procurement])
def list_procurements():
    return [_with_counts(p) for p in get_store().list_procurements()]


@router.post("", response_model=Procurement, status_code=201)
def create_procurement(data: ProcurementCreate):
    return get_store().create_procurement(data)


@router.get("/{ref}", response_model=Procurement)
def get_procurement(ref: str):
    return _with_counts(_require(ref))


@router.delete("/{ref}", status_code=204)
def delete_procurement(ref: str):
    """
    Remove a procurement, its findings and its uploaded files.

    Irreversible — the UI confirms first.
    """
    procurement = _require(ref)
    for doc in procurement.documents:
        if doc.gcs_path:
            delete_document(doc.gcs_path)
    get_store().delete_procurement(ref)


@router.patch("/{ref}", response_model=Procurement)
def patch_procurement(ref: str, patch: ProcurementPatch):
    _require(ref)
    return get_store().patch_procurement(ref, patch)


@router.post("/{ref}/documents", response_model=Procurement)
async def upload_documents(
    ref: str,
    files: List[UploadFile] = File(...),
    doc_types: Optional[List[str]] = Form(None),
):
    """
    Attach one or more PDFs.

    `doc_types` is positional against `files`; anything missing or unrecognised
    falls back to "Other" rather than rejecting the upload.
    """
    procurement = _require(ref)
    if procurement.status == "finalized":
        raise HTTPException(
            status_code=409, detail="This procurement has been finalized"
        )

    types = doc_types or []
    documents: List[ProcurementDocument] = []

    for index, upload in enumerate(files):
        data = await upload.read()
        if not data:
            continue
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{upload.filename} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
            )

        filename = upload.filename or f"document-{index + 1}.pdf"
        path, pages = save_document(ref, filename, data)
        doc_type = types[index] if index < len(types) else "Other"

        documents.append(
            ProcurementDocument(
                id=str(uuid.uuid4()),
                name=filename,
                doc_type=doc_type if doc_type in DOC_TYPES else "Other",
                pages=pages,
                uploaded=today(),
                gcs_path=path,
            )
        )

    if not documents:
        raise HTTPException(status_code=400, detail="No readable files were uploaded")

    return get_store().add_documents(ref, documents)


@router.delete("/{ref}/documents/{document_id}", response_model=Procurement)
def remove_document(ref: str, document_id: str):
    procurement = _require(ref)
    target = next((d for d in procurement.documents if d.id == document_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Unknown document")

    if target.gcs_path:
        delete_document(target.gcs_path)
    return get_store().remove_document(ref, document_id)


@router.post("/{ref}/finalize", response_model=FinalizeResponse)
def finalize(ref: str):
    procurement = _require(ref)
    procurement.status = "finalized"
    procurement.finalized_at = _now()
    procurement.finalized_by = ACTOR
    saved = get_store().save_procurement(procurement)
    return FinalizeResponse(
        ref=saved.ref,
        status=saved.status,
        finalized_at=saved.finalized_at,
        finalized_by=saved.finalized_by,
    )
