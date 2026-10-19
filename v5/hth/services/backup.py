"""Automatic daily backups (kept in <data>/backups, pruned to the last N)."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from hth.config import Settings
from hth.db.connection import Database
from hth.services.settings import SettingsService

log = logging.getLogger(__name__)
AUTO_PREFIX = "hth_auto_"


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
