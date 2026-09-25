"""
Storage interface.

Two implementations: MemoryStore for local development and tests,
FirestoreStore for Cloud Run. Routers depend on this class only, so swapping
backends is a config change.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain import (
    KnowledgeEntry,
    Procurement,
    ProcurementCreate,
    ProcurementDocument,
    ProcurementPatch,
)
from review.schema import Comment, StoredFinding


class Store(ABC):
    # --- procurements ---

    @abstractmethod
    def list_procurements(self) -> List[Procurement]: ...

    @abstractmethod
    def get_procurement(self, ref: str) -> Optional[Procurement]: ...

    @abstractmethod
    def create_procurement(self, data: ProcurementCreate) -> Procurement: ...

    @abstractmethod
    def patch_procurement(
        self, ref: str, patch: ProcurementPatch
    ) -> Optional[Procurement]: ...

    @abstractmethod
    def save_procurement(self, procurement: Procurement) -> Procurement:
        """Write a whole record. Used for status and review_status changes."""

    @abstractmethod
    def delete_procurement(self, ref: str) -> bool:
        """Remove the record and its findings. Returns False if it was absent."""

    # --- documents ---

    @abstractmethod
    def add_documents(
        self, ref: str, documents: List[ProcurementDocument]
    ) -> Optional[Procurement]: ...

    @abstractmethod
    def remove_document(self, ref: str, document_id: str) -> Optional[Procurement]: ...

    # --- findings ---

    @abstractmethod
    def list_findings(self, ref: str) -> List[StoredFinding]: ...

    @abstractmethod
    def replace_findings(
        self, ref: str, findings: List[StoredFinding]
    ) -> List[StoredFinding]:
        """Swap in a fresh review, discarding the previous run's findings."""

    @abstractmethod
    def get_finding(self, ref: str, finding_id: str) -> Optional[StoredFinding]: ...

    @abstractmethod
    def save_finding(self, finding: StoredFinding) -> StoredFinding: ...

    @abstractmethod
    def add_comment(
        self, ref: str, finding_id: str, comment: Comment
    ) -> Optional[StoredFinding]: ...

    # --- knowledge hub ---

    @abstractmethod
    def list_knowledge(
        self, category: Optional[str] = None, search: Optional[str] = None
    ) -> List[KnowledgeEntry]: ...

    @abstractmethod
    def get_knowledge(self, entry_id: str) -> Optional[KnowledgeEntry]: ...
