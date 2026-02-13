from __future__ import annotations

from contextlib import contextmanager
import sqlite3
import threading
from typing import Any, Iterator

from .settings import DB_PATH, ensure_runtime_dirs


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    options_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS cells (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    field_key TEXT NOT NULL,
    field_label TEXT NOT NULL,
    field_type TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_identifier TEXT NOT NULL,
    value_raw TEXT,
    value_normalized TEXT,
    confidence REAL NOT NULL,
    confidence_reasons_json TEXT NOT NULL,
    review_state TEXT NOT NULL,
    citation_json TEXT,
    extraction_meta_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_cells_job_field ON cells(job_id, field_key);
CREATE INDEX IF NOT EXISTS idx_cells_job_doc ON cells(job_id, document_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    cell_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    old_review_state TEXT,
    new_review_state TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(cell_id) REFERENCES cells(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_cell ON audit_logs(cell_id, created_at);
"""


class SQLiteStore:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        self._lock = threading.Lock()
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock:
            with self.connect() as conn:
                conn.execute(sql, params)

    def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if not rows:
            return
        with self._lock:
            with self.connect() as conn:
                conn.executemany(sql, rows)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()


store = SQLiteStore()
