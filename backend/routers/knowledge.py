"""
Knowledge Hub — the reusable reference library.

Deliberately separate from procurement documents: these are laws, issuances
and forms that apply across every procurement, not evidence belonging to one.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from domain import KNOWLEDGE_CATEGORIES, KnowledgeEntry
from store import get_store
from store.files import read_document

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


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
