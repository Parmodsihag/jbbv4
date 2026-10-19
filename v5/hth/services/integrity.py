"""Data-quality checks over the live database.

Each finding is (severity, area, ref_id, name, issue, detail).  Severity: ERROR = will
produce wrong numbers, WARN = probably a mistake, INFO = worth a look.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from hth.db.connection import Database
from hth.domain import numbers
from hth.domain.constants import DATE_FMT
from hth.domain.interest import parse_date


@dataclass(frozen=True)
class Finding:
    severity: str
    area: str  # Customer | Item | Krar | Ledger
    ref_id: int
    name: str
    issue: str
    detail: str

    def as_row(self) -> tuple:
        return (self.severity, self.area, self.ref_id, self.name, self.issue, self.detail)


class IntegrityService:
    def __init__(self, db: Database):
        self.db = db

    def run(self, today: dt.date | None = None) -> list[Finding]:
        today = today or dt.date.today()
        out: list[Finding] = []
        out += self._bad_dates(today)
        out += self._zero_amounts()
        out += self._lonely_settlements()
        out += self._duplicate_customers()
        out += self._negative_stock()
        out += self._krar_without_balance()
        out += self._stale_debtors(today)
        out += self._blank_descriptions()
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        return sorted(out, key=lambda f: (order[f.severity], f.area, f.ref_id))

    # Ledger --------------------------------------------------------------------------
    def _bad_dates(self, today: dt.date) -> list[Finding]:
        out = []
        rows = self.db.fetchall(
            "SELECT t.id, t.customer_id, c.name, t.date FROM transactions t JOIN customers c ON c.id = t.customer_id"
        )
        for r in rows:
            try:
                d = parse_date(r["date"])
            except ValueError:
                out.append(
                    Finding(
                        "ERROR",
                        "Customer",
                        r["customer_id"],
                        r["name"],
                        "Entry has an invalid date",
                        f"entry #{r['id']} date {r['date']!r} - interest cannot be computed",
                    )
                )
                continue
            if d > today:
                out.append(
                    Finding(
                        "WARN",
                        "Customer",
                        r["customer_id"],
                        r["name"],
                        "Entry dated in the future",
                        f"entry #{r['id']} dated {r['date']}",
                    )
                )
            elif d.year < 2000:
                out.append(
                    Finding(
                        "WARN",
                        "Customer",
                        r["customer_id"],
                        r["name"],
                        "Entry dated before 2000",
                        f"entry #{r['id']} dated {r['date']}",
                    )
                )
        return out

    def _zero_amounts(self) -> list[Finding]:
        rows = self.db.fetchall(
            "SELECT t.id, t.customer_id, c.name, t.date, t.description FROM transactions t "
            "JOIN customers c ON c.id = t.customer_id WHERE t.amount = 0 AND t.tag != '0'"
        )
        return [
            Finding(
                "WARN",
                "Customer",
                r["customer_id"],
                r["name"],
                "Entry with zero amount",
                f"entry #{r['id']} {r['date']} {r['description']}",
            )
            for r in rows
        ]

    def _lonely_settlements(self) -> list[Finding]:
        """Tag-0 rows normally come in threes (entry, Settled Amount, Discount) on one date."""
        rows = self.db.fetchall(
            "SELECT t.customer_id, c.name, t.date, COUNT(*) AS n, MIN(t.id) AS first_id FROM transactions t "
            "JOIN customers c ON c.id = t.customer_id WHERE t.tag = '0' "
            "GROUP BY t.customer_id, t.date HAVING n % 3 != 0"
        )
        return [
            Finding(
                "INFO",
                "Customer",
                r["customer_id"],
                r["name"],
                "Settlement rows not in a group of 3",
                f"{r['n']} tag-0 rows on {r['date']} (from entry #{r['first_id']})",
            )
            for r in rows
        ]

    def _blank_descriptions(self) -> list[Finding]:
        rows = self.db.fetchall(
            "SELECT t.id, t.customer_id, c.name, t.date, t.amount FROM transactions t "
            "JOIN customers c ON c.id = t.customer_id WHERE TRIM(t.description) = ''"
        )
        return [
            Finding(
                "INFO",
                "Customer",
                r["customer_id"],
                r["name"],
                "Entry without description",
                f"entry #{r['id']} {r['date']} amount {r['amount']:g}",
            )
            for r in rows
        ]

    # Customers -----------------------------------------------------------------------
    def _duplicate_customers(self) -> list[Finding]:
        rows = self.db.fetchall(
            "SELECT UPPER(TRIM(name)) AS n, UPPER(TRIM(other_details)) AS d, GROUP_CONCAT(id) AS ids, MIN(id) AS first "
            "FROM customers GROUP BY n, d HAVING COUNT(*) > 1"
        )
        return [
            Finding(
                "WARN", "Customer", r["first"], r["n"], "Duplicate customer (same name and details)", f"ids {r['ids']}"
            )
            for r in rows
        ]

    def _stale_debtors(self, today: dt.date, days: int = 365) -> list[Finding]:
        cutoff = (today - dt.timedelta(days=days)).strftime(DATE_FMT)
        rows = self.db.fetchall(
            "SELECT c.id, c.name, MAX(t.date) AS last, "
            "SUM(CASE WHEN t.type='P' THEN t.amount ELSE -t.amount END) AS principal "
            "FROM customers c JOIN transactions t ON t.customer_id = c.id AND t.tag != '0' "
            "GROUP BY c.id HAVING last < ? AND principal > 0",
            (cutoff,),
        )
        return [
            Finding(
                "INFO",
                "Customer",
                r["id"],
                r["name"],
                f"Owes money, no activity for {days}+ days",
                f"last entry {r['last']}, principal {numbers.amount(r['principal'])}",
            )
            for r in rows
        ]

    # Items ---------------------------------------------------------------------------
    def _negative_stock(self) -> list[Finding]:
        rows = self.db.fetchall(
            "SELECT i.id, i.name, COALESCE(SUM(t.received - t.sale), 0) AS q FROM items i "
            "LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id HAVING q < 0"
        )
        return [Finding("ERROR", "Item", r["id"], r["name"], "Negative stock", f"in stock {r['q']:g}") for r in rows]

    # Krar ----------------------------------------------------------------------------
    def _krar_without_balance(self) -> list[Finding]:
        rows = self.db.fetchall(
            "SELECT k.id, k.customer_id, c.name, "
            "COALESCE((SELECT SUM(CASE WHEN t.type='P' THEN t.amount ELSE -t.amount END) FROM transactions t "
            " WHERE t.customer_id = k.customer_id AND t.tag != '0' AND (t.date, t.id) > "
            "  (COALESCE((SELECT MAX(date) FROM transactions s "
            "   WHERE s.customer_id = k.customer_id AND s.tag='0'), ''), 0)), 0)"
            " AS principal FROM krar k JOIN customers c ON c.id = k.customer_id WHERE k.is_nill = 0"
        )
        return [
            Finding(
                "INFO",
                "Krar",
                r["customer_id"],
                r["name"],
                "Open krar but nothing owed",
                f"krar #{r['id']}, principal {numbers.amount(r['principal'])}",
            )
            for r in rows
            if r["principal"] <= 0
        ]
