"""Money - the cash book, GST bills and the finance reports in the new layout.

*Cash book*: a tile per money account (click one to see its book), monthly expenses that
are due, the entries of the period with + Expense / + Other income / Transfer, and this
month's money in and out.  It talks to the finance module through the money-flow handler
the Counter already uses, so core still never imports a module.  *GST bills* and
*Reports & setup* are the bills and finance modules' own screens, hosted here.
"""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth import i18n
from hth.modules import discover
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.services.sales import money_flow_handler
from hth.ui import theme
from hth.ui.format import open_path, today_str
from hth.ui.modern.actions import _lines
from hth.ui.modern.widgets import Freshness, button, card, dropdown_menu, popup, rupees, segmented
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, confirm, run_form

PERIODS = ["Today", "This week", "This month", "Last 30 days"]
CASH_BOOK = "Cash book"
REPORTS = "Reports & setup"


def _period(name: str) -> tuple[str, str]:
    today = dt.date.today()
    start = {
        "Today": today,
        "This week": today - dt.timedelta(days=today.weekday()),
        "This month": today.replace(day=1),
    }.get(name, today - dt.timedelta(days=30))
    return start.isoformat(), today.isoformat()


class MoneyView(BaseView):
    key = "money"
    title = "Money"
    permission = Permission.FINANCE

    def build(self) -> None:
        specs = {s.key: s for s in discover() if getattr(s, "area", None) == "money" and self.ctx.can(s.permission)}
        self.flow = money_flow_handler(self.ctx.db) if "finance" in specs else None
        self.pages: dict[str, tuple[str, object]] = {}  # name -> (classic key, factory or None)
        if self.flow is not None:
            self.pages[CASH_BOOK] = ("finance", None)
        if "bills" in specs:
            self.pages[specs["bills"].tab or "GST bills"] = ("bills", specs["bills"].view_factory)
        if "finance" in specs and self.ctx.can(Permission.FINANCE_REPORTS):
            self.pages[REPORTS] = ("finance_reports", specs["finance"].view_factory)
        for key, spec in specs.items():  # any other module that names Money as its area
            if key not in ("finance", "bills"):
                self.pages[spec.tab or spec.label] = (key, spec.view_factory)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        self.switch = segmented(head, list(self.pages), command=lambda v: self.show_page(v))
        self.switch.pack(side="left")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.book = CashBookPage(self.body, self) if self.flow is not None else None
        self.hosted: dict[str, BaseView] = {}
        self.current: str | None = None

    def show_page(self, name: str, **kwargs) -> None:
        if name not in self.pages:
            return
        for page in (self.book, *self.hosted.values()):
            if page is not None:
                page.pack_forget()
        key, factory = self.pages[name]
        if factory is None:
            page = self.book
        else:
            page = self.hosted.get(name)
            if page is None:
                page = factory(self.body, self.ctx)
                self.hosted[name] = page
        page.pack(fill="both", expand=True)
        self.current = key
        self.switch.set(name)
        page.on_show(**kwargs)

    def _page_for(self, key: str) -> str | None:
        return next((n for n, (k, _f) in self.pages.items() if k == key), None)

    def child(self, key: str):
        if key == "finance":
            return self.book
        name = self._page_for(key)
        return self.hosted.get(name) if name else None

    def on_show(self, tab: str | None = None, **kwargs) -> None:
        if tab == "finance" and kwargs.get("report") and REPORTS in self.pages:
            self.show_page(REPORTS, **kwargs)  # a finance report, from the Reports catalogue
            return
        name = self._page_for(tab) if tab else None
        if name is None:
            name = self._page_for(self.current) if self.current else next(iter(self.pages), None)
        if name is not None:
            self.show_page(name, **kwargs)

    def on_theme_change(self) -> None:
        if self.book is not None:
            self.book.table.restyle()
        for view in self.hosted.values():
            view.on_theme_change()

    def on_day_change(self) -> None:
        for view in self.hosted.values():
            view.on_day_change()
        if self.book is not None and self.current == "finance":
            self.book.reload()


