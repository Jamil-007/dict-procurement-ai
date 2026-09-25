"""
Firestore-backed store for Cloud Run.

Collections (prefix configurable so staging and prod can share a database):
    {prefix}procurements/{ref}
    {prefix}findings/{ref}__{finding_id}
    {prefix}knowledge/{id}

Not exercised locally — there are no credentials on a dev laptop. Run against
the emulator with FIRESTORE_EMULATOR_HOST, or deploy to staging.
"""

import re
import threading
from datetime import date
from typing import List, Optional

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
from store.memory import load_knowledge_seed


class FirestoreStore(Store):
    def __init__(self, project: str = "", prefix: str = "") -> None:
        from google.cloud import firestore  # imported lazily: prod-only dependency

        self._db = firestore.Client(project=project) if project else firestore.Client()
        self._prefix = prefix
        self._ref_lock = threading.Lock()

    def _col(self, name: str):
        return self._db.collection(f"{self._prefix}{name}")

    @staticmethod
    def _finding_key(ref: str, finding_id: str) -> str:
        return f"{ref}__{finding_id}"

    # --- procurements ---

    def list_procurements(self) -> List[Procurement]:
        docs = self._col("procurements").stream()
        rows = [Procurement(**doc.to_dict()) for doc in docs]
        return sorted(rows, key=lambda p: p.ref, reverse=True)

    def get_procurement(self, ref: str) -> Optional[Procurement]:
        snapshot = self._col("procurements").document(ref).get()
        return Procurement(**snapshot.to_dict()) if snapshot.exists else None

    def next_ref(self) -> str:
        """
        Sequential per year. Firestore has no autoincrement, so this scans the
        year's refs under a lock. Fine at BAC volumes; revisit if two people
        ever create a procurement in the same second.
        """
        prefix = f"PROC-{date.today().year}-"
        with self._ref_lock:
            used = [
                int(m.group(1))
                for doc in self._col("procurements").stream()
                if (m := re.fullmatch(rf"{prefix}(\d+)", doc.id))
            ]
            return f"{prefix}{max(used, default=0) + 1:03d}"

    def create_procurement(self, data: ProcurementCreate) -> Procurement:
        procurement = Procurement(ref=self.next_ref(), **data.model_dump())
        self._col("procurements").document(procurement.ref).set(
            procurement.model_dump()
        )
        return procurement

    def patch_procurement(
        self, ref: str, patch: ProcurementPatch
    ) -> Optional[Procurement]:
        procurement = self.get_procurement(ref)
        if not procurement:
            return None
        for key, value in patch.model_dump(exclude_none=True).items():
            setattr(procurement, key, value)
        return self.save_procurement(procurement)

    def save_procurement(self, procurement: Procurement) -> Procurement:
        procurement.updated = today()
        self._col("procurements").document(procurement.ref).set(
            procurement.model_dump()
        )
        return procurement

    def delete_procurement(self, ref: str) -> bool:
        doc = self._col("procurements").document(ref)
        if not doc.get().exists:
            return False

        batch = self._db.batch()
        for finding in (
            self._col("findings").where("procurement_ref", "==", ref).stream()
        ):
            batch.delete(finding.reference)
        batch.delete(doc)
        batch.commit()
        return True

    # --- documents ---

    def add_documents(
        self, ref: str, documents: List[ProcurementDocument]
    ) -> Optional[Procurement]:
        procurement = self.get_procurement(ref)
        if not procurement:
            return None
        procurement.documents.extend(documents)
        return self.save_procurement(procurement)

    def remove_document(self, ref: str, document_id: str) -> Optional[Procurement]:
        procurement = self.get_procurement(ref)
        if not procurement:
            return None
        procurement.documents = [d for d in procurement.documents if d.id != document_id]
        return self.save_procurement(procurement)

    # --- findings ---

    def list_findings(self, ref: str) -> List[StoredFinding]:
        docs = (
            self._col("findings").where("procurement_ref", "==", ref).stream()
        )
        rows = [StoredFinding(**doc.to_dict()) for doc in docs]
        return sorted(rows, key=lambda f: f.id)

    def replace_findings(
        self, ref: str, findings: List[StoredFinding]
    ) -> List[StoredFinding]:
        batch = self._db.batch()
        for doc in self._col("findings").where("procurement_ref", "==", ref).stream():
            batch.delete(doc.reference)
        for finding in findings:
            key = self._finding_key(ref, finding.id)
            batch.set(self._col("findings").document(key), finding.model_dump())
        batch.commit()
        return findings

    def get_finding(self, ref: str, finding_id: str) -> Optional[StoredFinding]:
        snapshot = (
            self._col("findings").document(self._finding_key(ref, finding_id)).get()
        )
        return StoredFinding(**snapshot.to_dict()) if snapshot.exists else None

    def save_finding(self, finding: StoredFinding) -> StoredFinding:
        key = self._finding_key(finding.procurement_ref, finding.id)
        self._col("findings").document(key).set(finding.model_dump())
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
        query = self._col("knowledge")
        if category and category != "all":
            query = query.where("category", "==", category)
        rows = [KnowledgeEntry(**doc.to_dict()) for doc in query.stream()]
        if search:
            # Firestore has no substring search; the Hub is small enough to
            # filter in process. Move to a search service if it grows.
            needle = search.lower()
            rows = [
                r
                for r in rows
                if needle in f"{r.title} {r.subtitle} {r.excerpt}".lower()
            ]
        return rows

    def get_knowledge(self, entry_id: str) -> Optional[KnowledgeEntry]:
        snapshot = self._col("knowledge").document(entry_id).get()
        return KnowledgeEntry(**snapshot.to_dict()) if snapshot.exists else None

    # --- setup ---

    def seed_knowledge(self, overwrite: bool = False) -> int:
        """Load the Knowledge Hub from data/knowledge_seed.json. Idempotent."""
        written = 0
        for entry in load_knowledge_seed():
            doc = self._col("knowledge").document(entry.id)
            if overwrite or not doc.get().exists:
                doc.set(entry.model_dump())
                written += 1
        return written
