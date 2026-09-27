# backend/tests/test_feedback_store_firestore.py
from feedback.models import FeedbackItem
from feedback.firestore_store import FirestoreFeedbackStore


def _item(**kw):
    base = dict(feature="forms", context_key="ppmp", thread_id="t1",
                signal_type="implicit", input_context="ctx")
    base.update(kw)
    return FeedbackItem(**base)


class _FakeDoc:
    def __init__(self, data): self._data = data
    def to_dict(self): return self._data


class _FakeQuery:
    def __init__(self, docs): self._docs = docs; self.calls = {}
    def where(self, *a, **k): return self
    def find_nearest(self, **k): self.calls["find_nearest"] = k; return self
    def get(self): return self._docs


class _FakeCollection:
    def __init__(self, docs): self.added = []; self._query = _FakeQuery(docs)
    def add(self, data): self.added.append(data)
    def where(self, *a, **k): return self._query
    def find_nearest(self, **k): return self._query.find_nearest(**k)


class _FakeClient:
    def __init__(self, docs): self._col = _FakeCollection(docs)
    def collection(self, name): return self._col


def test_record_writes_document_with_vector():
    client = _FakeClient([])
    store = FirestoreFeedbackStore(client=client, collection_name="feedback")
    store.record([_item(field_path="abc", ai_value="A", corrected_value="B")])
    assert len(client._col.added) == 1
    doc = client._col.added[0]
    assert doc["feature"] == "forms" and doc["context_key"] == "ppmp"
    assert doc["field_path"] == "abc"
    assert "embedding" in doc  # stored as a Vector


def test_retrieve_postfilters_field_path_and_trims_topk():
    docs = [
        _FakeDoc({"feature": "forms", "context_key": "ppmp", "field_path": "abc",
                  "thread_id": "t", "signal_type": "implicit", "input_context": "c1",
                  "id": "1", "created_at": 1.0, "metadata": {}}),
        _FakeDoc({"feature": "forms", "context_key": "ppmp", "field_path": "other",
                  "thread_id": "t", "signal_type": "implicit", "input_context": "c2",
                  "id": "2", "created_at": 1.0, "metadata": {}}),
        _FakeDoc({"feature": "forms", "context_key": "ppmp", "field_path": "abc",
                  "thread_id": "t", "signal_type": "implicit", "input_context": "c3",
                  "id": "3", "created_at": 1.0, "metadata": {}}),
    ]
    client = _FakeClient(docs)
    store = FirestoreFeedbackStore(client=client, collection_name="feedback")
    got = store.retrieve("forms", "ppmp", "c1", field_path="abc", top_k=1)
    assert len(got) == 1 and got[0].field_path == "abc"
