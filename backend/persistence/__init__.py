"""Durable storage for sessions, documents and findings.

The graph checkpointer and the archive share one SQLite file, so deleting a
session can remove its checkpoints in the same transaction instead of leaving
orphaned state behind.
"""

from persistence.db import (  # noqa: F401
    delete_session,
    get_session,
    init_db,
    list_sessions,
    save_session,
)
