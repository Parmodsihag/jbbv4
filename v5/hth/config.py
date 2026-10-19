"""Application settings and platform-aware paths.

The data directory is resolved in this order:

1. ``HTH_DATA_DIR`` environment variable (useful for tests and portable installs)
2. Windows: ``C:/JBB/v5`` (next to the v3 and v4 data folders the business already backs up)
3. macOS:   ``~/Library/Application Support/HighTableHoldings``
4. Linux:   ``$XDG_DATA_HOME/HighTableHoldings`` or ``~/.local/share/HighTableHoldings``

v5 keeps its own folder so v4's data is never changed.  On the first start in the default
Windows folder, v4's database (``C:/JBB/v4/hth.db``) is copied in read-only - see
:func:`previous_version_db` and :func:`copy_previous_version`.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENV_DATA_DIR = "HTH_DATA_DIR"
DB_FILENAME = "hth.db"

# Location of the legacy (v3) SQLite files, used by the migration tool.
LEGACY_DATA_DIR_WINDOWS = Path("C:/JBB/data")
# v4's data folder; its database is copied into v5's on the first start.
PREVIOUS_DATA_DIR_WINDOWS = Path("C:/JBB/v4")


def default_data_dir() -> Path:
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        return Path("C:/JBB/v5")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "HighTableHoldings"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "HighTableHoldings"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path = field(init=False)
    export_dir: Path = field(init=False)
    log_dir: Path = field(init=False)
    backup_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "db_path", self.data_dir / DB_FILENAME)
        object.__setattr__(self, "export_dir", self.data_dir / "exports")
        object.__setattr__(self, "log_dir", self.data_dir / "logs")
        object.__setattr__(self, "backup_dir", self.data_dir / "backups")

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.export_dir, self.log_dir, self.backup_dir):
            d.mkdir(parents=True, exist_ok=True)


def get_settings(data_dir: Path | None = None) -> Settings:
    settings = Settings(data_dir=data_dir or default_data_dir())
    settings.ensure_dirs()
    return settings


def previous_version_db(settings: Settings, previous_dir: Path | None = None) -> Path | None:
    """v4's database when v5 starts for the first time, else None.

    Only for the default location: with ``HTH_DATA_DIR`` set the folder was chosen on
    purpose and nothing is copied into it (``previous_dir`` overrides, for tests)."""
    if previous_dir is None:
        if os.environ.get(ENV_DATA_DIR) or not sys.platform.startswith("win"):
            return None
        previous_dir = PREVIOUS_DATA_DIR_WINDOWS
    candidate = previous_dir / DB_FILENAME
    if settings.db_path.exists() or not candidate.exists():
        return None
    if candidate.resolve() == settings.db_path.resolve():
        return None
    return candidate


def copy_previous_version(source: Path, dest: Path) -> Path:
    """Consistent copy of ``source`` (opened read-only - it is never modified) to ``dest``."""
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    tmp = dest.with_suffix(".copying")
    try:
        tmp.unlink(missing_ok=True)
        dst = sqlite3.connect(str(tmp))
        try:
            src.backup(dst)
        finally:
            dst.close()
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        src.close()
    tmp.replace(dest)  # only a complete copy ever becomes hth.db
    return dest
