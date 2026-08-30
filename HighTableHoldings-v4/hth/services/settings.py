"""Key/value application settings stored in the database (shared by all users)."""

from __future__ import annotations

from hth.db.connection import Database


class SettingsService:
    def __init__(self, db: Database, defaults: dict[str, str] | None = None):
        self.db = db
        self.defaults = dict(defaults or {})

    def get(self, key: str, default: str | None = None) -> str:
        row = self.db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        if row is not None:
            return str(row["value"])
        if default is not None:
            return default
        return self.defaults.get(key, "")

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def get_bool(self, key: str) -> bool:
        return self.get(key).strip().lower() in ("1", "true", "yes", "on")

    def get_list(self, key: str) -> list[str]:
        return [x.strip().upper() for x in self.get(key).split(",") if x.strip()]

    def set_list(self, key: str, values) -> None:
        self.set(key, ",".join(sorted({str(v).strip().upper() for v in values if str(v).strip()})))

    def get_floats(self, key: str) -> list[float]:
        return [float(x) for x in self.get(key).split(",") if x.strip()]
