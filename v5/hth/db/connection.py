"""Single SQLite database with transaction-scoped connections.

v3 opened one global connection per file at import time and shared a cursor across the
whole app.  v4 uses one database file and hands out a connection per unit of work via a
context manager, so every write is an atomic transaction and errors roll back cleanly.

Nested ``with db.connect()`` blocks on the same thread reuse the outer connection, so a
service that calls other services (e.g. recording a sale touches accounts, inventory and
the audit log) commits once, atomically, at the outermost block.

Each thread keeps its connection open between units of work (v5.6).  Opening one costs
about 300 times a small query - on Windows it creates the WAL side files, and closing the
last one checkpoints and deletes them again, under the virus scanner's eyes - and a screen
makes dozens of small queries.  The unit of work is unchanged: commit or roll back at the
outermost block, exactly as before.  :meth:`Database.close` closes them all (at exit, and
before the file itself is copied over or deleted).
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
        self._lock = threading.Lock()
        self._kept: dict[int, sqlite3.Connection] = {}  # thread ident -> its open connection
        self._generation = 0  # close() moves it on: connections kept before are not reused
        self._version = 0

    @property
    def version(self) -> int:
        """Goes up with every committed change.  A screen that remembers the version it was
        filled at can skip reloading while nothing has been written since."""
        return self._version

    def _open(self) -> sqlite3.Connection:
        # timeout: wait for a busy write lock instead of failing while a background
        # thread (dashboard, reports) holds a short transaction.
        conn = sqlite3.connect(":memory:" if self.is_memory else str(self.path), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if not self.is_memory:
            conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _thread_conn(self) -> sqlite3.Connection:
        """This thread's kept connection, opened on first use."""
        if self._memory_conn is not None:
            return self._memory_conn
        conn = getattr(self._local, "kept", None)
        if conn is not None and getattr(self._local, "generation", None) == self._generation:
            return conn
        conn = self._open()
        self._local.kept, self._local.generation = conn, self._generation
        with self._lock:
            alive = {t.ident for t in threading.enumerate()}
            for ident in [i for i in self._kept if i not in alive]:
                _quietly_close(self._kept.pop(ident))  # its thread has finished
            replaced = self._kept.get(threading.get_ident())
            if replaced is not None and replaced is not conn:
                _quietly_close(replaced)
            self._kept[threading.get_ident()] = conn
        return conn

    def _forget_thread_conn(self, conn: sqlite3.Connection) -> None:
        """A connection that failed even to roll back is not used again."""
        self._local.kept = None
        with self._lock:
            if self._kept.get(threading.get_ident()) is conn:
                del self._kept[threading.get_ident()]
        _quietly_close(conn)

    def close(self) -> None:
        """Close every kept connection; the next unit of work opens a fresh one."""
        if self._memory_conn is not None:
            return
        with self._lock:
            self._generation += 1
            kept, self._kept = list(self._kept.values()), {}
        for conn in kept:
            _quietly_close(conn)

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

        conn = self._thread_conn()
        self._local.conn = conn
        changes = conn.total_changes
        try:
            yield conn
            conn.commit()
            if conn.total_changes != changes:
                with self._lock:
                    self._version += 1
        except Exception:
            try:
                conn.rollback()
            except sqlite3.Error:
                if conn is not self._memory_conn:
                    self._forget_thread_conn(conn)
            raise
        finally:
            self._local.conn = None

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


def _quietly_close(conn: sqlite3.Connection) -> None:
    try:
        conn.close()
    except sqlite3.Error:
        pass
