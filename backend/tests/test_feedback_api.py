from fastapi.testclient import TestClient
import server
client = TestClient(server.app)

_UUID = "12345678-1234-4234-8234-123456789abc"


def _payload(**kw):
    item = dict(feature="forms", context_key="ppmp", thread_id=_UUID,
                signal_type="explicit", rating="down", field_path="abc",
                ai_value="A", note="wrong lot")
    item.update(kw)
    return {"items": [item]}


def test_feedback_stores_and_returns_count(monkeypatch):
    monkeypatch.setattr("server.settings.FEEDBACK_BANK_ENABLED", True)
    captured = {}
    monkeypatch.setattr("server.feedback_service.record_feedback",
                        lambda items: captured.setdefault("n", len(items)) or len(items))
    monkeypatch.setattr("server.feedback_service.resolve_input_context",
                        lambda tid, provided: "CTX")
    r = client.post("/feedback", json=_payload())
    assert r.status_code == 200
    assert r.json() == {"stored": 1}
    assert captured["n"] == 1


def test_feedback_rejects_empty_items():
    r = client.post("/feedback", json={"items": []})
    assert r.status_code == 422


def test_feedback_rejects_oversized_batch():
    item = {"feature": "forms", "context_key": "ppmp", "thread_id": _UUID,
            "signal_type": "implicit"}
    r = client.post("/feedback", json={"items": [item] * 101})
    assert r.status_code == 422


def test_feedback_rejects_bad_thread_id(monkeypatch):
    monkeypatch.setattr("server.feedback_service.record_feedback", lambda items: len(items))
    r = client.post("/feedback", json=_payload(thread_id="not-a-uuid"))
    assert r.status_code == 400


def test_feedback_inert_when_disabled(monkeypatch):
    monkeypatch.setattr("server.settings.FEEDBACK_BANK_ENABLED", False)
    def boom(*a, **k):
        raise AssertionError("must not be called when disabled")
    monkeypatch.setattr("server.feedback_service.resolve_input_context", boom)
    monkeypatch.setattr("server.feedback_service.record_feedback", boom)
    r = client.post("/feedback", json=_payload())
    assert r.status_code == 200 and r.json() == {"stored": 0}
