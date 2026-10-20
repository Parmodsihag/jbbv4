"""Automatic daily backups (kept in <data>/backups, pruned to the last N)."""

from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from hth.config import Settings
from hth.db.connection import Database
from hth.services.settings import SettingsService

log = logging.getLogger(__name__)
AUTO_PREFIX = "hth_auto_"


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    schema_version: int
    customers: int
    entries: int
    last_activity: str  # newest audit-log timestamp in the file


class BackupService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.prefs = SettingsService(db, {"backup.auto": "1", "backup.keep": "14"})

    def enabled(self) -> bool:
        return self.prefs.get_bool("backup.auto")

    def set_enabled(self, on: bool) -> None:
        self.prefs.set("backup.auto", "1" if on else "0")

    def keep(self) -> int:
        try:
            return max(1, int(self.prefs.get("backup.keep")))
        except ValueError:
            return 14

    def set_keep(self, n: int) -> None:
        if int(n) < 1:
            raise ValueError("Keep at least 1 backup.")
        self.prefs.set("backup.keep", str(int(n)))

    def auto_backups(self) -> list[Path]:
        return sorted(self.settings.backup_dir.glob(f"{AUTO_PREFIX}*.db"))

    def last_backup(self) -> Path | None:
        files = sorted(self.settings.backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime)
        return files[-1] if files else None

    def manual(self) -> Path:
        dest = self.settings.backup_dir / f"hth_{dt.datetime.now():%Y%m%d_%H%M%S}.db"
        return self.db.backup_to(dest)

    # Restore -----------------------------------------------------------------------------
    @staticmethod
    def inspect(path: Path) -> BackupInfo:
        """Check that ``path`` is a High Table Holdings database; raise ValueError if not."""
        from hth.db.schema import MIGRATIONS

        path = Path(path)
        if not path.is_file():
            raise ValueError(f"{path} does not exist.")
        try:
            conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise ValueError(f"Cannot open {path.name}: {exc}") from exc
        try:
            try:
                ok = conn.execute("PRAGMA quick_check").fetchone()[0]
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            except sqlite3.DatabaseError as exc:
                raise ValueError(f"{path.name} is not a database file ({exc}).") from exc
            if ok != "ok":
                raise ValueError(f"{path.name} is damaged: {ok}")
            if not {"customers", "transactions", "items", "users"} <= tables:
                raise ValueError(f"{path.name} is not a High Table Holdings database.")
            latest = MIGRATIONS[-1][0]
            if version > latest:
                raise ValueError(f"{path.name} was made by a newer version (schema {version} > {latest}).")
            customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            entries = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            last = conn.execute("SELECT MAX(ts) FROM audit_log").fetchone()[0] if "audit_log" in tables else None
        finally:
            conn.close()
        return BackupInfo(path, version, customers, entries, last or "")

    def restore(self, path: Path, username: str) -> Path:
        """Replace the live database with the backup at ``path``.

        The current data is first saved as ``hth_before_restore_<time>.db`` (returned), the
        backup is copied in with SQLite's backup API (consistent, never half-written), and
        any newer schema migrations are applied to it."""
        from hth.db.schema import initialize
        from hth.services.audit import AuditService

        info = self.inspect(path)
        safety = self.db.backup_to(
            self.settings.backup_dir / f"hth_before_restore_{dt.datetime.now():%Y%m%d_%H%M%S}.db"
        )
        src = sqlite3.connect(f"file:{info.path.as_posix()}?mode=ro", uri=True)
        try:
            with self.db.connect() as live:
                src.backup(live)
        finally:
            src.close()
        initialize(self.db)
        AuditService(self.db).log(
            "09", f"restored backup {info.path.name} (previous data saved as {safety.name})", username
        )
        log.warning("database restored from %s; previous data in %s", info.path, safety)
        return safety

    def daily(self, today: dt.date | None = None) -> Path | None:
        """Back up once per calendar day (if enabled); prune old automatic backups."""
        if not self.enabled():
            return None
        today = today or dt.date.today()
        dest = self.settings.backup_dir / f"{AUTO_PREFIX}{today:%Y%m%d}.db"
        if dest.exists():
            return None
        try:
            self.db.backup_to(dest)
        except Exception:  # noqa: BLE001 - never block start-up on a backup problem
            log.exception("automatic backup failed")
            return None
        for old in self.auto_backups()[: -self.keep()]:
            try:
                old.unlink()
            except OSError:
                log.warning("could not prune backup %s", old)
        log.info("automatic backup written: %s", dest.name)
        return dest
