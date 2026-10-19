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
class DayTotals:
    date: str
    entries: int
    debit: float  # sales / money paid out
    credit: float  # receipts / purchases


@dataclass(frozen=True)
class CollectionRow:
    id: int
    name: str
    details: str
    phone: str
    balance: float
    last_payment: str  # date or 'never'
    days_since_payment: int | None
    promised: str  # open krar date or ''
    status: str
    days_since_activity: int


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

    def day_totals(self, date: str | None = None) -> DayTotals:
        """Ledger debits / credits entered for ``date`` (default today).

        A settlement counts once - its own entry - not its derived *Settled Amount* and
        *Discount* rows."""
        date = date or dt.date.today().strftime(DATE_FMT)
        r = self.db.fetchone(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(CASE WHEN type = 'P' THEN amount END), 0) AS deb, "
            "COALESCE(SUM(CASE WHEN type = 'M' THEN amount END), 0) AS cred "
            "FROM transactions WHERE date = ? "
            "AND NOT (tag = '0' AND description IN ('Settled Amount', 'Discount'))",
            (date,),
        )
        return DayTotals(date, int(r["n"]), round(r["deb"], 2), round(r["cred"], 2))

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

    # v5 reports ---------------------------------------------------------------------
    def collections(self, today: dt.date | None = None, categories="settings") -> list[CollectionRow]:
        """Everyone who owes money, biggest first, with phone, last payment and promise -
        the shop's call list."""
        from hth.services.reminders import extract_phone

        today = today or dt.date.today()
        today_s = today.strftime(DATE_FMT)
        cats = self.categories.customer_report_categories() if categories == "settings" else categories
        customers = {c.id: c for c in self.accounts.list_customers(categories=cats)}
        totals = self.accounts.period_totals(today, list(customers))
        last_paid = {
            r["customer_id"]: r["d"]
            for r in self.db.fetchall(
                "SELECT customer_id, MAX(date) AS d FROM transactions WHERE type = 'M' "
                "AND NOT (tag = '0' AND description IN ('Settled Amount', 'Discount')) GROUP BY customer_id"
            )
        }
        promised = {e.customer_id: e.last_date for e in self.krar.entries("all", today)}
        out = []
        for cid, t in totals.items():
            if t.balance <= 0:
                continue
            c = customers[cid]
            paid = last_paid.get(cid)
            since = (today - dt.date.fromisoformat(paid)).days if paid else None
            p = promised.get(cid, "")
            if not p:
                status = "No promise"
            elif p < today_s:
                status = "Promise overdue"
            elif p == today_s:
                status = "Promised today"
            else:
                status = "Promised"
            out.append(
                CollectionRow(
                    cid,
                    c.name,
                    c.other_details,
                    extract_phone(c.other_details) or "",
                    t.balance,
                    paid or "never",
                    since,
                    p,
                    status,
                    t.days_since(today),
                )
            )
        return sorted(out, key=lambda r: -r.balance)

    def interest_by_fy(
        self, as_of: dt.date | None = None, categories="settings"
    ) -> list[tuple[str, float, float, float]]:
        """Open (unsettled) balances split by financial year: (FY, principal entered in that
        year, interest accrued in that year, total).  Positive = customers owe us.

        Shows how much of today's receivable is interest and when it built up."""
        from hth.domain.interest import fy_label, interest_schedule

        cats = self.categories.customer_report_categories() if categories == "settings" else categories
        ids = [c.id for c in self.accounts.list_customers(categories=cats)]
        principal: dict[str, float] = {}
        interest: dict[str, float] = {}
        for rows in self.accounts.current_period_entries(ids).values():
            for date, amount, tx_type, tag in rows:
                sign = 1 if tx_type == "P" else -1
                fy = fy_label(dt.date.fromisoformat(date))
                principal[fy] = principal.get(fy, 0.0) + sign * amount
                if tag == "1":
                    pieces = interest_schedule(amount, date, as_of)
                    if not pieces:
                        continue
                    # each entry's interest is rounded once (as everywhere else); the rounding
                    # lands in its last year so this report adds up to the interest summary
                    values = [v for _end, v in pieces]
                    values[-1] += round(sum(values), 2) - sum(values)
                    for (period_end, _v), value in zip(pieces, values, strict=True):
                        key = fy_label(period_end)
                        interest[key] = interest.get(key, 0.0) + sign * value
        out = []
        for fy in sorted(set(principal) | set(interest)):
            p, i = round(principal.get(fy, 0.0), 2), round(interest.get(fy, 0.0), 2)
            out.append((fy, p, i, round(p + i, 2)))
        return out

    def krar_forecast(self, days: int = 90, today: dt.date | None = None) -> list[tuple[str, int, float, float]]:
        """Money promised (open krar) by week for the next ``days`` days: (period, promises,
        expected, running total).  Expected = what the customer owes today; overdue first."""
        today = today or dt.date.today()
        horizon = today + dt.timedelta(days=days)
        entries = self.krar.entries("all", today)
        balances = self.accounts.balances(today, [e.customer_id for e in entries])
        buckets: dict[str, list] = {}
        for e in sorted(entries, key=lambda e: e.last_date):
            day = dt.date.fromisoformat(e.last_date)
            if day < today:
                label = "Overdue"
            elif day <= horizon:
                label = f"Week of {day - dt.timedelta(days=day.weekday()):%d %b %Y}"
            else:
                label = f"After {horizon:%d %b %Y}"
            bucket = buckets.setdefault(label, [0, 0.0])
            bucket[0] += 1
            bucket[1] += max(balances.get(e.customer_id, 0.0), 0.0)
        out, running = [], 0.0
        for label, (n, amount) in buckets.items():  # insertion order = date order, overdue first
            running += amount
            out.append((label, n, round(amount, 2), round(running, 2)))
        return out

    def item_profit(
        self, date_from: str, date_to: str, categories="settings"
    ) -> list[tuple[int, str, str, float, float, float, float, float | None]]:
        """Per item sold in range: (id, name, unit, qty, sales value, cost at current cost,
        margin, margin %).  Same rule as Finance -> Profit & loss: only movements that carry a
        value (Sales screen, v4.5+), crops excluded (they have FIFO margins in Crop Trade)."""
        cats = self.categories.item_report_categories() if categories == "settings" else categories
        clause, params = self._cat_clause("i", cats)
        rows = self.db.fetchall(
            "SELECT i.id, i.name, i.unit, i.stock_value AS cost, SUM(t.sale) AS qty, SUM(t.value) AS rev "
            "FROM items i JOIN item_transactions t ON t.item_id = i.id "
            "WHERE t.sale > 0 AND t.value > 0 AND i.item_type != 'C' AND t.date BETWEEN ? AND ?"
            + clause
            + " GROUP BY i.id ORDER BY rev DESC",
            (date_from, date_to, *params),
        )
        out = []
        for r in rows:
            qty, rev = float(r["qty"]), float(r["rev"])
            cost = round(qty * float(r["cost"]), 2)
            margin = round(rev - cost, 2)
            pct = round(margin / rev * 100, 1) if rev else None
            out.append((r["id"], r["name"], r["unit"], qty, round(rev, 2), cost, margin, pct))
        return out

    def gst_summary(self, date_from: str, date_to: str) -> list[tuple[str, float, int, float, float, float, float]]:
        """Invoice lines by month and GST rate: (month, GST %, bills, taxable, CGST, SGST, total)
        - the figures for the monthly GST return.  Empty without the bills module."""
        if self.db.fetchone("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'bill_lines'") is None:
            return []
        rows = self.db.fetchall(
            "SELECT substr(b.date, 1, 7) AS m, l.gst_rate AS rate, COUNT(DISTINCT b.id) AS bills, "
            "SUM(l.amount) AS taxable, SUM(l.cgst) AS cgst, SUM(l.sgst) AS sgst "
            "FROM bills b JOIN bill_lines l ON l.bill_id = b.id WHERE b.date BETWEEN ? AND ? "
            "GROUP BY m, rate ORDER BY m, rate",
            (date_from, date_to),
        )
        out = []
        for r in rows:
            taxable, cgst, sgst = (round(float(r[k] or 0), 2) for k in ("taxable", "cgst", "sgst"))
            total = round(taxable + cgst + sgst, 2)
            out.append((r["m"], float(r["rate"]), int(r["bills"]), taxable, cgst, sgst, total))
        return out

    def staff_activity(self, date_from: str, date_to: str) -> list[tuple[str, int, int, int, int, int, int, str]]:
        """Per user from the audit log: (user, days active, sales, receipts, changes, deletes,
        all actions, last seen)."""
        rows = self.db.fetchall(
            "SELECT username AS u, COUNT(DISTINCT date) AS days, "
            "SUM(code = '03') AS sales, SUM(code = '04') AS receipts, "
            "SUM(code IN ('01','02','05','07','10','11','12')) AS changes, SUM(code = '06') AS deletes, "
            "COUNT(*) AS n, MAX(ts) AS last FROM audit_log "
            "WHERE date BETWEEN ? AND ? AND username != 'system' GROUP BY username ORDER BY n DESC",
            (date_from, date_to),
        )
        return [
            (r["u"], r["days"], r["sales"], r["receipts"], r["changes"], r["deletes"], r["n"], r["last"]) for r in rows
        ]
