"""Audit log - the v3 'daily notes' database, now one indexed table."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode


@dataclass(frozen=True)
class AuditEntry:
    id: int
    ts: str
    date: str
    username: str
    code: str
    message: str

    @property
    def code_label(self) -> str:
        try:
            return AuditCode(self.code).label
        except ValueError:
            return self.code


class AuditService:
    def __init__(self, db: Database):
        self.db = db

    def log(self, code: AuditCode | str, message: str, username: str = "system") -> int:
        code_value = code.value if isinstance(code, AuditCode) else str(code)
        return self.db.execute(
            "INSERT INTO audit_log (username, code, message) VALUES (?, ?, ?)",
            (username, code_value, message),
        )

    def entries(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        code: str | None = None,
        search: str | None = None,
        limit: int = 1000,
    ) -> list[AuditEntry]:
        clauses, params = [], []
        if date_from:
            clauses.append("date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("date <= ?")
            params.append(date_to)
        if code:
            clauses.append("code = ?")
            params.append(code)
        if search:
            clauses.append("(message LIKE ? OR username LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.fetchall(f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?", (*params, limit))
        return [AuditEntry(**dict(r)) for r in rows]

    def daily_counts(self, days: int = 7) -> list[tuple[str, int]]:
        """[(YYYY-MM-DD, entries)] for the last ``days`` days, oldest first."""
        today = dt.date.today()
        dates = [today - dt.timedelta(days=i) for i in range(days - 1, -1, -1)]
        rows = self.db.fetchall(
            "SELECT date, COUNT(*) AS n FROM audit_log WHERE date >= ? GROUP BY date",
            (dates[0].strftime(DATE_FMT),),
        )
        counts = {r["date"]: r["n"] for r in rows}
        return [(d.strftime(DATE_FMT), counts.get(d.strftime(DATE_FMT), 0)) for d in dates]

    def count_today(self, code: AuditCode) -> int:
        row = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM audit_log WHERE date = date('now','localtime') AND code = ?",
            (code.value,),
        )
        return int(row["n"]) if row else 0
