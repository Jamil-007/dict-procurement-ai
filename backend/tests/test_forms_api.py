from fastapi.testclient import TestClient
import server
client = TestClient(server.app)

def test_catalog():
    r = client.get("/forms/catalog")
    assert r.status_code == 200 and len(r.json()) == 10

def test_generate_single_stream(monkeypatch):
    monkeypatch.setattr("server.forms_service.generate", lambda *a, **k: [("PPMP.xlsx", b"PK\x03\x04")])
    r = client.post("/forms/generate", json={"thread_id": "x", "form_keys": ["ppmp"]})
    assert r.status_code == 200
    assert "PPMP.xlsx" in r.headers["content-disposition"]