# --------------------------------------------------------------------------------------
class CashBookPage(ctk.CTkFrame):
    def __init__(self, master, view: MoneyView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.flow = view, view.ctx, view.flow
        self.account_id: int | None = None
        self.tiles: dict[int, tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]] = {}
        self.fresh = Freshness(self.ctx.db)

        self.tile_row = ctk.CTkFrame(self, fg_color="transparent")
        self.tile_row.pack(fill="x")
        self.banner = ctk.CTkFrame(
            self,
            fg_color=theme.color("warn_soft"),
            corner_radius=10,
            border_width=1,
            border_color=theme.color("warning"),
        )
        self.banner_text = ctk.CTkLabel(self.banner, text="", font=theme.font(13), text_color=theme.color("warning"))
        self.banner_text.pack(side="left", padx=14, pady=8)
        self.banner_button = button(self.banner, "Post now", self.post_due, height=30)
        self.banner_button.pack(side="right", padx=10)

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True, pady=(12, 0))
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_columnconfigure(1, weight=0, minsize=300)
        self.main.grid_rowconfigure(0, weight=1)

        book = card(self.main)
        book.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        bar = ctk.CTkFrame(book, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(12, 6))
        self.period = segmented(bar, PERIODS, command=lambda _v: self.reload(), height=30)
        self.period.set("Today")
        self.period.pack(side="left")
        button(bar, "Excel", self.export, height=32).pack(side="right")
        self.more_button = button(bar, "More ▾", self._more_menu, height=32)
        self.more_button.pack(side="right", padx=6)
        button(bar, "Transfer", lambda: self.add_entry("transfer"), height=32).pack(side="right")
        button(bar, "+ Other income", lambda: self.add_entry("income"), height=32).pack(side="right", padx=6)
        button(bar, "+ Expense", lambda: self.add_entry("expense"), primary=True, height=32).pack(side="right")
        can_delete = self.ctx.can(Permission.FINANCE_REPORTS)
        self.table = DataTable(
            book,
            [
                Column("date", "Date", 92),
                Column("type", "Type", 130),
                Column("details", "Details", 240, stretch=True),
                Column("in", "In", 105, "e", "money"),
                Column("out", "Out", 105, "e", "money"),
                Column("balance", "Balance", 115, "e", "money"),
                Column("by", "By", 70),
            ],
            on_double_click=self._open,
            row_actions=(lambda r: [("Delete…", lambda r=r: self.delete_entry(r))]) if can_delete else None,
            row_tags=lambda r: ["pos"] if r[3] else [],
        )
        self.table.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.totals = ctk.CTkLabel(book, text="", font=theme.font(12, "bold"), anchor="w")
        self.totals.pack(fill="x", padx=14, pady=(0, 12))

        side = card(self.main)
        side.grid(row=0, column=1, sticky="nsew")
        self.side = ctk.CTkFrame(side, fg_color="transparent")
        self.side.pack(fill="both", expand=True, padx=14, pady=12)

    # Loading ---------------------------------------------------------------------------
    def on_show(self, **kwargs) -> None:
        if self.fresh.stale():
            self.reload()

    def reload(self) -> None:
        self.fresh.filling()
        balances = self.flow.balances()
        if self.account_id not in {a.id for a, _b in balances}:
            default = self.flow.default_account_id()
            self.account_id = (
                default if default in {a.id for a, _b in balances} else (balances[0][0].id if balances else None)
            )
        self._render_tiles(balances)
        self._render_banner()
        self._render_book()
        self._render_month()

    def _render_tiles(self, balances) -> None:
        for w in self.tile_row.winfo_children():
            w.destroy()
        self.tiles.clear()
        cols = len(balances) + 1
        for i in range(cols):
            self.tile_row.grid_columnconfigure(i, weight=1, uniform="m")
        default = self.flow.default_account_id()
        for i, (a, bal) in enumerate(balances):
            on = a.id == self.account_id
            t = ctk.CTkFrame(
                self.tile_row,
                corner_radius=12,
                border_width=2 if on else 1,
                border_color=theme.color("accent") if on else theme.color("line"),
                fg_color=theme.color("accent_soft") if on else theme.color("surface"),
                cursor="hand2",
            )
            t.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            note = " · default for Counter" if a.id == default else ""
            label = ctk.CTkLabel(
                t,
                text=f"{i18n.tr_cell(a.name)}{note}",
                font=theme.font(11),
                text_color=theme.color("muted"),
                anchor="w",
            )
            label.pack(fill="x", padx=14, pady=(10, 0))
            value = ctk.CTkLabel(t, text=rupees(bal), font=theme.font(18, "bold"), anchor="w")
            value.pack(fill="x", padx=14, pady=(0, 10))
            for w in (t, label, value):
                w.bind("<Button-1>", lambda e, aid=a.id: self.pick(aid))
            self.tiles[a.id] = (t, label, value)
        total = ctk.CTkFrame(self.tile_row, corner_radius=12, fg_color=theme.color("stripe"))
        total.grid(row=0, column=cols - 1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(total, text="All accounts", font=theme.font(11), text_color=theme.color("muted"), anchor="w").pack(
            fill="x", padx=14, pady=(10, 0)
        )
        ctk.CTkLabel(total, text=rupees(sum(b for _a, b in balances)), font=theme.font(18, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(0, 10)
        )

    def _render_banner(self) -> None:
        due = self.flow.due_recurring() if hasattr(self.flow, "due_recurring") else []
        if not due:
            self.banner.pack_forget()
            return
        months = sum(len(m) for _r, m in due)
        heads = ", ".join(f"{r.head_name.title()} {rupees(r.amount)}" for r, _m in due[:3])
        self.banner_text.configure(text=f"{months} monthly expense(s) due  ·  {heads}")
        if self.ctx.can(Permission.FINANCE_REPORTS):
            self.banner_button.pack(side="right", padx=10)
        else:
            self.banner_button.pack_forget()
        self.banner.pack(fill="x", pady=(10, 0), before=self.main)

    def _render_book(self) -> None:
        if self.account_id is None:
            self.table.set_rows([], "Add a money account in Reports & setup")
            self.totals.configure(text="")
            return
        date_from, date_to = _period(self.period.get())
        opening, rows, closing = self.flow.cash_book(self.account_id, date_from, date_to)
        shown = [
            (r[1], i18n.tr(r[2]), i18n.tr_cell(r[3]), r[4], r[5], r[6], r[7], r[0], r[8])
            for r in reversed(rows)  # newest first
        ]
        money_in = sum(r[4] or 0 for r in rows)
        money_out = sum(r[5] or 0 for r in rows)
        self.table.set_rows(shown, f"{len(rows)} entries · opening {rupees(opening)}")
        self.totals.configure(
            text=f"In {rupees(money_in)}   ·   Out {rupees(money_out)}   ·   Closing {rupees(closing)}"
        )

    def _render_month(self) -> None:
        for w in self.side.winfo_children():
            w.destroy()
        today = dt.date.today()
        cf = self.flow.cash_flow(today.replace(day=1).isoformat(), today.isoformat())
        head = ctk.CTkFrame(self.side, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=i18n.date_text(today, "%B so far"), font=theme.font(15, "bold")).pack(side="left")
        if REPORTS in self.view.pages:
            button(head, "P&L", lambda: self.view.show_page(REPORTS), height=26).pack(side="right")

        def section(title: str, items: list[tuple[str, float]], color: str) -> None:
            ctk.CTkLabel(
                self.side,
                text=i18n.tr(title).upper(),
                font=theme.font(11, "bold"),
                text_color=theme.color("muted"),
                anchor="w",
            ).pack(fill="x", pady=(12, 2))
            if not items:
                ctk.CTkLabel(
                    self.side, text="nothing yet", font=theme.font(12), text_color=theme.color("muted"), anchor="w"
                ).pack(fill="x")
            for label, amount in items:
                r = ctk.CTkFrame(self.side, fg_color="transparent")
                r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=i18n.tr(label), font=theme.font(12), anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=rupees(amount), font=theme.font(12, "bold"), text_color=theme.color(color)).pack(
                    side="right"
                )

        section("Money in", list(cf.inflows.items()), "weowe")
        section("Money out", list(cf.outflows.items()), "text")
        heads = [(h.title(), a) for h, a in cf.expenses_by_head[:5]]
        section(f"Expenses by head · {rupees(sum(a for _h, a in cf.expenses_by_head))}", heads, "text")

    # Actions ---------------------------------------------------------------------------
    def pick(self, account_id: int) -> None:
        self.account_id = account_id
        self.reload()

    def _open(self, row) -> None:
        e = self.flow.get_entry(row[7])
        if e and e.customer_id:
            self.ctx.navigate("customers", customer_id=e.customer_id)

    def _more_menu(self) -> None:
        menu = dropdown_menu(self)
        menu.add_command(label=i18n.tr("Capital in"), command=lambda: self.add_entry("owner_in"))
        menu.add_command(label=i18n.tr("Drawings (owner takes money out)"), command=lambda: self.add_entry("owner_out"))
        popup(menu, self.more_button)

    def add_entry(self, kind: str) -> None:
        accounts = {a.name: a.id for a in self.flow.money_accounts()}
        if not accounts:
            self.ctx.toast("Add a money account first (Reports & setup › Setup)", "error")
            return
        names = list(accounts)
        current = next((n for n, i in accounts.items() if i == self.account_id), names[0])
        fields = [Field("date", "Date", default=today_str())]
        if kind == "transfer":
            other = next((n for n in names if n != current), current)
            fields += [
                Field("from", "From account", "option", current, names),
                Field("to", "To account", "option", other, names),
            ]
        else:
            fields.append(Field("account", "Money account", "option", current, names))
        heads = {}
        if kind in ("expense", "income"):
            heads = {h.name: h.id for h in self.flow.heads(kind)}
            if not heads:
                self.ctx.toast(f"No {kind} heads - add one in Reports & setup › Setup", "error")
                return
            fields.append(Field("head", "Head", "option", next(iter(heads)), list(heads)))
        fields += [Field("amount", "Amount"), Field("description", "Description")]
        titles = {
            "expense": "Add expense",
            "income": "Add other income",
            "transfer": "Transfer between accounts",
            "owner_in": "Capital introduced",
            "owner_out": "Drawings (owner takes money out)",
        }

        def submit(v: dict) -> None:
            u, f = self.ctx.username, self.flow
            if kind == "transfer":
                f.transfer(v["date"], accounts[v["from"]], accounts[v["to"]], v["amount"], v["description"], u)
            elif kind == "expense":
                f.add_expense(v["date"], accounts[v["account"]], heads[v["head"]], v["amount"], v["description"], u)
            elif kind == "income":
                f.add_income(v["date"], accounts[v["account"]], heads[v["head"]], v["amount"], v["description"], u)
            else:
                f.owner(
                    v["date"],
                    accounts[v["account"]],
                    v["amount"],
                    "in" if kind == "owner_in" else "out",
                    v["description"],
                    u,
                )

        if run_form(self, titles[kind], fields, submit):
            self.ctx.toast("Entry saved", "success")
            self.reload()

    def delete_entry(self, row) -> None:
        linked = row[8]
        text = _lines(
            f"Delete entry ({row[1]}, {rupees(row[3] or row[4])})?",
            "The ledger entry it came from is NOT deleted - remove that from the customer's khata." if linked else "",
        )
        if confirm(self, "Delete entry", text):
            try:
                self.flow.delete_entry(row[7], self.ctx.username)
            except ValidationError as exc:
                self.ctx.toast(str(exc), "error")
                return
            self.reload()

    def post_due(self) -> None:
        n = self.flow.post_due(self.ctx.username)
        self.ctx.toast(f"{n} expense entr{'y' if n == 1 else 'ies'} posted", "success")
        self.reload()

    def export(self) -> None:
        if not self.table.rows:
            self.ctx.toast("Nothing to export", "warning")
            return
        name = next((a.name for a in self.flow.money_accounts() if a.id == self.account_id), "cash")
        path = self.ctx.settings.export_dir / f"cashbook_{safe_filename(name)}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        export_rows(path, self.table.export_columns(), self.table.export_rows(), f"Cash book - {name}")
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)
