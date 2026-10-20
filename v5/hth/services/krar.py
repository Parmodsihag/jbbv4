"""Krar - promised payment dates.  One open krar per customer; rescheduling appends a date."""

from __future__ import annotations

import datetime as dt

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.models import KrarEntry
from hth.services.accounts import _validate_date
from hth.services.audit import AuditService


class KrarService:
    def __init__(self, db: Database):
        self.db = db
        self.audit = AuditService(db)

    def add_or_update(self, customer_id: int, date: str, username: str = "system") -> int:
        date = _validate_date(date)
        with self.db.connect():
            row = self.db.fetchone("SELECT id FROM krar WHERE customer_id = ? AND is_nill = 0", (customer_id,))
            krar_id = row["id"] if row else self.db.execute("INSERT INTO krar (customer_id) VALUES (?)", (customer_id,))
            self.db.execute("INSERT INTO krar_dates (krar_id, date) VALUES (?, ?)", (krar_id, date))
            self.audit.log(AuditCode.KRAR, f"krar {krar_id} customer {customer_id} date {date}", username)
        return krar_id

    def settle(self, customer_id: int, username: str = "system") -> None:
        with self.db.connect():
            self.db.execute("UPDATE krar SET is_nill = 1 WHERE customer_id = ? AND is_nill = 0", (customer_id,))
            self.audit.log(AuditCode.KRAR, f"krar settled customer {customer_id}", username)

    def unsettled_customer_ids(self) -> list[int]:
        return [
            r["customer_id"]
            for r in self.db.fetchall("SELECT DISTINCT customer_id FROM krar WHERE is_nill = 0 ORDER BY customer_id")
        ]

    def unsettled_dates(self, customer_id: int) -> list[str]:
        return [
            r["date"]
            for r in self.db.fetchall(
                "SELECT d.date FROM krar k JOIN krar_dates d ON d.krar_id = k.id "
                "WHERE k.customer_id = ? AND k.is_nill = 0 ORDER BY d.id",
                (customer_id,),
            )
        ]

    def entries(self, bucket: str = "all", today: dt.date | None = None) -> list[KrarEntry]:
        """Open krars grouped by customer.  ``bucket``: today | past | future | all.

        Classification uses the *latest* promised date, as v3 did.
        """
        today_s = (today or dt.date.today()).strftime(DATE_FMT)
        rows = self.db.fetchall(
            "SELECT k.id AS krar_id, k.customer_id, c.name, c.other_details, "
            "GROUP_CONCAT(d.date, '|') AS dates, MAX(d.date) AS last_date "
            "FROM krar k JOIN customers c ON c.id = k.customer_id "
            "JOIN krar_dates d ON d.krar_id = k.id WHERE k.is_nill = 0 "
            "GROUP BY k.id ORDER BY last_date, c.name"
        )
        out = []
        for r in rows:
            last = r["last_date"] or ""
            if bucket == "today" and last != today_s:
                continue
            if bucket == "past" and not last < today_s:
                continue
            if bucket == "future" and not last > today_s:
                continue
            out.append(
                KrarEntry(
                    r["krar_id"],
                    r["customer_id"],
                    r["name"],
                    r["other_details"],
                    sorted((r["dates"] or "").split("|")),
                )
            )
        return out

    def settled_history(self, customer_id: int) -> list[tuple[int, int, str, str]]:
        return [
            tuple(r)
            for r in self.db.fetchall(
                "SELECT k.id, COUNT(*), MIN(d.date), MAX(d.date) FROM krar k "
                "JOIN krar_dates d ON d.krar_id = k.id WHERE k.customer_id = ? AND k.is_nill = 1 GROUP BY k.id",
                (customer_id,),
            )
        ]

    # Admin edits (Modify page) ------------------------------------------------------
    def update_krar(self, krar_id: int, customer_id: int, is_nill: int, username: str) -> None:
        with self.db.connect():
            self.db.execute(
                "UPDATE krar SET customer_id = ?, is_nill = ? WHERE id = ?",
                (customer_id, 1 if int(is_nill) else 0, krar_id),
            )
            self.audit.log(
                AuditCode.MODIFY,
                f"krar {krar_id}: customer {customer_id}, nill {is_nill}",
                username,
            )

    def update_krar_date(self, date_id: int, date: str, username: str) -> None:
        date = _validate_date(date)
        with self.db.connect():
            self.db.execute("UPDATE krar_dates SET date = ? WHERE id = ?", (date, date_id))
            self.audit.log(AuditCode.MODIFY, f"krar date {date_id}: {date}", username)

    def delete_krar(self, krar_id: int, username: str) -> None:
        with self.db.connect():
            self.db.execute("DELETE FROM krar WHERE id = ?", (krar_id,))
            self.audit.log(AuditCode.DELETE, f"krar {krar_id}", username)

    def krar_dates_rows(self, krar_id: int) -> list[tuple[int, str]]:
        return [
            (r["id"], r["date"])
            for r in self.db.fetchall("SELECT id, date FROM krar_dates WHERE krar_id = ? ORDER BY id", (krar_id,))
        ]
