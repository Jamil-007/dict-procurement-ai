"""The archive: sessions, their documents, and their findings.

Separate from the LangGraph checkpointer, which stores opaque execution state
keyed by thread. This stores the *results* in a queryable shape, so the
history panel can list past reviews without replaying a graph, and so the
findings across sessions can be counted later without re-running anything.

Both live in the same SQLite file (`settings.DB_PATH`) so that deleting a
session removes its checkpoints too.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings

_lock = threading.Lock()
_connection: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    thread_id       TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    confidence      INTEGER NOT NULL DEFAULT 0,
    file_count      INTEGER NOT NULL DEFAULT 0,
    finding_count   INTEGER NOT NULL DEFAULT 0,
    high_count      INTEGER NOT NULL DEFAULT 0,
    checkers        TEXT NOT NULL DEFAULT '[]',
    report          TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id       TEXT NOT NULL,
    filename        TEXT NOT NULL DEFAULT '',
    doc_type        TEXT NOT NULL DEFAULT '',
    label           TEXT NOT NULL DEFAULT '',
    confidence      REAL NOT NULL DEFAULT 0,
    pages_read      INTEGER NOT NULL DEFAULT 0,
    total_pages     INTEGER NOT NULL DEFAULT 0,
    ingest_source   TEXT NOT NULL DEFAULT '',
    facts           TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS findings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id       TEXT NOT NULL,
    rule_id         TEXT NOT NULL DEFAULT '',
    task            TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT '',
    severity        TEXT NOT NULL DEFAULT '',
    title           TEXT NOT NULL DEFAULT '',
    detail          TEXT NOT NULL DEFAULT '',
    passed          INTEGER NOT NULL DEFAULT 0,
    skipped_reason  TEXT,
    field           TEXT,
    payload         TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_documents_thread ON documents(thread_id);
CREATE INDEX IF NOT EXISTS idx_findings_thread ON findings(thread_id);
CREATE INDEX IF NOT EXISTS idx_findings_rule ON findings(rule_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""

# LangGraph's SqliteSaver owns these. Named here only so a session delete can
# take its checkpoints with it; missing tables are ignored.
_CHECKPOINT_TABLES = ("checkpoints", "writes", "checkpoint_writes", "checkpoint_blobs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection() -> sqlite3.Connection:
    """One shared connection. SQLite handles the locking; the GIL is not it."""
    global _connection
    with _lock:
        if _connection is None:
            path = Path(settings.DB_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            _connection = sqlite3.connect(str(path), check_same_thread=False)
            _connection.row_factory = sqlite3.Row
            _connection.execute("PRAGMA journal_mode=WAL")
            _connection.executescript(SCHEMA)
            _connection.commit()
        return _connection


def init_db() -> None:
    get_connection()


# -- writing ---------------------------------------------------------------


def save_session(thread_id: str, state: Dict[str, Any]) -> None:
    """Record a completed run.

    Called after the graph reaches its interrupt, so the archive holds the
    report the user was actually shown. Re-saving the same thread replaces
    its documents and findings rather than appending -- a resumed run is the
    same review, not a second one.
    """
    conn = get_connection()

    report_json = state.get("compiled_report") or ""
    try:
        report = json.loads(report_json) if report_json else {}
    except json.JSONDecodeError:
        report = {}

    documents = state.get("documents") or []
    findings = state.get("findings") or []
    summary = report.get("summary") or {}

    title = report.get("title") or _derive_title(documents)
    now = _now()

    with _lock:
        cursor = conn.cursor()
        existing = cursor.execute(
            "SELECT created_at FROM sessions WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        created_at = existing["created_at"] if existing else now

        cursor.execute(
            """
            INSERT INTO sessions (thread_id, created_at, updated_at, title, status,
                                  confidence, file_count, finding_count, high_count,
                                  checkers, report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                updated_at=excluded.updated_at, title=excluded.title,
                status=excluded.status, confidence=excluded.confidence,
                file_count=excluded.file_count, finding_count=excluded.finding_count,
                high_count=excluded.high_count, checkers=excluded.checkers,
                report=excluded.report
            """,
            (
                thread_id,
                created_at,
                now,
                title,
                report.get("status", ""),
                int(report.get("confidence", 0) or 0),
                len(documents),
                int(summary.get("failed", 0) or 0),
                int(summary.get("high", 0) or 0),
                json.dumps(state.get("routed_checkers") or []),
                report_json,
            ),
        )

        cursor.execute("DELETE FROM documents WHERE thread_id = ?", (thread_id,))
        cursor.executemany(
            """INSERT INTO documents (thread_id, filename, doc_type, label, confidence,
                                      pages_read, total_pages, ingest_source, facts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [_document_row(thread_id, d) for d in documents],
        )

        cursor.execute("DELETE FROM findings WHERE thread_id = ?", (thread_id,))
        cursor.executemany(
            """INSERT INTO findings (thread_id, rule_id, task, category, severity,
                                     title, detail, passed, skipped_reason, field,
                                     payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [_finding_row(thread_id, f) for f in findings if isinstance(f, dict)],
        )
        conn.commit()


def _derive_title(documents: List[Dict[str, Any]]) -> str:
    for doc in documents:
        title = (doc.get("project_title") or "").strip()
        if title:
            return title
    if documents:
        return f"{len(documents)} document(s)"
    return "Untitled review"


def _document_row(thread_id: str, doc: Dict[str, Any]) -> tuple:
    source = doc.get("source") or {}
    return (
        thread_id,
        source.get("filename") or source.get("file") or "",
        doc.get("doc_type", ""),
        doc.get("doc_type", ""),
        float(doc.get("doc_type_confidence", 0) or 0),
        int(source.get("pages_read", 0) or 0),
        int(source.get("total_pages", 0) or 0),
        source.get("ingest_source", ""),
        json.dumps(doc),
    )


def _finding_row(thread_id: str, finding: Dict[str, Any]) -> tuple:
    return (
        thread_id,
        finding.get("rule_id", ""),
        finding.get("task", ""),
        finding.get("category", ""),
        finding.get("severity", ""),
        finding.get("title", ""),
        finding.get("detail", ""),
        1 if finding.get("passed") else 0,
        finding.get("skipped_reason"),
        finding.get("field"),
        json.dumps(finding),
    )


# -- reading ---------------------------------------------------------------


def list_sessions(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Most recent first. Summary only -- the report body is not loaded."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT thread_id, created_at, updated_at, title, status, confidence,
                  file_count, finding_count, high_count, checkers
           FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()

    sessions = []
    for row in rows:
        session = dict(row)
        session["checkers"] = json.loads(session.get("checkers") or "[]")
        sessions.append(session)
    return sessions


def get_session(thread_id: str) -> Optional[Dict[str, Any]]:
    """One archived review in full: verdict, documents, findings."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sessions WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    if not row:
        return None

    session = dict(row)
    session["checkers"] = json.loads(session.get("checkers") or "[]")
    try:
        session["report"] = json.loads(session["report"]) if session["report"] else None
    except json.JSONDecodeError:
        session["report"] = None

    session["documents"] = [
        {
            "filename": d["filename"],
            "doc_type": d["doc_type"],
            "confidence": d["confidence"],
            "pages_read": d["pages_read"],
            "total_pages": d["total_pages"],
            "ingest_source": d["ingest_source"],
        }
        for d in conn.execute(
            "SELECT * FROM documents WHERE thread_id = ? ORDER BY id", (thread_id,)
        ).fetchall()
    ]

    # Passing checks are stored -- the row count is the proof of how much was
    # examined -- but they are not returned here. A reopened review should
    # show what needs attention, and the totals are already in the report
    # summary. Query the table directly for the full audit trail.
    session["findings"] = [
        json.loads(f["payload"])
        for f in conn.execute(
            "SELECT payload FROM findings WHERE thread_id = ? AND passed = 0 ORDER BY id",
            (thread_id,),
        ).fetchall()
    ]
    return session


def delete_session(thread_id: str) -> bool:
    """Remove a session, its results, and its graph checkpoints."""
    conn = get_connection()
    with _lock:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM findings WHERE thread_id = ?", (thread_id,))
        cursor.execute("DELETE FROM documents WHERE thread_id = ?", (thread_id,))
        cursor.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
        deleted = cursor.rowcount > 0

        for table in _CHECKPOINT_TABLES:
            try:
                cursor.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            except sqlite3.OperationalError:
                # The checkpointer creates its tables lazily and its schema
                # has changed between versions. A missing table here is not
                # a reason to fail the delete.
                pass
        conn.commit()
    return deleted
