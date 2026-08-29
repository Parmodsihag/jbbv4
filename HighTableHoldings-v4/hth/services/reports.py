"""Cross-cutting aggregates for the dashboard and the reports screen."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.interest import calculate_interest
from hth.domain.models import CustomerSummary
from hth.services.accounts import AccountsService
from hth.services.audit import AuditService
from hth.services.inventory import InventoryService
from hth.services.krar import KrarService

AGING_BUCKETS: list[tuple[str, int, int | None]] = [
    ("0-30 days", 0, 30),
    ("31-90 days", 31, 90),
    ("91-180 days", 91, 180),
    ("180+ days", 181, None),
]


@dataclass(frozen=True)
class Kpis:
    receivable: float  # sum of positive balances (customers owe us)
    payable: float  # sum of negative balances (we owe customers), as a positive number
    customers: int
    debtors: int  # customers with balance > 0
    items: int
    stock_value: float
    krar_today: int
    krar_overdue: int
    sales_today: int
    receipts_today: int
    activity_today: int


@dataclass(frozen=True)
class MonthFlow:
    month: str  # YYYY-MM
    debit: float
    credit: float

    @property
    def net(self) -> float:
        return round(self.debit - self.credit, 2)


class ReportsService:
    def __init__(self, db: Database):
        self.db = db
        self.accounts = AccountsService(db)
        self.inventory = InventoryService(db)
        self.krar = KrarService(db)
        self.audit = AuditService(db)

    # Dashboard --------------------------------------------------------------------
    def kpis(self, summaries: list[CustomerSummary] | None = None) -> Kpis:
        summaries = summaries if summaries is not None else self.accounts.summaries()
        receivable = round(sum(s.balance for s in summaries if s.balance > 0), 2)
        payable = round(-sum(s.balance for s in summaries if s.balance < 0), 2)
        items = self.inventory.summaries()
        return Kpis(
            receivable=receivable,
            payable=payable,
            customers=len(summaries),
            debtors=sum(1 for s in summaries if s.balance > 0),
            items=len(items),
            stock_value=round(sum(i.total_value for i in items), 2),
            krar_today=len(self.krar.entries("today")),
            krar_overdue=len(self.krar.entries("past")),
            sales_today=self.audit.count_today(AuditCode.SALE),
            receipts_today=self.audit.count_today(AuditCode.RECEIVE),
            activity_today=self.audit.daily_counts(1)[0][1],
        )

    def aging(self, summaries: list[CustomerSummary] | None = None) -> list[tuple[str, int, float]]:
        """Receivables by days since last activity: [(bucket, customers, amount)]."""
        summaries = summaries if summaries is not None else self.accounts.summaries()
        out = []
        for label, lo, hi in AGING_BUCKETS:
            group = [s for s in summaries if s.balance > 0 and s.days >= lo and (hi is None or s.days <= hi)]
            out.append((label, len(group), round(sum(s.balance for s in group), 2)))
        return out

    def top_debtors(self, n: int = 10, summaries: list[CustomerSummary] | None = None) -> list[CustomerSummary]:
        summaries = summaries if summaries is not None else self.accounts.summaries()
        return sorted([s for s in summaries if s.balance > 0], key=lambda s: s.balance, reverse=True)[:n]

    def monthly_flow(self, months: int = 12) -> list[MonthFlow]:
        """Debits vs credits per month (settlement rows excluded), oldest first."""
        first = (dt.date.today().replace(day=1) - dt.timedelta(days=31 * (months - 1))).replace(day=1)
        rows = self.db.fetchall(
            "SELECT substr(date, 1, 7) AS m, "
            "SUM(CASE WHEN type = 'P' THEN amount ELSE 0 END) AS debit, "
            "SUM(CASE WHEN type = 'M' THEN amount ELSE 0 END) AS credit "
            "FROM transactions WHERE tag != '0' AND date >= ? GROUP BY m ORDER BY m",
            (first.strftime(DATE_FMT),),
        )
        return [MonthFlow(r["m"], round(r["debit"] or 0, 2), round(r["credit"] or 0, 2)) for r in rows]

    def daily_activity(self, days: int = 7) -> list[tuple[str, int]]:
        return self.audit.daily_counts(days)

    # Reports ----------------------------------------------------------------------
    def interest_summary(self, as_of: dt.date | None = None) -> list[tuple[int, str, float, float, float]]:
        """Per customer: (id, name, principal, interest, total) for the current period."""
        out = []
        for c in self.accounts.list_customers():
            principal = 0.0
            interest = 0.0
            for tx in self.accounts.current_period_transactions(c.id):
                sign = 1 if tx.is_debit else -1
                principal += sign * tx.amount
                if tx.tag == "1":
                    interest += sign * calculate_interest(tx.amount, tx.date, as_of)
            out.append(
                (
                    c.id,
                    c.name,
                    round(principal, 2),
                    round(interest, 2),
                    round(principal + interest, 2),
                )
            )
        return out

    def item_movement(self, date_from: str, date_to: str) -> list[tuple[int, str, float, float, float]]:
        """Per item: (id, name, received, sold, closing stock) within the range."""
        rows = self.db.fetchall(
            "SELECT i.id, i.name, "
            "COALESCE(SUM(CASE WHEN t.date BETWEEN ? AND ? THEN t.received END), 0) AS recv, "
            "COALESCE(SUM(CASE WHEN t.date BETWEEN ? AND ? THEN t.sale END), 0) AS sold, "
            "COALESCE(SUM(t.received - t.sale), 0) AS stock "
            "FROM items i LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id ORDER BY sold DESC",
            (date_from, date_to, date_from, date_to),
        )
        return [(r["id"], r["name"], float(r["recv"]), float(r["sold"]), float(r["stock"])) for r in rows]

    def dead_stock(self, days: int = 90, today: dt.date | None = None) -> list[tuple[int, str, float, str]]:
        """Items with stock on hand and no sale in the last ``days``: (id, name, stock, last_sale)."""
        cutoff = ((today or dt.date.today()) - dt.timedelta(days=days)).strftime(DATE_FMT)
        rows = self.db.fetchall(
            "SELECT i.id, i.name, COALESCE(SUM(t.received - t.sale), 0) AS stock, "
            "MAX(CASE WHEN t.sale > 0 THEN t.date END) AS last_sale "
            "FROM items i LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id "
            "HAVING stock > 0 AND (last_sale IS NULL OR last_sale < ?) ORDER BY last_sale",
            (cutoff,),
        )
        return [(r["id"], r["name"], float(r["stock"]), r["last_sale"] or "never") for r in rows]

    def day_book(self, date: str) -> list[tuple[int, str, str, float, str, str, str]]:
        """Every ledger entry on a date: (tx id, customer, description, amount, type, tag, user)."""
        rows = self.db.fetchall(
            "SELECT t.id, c.name, t.description, t.amount, t.type, t.tag, COALESCE(t.created_by, '') AS u "
            "FROM transactions t JOIN customers c ON c.id = t.customer_id WHERE t.date = ? ORDER BY t.id",
            (date,),
        )
        return [tuple(r) for r in rows]

    def customer_activity(self, date_from: str, date_to: str) -> list[tuple[int, str, int, float, float]]:
        """Per customer in range: (id, name, transactions, debited, credited)."""
        rows = self.db.fetchall(
            "SELECT c.id, c.name, COUNT(t.id) AS n, "
            "COALESCE(SUM(CASE WHEN t.type='P' AND t.tag != '0' THEN t.amount END), 0) AS deb, "
            "COALESCE(SUM(CASE WHEN t.type='M' AND t.tag != '0' THEN t.amount END), 0) AS cred "
            "FROM customers c JOIN transactions t ON t.customer_id = c.id "
            "WHERE t.date BETWEEN ? AND ? GROUP BY c.id ORDER BY deb DESC",
            (date_from, date_to),
        )
        return [(r["id"], r["name"], r["n"], round(r["deb"], 2), round(r["cred"], 2)) for r in rows]
