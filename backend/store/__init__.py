"""
Store factory.

    from store import get_store
    store = get_store()

Backend chosen by STORE_BACKEND: "memory" locally, "firestore" on Cloud Run.
"""

import os
from functools import lru_cache

from config import settings
from store.base import Store


@lru_cache(maxsize=1)
def get_store() -> Store:
    if settings.STORE_BACKEND == "firestore":
        from store.firestore import FirestoreStore

        # An empty database id means "(default)". In ai-innov-474401 that is a
        # shared database belonging to other applications, and this store
        # batch-deletes and seeds on startup — so refuse rather than write into
        # someone else's data. The emulator is a throwaway, so it is exempt.
        if not settings.FIRESTORE_DATABASE and not os.environ.get(
            "FIRESTORE_EMULATOR_HOST"
        ):
            raise RuntimeError(
                "STORE_BACKEND=firestore requires FIRESTORE_DATABASE. Leaving it "
                "empty targets the shared (default) database, which this project "
                "does not own. Set it to our named database, or set "
                "FIRESTORE_EMULATOR_HOST to work locally."
            )

        return FirestoreStore(
            project=settings.GOOGLE_CLOUD_PROJECT,
            prefix=settings.FIRESTORE_PREFIX,
            database=settings.FIRESTORE_DATABASE,
        )

    from store.memory import MemoryStore

    return MemoryStore()


__all__ = ["Store", "get_store"]
