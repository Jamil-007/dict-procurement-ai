import json
import math
import sqlite3
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from config import settings
from agents.feedback.embedder import local_embed
from agents.feedback.models import FeedbackItem

_STORED_FIELDS = [
    "id", "created_at", "feature", "context_key", "field_path", "thread_id",
    "source_ref", "signal_type", "ai_value", "corrected_value", "rating",
    "note", "input_context", "metadata",
]


@runtime_checkable
class FeedbackStore(Protocol):
    def record(self, items: list[FeedbackItem]) -> None: ...
    def retrieve(
        self, feature: str, context_key: str, input_context: str,
        field_path: Optional[str] = None, top_k: int = 3,
    ) -> list[FeedbackItem]: ...


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class LocalFeedbackStore:
    """SQLite-backed store with in-process cosine ranking. Dev/test only."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, created_at REAL, feature TEXT,
                    context_key TEXT, field_path TEXT, thread_id TEXT,
                    source_ref TEXT, signal_type TEXT, ai_value TEXT,
                    corrected_value TEXT, rating TEXT, note TEXT,
                    input_context TEXT, metadata TEXT, embedding TEXT
                )"""
            )

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, items: list[FeedbackItem]) -> None:
        with self._conn() as c:
            for it in items:
                emb = local_embed(it.input_context)
                c.execute(
                    "INSERT OR REPLACE INTO feedback "
                    "(id, created_at, feature, context_key, field_path, thread_id, "
                    "source_ref, signal_type, ai_value, corrected_value, rating, "
                    "note, input_context, metadata, embedding) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (it.id, it.created_at, it.feature, it.context_key, it.field_path,
                     it.thread_id, it.source_ref, it.signal_type, it.ai_value,
                     it.corrected_value, it.rating, it.note, it.input_context,
                     json.dumps(it.metadata), json.dumps(emb)),
                )

    def retrieve(self, feature, context_key, input_context,
                 field_path=None, top_k=3):
        query_vec = local_embed(input_context)
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM feedback WHERE feature=? AND context_key=?",
                (feature, context_key),
            ).fetchall()
        scored = []
        for r in rows:
            if field_path is not None and r["field_path"] != field_path:
                continue
            score = cosine(query_vec, json.loads(r["embedding"]))
            scored.append((score, r))
        scored.sort(key=lambda t: t[0], reverse=True)
        out = []
        for _, r in scored[:top_k]:
            data = {k: r[k] for k in _STORED_FIELDS if k != "metadata"}
            data["metadata"] = json.loads(r["metadata"] or "{}")
            out.append(FeedbackItem(**data))
        return out


def get_feedback_store() -> FeedbackStore:
    if settings.FEEDBACK_BACKEND == "firestore":
        from agents.feedback.firestore_store import FirestoreFeedbackStore
        return FirestoreFeedbackStore()
    return LocalFeedbackStore(settings.FEEDBACK_LOCAL_DB)
