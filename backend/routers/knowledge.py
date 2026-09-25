"""
Knowledge Hub — the reusable reference library.

Deliberately separate from procurement documents: these are laws, issuances
and forms that apply across every procurement, not evidence belonging to one.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from domain import KNOWLEDGE_CATEGORIES, KnowledgeEntry
from store import get_store

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
