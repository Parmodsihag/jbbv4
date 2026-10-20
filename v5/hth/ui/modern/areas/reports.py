"""Reports - one catalogue for every report in the new layout.

A search box, pinned favourites (shop-wide, ``reports.pinned``) and the reports in groups.
Opening a core report shows it in the classic report runner - parameters, filter, sort,
Excel - with a way back to the catalogue; a module's report (crops, finance) opens on that
module's own screen, straight on the chosen report.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import customtkinter as ctk

from hth import i18n
from hth.modules import discover
from hth.services.permissions import Permission
from hth.services.settings import SettingsService
from hth.ui import theme
from hth.ui.modern.widgets import button, card
from hth.ui.views.base import BaseView
from hth.ui.views.reports import REPORTS, ReportsView

PINS_KEY = "reports.pinned"
DEFAULT_PINS = "r:collections,r:daybook,r:reorder,m:finance:Profit & loss"
MAX_PINS = 4

# classic report -> (new group, one-line hint)
GROUPS = ("Customers & collections", "Stock", "Crops", "Money", "Sales & tax", "Admin")
CORE = {
    "collections": ("Customers & collections", "everyone who owes, biggest first"),
    "krar": ("Customers & collections", "late · today · upcoming promises"),
    "forecast": ("Customers & collections", "promised money, next N days"),
    "aging": ("Customers & collections", "who owes, by how long"),
    "top": ("Customers & collections", "the biggest balances"),
    "summary": ("Customers & collections", "every account, balance and days"),
    "ledger": ("Customers & collections", "one customer"),
    "activity": ("Customers & collections", "dates"),
    "interest": ("Customers & collections", "interest on open balances"),
    "fy_interest": ("Customers & collections", "principal and interest per year"),
    "items": ("Stock", "every item and its value"),
    "low": ("Stock", "below how many"),
    "reorder": ("Stock", "what the current sales will use up"),
    "expiring": ("Stock", "within days"),
    "dead": ("Stock", "days without a sale"),
    "movement": ("Stock", "dates"),
    "profit": ("Stock", "dates"),
    "daybook": ("Sales & tax", "every entry of one day"),
    "monthly": ("Sales & tax", "months"),
    "gst": ("Sales & tax", "dates"),
    "datacheck": ("Admin", "double-click a finding to fix it"),
    "staff": ("Admin", "dates"),
    "audit": ("Admin", "dates, action, words"),
}
MODULE_GROUPS = {"crops": "Crops", "finance": "Money"}


@dataclass(frozen=True)
class Entry:
    id: str  # r:<report key> | m:<module key>:<report name>
    title: str
    hint: str
    group: str
    open: Callable[[], None]


class ReportsArea(BaseView):
    key = "reports"
    title = "Reports"
    permission = Permission.VIEW_REPORTS

    def build(self) -> None:
        self.settings = SettingsService(self.ctx.db, {PINS_KEY: DEFAULT_PINS})
        self.entries = self._entries()
        self.catalogue = ctk.CTkFrame(self, fg_color="transparent")
        self.runner_box = ctk.CTkFrame(self, fg_color="transparent")
        bar = ctk.CTkFrame(self.runner_box, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 6))
        button(bar, "← All reports", self.show_catalogue, height=32).pack(side="left")
        self.pin_button = button(bar, "", self._toggle_runner_pin, height=32)
        self.pin_button.pack(side="left", padx=8)
        self.runner: ReportsView | None = None
        self.current_report: str | None = None
        self._build_catalogue()

    # Data ------------------------------------------------------------------------------
    def _entries(self) -> list[Entry]:
        out = []
        for spec in REPORTS:
            if not self.ctx.can(spec.permission):
                continue
            group, hint = CORE.get(spec.key, (spec.group, ""))
            out.append(Entry(f"r:{spec.key}", spec.title, hint, group, lambda k=spec.key: self.open_report(k)))
        for spec in discover():
            if not spec.reports or not self.ctx.can(spec.permission):
                continue
            if spec.key == "finance" and not self.ctx.can(Permission.FINANCE_REPORTS):
                continue
            group = MODULE_GROUPS.get(spec.key, spec.label)
            where = f"opens in {spec.tab or spec.label}" if spec.key != "finance" else "opens in Money"
            for name in spec.reports:
                out.append(
                    Entry(
                        f"m:{spec.key}:{name}",
                        name,
                        where,
                        group,
                        lambda k=spec.key, n=name: self.ctx.navigate(k, report=n),
                    )
                )
        return out

    def pins(self) -> list[str]:
        ids = {e.id for e in self.entries}
        return [p for p in self.settings.get(PINS_KEY).split(",") if p in ids][:MAX_PINS]

    def toggle_pin(self, entry_id: str) -> None:
        pins = [p for p in self.settings.get(PINS_KEY).split(",") if p]
        if entry_id in pins:
            pins.remove(entry_id)
        else:
            pins = [entry_id, *pins][:MAX_PINS]
        self.settings.set(PINS_KEY, ",".join(pins))
        self._render()

    # Catalogue -------------------------------------------------------------------------
    def _build_catalogue(self) -> None:
        head = ctk.CTkFrame(self.catalogue, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(head, text="Reports", font=theme.font(22, "bold")).pack(side="left")
        self.search = ctk.CTkEntry(
            head,
            placeholder_text="Find a report — aging, gst, lots, profit…",
            width=420,
            height=36,
            font=theme.font(13),
        )
        self.search.pack(side="left", padx=16)
        self.search.bind("<KeyRelease>", lambda e: self._render())
        self.search.bind("<Return>", lambda e: self._open_first())
        ctk.CTkLabel(
            head,
            text=f"{len(self.entries)} reports · each one sorts, filters and goes to Excel",
            font=theme.font(12),
            text_color=theme.color("muted"),
        ).pack(side="left")
        self.pinned = ctk.CTkFrame(self.catalogue, fg_color="transparent")
        self.pinned.pack(fill="x")
        self.grid_box = ctk.CTkScrollableFrame(self.catalogue, fg_color="transparent")
        self.grid_box.pack(fill="both", expand=True, pady=(12, 0))
        self.grid_box.grid_columnconfigure((0, 1, 2), weight=1, uniform="g")

    def _render(self) -> None:
        words = self.search.get().strip().lower().split()
        pins = self.pins()

        for w in self.pinned.winfo_children():
            w.destroy()
        shown_pins = [e for p in pins for e in self.entries if e.id == p]
        if shown_pins and not words:
            ctk.CTkLabel(
                self.pinned,
                text=i18n.tr("Pinned").upper(),
                font=theme.font(11, "bold"),
                text_color=theme.color("muted"),
            ).pack(anchor="w")
            row = ctk.CTkFrame(self.pinned, fg_color="transparent")
            row.pack(fill="x", pady=(4, 0))
            for i in range(MAX_PINS):
                row.grid_columnconfigure(i, weight=1, uniform="p")
            for i, e in enumerate(shown_pins):
                c = card(row, cursor="hand2")
                c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
                t = ctk.CTkLabel(c, text=f"★  {i18n.tr(e.title)}", font=theme.font(14, "bold"), anchor="w")
                t.pack(fill="x", padx=14, pady=(10, 0))
                h = ctk.CTkLabel(c, text=e.hint, font=theme.font(11), text_color=theme.color("muted"), anchor="w")
                h.pack(fill="x", padx=14, pady=(0, 10))
                for w in (c, t, h):
                    w.bind("<Button-1>", lambda ev, en=e: en.open())

        for w in self.grid_box.winfo_children():
            w.destroy()
        groups: dict[str, list[Entry]] = {}
        for e in self.entries:
            text = f"{e.title} {i18n.tr(e.title)} {e.hint} {e.group}".lower()
            if all(w in text for w in words):
                groups.setdefault(e.group, []).append(e)
        order = [g for g in GROUPS if g in groups] + [g for g in groups if g not in GROUPS]
        # three columns: the long customers group alone, the rest stacked two by two
        columns: list[list[str]] = [[], [], []]
        for g in order:
            columns[min(range(3), key=lambda i: sum(len(groups[x]) + 2 for x in columns[i]))].append(g)
        self._shown = [e for g in order for e in groups[g]]
        for col, names in enumerate(columns):
            box = ctk.CTkFrame(self.grid_box, fg_color="transparent")
            box.grid(row=0, column=col, sticky="new", padx=(0 if col == 0 else 6, 0))
            for g in names:
                self._group(box, g, groups[g], pins)
        if not self._shown:
            ctk.CTkLabel(
                self.grid_box, text="No report matches - try another word.", text_color=theme.color("muted")
            ).grid(row=0, column=0, sticky="w", pady=20)

    def _group(self, master, name: str, entries: list[Entry], pins: list[str]) -> None:
        c = card(master)
        c.pack(fill="x", pady=(0, 10))
        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(head, text=name, font=theme.font(14, "bold")).pack(side="left")
        ctk.CTkLabel(head, text=str(len(entries)), font=theme.font(12), text_color=theme.color("muted")).pack(
            side="left", padx=8
        )
        for e in entries:
            ctk.CTkFrame(c, height=1, fg_color=theme.color("line")).pack(fill="x", padx=14)
            r = ctk.CTkFrame(c, fg_color="transparent")
            r.pack(fill="x", padx=8, pady=1)
            star = ctk.CTkButton(
                r,
                text="★" if e.id in pins else "☆",
                width=26,
                height=26,
                fg_color="transparent",
                hover_color=theme.color("surface_hover"),
                text_color=theme.color("accent") if e.id in pins else theme.color("muted"),
                font=theme.font(14),
                command=lambda i=e.id: self.toggle_pin(i),
            )
            star.pack(side="left")
            ctk.CTkButton(
                r,
                text=e.title,
                anchor="w",
                width=10,
                height=26,
                fg_color="transparent",
                hover_color=theme.color("surface_hover"),
                text_color=theme.color("accent"),
                font=theme.font(13, "bold"),
                command=e.open,
            ).pack(side="left")
            if e.hint:
                ctk.CTkLabel(r, text=e.hint, font=theme.font(11), text_color=theme.color("muted")).pack(
                    side="left", padx=4
                )
        ctk.CTkFrame(c, height=6, fg_color="transparent").pack()

    def _open_first(self) -> None:
        if getattr(self, "_shown", None):
            self._shown[0].open()

    # Showing ---------------------------------------------------------------------------
    def show_catalogue(self) -> None:
        self.runner_box.pack_forget()
        self.catalogue.pack(fill="both", expand=True)
        self.current_report = None
        self._render()
        self.after(60, self.search.focus_set)

    def open_report(self, key: str, **kwargs) -> None:
        if self.runner is None:
            self.runner = ReportsView(self.runner_box, self.ctx)
            for w in self.runner.grid_slaves(row=0, column=0):
                w.grid_remove()  # its own list of reports: the catalogue does that job here
            self.runner.pack(fill="both", expand=True)
        self.catalogue.pack_forget()
        self.runner_box.pack(fill="both", expand=True)
        self.current_report = key
        self._update_runner_pin()
        self.runner.on_show(report=key, **kwargs)

    def _update_runner_pin(self) -> None:
        pinned = f"r:{self.current_report}" in self.pins()
        self.pin_button.configure(text="★  Pinned" if pinned else "☆  Pin")

    def _toggle_runner_pin(self) -> None:
        if self.current_report:
            self.toggle_pin(f"r:{self.current_report}")
            self._update_runner_pin()

    def child(self, key: str):
        return self.runner if key == "reports" and self.current_report else None

    def on_show(self, report: str | None = None, tab: str | None = None, **kwargs) -> None:
        if report and any(s.key == report and self.ctx.can(s.permission) for s in REPORTS):
            self.open_report(report, **kwargs)
        elif self.current_report is None:
            self.show_catalogue()
        else:
            self.runner.on_show()

    def on_theme_change(self) -> None:
        if self.runner is not None:
            self.runner.on_theme_change()
