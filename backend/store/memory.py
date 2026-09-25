"""
In-process store for local development.

Data lives for the lifetime of the process. Fine on a laptop, useless on Cloud
Run — set STORE_BACKEND=firestore there.
"""

import json
import re
import threading
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from domain import (
    KnowledgeEntry,
    Procurement,
    ProcurementCreate,
    ProcurementDocument,
    ProcurementPatch,
    today,
)
from review.schema import Comment, StoredFinding
from store.base import Store

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_seed.json"


def load_knowledge_seed() -> List[KnowledgeEntry]:
    with open(SEED_PATH, encoding="utf-8") as handle:
        return [KnowledgeEntry(**row) for row in json.load(handle)]


class MemoryStore(Store):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._procurements: Dict[str, Procurement] = {}
        self._findings: Dict[str, List[StoredFinding]] = {}
        self._knowledge: List[KnowledgeEntry] = load_knowledge_seed()

    # --- procurements ---

    def list_procurements(self) -> List[Procurement]:
        with self._lock:
            return sorted(
                self._procurements.values(), key=lambda p: p.ref, reverse=True
            )

    def get_procurement(self, ref: str) -> Optional[Procurement]:
        with self._lock:
            return self._procurements.get(ref)

    def next_ref(self) -> str:
        year = date.today().year
        prefix = f"PROC-{year}-"
        with self._lock:
            used = [
                int(m.group(1))
                for ref in self._procurements
                if (m := re.fullmatch(rf"{prefix}(\d+)", ref))
            ]
        return f"{prefix}{max(used, default=0) + 1:03d}"

    def create_procurement(self, data: ProcurementCreate) -> Procurement:
        procurement = Procurement(ref=self.next_ref(), **data.model_dump())
        with self._lock:
            self._procurements[procurement.ref] = procurement
            self._findings[procurement.ref] = []
        return procurement

    def patch_procurement(
        self, ref: str, patch: ProcurementPatch
    ) -> Optional[Procurement]:
        with self._lock:
            procurement = self._procurements.get(ref)
            if not procurement:
                return None
            for key, value in patch.model_dump(exclude_none=True).items():
                setattr(procurement, key, value)
            procurement.updated = today()
            return procurement

    def save_procurement(self, procurement: Procurement) -> Procurement:
        procurement.updated = today()
        with self._lock:
            self._procurements[procurement.ref] = procurement
        return procurement

    def delete_procurement(self, ref: str) -> bool:
        """Drops the record and its findings. Files are the caller's problem."""
        with self._lock:
            self._findings.pop(ref, None)
            return self._procurements.pop(ref, None) is not None

    # --- documents ---

    def add_documents(
        self, ref: str, documents: List[ProcurementDocument]
    ) -> Optional[Procurement]:
        with self._lock:
            procurement = self._procurements.get(ref)
            if not procurement:
                return None
            procurement.documents.extend(documents)
            procurement.updated = today()
            return procurement

    def remove_document(self, ref: str, document_id: str) -> Optional[Procurement]:
        with self._lock:
            procurement = self._procurements.get(ref)
            if not procurement:
                return None
            procurement.documents = [
                d for d in procurement.documents if d.id != document_id
            ]
            procurement.updated = today()
            return procurement

    # --- findings ---

    def list_findings(self, ref: str) -> List[StoredFinding]:
        with self._lock:
            return list(self._findings.get(ref, []))

    def replace_findings(
        self, ref: str, findings: List[StoredFinding]
    ) -> List[StoredFinding]:
        with self._lock:
            self._findings[ref] = list(findings)
            return list(findings)

    def get_finding(self, ref: str, finding_id: str) -> Optional[StoredFinding]:
        with self._lock:
            for finding in self._findings.get(ref, []):
                if finding.id == finding_id:
                    return finding
        return None

    def save_finding(self, finding: StoredFinding) -> StoredFinding:
        with self._lock:
            bucket = self._findings.setdefault(finding.procurement_ref, [])
            for index, existing in enumerate(bucket):
                if existing.id == finding.id:
                    bucket[index] = finding
                    break
            else:
                bucket.append(finding)
        return finding

    def add_comment(
        self, ref: str, finding_id: str, comment: Comment
    ) -> Optional[StoredFinding]:
        finding = self.get_finding(ref, finding_id)
        if not finding:
            return None
        finding.comments.append(comment)
        return self.save_finding(finding)

    # --- knowledge hub ---

    def list_knowledge(
        self, category: Optional[str] = None, search: Optional[str] = None
    ) -> List[KnowledgeEntry]:
        rows = self._knowledge
        if category and category != "all":
            rows = [r for r in rows if r.category == category]
        if search:
            needle = search.lower()
            rows = [
                r
                for r in rows
                if needle in f"{r.title} {r.subtitle} {r.excerpt}".lower()
            ]
        return list(rows)

    def get_knowledge(self, entry_id: str) -> Optional[KnowledgeEntry]:
        for entry in self._knowledge:
            if entry.id == entry_id:
                return entry
        return None
