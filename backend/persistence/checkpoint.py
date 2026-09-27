"""The LangGraph checkpointer.

`MemorySaver` loses every in-flight session when the backend restarts, which
also means the human-in-the-loop interrupt cannot be resumed after a reload --
the user's report simply disappears. The SQLite saver writes to the same file
as the archive, so a session and its checkpoints stay together.

`STATE_STORAGE=memory` still selects the in-memory saver, which is what the
tests want.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config import settings


def get_checkpointer():
    storage = (settings.STATE_STORAGE or "memory").lower()

    if storage == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if storage == "postgres":
        # Not wired for the prototype. Falling back silently would leave the
        # operator believing they had Postgres durability.
        raise NotImplementedError(
            "STATE_STORAGE=postgres is not implemented; use 'sqlite' or 'memory'."
        )

    from langgraph.checkpoint.sqlite import SqliteSaver

    path = Path(settings.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False because FastAPI serves requests on a thread pool
    # and the saver is shared across them.
    connection = sqlite3.connect(str(path), check_same_thread=False)
    connection.execute("PRAGMA journal_mode=WAL")
    saver = SqliteSaver(connection)
    saver.setup()
    return saver
