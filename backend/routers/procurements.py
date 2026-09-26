"""
Procurement records and their documents.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from domain import (
    DOC_TYPES,
    Procurement,
    ProcurementCreate,
    ProcurementDocument,
    ProcurementPatch,
    today,
)
from review.schema import empty_counts
from store import get_store
from store.files import (
    delete_document,
    extract_text,
    read_document,
    save_document,
)
from utils.doc_classifier import CLASSIFY_PAGES, classify_many

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


class DocumentPatch(BaseModel):
    doc_type: str


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
    counts = empty_counts()
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


def _store_upload(
    ref: str, filename: str, data: bytes, given: str
) -> tuple[ProcurementDocument, Optional[str]]:
    """
    Store one uploaded file, and read an excerpt from it if its type is unknown.

    Both calls block: save_document counts the pages with PyMuPDF and uploads
    to the bucket, extract_text parses the opening pages. Kept together in one
    synchronous function so the caller can hand the whole thing to a thread.

    Returns the document, and the excerpt to classify or None if the caller
    already told us the type.
    """
    path, pages = save_document(ref, filename, data)

    excerpt = None
    if given not in DOC_TYPES:
        excerpt = extract_text(data, max_pages=CLASSIFY_PAGES, markers=False)

    return (
        ProcurementDocument(
            id=str(uuid.uuid4()),
            name=filename,
            doc_type=given if given in DOC_TYPES else "Other",
            pages=pages,
            uploaded=today(),
            gcs_path=path,
        ),
        excerpt,
    )


@router.post("/{ref}/documents", response_model=Procurement)
async def upload_documents(
    ref: str,
    files: List[UploadFile] = File(...),
    doc_types: Optional[List[str]] = Form(None),
):
    """
    Attach one or more PDFs.

    The type of each document is inferred from its opening pages — the BAC no
    longer picks one on upload — and can be corrected afterwards from the
    documents table. `doc_types` is still honoured, positional against `files`,
    so a caller that already knows the type skips the inference.
    """
    procurement = _require(ref)
    if procurement.status == "finalized":
        raise HTTPException(
            status_code=409, detail="This procurement has been finalized"
        )

    types = doc_types or []

    # Read the request bodies first — that part is properly async — and only
    # then do the blocking work, so the size check still rejects an oversized
    # file before anything of it reaches the bucket.
    pending: List[tuple[str, bytes, str]] = []
    for index, upload in enumerate(files):
        data = await upload.read()
        if not data:
            continue
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{upload.filename} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
            )
        pending.append(
            (
                upload.filename or f"document-{index + 1}.pdf",
                data,
                types[index] if index < len(types) else "",
            )
        )

    # Off the event loop, one thread per file. Uploading and parsing inline
    # held the only loop for the length of every upload in turn, so the rest of
    # the API — the procurement page, /health — queued behind a file transfer.
    # The files are independent, so they go at once; gather preserves their
    # order, which the positional `doc_types` depends on.
    stored = await asyncio.gather(
        *(
            asyncio.to_thread(_store_upload, ref, filename, data, given)
            for filename, data, given in pending
        )
    )

    documents: List[ProcurementDocument] = []
    # Index in `documents` -> excerpt, for the ones nobody told us the type of.
    to_classify: dict[int, str] = {}
    for document, excerpt in stored:
        if excerpt is not None:
            to_classify[len(documents)] = excerpt
        documents.append(document)

    if not documents:
        raise HTTPException(status_code=400, detail="No readable files were uploaded")

    if to_classify:
        positions = list(to_classify)
        inferred = await classify_many(
            [(documents[i].name, to_classify[i]) for i in positions]
        )
        for position, doc_type in zip(positions, inferred):
            documents[position].doc_type = doc_type

    return get_store().add_documents(ref, documents)


@router.get("/{ref}/documents/{document_id}/download")
def download_document(ref: str, document_id: str, inline: bool = False):
    """
    Serve an attached PDF, from the bucket or local disk depending on config.

    `inline=true` renders in the browser instead of prompting a save, which is
    what the Preview modal needs.
    """
    procurement = _require(ref)
    target = next((d for d in procurement.documents if d.id == document_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Unknown document")

    try:
        data = read_document(target.gcs_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=404, detail="The file is no longer available"
        ) from exc

    disposition = "inline" if inline else "attachment"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{target.name}"'
        },
    )


@router.patch("/{ref}/documents/{document_id}", response_model=Procurement)
def retype_document(ref: str, document_id: str, body: DocumentPatch):
    """
    Correct an inferred document type.

    The type steers which documents each review dimension reads, so getting it
    wrong is worth one click to fix rather than a re-upload.
    """
    procurement = _require(ref)
    target = next((d for d in procurement.documents if d.id == document_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Unknown document")
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(
            status_code=422, detail=f"Unknown document type: {body.doc_type}"
        )

    target.doc_type = body.doc_type
    procurement.updated = today()
    return get_store().save_procurement(procurement)


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
