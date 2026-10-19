"""Customer and item categories (A-E).

* Stored on the record.  New customers/items get ``default_category`` (C).
* **E** = defaulter (customers) / discontinued (items): assigned by hand only; re-scoring
  never gives or takes away E.
* Setting a category by hand *locks* it - re-scoring skips locked records.
* Re-scoring maps the v3 account score (0 = small & recent ... 1 = large & long
  outstanding) to A-D by three thresholds.  Customers with nothing outstanding are A.
* With ``exclude_defaulters_from_score`` on (default), E customers are left out of the
  score's min/max normalisation so they do not push everyone else down.
* ``report_categories`` decide which customers / items feed the dashboard and reports.
* Items can be auto-categorised by sales velocity: sold within N1 days = A, N2 = B,
  N3 = C, older or never = D.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field

from hth.db.connection import Database
from hth.domain.constants import CATEGORIES, DEFAULTER_CATEGORY, AuditCode
from hth.domain.interest import parse_date
from hth.domain.models import CustomerSummary
from hth.services.accounts import AccountsService, ValidationError
from hth.services.audit import AuditService
from hth.services.inventory import InventoryService
from hth.services.settings import SettingsService

DEFAULTS: dict[str, str] = {
    "customer.default_category": "C",
    "customer.report_categories": "A,B,C,D",
    "customer.thresholds": "0.25,0.5,0.75",
    "customer.exclude_defaulters_from_score": "1",
    "item.report_categories": "A,B,C,D",
    "item.velocity_days": "30,90,180",
}


@dataclass
class RescoreReport:
    counts: dict[str, int] = field(default_factory=dict)  # category -> customers now in it
    changed: int = 0
    locked: int = 0
    defaulters: int = 0

    def as_text(self) -> str:
        cats = ", ".join(f"{k}: {v}" for k, v in sorted(self.counts.items()))
        return f"{self.changed} changed · {self.locked} locked (kept) · {self.defaulters} defaulters (E)\n{cats}"


def _validate_categories(values: Iterable[str]) -> set[str]:
    cats = {str(v).strip().upper() for v in values}
    bad = cats - set(CATEGORIES)
    if bad:
        raise ValidationError(f"Unknown categories: {', '.join(sorted(bad))}")
    return cats


class CategoryService:
    def __init__(self, db: Database):
        self.db = db
        self.settings = SettingsService(db, DEFAULTS)
        self.accounts = AccountsService(db)
        self.inventory = InventoryService(db)
        self.audit = AuditService(db)

    # Settings ------------------------------------------------------------------------
    def customer_report_categories(self) -> set[str]:
        return set(self.settings.get_list("customer.report_categories"))

    def set_customer_report_categories(self, cats: Iterable[str]) -> None:
        self.settings.set_list("customer.report_categories", _validate_categories(cats))

    def item_report_categories(self) -> set[str]:
        return set(self.settings.get_list("item.report_categories"))

    def set_item_report_categories(self, cats: Iterable[str]) -> None:
        self.settings.set_list("item.report_categories", _validate_categories(cats))

    def thresholds(self) -> tuple[float, float, float]:
        vals = self.settings.get_floats("customer.thresholds")
        if len(vals) != 3:
            vals = [float(x) for x in DEFAULTS["customer.thresholds"].split(",")]
        return vals[0], vals[1], vals[2]

    def set_thresholds(self, a_max: float, b_max: float, c_max: float) -> None:
        vals = [float(a_max), float(b_max), float(c_max)]
        if not (0 < vals[0] < vals[1] < vals[2] <= 1):
            raise ValidationError("Thresholds must be increasing values between 0 and 1 (e.g. 0.25, 0.5, 0.75).")
        self.settings.set("customer.thresholds", ",".join(f"{v:g}" for v in vals))

    def exclude_defaulters_from_score(self) -> bool:
        return self.settings.get_bool("customer.exclude_defaulters_from_score")

    def set_exclude_defaulters_from_score(self, on: bool) -> None:
        self.settings.set("customer.exclude_defaulters_from_score", "1" if on else "0")

    def default_customer_category(self) -> str:
        v = self.settings.get("customer.default_category").upper()
        return v if v in CATEGORIES and v != DEFAULTER_CATEGORY else "C"

    def set_default_customer_category(self, cat: str) -> None:
        cat = (cat or "").upper()
        if cat not in CATEGORIES or cat == DEFAULTER_CATEGORY:
            raise ValidationError("Default category must be A-D.")
        self.settings.set("customer.default_category", cat)

    def velocity_days(self) -> tuple[int, int, int]:
        vals = [int(float(x)) for x in self.settings.get("item.velocity_days").split(",") if x.strip()]
        if len(vals) != 3:
            vals = [30, 90, 180]
        return vals[0], vals[1], vals[2]

    def set_velocity_days(self, a: int, b: int, c: int) -> None:
        vals = [int(a), int(b), int(c)]
        if not (0 < vals[0] < vals[1] < vals[2]):
            raise ValidationError("Velocity days must be increasing (e.g. 30, 90, 180).")
        self.settings.set("item.velocity_days", ",".join(str(v) for v in vals))

    # Scoped queries used by dashboard / reports -------------------------------------------
    def score_exclusions(self) -> set[str]:
        return {DEFAULTER_CATEGORY} if self.exclude_defaulters_from_score() else set()

    def customer_summaries(self, as_of: dt.date | None = None, scope: str = "settings") -> list[CustomerSummary]:
        """``scope``: 'settings' = categories chosen in Settings, 'all' = everyone."""
        cats = None if scope == "all" else self.customer_report_categories()
        return self.accounts.summaries(as_of, categories=cats, exclude_from_score=self.score_exclusions())

    def customer_scope(self, scope: str = "settings") -> set[str] | None:
        return None if scope == "all" else self.customer_report_categories()

    def item_scope(self, scope: str = "settings") -> set[str] | None:
        return None if scope == "all" else self.item_report_categories()

    # Assignment ------------------------------------------------------------------------
    def category_for_score(self, score: float, balance: float) -> str:
        if balance <= 0:
            return "A"
        a, b, c = self.thresholds()
        if score < a:
            return "A"
        if score < b:
            return "B"
        if score < c:
            return "C"
        return "D"

    def set_customer_category(self, customer_id: int, category: str, username: str) -> None:
        self.accounts.set_category(customer_id, category, username, locked=True)

    def unlock_customer(self, customer_id: int, username: str) -> None:
        c = self.accounts.get_customer(customer_id)
        if c is None:
            return
        if c.category == DEFAULTER_CATEGORY:
            raise ValidationError("Category E is manual - set another category first.")
        self.accounts.set_category(customer_id, c.category, username, locked=False)

    def set_item_category(self, item_id: int, category: str, username: str) -> None:
        self.inventory.set_category(item_id, category, username, locked=True)

    def rescore_customers(self, username: str, as_of: dt.date | None = None) -> RescoreReport:
        report = RescoreReport()
        summaries = {s.id: s for s in self.accounts.summaries(as_of, exclude_from_score=self.score_exclusions())}
        with self.db.connect():
            for c in self.accounts.list_customers():
                if c.category == DEFAULTER_CATEGORY:
                    report.defaulters += 1
                    report.counts["E"] = report.counts.get("E", 0) + 1
                    continue
                if c.category_locked:
                    report.locked += 1
                    report.counts[c.category] = report.counts.get(c.category, 0) + 1
                    continue
                s = summaries[c.id]
                new = self.category_for_score(s.score, s.balance)
                if new != c.category:
                    self.db.execute("UPDATE customers SET category = ? WHERE id = ?", (new, c.id))
                    report.changed += 1
                report.counts[new] = report.counts.get(new, 0) + 1
            self.audit.log(
                AuditCode.MODIFY,
                f"re-scored customers: {report.changed} changed, {report.locked} locked, {report.defaulters} E",
                username,
            )
        return report

    def auto_categorize_items(self, username: str, today: dt.date | None = None) -> RescoreReport:
        today = today or dt.date.today()
        a, b, c = self.velocity_days()
        last_sale = self.inventory.last_sale_dates()
        report = RescoreReport()
        with self.db.connect():
            for item in self.inventory.list_items():
                if item.category == DEFAULTER_CATEGORY:
                    report.defaulters += 1
                    report.counts["E"] = report.counts.get("E", 0) + 1
                    continue
                if item.category_locked:
                    report.locked += 1
                    report.counts[item.category] = report.counts.get(item.category, 0) + 1
                    continue
                last = last_sale.get(item.id)
                age = (today - parse_date(last)).days if last else None
                new = "D" if age is None else "A" if age <= a else "B" if age <= b else "C" if age <= c else "D"
                if new != item.category:
                    self.db.execute("UPDATE items SET category = ? WHERE id = ?", (new, item.id))
                    report.changed += 1
                report.counts[new] = report.counts.get(new, 0) + 1
            self.audit.log(
                AuditCode.MODIFY,
                f"auto-categorised items: {report.changed} changed, {report.locked} locked, {report.defaulters} E",
                username,
            )
        return report
