"""Application settings and platform-aware paths.

The data directory is resolved in this order:

1. ``HTH_DATA_DIR`` environment variable (useful for tests and portable installs)
2. Windows: ``C:/JBB/v4`` (kept next to the v3 data folder the business already backs up)
3. macOS:   ``~/Library/Application Support/HighTableHoldings``
4. Linux:   ``$XDG_DATA_HOME/HighTableHoldings`` or ``~/.local/share/HighTableHoldings``
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENV_DATA_DIR = "HTH_DATA_DIR"
DB_FILENAME = "hth.db"

# Location of the legacy (v3) SQLite files, used by the migration tool.
LEGACY_DATA_DIR_WINDOWS = Path("C:/JBB/data")


def default_data_dir() -> Path:
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        return Path("C:/JBB/v4")
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
