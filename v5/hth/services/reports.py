"""Cross-cutting aggregates for the dashboard and the reports screen."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.models import CustomerSummary
from hth.services.accounts import AccountsService
from hth.services.audit import AuditService
from hth.services.categories import CategoryService
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
        self.categories = CategoryService(db)

    # Dashboard --------------------------------------------------------------------
    def kpis(self, summaries: list[CustomerSummary] | None = None, item_categories=None) -> Kpis:
        """Customers per ``summaries`` (default: Settings scope); items per ``item_categories``
        (default: Settings scope)."""
        summaries = summaries if summaries is not None else self.categories.customer_summaries()
        receivable = round(sum(s.balance for s in summaries if s.balance > 0), 2)
        payable = round(-sum(s.balance for s in summaries if s.balance < 0), 2)
        item_cats = self.categories.item_report_categories() if item_categories is None else item_categories
        items = self.inventory.summaries(categories=item_cats)
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
        summaries = summaries if summaries is not None else self.categories.customer_summaries()
        out = []
        for label, lo, hi in AGING_BUCKETS:
            group = [s for s in summaries if s.balance > 0 and s.days >= lo and (hi is None or s.days <= hi)]
            out.append((label, len(group), round(sum(s.balance for s in group), 2)))
        return out

    def top_debtors(self, n: int = 10, summaries: list[CustomerSummary] | None = None) -> list[CustomerSummary]:
        summaries = summaries if summaries is not None else self.categories.customer_summaries()
        return sorted([s for s in summaries if s.balance > 0], key=lambda s: s.balance, reverse=True)[:n]

    @staticmethod
    def _cat_clause(alias: str, categories) -> tuple[str, list]:
        if categories is None:
            return "", []
        cats = sorted(set(categories))
        if not cats:
            return f" AND {alias}.category IN ('')", []
        return f" AND {alias}.category IN ({','.join('?' * len(cats))})", cats

    def monthly_flow(self, months: int = 12, categories="settings", today: dt.date | None = None) -> list[MonthFlow]:
        """Debits vs credits per month (settlement rows excluded) for the last ``months`` calendar
        months up to ``today``'s, oldest first.

        ``categories``: 'settings' (default), None for all, or an explicit set."""
        today = today or dt.date.today()
        y, m = divmod(today.year * 12 + today.month - months, 12)  # first of the earliest month
        first = dt.date(y, m + 1, 1)
        cats = self.categories.customer_report_categories() if categories == "settings" else categories
        clause, params = self._cat_clause("c", cats)
        rows = self.db.fetchall(
            "SELECT substr(t.date, 1, 7) AS m, "
            "SUM(CASE WHEN t.type = 'P' THEN t.amount ELSE 0 END) AS debit, "
            "SUM(CASE WHEN t.type = 'M' THEN t.amount ELSE 0 END) AS credit "
            "FROM transactions t JOIN customers c ON c.id = t.customer_id "
            "WHERE t.tag != '0' AND t.date >= ?" + clause + " GROUP BY m ORDER BY m",
            (first.strftime(DATE_FMT), *params),
        )
        return [MonthFlow(r["m"], round(r["debit"] or 0, 2), round(r["credit"] or 0, 2)) for r in rows]

    def daily_activity(self, days: int = 7) -> list[tuple[str, int]]:
        return self.audit.daily_counts(days)

    # Reports ----------------------------------------------------------------------
    def interest_summary(
        self, as_of: dt.date | None = None, categories="settings"
    ) -> list[tuple[int, str, float, float, float]]:
        """Per customer: (id, name, principal, interest, total) for the current period."""
        cats = self.categories.customer_report_categories() if categories == "settings" else categories
        customers = self.accounts.list_customers(categories=cats)
        totals = self.accounts.period_totals(as_of, [c.id for c in customers])
        out = []
        for c in customers:
            t = totals[c.id]
            out.append((c.id, c.name, t.principal, t.interest, t.total))
        return out

    def item_movement(
        self, date_from: str, date_to: str, categories="settings"
    ) -> list[tuple[int, str, float, float, float]]:
        """Per item: (id, name, received, sold, closing stock) within the range."""
        cats = self.categories.item_report_categories() if categories == "settings" else categories
        clause, params = self._cat_clause("i", cats)
        rows = self.db.fetchall(
            "SELECT i.id, i.name, "
            "COALESCE(SUM(CASE WHEN t.date BETWEEN ? AND ? THEN t.received END), 0) AS recv, "
            "COALESCE(SUM(CASE WHEN t.date BETWEEN ? AND ? THEN t.sale END), 0) AS sold, "
            "COALESCE(SUM(t.received - t.sale), 0) AS stock "
            "FROM items i LEFT JOIN item_transactions t ON t.item_id = i.id WHERE 1=1"
            + clause
            + " GROUP BY i.id ORDER BY sold DESC",
            (date_from, date_to, date_from, date_to, *params),
        )
        return [(r["id"], r["name"], float(r["recv"]), float(r["sold"]), float(r["stock"])) for r in rows]

    def dead_stock(
        self, days: int = 90, today: dt.date | None = None, categories="settings"
    ) -> list[tuple[int, str, float, str]]:
        """Items with stock on hand and no sale in the last ``days``: (id, name, stock, last_sale)."""
        cutoff = ((today or dt.date.today()) - dt.timedelta(days=days)).strftime(DATE_FMT)
        cats = self.categories.item_report_categories() if categories == "settings" else categories
        clause, params = self._cat_clause("i", cats)
        rows = self.db.fetchall(
            "SELECT i.id, i.name, COALESCE(SUM(t.received - t.sale), 0) AS stock, "
            "MAX(CASE WHEN t.sale > 0 THEN t.date END) AS last_sale "
            "FROM items i LEFT JOIN item_transactions t ON t.item_id = i.id WHERE 1=1" + clause + " GROUP BY i.id "
            "HAVING stock > 0 AND (last_sale IS NULL OR last_sale < ?) ORDER BY last_sale",
            (*params, cutoff),
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

    def customer_activity(
        self, date_from: str, date_to: str, categories="settings"
    ) -> list[tuple[int, str, int, float, float]]:
        """Per customer in range: (id, name, transactions, debited, credited)."""
        cats = self.categories.customer_report_categories() if categories == "settings" else categories
        clause, params = self._cat_clause("c", cats)
        rows = self.db.fetchall(
            "SELECT c.id, c.name, COUNT(t.id) AS n, "
            "COALESCE(SUM(CASE WHEN t.type='P' AND t.tag != '0' THEN t.amount END), 0) AS deb, "
            "COALESCE(SUM(CASE WHEN t.type='M' AND t.tag != '0' THEN t.amount END), 0) AS cred "
            "FROM customers c JOIN transactions t ON t.customer_id = c.id "
            "WHERE t.date BETWEEN ? AND ?" + clause + " GROUP BY c.id ORDER BY deb DESC",
            (date_from, date_to, *params),
        )
        return [(r["id"], r["name"], r["n"], round(r["deb"], 2), round(r["cred"], 2)) for r in rows]
