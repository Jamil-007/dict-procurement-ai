"""
Ref-based forms endpoints: recommend + generate forms from a procurement
record's own documents, alongside the existing thread-based /forms/* endpoints
(test_forms_api.py) which are unchanged.
"""

from fastapi.testclient import TestClient

import server
from domain import Procurement

client = TestClient(server.app)

REF = "PROC-FORMS-API-001"


class FakeStore:
    def __init__(self, procurement):
        self._procurement = procurement

    def get_procurement(self, ref):
        return self._procurement if ref == REF else None


def _mock_procurement(monkeypatch, exists=True):
    procurement = Procurement(ref=REF, title="Supply of Rack Servers") if exists else None
    import store

    monkeypatch.setattr(store, "get_store", lambda: FakeStore(procurement))


def test_detect_unknown_procurement_404(monkeypatch):
    _mock_procurement(monkeypatch, exists=False)
    r = client.post(f"/procurements/{REF}/forms/detect")
    assert r.status_code == 404


def test_detect_returns_service_output(monkeypatch):
    _mock_procurement(monkeypatch, exists=True)
    monkeypatch.setattr(
        "server.forms_service.detect_for_ref",
        lambda ref: {"doc_types": ["Terms of Reference"], "forms": {"ppmp": {"available": True}}},
    )
    r = client.post(f"/procurements/{REF}/forms/detect")
    assert r.status_code == 200
    body = r.json()
    assert body["doc_types"] == ["Terms of Reference"]
    assert "ppmp" in body["forms"]


def test_generate_unknown_procurement_404(monkeypatch):
    _mock_procurement(monkeypatch, exists=False)
    r = client.post(f"/procurements/{REF}/forms/generate", json={"form_keys": ["ppmp"]})
    assert r.status_code == 404


def test_generate_unknown_form_key_400(monkeypatch):
    _mock_procurement(monkeypatch, exists=True)
    r = client.post(f"/procurements/{REF}/forms/generate", json={"form_keys": ["not-a-form"]})
    assert r.status_code == 400


def test_generate_single_stream(monkeypatch):
    _mock_procurement(monkeypatch, exists=True)
    monkeypatch.setattr(
        "server.forms_service.generate_for_ref", lambda *a, **k: [("PPMP.xlsx", b"PK\x03\x04")]
    )
    r = client.post(f"/procurements/{REF}/forms/generate", json={"form_keys": ["ppmp"]})
    assert r.status_code == 200
    assert "PPMP.xlsx" in r.headers["content-disposition"]


def test_generate_multiple_forms_returns_zip(monkeypatch):
    _mock_procurement(monkeypatch, exists=True)
    monkeypatch.setattr(
        "server.forms_service.generate_for_ref",
        lambda *a, **k: [("PPMP.xlsx", b"PK\x03\x04"), ("BSD.docx", b"PK\x03\x04")],
    )
    r = client.post(f"/procurements/{REF}/forms/generate", json={"form_keys": ["ppmp", "bsd"]})
    assert r.status_code == 200
    assert "procurement_forms.zip" in r.headers["content-disposition"]
    assert r.headers["content-type"] == "application/zip"


def test_generate_error_returns_generic_500(monkeypatch):
    _mock_procurement(monkeypatch, exists=True)
    from agents.doc_generation.service import FormGenerationError

    def boom(*a, **k):
        raise FormGenerationError("boom detail")

    monkeypatch.setattr("server.forms_service.generate_for_ref", boom)
    r = client.post(f"/procurements/{REF}/forms/generate", json={"form_keys": ["market"]})
    assert r.status_code == 500
    assert "boom detail" not in r.text
