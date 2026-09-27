import hashlib
import math
import re

from config import settings
from feedback.models import EMBEDDING_DIM

_TOKEN = re.compile(r"[a-z0-9]+")


def local_embed(text: str) -> list[float]:
    """Deterministic bag-of-words hash embedding, L2-normalized. No network,
    no API key — used for local dev and tests. Empty input -> zero vector."""
    vec = [0.0] * EMBEDDING_DIM
    for tok in _TOKEN.findall((text or "").lower()):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBEDDING_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec  # all-zeros: safe, cosine with it is 0
    return [x / norm for x in vec]


def _vertex_embed(text: str) -> list[float]:
    from langchain_google_vertexai import VertexAIEmbeddings

    emb = VertexAIEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        project=settings.FIRESTORE_PROJECT or settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GOOGLE_CLOUD_LOCATION,
    )
    return emb.embed_query(text[:20000])


def embed_text(text: str) -> list[float]:
    """Embed with Vertex in prod (firestore backend), local hash otherwise."""
    if settings.FEEDBACK_BACKEND == "firestore":
        return _vertex_embed(text)
    return local_embed(text)
