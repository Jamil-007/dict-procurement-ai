from typing import Optional

from config import settings
from feedback.embedder import embed_text
from feedback.models import FeedbackItem

_ITEM_FIELDS = [
    "id", "created_at", "feature", "context_key", "field_path", "thread_id",
    "source_ref", "signal_type", "ai_value", "corrected_value", "rating",
    "note", "input_context", "metadata",
]


class FirestoreFeedbackStore:
    """Firestore Native store using native vector search (find_nearest)."""

    def __init__(self, client=None, collection_name: Optional[str] = None):
        if client is None:
            from google.cloud import firestore
            client = firestore.Client(
                project=settings.FIRESTORE_PROJECT or settings.GOOGLE_CLOUD_PROJECT
            )
        self._client = client
        self._name = collection_name or settings.FIRESTORE_COLLECTION

    def _col(self):
        return self._client.collection(self._name)

    def record(self, items: list[FeedbackItem]) -> None:
        from google.cloud.firestore_v1.vector import Vector

        col = self._col()
        for it in items:
            doc = it.model_dump()
            doc["embedding"] = Vector(embed_text(it.input_context))
            col.add(doc)

    def retrieve(self, feature, context_key, input_context,
                 field_path=None, top_k=3):
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
        from google.cloud.firestore_v1.vector import Vector

        limit = max(1, top_k) * max(1, settings.FEEDBACK_OVERSAMPLE)
        query = (
            self._col()
            .where("feature", "==", feature)
            .where("context_key", "==", context_key)
            .find_nearest(
                vector_field="embedding",
                query_vector=Vector(embed_text(input_context)),
                distance_measure=DistanceMeasure.COSINE,
                limit=limit,
            )
        )
        out = []
        for doc in query.get():
            data = doc.to_dict()
            if field_path is not None and data.get("field_path") != field_path:
                continue
            out.append(FeedbackItem(**{k: data.get(k) for k in _ITEM_FIELDS}))
            if len(out) >= top_k:
                break
        return out
