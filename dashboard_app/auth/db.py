"""Base SQLite dédiée à l'authentification (jamais la base DuckDB analytique)."""
from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    password_hash TEXT,
    status TEXT NOT NULL CHECK (status IN ('invited', 'active', 'disabled')),
    email_verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT,
    password_changed_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_hash TEXT NOT NULL,
    csrf_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    user_agent TEXT,
    ip TEXT
);

CREATE TABLE IF NOT EXISTS tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('invite', 'reset')),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    event TEXT NOT NULL,
    email TEXT,
    user_id TEXT,
    ip TEXT,
    user_agent TEXT,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_tokens_user_kind ON tokens(user_id, kind);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at);
"""

_USER_COLUMNS = (
    "id", "email", "full_name", "role", "password_hash", "status",
    "email_verified", "created_at", "updated_at", "last_login_at",
    "password_changed_at",
)


class AuthStore:
    """Accès thread-safe à la base d'authentification (connexion unique)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._con = sqlite3.connect(
            str(self.path), check_same_thread=False, timeout=15,
        )
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.execute("PRAGMA foreign_keys=ON")
            self._con.executescript(SCHEMA)
            self._con.commit()

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = {key: row[key] for key in row.keys()}
        if "email_verified" in data:
            data["email_verified"] = bool(data["email_verified"])
        return data

    def close(self) -> None:
        with self._lock:
            self._con.close()

    # --------------------------------------------------------------- users
    def create_user(
        self, *, email: str, full_name: str, role: str, password_hash: str | None,
        status: str, email_verified: bool, created_at: str, updated_at: str,
    ) -> dict[str, Any]:
        user_id = uuid.uuid4().hex
        with self._lock:
            self._con.execute(
                "INSERT INTO users (id, email, full_name, role, password_hash, status,"
                " email_verified, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, email, full_name, role, password_hash, status,
                 int(email_verified), created_at, updated_at),
            )
            self._con.commit()
            row = self._con.execute(
                f"SELECT {', '.join(_USER_COLUMNS)} FROM users WHERE id = ?", (user_id,),
            ).fetchone()
        return self._row(row) or {}

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute(
                f"SELECT {', '.join(_USER_COLUMNS)} FROM users WHERE id = ?", (user_id,),
            ).fetchone()
        return self._row(row)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute(
                f"SELECT {', '.join(_USER_COLUMNS)} FROM users WHERE email = ?", (email,),
            ).fetchone()
        return self._row(row)

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._con.execute(
                f"SELECT {', '.join(_USER_COLUMNS)} FROM users"
                " ORDER BY role DESC, email ASC",
            ).fetchall()
        return [self._row(row) for row in rows if row is not None]  # type: ignore[misc]

    def update_user(self, user_id: str, *, updated_at: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "email", "full_name", "role", "password_hash", "status",
            "email_verified", "last_login_at", "password_changed_at",
        }
        changes = {key: value for key, value in fields.items() if key in allowed}
        if not changes:
            return self.get_user(user_id)
        changes["updated_at"] = updated_at
        if "email_verified" in changes:
            changes["email_verified"] = int(bool(changes["email_verified"]))
        assignments = ", ".join(f"{key} = ?" for key in changes)
        with self._lock:
            self._con.execute(
                f"UPDATE users SET {assignments} WHERE id = ?",
                (*changes.values(), user_id),
            )
            self._con.commit()
        return self.get_user(user_id)

    def count_active_admins(self) -> int:
        with self._lock:
            row = self._con.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin'"
                " AND status = 'active' AND email_verified = 1",
            ).fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------ sessions
    def create_session(
        self, *, session_id: str, user_id: str, refresh_hash: str, csrf_hash: str,
        created_at: str, expires_at: str, user_agent: str, ip: str,
    ) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO sessions (id, user_id, refresh_hash, csrf_hash, created_at,"
                " expires_at, user_agent, ip) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, user_id, refresh_hash, csrf_hash, created_at,
                 expires_at, user_agent, ip),
            )
            self._con.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,),
            ).fetchone()
        return self._row(row)

    def rotate_session(self, session_id: str, *, refresh_hash: str, csrf_hash: str) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE sessions SET refresh_hash = ?, csrf_hash = ? WHERE id = ?",
                (refresh_hash, csrf_hash, session_id),
            )
            self._con.commit()

    def revoke_session(self, session_id: str, *, revoked_at: str) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (revoked_at, session_id),
            )
            self._con.commit()

    def revoke_user_sessions(self, user_id: str, *, revoked_at: str) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (revoked_at, user_id),
            )
            self._con.commit()

    # -------------------------------------------------------------- tokens
    def create_token(
        self, *, user_id: str, kind: str, token_hash: str, created_at: str,
        expires_at: str, created_by: str | None,
    ) -> str:
        token_id = uuid.uuid4().hex
        with self._lock:
            self._con.execute(
                "INSERT INTO tokens (id, user_id, kind, token_hash, created_at,"
                " expires_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (token_id, user_id, kind, token_hash, created_at, expires_at, created_by),
            )
            self._con.commit()
        return token_id

    def get_token_by_hash(self, token_hash: str, kind: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM tokens WHERE token_hash = ? AND kind = ?",
                (token_hash, kind),
            ).fetchone()
        return self._row(row)

    def consume_token(self, token_id: str, *, used_at: str) -> bool:
        with self._lock:
            cursor = self._con.execute(
                "UPDATE tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
                (used_at, token_id),
            )
            self._con.commit()
        return cursor.rowcount == 1

    def invalidate_open_tokens(self, user_id: str, kind: str, *, used_at: str) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE tokens SET used_at = ? WHERE user_id = ? AND kind = ?"
                " AND used_at IS NULL",
                (used_at, user_id, kind),
            )
            self._con.commit()

    # --------------------------------------------------------------- audit
    def log_event(
        self, *, at: str, event: str, email: str | None = None,
        user_id: str | None = None, ip: str | None = None,
        user_agent: str | None = None, detail: str | None = None,
    ) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO audit_log (at, event, email, user_id, ip, user_agent, detail)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (at, event, email, user_id, ip, user_agent, detail),
            )
            self._con.commit()

    def audit_tail(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [self._row(row) for row in rows if row is not None]  # type: ignore[misc]
