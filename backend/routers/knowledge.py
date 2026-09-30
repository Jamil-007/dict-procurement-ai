"""
Knowledge Hub — the reusable reference library.

Deliberately separate from procurement documents: these are laws, issuances
and forms that apply across every procurement, not evidence belonging to one.
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

from rate_limit import upload_rate_limit
from pydantic import BaseModel

from domain import KNOWLEDGE_CATEGORIES, KnowledgeEntry, today
from knowledge.index import IndexAppendError
from knowledge.ingest import ingest_document
from store import get_store
from store.files import read_document, save_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

#: Same ceiling as procurement document uploads (routers/procurements.py).
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class KnowledgeListResponse(BaseModel):
    categories: List[str]
    total: int
    entries: List[KnowledgeEntry]


@router.get("", response_model=KnowledgeListResponse)
def list_knowledge(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    store = get_store()
    entries = store.list_knowledge(category=category, search=search)
    return KnowledgeListResponse(
        categories=KNOWLEDGE_CATEGORIES,
        total=len(store.list_knowledge()),
        entries=entries,
    )


class KnowledgeUploadResponse(BaseModel):
    entry: KnowledgeEntry
    chunks_indexed: int
    searchable: bool
    """
    True only when vectors were actually written for this document's chunks
    — not merely that chunks exist. False for no extractable text, for a
    keyword-only append (embedder unavailable but safe to append), and for a
    refused append (see `message`).
    """
    message: str = ""
    """Explains a degraded or refused indexing outcome; empty on a clean win."""


@router.post(
    "/upload",
    response_model=KnowledgeUploadResponse,
    dependencies=[Depends(upload_rate_limit)],
)
async def upload_knowledge(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
):
    """
    Add one reference PDF to the Knowledge Hub and embed it into the RAG
    index immediately, so AI review can cite it on the very next run.

    Unlike the offline `scripts/build_knowledge_index.py` rebuild, this
    appends to the existing index in place (`knowledge/ingest.py` +
    `knowledge/index.py:append_to_index`) rather than rewriting it, and clears
    the process-local index cache (`knowledge/index.py:reset_cache`) so the
    new content is visible right away.
    """
    if category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    if not title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{file.filename} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
        )

    entry_id = f"kb-{uuid.uuid4().hex[:12]}"
    filename = file.filename or f"{entry_id}.pdf"

    path, pages = save_document(entry_id, filename, data, prefix="knowledge")

    entry = KnowledgeEntry(
        id=entry_id,
        title=title,
        category=category,
        doc_type="",
        date=today(),
        pages=pages,
        gcs_path=path,
    )
    get_store().save_knowledge(entry)

    try:
        result = ingest_document(entry_id, title, filename, data)
    except IndexAppendError as exc:
        # The file and KnowledgeEntry are already saved (see above) — only
        # indexing failed, and it failed *safely*: append_to_index wrote
        # nothing, so every previously-embedded document is still fully
        # searchable. Surface that clearly rather than reporting success.
        logger.warning("Knowledge upload %s was not indexed: %s", entry_id, exc)
        raise HTTPException(
            status_code=502,
            detail=(
                f"{entry.title} was saved to the library, but could not be "
                f"indexed for AI search right now ({exc}). It will not be "
                "found by AI review until the index is rebuilt or the "
                "embedding service is available again."
            ),
        ) from exc

    message = ""
    if not result.chunks:
        message = f"{entry.title} has no extractable text; it is stored but not searchable."
    elif not result.indexed:
        message = (
            f"{entry.title} was indexed for keyword search only; embeddings "
            "were unavailable when it was uploaded."
        )

    return KnowledgeUploadResponse(
        entry=entry,
        chunks_indexed=len(result.chunks),
        searchable=result.indexed,
        message=message,
    )


@router.get("/{entry_id}", response_model=KnowledgeEntry)
def get_knowledge(entry_id: str):
    entry = get_store().get_knowledge(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown reference")
    return entry


@router.get("/{entry_id}/download")
def download_knowledge(entry_id: str, inline: bool = False):
    """
    Serve the reference PDF.

    Entries are seeded as metadata only; the files are put in the bucket
    separately by scripts/upload_knowledge.py. Until that has been run for an
    entry there is nothing to send, which is a 404 with a plain explanation
    rather than an error.
    """
    entry = get_store().get_knowledge(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown reference")
    if not entry.gcs_path:
        raise HTTPException(
            status_code=404,
            detail=f"{entry.title} has not been uploaded to the library yet",
        )

    try:
        data = read_document(entry.gcs_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=404, detail="The file is no longer available"
        ) from exc

    disposition = "inline" if inline else "attachment"
    filename = f"{entry.id}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
