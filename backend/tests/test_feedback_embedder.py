# backend/tests/test_feedback_embedder.py
import math
from feedback.embedder import local_embed, embed_text
from feedback.models import EMBEDDING_DIM


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def test_local_embed_shape_and_normalized():
    v = local_embed("Department of Information and Communications Technology")
    assert len(v) == EMBEDDING_DIM
    assert abs(_norm(v) - 1.0) < 1e-6


def test_local_embed_deterministic():
    assert local_embed("same text") == local_embed("same text")


def test_local_embed_similar_more_than_different():
    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))
    base = local_embed("procuring entity department of ICT")
    near = local_embed("procuring entity department of ICT budget")
    far = local_embed("banana smoothie recipe with mango")
    assert cos(base, near) > cos(base, far)


def test_empty_text_is_safe_zero_vector():
    v = local_embed("   ")
    assert len(v) == EMBEDDING_DIM
    assert _norm(v) == 0.0  # no divide-by-zero, returns zeros


def test_embed_text_uses_local_when_backend_local(monkeypatch):
    monkeypatch.setattr("feedback.embedder.settings.FEEDBACK_BACKEND", "local")
    assert embed_text("hello") == local_embed("hello")
