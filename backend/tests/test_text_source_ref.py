"""
Ref-based text source: read a procurement record's own attached documents
(store/files.py, GCS-or-local) instead of a fresh-upload thread directory.
"""

from domain import Procurement, ProcurementDocument
from agents.doc_generation import text_source

REF = "PROC-FORMS-001"


def make_procurement(documents=None) -> Procurement:
    return Procurement(ref=REF, title="Supply of Rack Servers", documents=documents or [])


def make_doc(name="TOR.pdf", gcs_path="gs://bucket/TOR.pdf", doc_type="Terms of Reference (TOR)") -> ProcurementDocument:
    return ProcurementDocument(id="d1", name=name, doc_type=doc_type, gcs_path=gcs_path)


class FakeStore:
    def __init__(self, procurement):
        self._procurement = procurement

    def get_procurement(self, ref):
        return self._procurement if ref == REF else None


def test_no_procurement_returns_empty(monkeypatch):
    monkeypatch.setattr(text_source, "get_store", lambda: FakeStore(None))
    assert text_source.get_ref_source_documents(REF) == []
    assert text_source.has_ref_source_documents(REF) is False
    assert text_source.get_ref_source_text(REF) == ""


def test_no_documents_returns_empty(monkeypatch):
    monkeypatch.setattr(text_source, "get_store", lambda: FakeStore(make_procurement([])))
    assert text_source.get_ref_source_documents(REF) == []
    assert text_source.has_ref_source_documents(REF) is False


def test_reads_documents_via_store_files(monkeypatch):
    doc = make_doc()
    monkeypatch.setattr(text_source, "get_store", lambda: FakeStore(make_procurement([doc])))
    monkeypatch.setattr(text_source, "read_document", lambda path: f"BYTES({path})".encode())
    monkeypatch.setattr(
        text_source,
        "_extract_document_text",
        lambda data, markers=True: f"TEXT({data.decode()})",
    )

    docs = text_source.get_ref_source_documents(REF)

    assert docs == [{"filename": "TOR.pdf", "text": "TEXT(BYTES(gs://bucket/TOR.pdf))"}]
    assert text_source.has_ref_source_documents(REF) is True
    assert text_source.get_ref_source_text(REF) == "TEXT(BYTES(gs://bucket/TOR.pdf))"


def test_document_without_gcs_path_has_empty_text(monkeypatch):
    doc = make_doc(gcs_path="")
    monkeypatch.setattr(text_source, "get_store", lambda: FakeStore(make_procurement([doc])))

    docs = text_source.get_ref_source_documents(REF)

    assert docs == [{"filename": "TOR.pdf", "text": ""}]
    assert text_source.get_ref_source_text(REF) == ""


def test_read_error_yields_empty_text_not_a_raise(monkeypatch):
    doc = make_doc()
    monkeypatch.setattr(text_source, "get_store", lambda: FakeStore(make_procurement([doc])))

    def boom(path):
        raise RuntimeError("bucket unreachable")

    monkeypatch.setattr(text_source, "read_document", boom)

    docs = text_source.get_ref_source_documents(REF)

    assert docs == [{"filename": "TOR.pdf", "text": ""}]


def test_multiple_documents_joined_in_order(monkeypatch):
    docs_in = [
        make_doc(name="TOR.pdf", gcs_path="gs://b/TOR.pdf"),
        make_doc(name="Market.pdf", gcs_path="gs://b/Market.pdf"),
    ]
    monkeypatch.setattr(text_source, "get_store", lambda: FakeStore(make_procurement(docs_in)))
    monkeypatch.setattr(text_source, "read_document", lambda path: path.encode())
    monkeypatch.setattr(text_source, "_extract_document_text", lambda data, markers=True: f"[{data.decode()}]")

    text = text_source.get_ref_source_text(REF)

    assert text == "[gs://b/TOR.pdf]\n\n[gs://b/Market.pdf]"
