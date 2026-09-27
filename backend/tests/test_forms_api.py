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

def test_generate_price_local_ascii_content_disposition(monkeypatch):
    # The real filename contains an em-dash (U+2014) which is not latin-1 encodable.
    emdash_name = "Price Schedule — within the Philippines.docx"
    monkeypatch.setattr("server.forms_service.generate", lambda *a, **k: [(emdash_name, b"PK\x03\x04")])
    r = client.post("/forms/generate", json={"thread_id": "x", "form_keys": ["price_local"]})
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    # Header must be latin-1 encodable (Starlette encodes it as latin-1).
    cd.encode("latin-1")
    assert 'filename="Price_Schedule_within_the_Philippines.docx"' in cd
    # RFC 5987 variant preserves the original name.
    assert "filename*=UTF-8''" in cd

def test_generate_error_returns_generic_500(monkeypatch):
    from forms.service import FormGenerationError
    def boom(*a, **k):
        raise FormGenerationError("boom detail")
    monkeypatch.setattr("server.forms_service.generate", boom)
    r = client.post("/forms/generate", json={"thread_id": "x", "form_keys": ["market"]})
    assert r.status_code == 500
    assert "boom detail" not in r.text  # no leaked internal detail
