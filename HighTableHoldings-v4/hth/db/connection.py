"""Single SQLite database with transaction-scoped connections.

v3 opened one global connection per file at import time and shared a cursor across the
whole app.  v4 uses one database file and hands out a connection per unit of work via a
context manager, so every write is an atomic transaction and errors roll back cleanly.

Nested ``with db.connect()`` blocks on the same thread reuse the outer connection, so a
service that calls other services (e.g. recording a sale touches accounts, inventory and
the audit log) commits once, atomically, at the outermost block.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.is_memory = str(path) == ":memory:"
        if not self.is_memory:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        # ':memory:' databases vanish per-connection, so keep one open (tests).
        self._memory_conn: sqlite3.Connection | None = self._open() if self.is_memory else None

    def _open(self) -> sqlite3.Connection:
        # timeout: wait for a busy write lock instead of failing while a background
        # thread (dashboard, reports) holds a short transaction.
        conn = sqlite3.connect(":memory:" if self.is_memory else str(self.path), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if not self.is_memory:
            conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection; commit on success, roll back on any exception.

        Re-entrant: an inner block inside an active outer block shares the outer
        connection and defers commit/rollback to the outer block.
        """
        active = getattr(self._local, "conn", None)
        if active is not None:
            yield active
            return

        conn = self._memory_conn if self._memory_conn is not None else self._open()
        self._local.conn = conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._local.conn = None
            if self._memory_conn is None:
                conn.close()

    # Convenience helpers -----------------------------------------------------------
    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute a write statement and return lastrowid."""
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            return int(cur.lastrowid or 0)

    def backup_to(self, dest: Path) -> Path:
        """Consistent online backup using the sqlite backup API."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as src:
            dst = sqlite3.connect(str(dest))
            try:
                src.backup(dst)
            finally:
                dst.close()
        return dest
