from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence


def now_ms() -> int:
    return int(time.time() * 1000)


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    last_login_at INTEGER
);

CREATE TABLE IF NOT EXISTS backoffice_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator' CHECK(role IN ('admin', 'operator')),
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    last_login_at INTEGER,
    last_assigned_at INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('user', 'admin')),
    subject_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_subject ON sessions(kind, subject_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    last_four TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    created_at INTEGER NOT NULL,
    last_used_at INTEGER,
    revoked_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    protocol TEXT NOT NULL DEFAULT 'both' CHECK(protocol IN ('systemone', 'google', 'both')),
    description TEXT NOT NULL DEFAULT '',
    context_window INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS model_assignments (
    backoffice_user_id TEXT NOT NULL REFERENCES backoffice_users(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    PRIMARY KEY (backoffice_user_id, model_name)
);
CREATE INDEX IF NOT EXISTS idx_assignments_model ON model_assignments(model_name);

CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    protocol TEXT NOT NULL CHECK(protocol IN ('systemone', 'google')),
    status TEXT NOT NULL CHECK(status IN ('queued', 'assigned', 'answered', 'timed_out', 'cancelled')),
    input_json TEXT NOT NULL,
    input_text TEXT NOT NULL DEFAULT '',
    questions_json TEXT NOT NULL,
    raw_request TEXT NOT NULL,
    raw_response TEXT,
    draft_json TEXT,
    answers_json TEXT,
    user_id TEXT,
    api_key_id TEXT,
    assigned_to TEXT,
    answered_by TEXT,
    created_at INTEGER NOT NULL,
    deadline_at INTEGER NOT NULL,
    auto_fill_at INTEGER,
    completed_at INTEGER,
    auto_filled INTEGER NOT NULL DEFAULT 0,
    timeout_seconds INTEGER NOT NULL,
    duration_ms INTEGER,
    error TEXT,
    client_ip TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_model ON requests(model, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_user ON requests(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_assigned ON requests(assigned_to, status);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_kind TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

PRAGMA user_version=1;
"""


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql, params).fetchall())

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self.transaction() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def get_meta(self, key: str) -> str | None:
        row = self.fetch_one("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, encoded),
            )

    def audit(self, actor_kind: str, actor_id: str | None, action: str, target: str | None = None, detail: Any = None) -> None:
        from .security import new_id

        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO audit_logs(id, actor_kind, actor_id, action, target, detail, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id("aud"),
                    actor_kind,
                    actor_id,
                    action,
                    target,
                    json.dumps(detail, ensure_ascii=False) if detail is not None else None,
                    now_ms(),
                ),
            )
