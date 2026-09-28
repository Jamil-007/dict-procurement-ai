"""
Task 4: a document uploaded through the Forms tab's "missing document" prompt
must go through the existing procurement upload path (routers/procurements.py
upload_documents) so it lands in procurement.documents — after which the
ref-based resolver (Task 3, agents/doc_generation/text_source.py) sees it for
generation, with no separate forms-only storage.
"""

import asyncio

from domain import Procurement
from routers import procurements
from agents.doc_generation import text_source

REF = "PROC-FORMS-TASK4"


class FakeUpload:
    def __init__(self, filename: str):
        self.filename = filename

    async def read(self):
        return b"%PDF-1.4 fake cost breakdown"


class FakeStore:
    """Shared between the upload path and the ref-based text source, exactly as
    the real store is: one Firestore/MemoryStore record is what both read."""

    def __init__(self, procurement):
        self._procurement = procurement

    def get_procurement(self, ref):
        return self._procurement if ref == REF else None

    def add_documents(self, ref, documents):
        self._procurement.documents = list(self._procurement.documents) + list(documents)
        return self._procurement


def test_uploaded_missing_doc_is_visible_to_ref_based_generation(monkeypatch):
    procurement = Procurement(ref=REF, title="Supply of Rack Servers", documents=[])
    fake_store = FakeStore(procurement)

    # --- Task 4: persist the upload via the existing procurement path ---
    monkeypatch.setattr(
        procurements,
        "save_document",
        lambda ref, filename, data: (f"gs://bucket/{ref}/{filename}", 3),
    )
    monkeypatch.setattr(
        procurements, "extract_text", lambda data, max_pages=0, markers=True: "Detailed Cost Breakdown of items."
    )
    monkeypatch.setattr(procurements, "get_store", lambda: fake_store)

    async def classified(pairs):
        return ["Detailed Cost Breakdown"] * len(pairs)

    monkeypatch.setattr(procurements, "classify_many", classified)

    result = asyncio.run(
        procurements.upload_documents(
            REF, files=[FakeUpload("Cost Breakdown.pdf")], doc_types=None
        )
    )

    assert len(result.documents) == 1
    uploaded = result.documents[0]
    assert uploaded.name == "Cost Breakdown.pdf"
    assert uploaded.doc_type == "Detailed Cost Breakdown"
    assert uploaded.gcs_path == f"gs://bucket/{REF}/Cost Breakdown.pdf"

    # --- Task 3: the ref-based resolver reads it straight back off the record ---
    monkeypatch.setattr(text_source, "get_store", lambda: fake_store)
    monkeypatch.setattr(text_source, "read_document", lambda path: f"BYTES({path})".encode())
    monkeypatch.setattr(
        text_source, "_extract_document_text", lambda data, markers=True: data.decode()
    )

    docs = text_source.get_ref_source_documents(REF)

    assert docs == [
        {
            "filename": "Cost Breakdown.pdf",
            "text": f"BYTES(gs://bucket/{REF}/Cost Breakdown.pdf)",
        }
    ]
