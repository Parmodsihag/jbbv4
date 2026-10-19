"""Reports: a declarative catalogue.  Add a ReportSpec to REPORTS to add a report."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

import customtkinter as ctk

from hth.domain.constants import AuditCode
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.context import AppContext
from hth.ui.format import days_ago_str, money, open_path, today_str
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import confirm
from hth.ui.widgets.forms import primary_button, secondary_button
from hth.ui.widgets.searchbox import SearchBox


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    kind: str = "text"  # text | date | int | customer | choice
    default: str | Callable[[], str] = ""  # a callable is evaluated when the report is opened
    choices: Sequence[str] = ()


@dataclass(frozen=True)
class ReportSpec:
    key: str
    title: str
    group: str
    columns: Sequence[Column]
    run: Callable[[AppContext, dict], tuple[list[Sequence], str]]
    params: Sequence[Param] = field(default_factory=tuple)
    permission: Permission | None = None
    row_tags: Callable[[Sequence], Sequence[str]] | None = None
    open_customer_col: int | None = None  # double-click opens this customer's ledger
    open_item_col: int | None = None
    # custom double-click: row -> (view key, kwargs) or None
    open_row: Callable[[Sequence], tuple[str, dict] | None] | None = None


def _default(p: Param) -> str:
    return p.default() if callable(p.default) else p.default


SCOPE = Param("scope", "Scope", "choice", "Per settings", ["Per settings", "All categories"])


def _scope(p) -> str:
    return "all" if p.get("scope") == "All categories" else "settings"


# --- report bodies ------------------------------------------------------------------------
def _account_summary(ctx, p):
    rows = [
        (s.id, s.name, s.other_details, s.balance, s.days, f"{s.score:.2f}" if s.scored else "-", s.category)
        for s in ctx.categories.customer_summaries(scope=_scope(p))
    ]
    recv = sum(r[3] for r in rows if r[3] > 0)
    pay = -sum(r[3] for r in rows if r[3] < 0)
    return rows, f"{len(rows)} accounts · receivable {money(recv)} · payable {money(pay)}"


def _ledger(ctx, p):
    cid = p.get("customer")
    if not cid:
        raise ValueError("Pick a customer.")
    rows = [
        (r.id, r.date, r.particulars, r.interest, r.debit, r.credit, r.balance, r.tag, r.type)
        for r in ctx.accounts.ledger(int(cid))
    ]
    return rows, f"{len(rows)} entries · balance {money(ctx.accounts.get_balance(int(cid)))}"


def _items(ctx, p):
    rows = [
        (
            s.item.id,
            s.item.name,
            s.item.batch,
            s.item.unit,
            s.in_stock,
            s.item.stock_value,
            s.total_value,
            s.item.last_value,
            s.item.expiry_date,
            s.item.gst_rate,
            s.item.item_type,
            s.item.pakka_kacha,
        )
        for s in ctx.inventory.summaries(categories=ctx.categories.item_scope(_scope(p)))
    ]
    return rows, f"{len(rows)} items · stock value {money(sum(r[6] for r in rows))}"


def _movement(ctx, p):
    rows = ctx.reports.item_movement(p["from"], p["to"], categories=ctx.categories.item_scope(_scope(p)))
    return (
        rows,
        f"{len(rows)} items · sold {sum(r[3] for r in rows):g} · received {sum(r[2] for r in rows):g}",
    )


def _aging(ctx, p):
    rows = ctx.reports.aging(ctx.categories.customer_summaries(scope=_scope(p)))
    return rows, f"total receivable {money(sum(r[2] for r in rows))}"


def _top(ctx, p):
    rows = [
        (s.id, s.name, s.other_details, s.balance, s.days)
        for s in ctx.reports.top_debtors(int(p["n"] or 10), ctx.categories.customer_summaries(scope=_scope(p)))
    ]
    return rows, f"{len(rows)} debtors · {money(sum(r[3] for r in rows))}"


def _interest(ctx, p):
    rows = ctx.reports.interest_summary(categories=ctx.categories.customer_scope(_scope(p)))
    return (
        rows,
        f"principal {money(sum(r[2] for r in rows))} · interest {money(sum(r[3] for r in rows))}"
        f" · total {money(sum(r[4] for r in rows))}",
    )


def _monthly(ctx, p):
    rows = [
        (m.month, m.debit, m.credit, m.net)
        for m in ctx.reports.monthly_flow(int(p["months"] or 12), categories=ctx.categories.customer_scope(_scope(p)))
    ]
    return rows, f"debit {money(sum(r[1] for r in rows))} · credit {money(sum(r[2] for r in rows))}"


def _daybook(ctx, p):
    rows = ctx.reports.day_book(p["date"])
    deb = sum(r[3] for r in rows if r[4] == "P" and r[5] != "0")
    cred = sum(r[3] for r in rows if r[4] == "M" and r[5] != "0")
    return rows, f"{len(rows)} entries · debit {money(deb)} · credit {money(cred)}"


def _activity(ctx, p):
    rows = ctx.reports.customer_activity(p["from"], p["to"], categories=ctx.categories.customer_scope(_scope(p)))
    return (
        rows,
        f"{len(rows)} customers · debited {money(sum(r[3] for r in rows))} · credited {money(sum(r[4] for r in rows))}",
    )


def _low_stock(ctx, p):
    rows = [
        (s.item.id, s.item.name, s.item.batch, s.in_stock, s.item.unit)
        for s in ctx.inventory.low_stock(float(p["threshold"] or 5))
        if _in_scope(ctx, s, p)
    ]
    return rows, f"{len(rows)} items at or below {p['threshold'] or 5}"


def _expiring(ctx, p):
    rows = [
        (s.item.id, s.item.name, s.item.batch, s.item.expiry_date, d, s.in_stock)
        for s, d in ctx.inventory.expiring(int(p["days"] or 60))
        if _in_scope(ctx, s, p)
    ]
    return (
        rows,
        f"{len(rows)} items expiring within {p['days'] or 60} days (negative = already expired)",
    )


def _dead(ctx, p):
    rows = ctx.reports.dead_stock(int(p["days"] or 90), categories=ctx.categories.item_scope(_scope(p)))
    return rows, f"{len(rows)} items with stock and no sale in {p['days'] or 90} days"


def _in_scope(ctx, summary, p) -> bool:
    scope = ctx.categories.item_scope(_scope(p))
    return scope is None or summary.item.category in scope


def _krar(ctx, p):
    bucket = {"Overdue": "past", "Today": "today", "Upcoming": "future", "All": "all"}[p["bucket"] or "All"]
    rows = [
        (
            e.krar_id,
            e.customer_id,
            e.customer_name,
            e.other_details,
            e.last_date,
            ", ".join(e.dates),
        )
        for e in ctx.krar.entries(bucket)
    ]
    return rows, f"{len(rows)} open krar"


def _audit(ctx, p):
    code = None if p["code"] in ("", "All") else p["code"][:2]
    rows = [
        (e.id, e.ts, e.username, e.code_label, e.message)
        for e in ctx.audit.entries(p["from"], p["to"], code, p["search"] or None, 5000)
    ]
    return rows, f"{len(rows)} entries"


def _datacheck(ctx, p):
    findings = ctx.integrity.run()
    rows = [f.as_row() for f in findings]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("ERROR", "WARN", "INFO")}
    return rows, f"{counts['ERROR']} errors · {counts['WARN']} warnings · {counts['INFO']} info"


def _open_finding(row):
    area, ref = row[1], int(row[2])
    if area in ("Customer", "Krar"):
        return "customers", {"customer_id": ref}
    if area == "Item":
        return "items", {"item_id": ref}
    return None


def _collections(ctx, p):
    rows = [
        (
            r.id,
            r.name,
            r.phone,
            r.balance,
            r.last_payment,
            r.days_since_payment,
            r.promised,
            r.status,
            r.days_since_activity,
        )
        for r in ctx.reports.collections(categories=ctx.categories.customer_scope(_scope(p)))
    ]
    promised = sum(1 for r in rows if r[6])
    return rows, (
        f"{len(rows)} debtors · {money(sum(r[3] for r in rows))} owed · {promised} with a promise date"
        " · double-click opens the ledger"
    )


def _fy_interest(ctx, p):
    rows = ctx.reports.interest_by_fy(categories=ctx.categories.customer_scope(_scope(p)))
    return rows, (
        f"open balances: principal {money(sum(r[1] for r in rows))} + interest {money(sum(r[2] for r in rows))}"
        f" = {money(sum(r[3] for r in rows))}"
    )


def _forecast(ctx, p):
    rows = ctx.reports.krar_forecast(int(p["days"] or 90))
    return rows, f"{sum(r[1] for r in rows)} open promises · {money(rows[-1][3] if rows else 0)} expected in all"


def _profit(ctx, p):
    rows = ctx.reports.item_profit(p["from"], p["to"], categories=ctx.categories.item_scope(_scope(p)))
    rev, margin = sum(r[4] for r in rows), sum(r[6] for r in rows)
    pct = f" ({margin / rev * 100:.1f}%)" if rev else ""
    return rows, (
        f"{len(rows)} items · sales {money(rev)} · margin {money(margin)}{pct}"
        " · cost = today's item cost; only Sales-screen entries carry a value"
    )


def _reorder(ctx, p):
    from hth.services.insights import InsightsService

    window = int(p["days"] or 30)
    rows = [
        (r.item_id, r.name, r.unit, r.in_stock, r.sold_window, r.days_left)
        for r in InsightsService(ctx.db).reorder_suggestions(window)
    ]
    return rows, f"{len(rows)} items sold more in the last {window} days than is left in stock"


def _gst(ctx, p):
    rows = ctx.reports.gst_summary(p["from"], p["to"])
    return rows, (
        f"taxable {money(sum(r[3] for r in rows))} · CGST {money(sum(r[4] for r in rows))}"
        f" · SGST {money(sum(r[5] for r in rows))} · total {money(sum(r[6] for r in rows))}"
    )


def _staff(ctx, p):
    rows = ctx.reports.staff_activity(p["from"], p["to"])
    return rows, f"{len(rows)} users · {sum(r[6] for r in rows)} actions"


def _fy_start() -> str:
    from hth.services.statements import financial_year_start

    return financial_year_start()


def _month_start() -> str:
    import datetime as _dt

    return _dt.date.today().replace(day=1).strftime("%Y-%m-%d")


AUDIT_CODES = ["All"] + [f"{c.value} {c.label}" for c in AuditCode]

REPORTS: list[ReportSpec] = [
    ReportSpec(
        "summary",
        "Account summary",
        "Accounts",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("name", "Name", 220, stretch=True),
            Column("details", "Details", 180),
            Column("balance", "Balance", 120, "e", "money"),
            Column("days", "Days", 70, "e", "int"),
            Column("score", "Score", 70, "e"),
            Column("cat", "Cat", 45, "center"),
        ],
        _account_summary,
        row_tags=lambda r: ["neg"] if r[3] > 0 else (["pos"] if r[3] < 0 else ["muted"]),
        open_customer_col=0,
    ),
    ReportSpec(
        "ledger",
        "Customer ledger",
        "Accounts",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("date", "Date", 100),
            Column("particulars", "Particulars", 280, stretch=True),
            Column("interest", "Interest", 100, "e", "money"),
            Column("debit", "Debit", 110, "e", "money"),
            Column("credit", "Credit", 110, "e", "money"),
            Column("balance", "Balance", 120, "e", "money"),
            Column("tag", "Tag", 50, "center"),
            Column("type", "P/M", 50, "center"),
        ],
        _ledger,
        [Param("customer", "Customer", "customer")],
        row_tags=lambda r: ["muted", "bold"] if r[7] == "0" else [],
    ),
    ReportSpec(
        "aging",
        "Receivables aging",
        "Accounts",
        [
            Column("bucket", "Age", 140),
            Column("n", "Customers", 100, "e", "int"),
            Column("amount", "Amount", 140, "e", "money"),
        ],
        _aging,
    ),
    ReportSpec(
        "top",
        "Top debtors",
        "Accounts",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("name", "Name", 220, stretch=True),
            Column("details", "Details", 180),
            Column("balance", "Balance", 120, "e", "money"),
            Column("days", "Days", 70, "e", "int"),
        ],
        _top,
        [Param("n", "How many", "int", "10")],
        open_customer_col=0,
    ),
    ReportSpec(
        "interest",
        "Interest summary",
        "Accounts",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("name", "Name", 220, stretch=True),
            Column("principal", "Principal", 120, "e", "money"),
            Column("interest", "Interest", 120, "e", "money"),
            Column("total", "Total", 120, "e", "money"),
        ],
        _interest,
        row_tags=lambda r: ["neg"] if r[4] > 0 else ["pos"],
        open_customer_col=0,
    ),
    ReportSpec(
        "activity",
        "Customer activity",
        "Accounts",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("name", "Name", 220, stretch=True),
            Column("n", "Entries", 80, "e", "int"),
            Column("debited", "Debited", 120, "e", "money"),
            Column("credited", "Credited", 120, "e", "money"),
        ],
        _activity,
        [Param("from", "From", "date", lambda: days_ago_str(30)), Param("to", "To", "date", today_str)],
        open_customer_col=0,
    ),
    ReportSpec(
        "collections",
        "Collections list",
        "Accounts",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("name", "Name", 220, stretch=True),
            Column("phone", "Phone", 110),
            Column("balance", "Balance", 120, "e", "money"),
            Column("paid", "Last paid", 100),
            Column("since", "Since paid", 90, "e", "int"),
            Column("promised", "Promised", 100),
            Column("status", "Status", 130),
            Column("days", "Idle days", 80, "e", "int"),
        ],
        _collections,
        row_tags=lambda r: ["neg"] if r[7] == "Promise overdue" else (["warn"] if r[7] == "Promised today" else []),
        open_customer_col=0,
    ),
    ReportSpec(
        "fy_interest",
        "Interest by financial year",
        "Accounts",
        [
            Column("fy", "Financial year", 140),
            Column("principal", "Principal entered", 150, "e", "money"),
            Column("interest", "Interest accrued", 150, "e", "money"),
            Column("total", "Total", 150, "e", "money"),
        ],
        _fy_interest,
    ),
    ReportSpec(
        "monthly",
        "Monthly debits vs credits",
        "Trends",
        [
            Column("month", "Month", 100),
            Column("debit", "Debit", 130, "e", "money"),
            Column("credit", "Credit", 130, "e", "money"),
            Column("net", "Net", 130, "e", "money"),
        ],
        _monthly,
        [Param("months", "Months", "int", "12")],
    ),
    ReportSpec(
        "daybook",
        "Day book",
        "Trends",
        [
            Column("id", "ID", 60, "e", "int"),
            Column("customer", "Customer", 220, stretch=True),
            Column("desc", "Description", 220),
            Column("amount", "Amount", 110, "e", "money"),
            Column("type", "P/M", 50, "center"),
            Column("tag", "Tag", 50, "center"),
            Column("user", "By", 80),
        ],
        _daybook,
        [Param("date", "Date", "date", today_str)],
    ),
    ReportSpec(
        "forecast",
        "Promised receipts forecast",
        "Trends",
        [
            Column("period", "When", 180),
            Column("n", "Promises", 90, "e", "int"),
            Column("amount", "Expected", 140, "e", "money"),
            Column("running", "Running total", 140, "e", "money"),
        ],
        _forecast,
        [Param("days", "Next days", "int", "90")],
        row_tags=lambda r: ["neg"] if r[0] == "Overdue" else [],
    ),
    ReportSpec(
        "items",
        "Stock on hand",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Name", 220, stretch=True),
            Column("batch", "Batch", 90),
            Column("unit", "Unit", 60),
            Column("stock", "In stock", 90, "e", "qty"),
            Column("value", "Cost", 90, "e", "money"),
            Column("total", "Stock value", 110, "e", "money"),
            Column("last", "Last price", 90, "e", "money"),
            Column("expiry", "Expiry", 100),
            Column("gst", "GST%", 60, "e", "qty"),
            Column("type", "Type", 50, "center"),
            Column("pk", "P/K", 45, "center"),
        ],
        _items,
        row_tags=lambda r: ["warn"] if r[4] <= 0 else [],
        open_item_col=0,
    ),
    ReportSpec(
        "movement",
        "Item movement",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Name", 240, stretch=True),
            Column("recv", "Received", 100, "e", "qty"),
            Column("sold", "Sold", 100, "e", "qty"),
            Column("stock", "Closing stock", 110, "e", "qty"),
        ],
        _movement,
        [Param("from", "From", "date", lambda: days_ago_str(30)), Param("to", "To", "date", today_str)],
        open_item_col=0,
    ),
    ReportSpec(
        "low",
        "Low stock",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Name", 240, stretch=True),
            Column("batch", "Batch", 90),
            Column("stock", "In stock", 100, "e", "qty"),
            Column("unit", "Unit", 60),
        ],
        _low_stock,
        [Param("threshold", "At or below", "int", "5")],
        row_tags=lambda r: ["neg"] if r[3] <= 0 else ["warn"],
        open_item_col=0,
    ),
    ReportSpec(
        "expiring",
        "Expiring items",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Name", 240, stretch=True),
            Column("batch", "Batch", 90),
            Column("expiry", "Expiry", 100),
            Column("days", "Days left", 90, "e", "int"),
            Column("stock", "In stock", 100, "e", "qty"),
        ],
        _expiring,
        [Param("days", "Within days", "int", "60")],
        row_tags=lambda r: ["neg"] if r[4] < 0 else ["warn"],
        open_item_col=0,
    ),
    ReportSpec(
        "dead",
        "Dead stock",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Name", 240, stretch=True),
            Column("stock", "In stock", 100, "e", "qty"),
            Column("last", "Last sale", 110),
        ],
        _dead,
        [Param("days", "No sale for days", "int", "90")],
        open_item_col=0,
    ),
    ReportSpec(
        "profit",
        "Item profit",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Item", 220, stretch=True),
            Column("unit", "Unit", 55),
            Column("qty", "Sold", 90, "e", "qty"),
            Column("rev", "Sales value", 120, "e", "money"),
            Column("cost", "Cost", 120, "e", "money"),
            Column("margin", "Margin", 120, "e", "money"),
            Column("pct", "Margin %", 80, "e", "qty"),
        ],
        _profit,
        [Param("from", "From", "date", _fy_start), Param("to", "To", "date", today_str)],
        row_tags=lambda r: ["neg"] if r[6] < 0 else [],
        open_item_col=0,
    ),
    ReportSpec(
        "reorder",
        "Reorder suggestions",
        "Inventory",
        [
            Column("id", "ID", 55, "e", "int"),
            Column("name", "Item", 240, stretch=True),
            Column("unit", "Unit", 55),
            Column("stock", "In stock", 100, "e", "qty"),
            Column("sold", "Sold in window", 120, "e", "qty"),
            Column("left", "Days left", 90, "e", "qty"),
        ],
        _reorder,
        [Param("days", "Sales window (days)", "int", "30")],
        row_tags=lambda r: ["neg"] if r[3] <= 0 else ["warn"],
        open_item_col=0,
    ),
    ReportSpec(
        "krar",
        "Krar list",
        "Krar",
        [
            Column("krar", "Krar", 60, "e", "int"),
            Column("cid", "Cust", 60, "e", "int"),
            Column("name", "Customer", 220, stretch=True),
            Column("details", "Details", 160),
            Column("last", "Promised", 100),
            Column("dates", "History", 240),
        ],
        _krar,
        [Param("bucket", "Show", "choice", "All", ["All", "Overdue", "Today", "Upcoming"])],
        open_customer_col=1,
    ),
    ReportSpec(
        "gst",
        "GST summary (invoices)",
        "Tax",
        [
            Column("month", "Month", 90),
            Column("rate", "GST %", 70, "e", "qty"),
            Column("bills", "Bills", 70, "e", "int"),
            Column("taxable", "Taxable", 130, "e", "money"),
            Column("cgst", "CGST", 110, "e", "money"),
            Column("sgst", "SGST", 110, "e", "money"),
            Column("total", "Total", 130, "e", "money"),
        ],
        _gst,
        [Param("from", "From", "date", _month_start), Param("to", "To", "date", today_str)],
        permission=Permission.BILLING,
    ),
    ReportSpec(
        "staff",
        "Staff activity",
        "Admin",
        [
            Column("user", "User", 120),
            Column("days", "Days active", 100, "e", "int"),
            Column("sales", "Sales", 80, "e", "int"),
            Column("receipts", "Receipts", 80, "e", "int"),
            Column("changes", "Adds / edits", 100, "e", "int"),
            Column("deletes", "Deletes", 80, "e", "int"),
            Column("n", "All actions", 100, "e", "int"),
            Column("last", "Last seen", 150),
        ],
        _staff,
        [Param("from", "From", "date", lambda: days_ago_str(30)), Param("to", "To", "date", today_str)],
        permission=Permission.VIEW_AUDIT,
        row_tags=lambda r: ["warn"] if r[5] else [],
    ),
    ReportSpec(
        "audit",
        "Audit log",
        "Admin",
        [
            Column("id", "ID", 70, "e", "int"),
            Column("ts", "Time", 150),
            Column("user", "User", 90),
            Column("code", "Action", 120),
            Column("msg", "Details", 500, stretch=True),
        ],
        _audit,
        [
            Param("from", "From", "date", lambda: days_ago_str(7)),
            Param("to", "To", "date", today_str),
            Param("code", "Action", "choice", "All", AUDIT_CODES),
            Param("search", "Search", "text"),
        ],
        permission=Permission.VIEW_AUDIT,
    ),
    ReportSpec(
        "datacheck",
        "Data check",
        "Admin",
        [
            Column("sev", "Severity", 80),
            Column("area", "Area", 90),
            Column("ref", "ID", 60, "e", "int"),
            Column("name", "Name", 200),
            Column("issue", "Issue", 260),
            Column("detail", "Detail", 360, stretch=True),
        ],
        _datacheck,
        permission=Permission.VIEW_AUDIT,
        row_tags=lambda r: ["neg"] if r[0] == "ERROR" else (["warn"] if r[0] == "WARN" else ["muted"]),
        open_row=_open_finding,
    ),
]


SCOPED_REPORTS = {
    "collections",
    "fy_interest",
    "profit",
    "summary",
    "aging",
    "top",
    "interest",
    "activity",
    "monthly",
    "items",
    "movement",
    "low",
    "expiring",
    "dead",
}
REPORTS = [replace(spec, params=(*spec.params, SCOPE)) if spec.key in SCOPED_REPORTS else spec for spec in REPORTS]


class ReportsView(BaseView):
    key = "reports"
    title = "Reports"
    permission = Permission.VIEW_REPORTS

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.spec: ReportSpec | None = None
        self._param_widgets: dict[str, object] = {}
        self._buttons: dict[str, ctk.CTkButton] = {}

        nav = ctk.CTkScrollableFrame(
            self,
            width=210,
            fg_color=theme.color("surface"),
            corner_radius=10,
            label_text="Reports",
            label_font=theme.font(14, "bold"),
            label_anchor="w",
        )
        nav.grid(row=0, column=0, sticky="nsw", padx=(4, 8), pady=4)
        group = None
        for spec in REPORTS:
            if not self.ctx.can(spec.permission):
                continue
            if spec.group != group:
                group = spec.group
                ctk.CTkLabel(
                    nav,
                    text=group.upper(),
                    font=theme.font(11, "bold"),
                    text_color=theme.color("muted"),
                    anchor="w",
                ).pack(fill="x", pady=(10, 2), padx=4)
            b = ctk.CTkButton(
                nav,
                text=spec.title,
                anchor="w",
                font=theme.font(13),
                height=32,
                fg_color="transparent",
                hover_color=theme.color("surface2"),
                text_color=theme.color("text"),
                command=lambda s=spec: self.select(s),
            )
            b.pack(fill="x", pady=1)
            self._buttons[spec.key] = b

        main = ctk.CTkFrame(self, fg_color=theme.color("surface"), corner_radius=10)
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 4))
        self.title_label = ctk.CTkLabel(head, text="Choose a report", font=theme.font(17, "bold"))
        self.title_label.pack(side="left")
        secondary_button(head, "Export Excel", self.export, width=110).pack(side="right")
        self.row_filter = ctk.CTkEntry(
            head, placeholder_text="Filter rows…  (any words)", width=240, height=34, font=theme.font(13)
        )
        self.row_filter.pack(side="right", padx=8)
        self.row_filter.bind("<KeyRelease>", lambda e: self.table.filter(self.row_filter.get()) if self.table else None)
        self.params_frame = ctk.CTkFrame(main, fg_color="transparent")
        self.params_frame.pack(fill="x", padx=12, pady=(0, 6))
        self.table_host = ctk.CTkFrame(main, fg_color="transparent")
        self.table_host.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.table: DataTable | None = None
        self.hint = ctk.CTkLabel(
            self.table_host,
            text="Pick a report on the left.",
            font=theme.font(13),
            text_color=theme.color("muted"),
        )
        self.hint.pack(expand=True)

    def on_show(self, report: str | None = None, **kwargs) -> None:
        if report:
            for spec in REPORTS:
                if spec.key == report and self.ctx.can(spec.permission):
                    self.select(spec)
        elif self.spec is None:
            self.select(REPORTS[0])

    def on_theme_change(self) -> None:
        if self.table:
            self.table.restyle()

    # Selection & params ----------------------------------------------------------------
    def select(self, spec: ReportSpec) -> None:
        self.spec = spec
        for key, b in self._buttons.items():
            b.configure(fg_color=theme.color("select") if key == spec.key else "transparent")
        self.title_label.configure(text=spec.title)
        for w in self.params_frame.winfo_children():
            w.destroy()
        self._param_widgets = {}
        for p in spec.params:
            box = ctk.CTkFrame(self.params_frame, fg_color="transparent")
            box.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(box, text=p.label, font=theme.font(11), text_color=theme.color("muted"), anchor="w").pack(
                fill="x"
            )
            if p.kind == "customer":
                w = SearchBox(
                    box,
                    lambda: [(c.id, c.display) for c in self.ctx.accounts.list_customers()],
                    "Search customer",
                    width=320,
                )
                w.refresh()
            elif p.kind == "choice":
                w = ctk.CTkOptionMenu(box, values=list(p.choices), font=theme.font(13), height=34, width=160)
                w.set(_default(p))
            else:
                w = ctk.CTkEntry(box, font=theme.font(13), height=34, width=130 if p.kind != "text" else 220)
                w.insert(0, _default(p))
                w.bind("<Return>", lambda e: self.run())
            w.pack()
            self._param_widgets[p.key] = w
        primary_button(self.params_frame, "Run", self.run, width=90).pack(side="left", pady=(14, 0))

        if self.table:
            self.table.destroy()
        self.row_filter.delete(0, "end")
        self.hint.pack_forget()
        self.table = DataTable(self.table_host, spec.columns, row_tags=spec.row_tags, on_double_click=self._open_row)
        self.table.pack(fill="both", expand=True)
        if not any(p.kind == "customer" for p in spec.params):
            self.run()

    def _params(self) -> dict:
        out = {}
        for key, w in self._param_widgets.items():
            out[key] = w.get_key() if isinstance(w, SearchBox) else w.get().strip()
        return out

    def run(self) -> None:
        if not self.spec or not self.table:
            return
        spec, params = self.spec, self._params()
        self.table.set_footer("Running…")
        self.run_async(
            lambda: spec.run(self.ctx, params),
            lambda res: self.table.set_rows(res[0], res[1]) if self.spec is spec else None,
            lambda exc: self.ctx.toast(str(exc), "error"),
        )

    def _open_row(self, row) -> None:
        if not self.spec:
            return
        if self.spec.open_row is not None:
            target = self.spec.open_row(row)
            if target:
                self.ctx.navigate(target[0], **target[1])
            return
        if self.spec.open_customer_col is not None and self.ctx.can(Permission.ADD_CUSTOMER):
            self.ctx.navigate("customers", customer_id=int(row[self.spec.open_customer_col]))
        elif self.spec.open_item_col is not None and self.ctx.can(Permission.ADD_ITEM):
            self.ctx.navigate("items", item_id=int(row[self.spec.open_item_col]))

    def export(self) -> None:
        if not (self.spec and self.table and self.table.rows):
            self.ctx.toast("Nothing to export", "warning")
            return
        path = self.ctx.settings.export_dir / f"{safe_filename(self.spec.title)}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        export_rows(path, self.table.export_columns(), self.table.export_rows(), self.spec.title)
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)
