"""
Store factory.

    from store import get_store
    store = get_store()

Backend chosen by STORE_BACKEND: "memory" locally, "firestore" on Cloud Run.
"""

from functools import lru_cache

from config import settings
from store.base import Store


@lru_cache(maxsize=1)
def get_store() -> Store:
    if settings.STORE_BACKEND == "firestore":
        from store.firestore import FirestoreStore

        return FirestoreStore(
            project=settings.GOOGLE_CLOUD_PROJECT,
            prefix=settings.FIRESTORE_PREFIX,
        )

    from store.memory import MemoryStore

    return MemoryStore()


__all__ = ["Store", "get_store"]
