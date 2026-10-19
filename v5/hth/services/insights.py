""" "Needs attention" findings for the dashboard: things the shop should act on today.

Each insight names what is wrong, how big it is, and where to go to fix it.  Everything is
computed from data the shop already records - nothing here writes to the database.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from hth.config import Settings
from hth.db.connection import Database
from hth.domain import numbers
from hth.domain.constants import DATE_FMT, DEFAULTER_CATEGORY
from hth.domain.models import CustomerSummary
from hth.services.auth import DEFAULT_USERS, AuthService
from hth.services.integrity import IntegrityService
from hth.services.inventory import InventoryService
from hth.services.krar import KrarService

SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2, "ok": 3}
INACTIVE_DAYS = 180
EXPIRY_DAYS = 30
REORDER_WINDOW_DAYS = 30
BACKUP_STALE_DAYS = 2


@dataclass(frozen=True)
class Insight:
    severity: str  # danger | warning | info | ok
    title: str
    detail: str = ""
    view: str | None = None  # where to fix it (navigation key)
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReorderLine:
    item_id: int
    name: str
    unit: str
    in_stock: float
    sold_window: float  # sold in the last REORDER_WINDOW_DAYS
    days_left: float | None  # at the recent selling rate; None = not selling


class InsightsService:
    def __init__(self, db: Database, settings: Settings | None = None):
        self.db = db
        self.settings = settings
        self.inventory = InventoryService(db)
        self.krar = KrarService(db)

    # Building blocks ---------------------------------------------------------------------
    def reorder_suggestions(
        self, window_days: int = REORDER_WINDOW_DAYS, today: dt.date | None = None
    ) -> list[ReorderLine]:
        """Items whose sales over the last ``window_days`` exceed (or use up) the stock on hand,
        most urgent first.  Discontinued (E) items are left out."""
        today = today or dt.date.today()
        since = (today - dt.timedelta(days=window_days)).strftime(DATE_FMT)
        rows = self.db.fetchall(
            "SELECT i.id, i.name, i.unit, i.category, COALESCE(SUM(t.received - t.sale), 0) AS stock, "
            "COALESCE(SUM(CASE WHEN t.date >= ? THEN t.sale END), 0) AS sold "
            "FROM items i LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id",
            (since,),
        )
        out = []
        for r in rows:
            sold, stock = float(r["sold"]), float(r["stock"])
            if r["category"] == DEFAULTER_CATEGORY or sold <= 0 or stock > sold:
                continue
            rate = sold / window_days
            out.append(
                ReorderLine(
                    r["id"], r["name"], r["unit"], round(stock, 4), round(sold, 4), round(max(stock, 0) / rate, 1)
                )
            )
        return sorted(out, key=lambda x: (x.days_left if x.days_left is not None else 1e9, -x.sold_window))

    def default_password_users(self) -> list[str]:
        """Built-in accounts still using their first-launch password (admin/admin, emp1/emp1)."""
        auth = AuthService(self.db)
        return [u for u, p, _n, _r in DEFAULT_USERS if auth.verify(u, p) is not None]

    # The list ----------------------------------------------------------------------------
    def collect(self, summaries: list[CustomerSummary], today: dt.date | None = None) -> list[Insight]:
        today = today or dt.date.today()
        today_s = today.strftime(DATE_FMT)
        out: list[Insight] = []
        balances = {s.id: s.balance for s in summaries}

        overdue = self.krar.entries("past", today)
        if overdue:
            owed = sum(max(balances.get(e.customer_id, 0.0), 0.0) for e in overdue)
            out.append(
                Insight(
                    "danger",
                    f"{len(overdue)} promised payment(s) overdue",
                    f"{numbers.amount(owed)} outstanding on those accounts",
                    "karar",
                    {"bucket": "Overdue"},
                )
            )
        due_today = self.krar.entries("today", today)
        if due_today:
            out.append(Insight("warning", f"{len(due_today)} promise(s) due today", "", "karar", {"bucket": "Today"}))

        silent = [s for s in summaries if s.balance > 0 and s.days >= INACTIVE_DAYS]
        if silent:
            out.append(
                Insight(
                    "warning",
                    f"{len(silent)} debtor(s) silent for {INACTIVE_DAYS}+ days",
                    f"{numbers.amount(sum(s.balance for s in silent))} owed - consider a krar or a reminder",
                    "reports",
                    {"report": "collections"},
                )
            )

        reorder = self.reorder_suggestions(today=today)
        if reorder:
            names = ", ".join(r.name for r in reorder[:3])
            out.append(
                Insight(
                    "warning",
                    f"{len(reorder)} item(s) may run out within a month",
                    names + (" …" if len(reorder) > 3 else ""),
                    "reports",
                    {"report": "reorder"},
                )
            )

        expiring = [(s, d) for s, d in self.inventory.expiring(EXPIRY_DAYS, today) if s.in_stock > 0]
        if expiring:
            expired = sum(1 for _s, d in expiring if d < 0)
            detail = f"{expired} already expired" if expired else f"within {EXPIRY_DAYS} days"
            out.append(
                Insight(
                    "danger" if expired else "warning",
                    f"{len(expiring)} item(s) with stock expiring",
                    detail,
                    "reports",
                    {"report": "expiring"},
                )
            )

        findings = IntegrityService(self.db).run(today)
        errors = sum(1 for f in findings if f.severity == "ERROR")
        future = sum(1 for f in findings if f.issue == "Entry dated in the future")
        if errors:
            out.append(
                Insight(
                    "danger", f"{errors} data error(s)", "wrong numbers until fixed", "reports", {"report": "datacheck"}
                )
            )
        if future:
            out.append(
                Insight(
                    "info",
                    f"{future} ledger entr{'y is' if future == 1 else 'ies are'} dated after {today_s}",
                    "usually a typo in the year",
                    "reports",
                    {"report": "datacheck"},
                )
            )

        if self.settings is not None:
            backups = sorted(self.settings.backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime)
            if not backups:
                out.append(Insight("warning", "No backup yet", "Settings → Backup now", "settings"))
            else:
                age = (dt.datetime.now() - dt.datetime.fromtimestamp(backups[-1].stat().st_mtime)).days
                if age >= BACKUP_STALE_DAYS:
                    out.append(
                        Insight("warning", f"Last backup is {age} days old", "Settings → Backup now", "settings")
                    )

        weak = self.default_password_users()
        if weak:
            out.append(
                Insight(
                    "danger",
                    "Default password still in use",
                    ", ".join(weak) + " - change it in Users / Settings",
                    "users" if "admin" in weak else "settings",
                )
            )

        if not out:
            out.append(Insight("ok", "All clear", "nothing needs attention right now"))
        return sorted(out, key=lambda i: SEVERITY_ORDER[i.severity])
