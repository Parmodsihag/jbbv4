"""Finance screen: cash book, setup (accounts / heads / recurring), reports."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.modules.finance.service import ACCOUNT_KINDS, FinanceService
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import days_ago_str, money, open_path, today_str
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, confirm, run_form
from hth.ui.widgets.forms import Card, danger_button, primary_button, secondary_button
from hth.ui.widgets.kpi import KpiTile


def _tabview(master) -> ctk.CTkTabview:
    tabs = ctk.CTkTabview(master, fg_color=theme.color("surface"), corner_radius=10)
    try:
        tabs._segmented_button.configure(font=theme.font(13, "bold"))  # noqa: SLF001
    except Exception:  # noqa: BLE001
        pass
    return tabs


class FinanceView(BaseView):
    key = "finance"
    title = "Finance"
    permission = Permission.FINANCE

    def build(self) -> None:
        self.svc = FinanceService(self.ctx.db)
        self.svc.ensure_defaults()
        self.tabs = _tabview(self)
        self.tabs.pack(fill="both", expand=True, padx=4, pady=4)
        self.book = self.setup = self.reports = None
        # the new layout (v5.5) has its own cash book in Money; there this screen is Reports & Setup
        if getattr(getattr(self.ctx, "app", None), "layout", "classic") != "new":
            self.tabs.add("Cash book")
            self.book = CashBookPanel(self.tabs.tab("Cash book"), self)
            self.book.pack(fill="both", expand=True)
        if self.ctx.can(Permission.FINANCE_REPORTS):
            self.tabs.add("Reports")
            self.reports = FinanceReportsPanel(self.tabs.tab("Reports"), self)
            self.reports.pack(fill="both", expand=True)
            self.tabs.add("Setup")
            self.setup = SetupPanel(self.tabs.tab("Setup"), self)
            self.setup.pack(fill="both", expand=True)

    def on_show(self, **kwargs) -> None:
        for p in (self.book, self.setup, self.reports):
            if p is not None:
                p.reload()

    def on_theme_change(self) -> None:
        for p in (self.book, self.setup, self.reports):
            if p is not None:
                for t in p.tables():
                    t.restyle()

    # helpers shared by panels
    def reload_book(self) -> None:
        if self.book is not None:
            self.book.reload()

    def account_names(self) -> list[str]:
        return [a.name for a in self.svc.money_accounts()]

    def account_id(self, name: str) -> int | None:
        return next((a.id for a in self.svc.money_accounts(active_only=False) if a.name == name), None)

    def head_names(self, kind: str) -> list[str]:
        return [h.name for h in self.svc.heads(kind)]

    def head_id(self, name: str) -> int | None:
        return next((h.id for h in self.svc.heads(active_only=False) if h.name == name), None)


# ------------------------------------------------------------------------------------------
class CashBookPanel(ctk.CTkFrame):
    def __init__(self, master, view: FinanceView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        self.tiles_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tiles_frame.pack(fill="x", pady=(4, 6))
        self.tiles: list[KpiTile] = []

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(bar, text="Account", font=theme.font(12), text_color=theme.color("muted")).pack(side="left")
        self.account = ctk.CTkOptionMenu(
            bar, values=["-"], width=160, height=34, font=theme.font(13), command=lambda _v: self.reload()
        )
        self.account.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(bar, text="From", font=theme.font(12), text_color=theme.color("muted")).pack(side="left")
        self.d_from = ctk.CTkEntry(bar, width=105, height=34, font=theme.font(13))
        self.d_from.insert(0, days_ago_str(30))
        self.d_from.pack(side="left", padx=(4, 8))
        ctk.CTkLabel(bar, text="To", font=theme.font(12), text_color=theme.color("muted")).pack(side="left")
        self.d_to = ctk.CTkEntry(bar, width=105, height=34, font=theme.font(13))
        self.d_to.insert(0, today_str())
        self.d_to.pack(side="left", padx=(4, 8))
        secondary_button(bar, "Show", self.reload, width=60).pack(side="left")
        if self.ctx.can(Permission.FINANCE_REPORTS):
            danger_button(bar, "Delete entry", self.delete_entry, width=100).pack(side="right")
        secondary_button(bar, "Export", self.export, width=70).pack(side="right", padx=6)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", pady=(0, 6))
        primary_button(actions, "+ Expense", lambda: self.add_entry("expense"), width=110).pack(side="left")
        secondary_button(actions, "+ Other income", lambda: self.add_entry("income"), width=120).pack(
            side="left", padx=6
        )
        secondary_button(actions, "Transfer", lambda: self.add_entry("transfer"), width=90).pack(side="left", padx=6)
        secondary_button(actions, "Capital in", lambda: self.add_entry("owner_in"), width=90).pack(side="left", padx=6)
        secondary_button(actions, "Drawings", lambda: self.add_entry("owner_out"), width=90).pack(side="left", padx=6)
        ctk.CTkLabel(
            actions,
            text="Customer receipts / payments come from the Sales screen (item CASH + money account).",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="right")

        self.table = DataTable(
            self,
            [
                Column("id", "ID", 55, "e", "int"),
                Column("date", "Date", 95),
                Column("kind", "Kind", 130),
                Column("details", "Details", 320, stretch=True),
                Column("in", "In", 110, "e", "money"),
                Column("out", "Out", 110, "e", "money"),
                Column("bal", "Balance", 120, "e", "money"),
                Column("by", "By", 70),
            ],
            row_tags=lambda r: ["pos"] if r[4] else (["neg"] if r[5] else []),
            on_double_click=self._open,
        )
        self.table.pack(fill="both", expand=True)

    def tables(self):
        return [self.table]

    def reload(self) -> None:
        names = self.view.account_names() or ["-"]
        current = self.account.get() if self.account.get() in names else names[0]
        self.account.configure(values=names)
        self.account.set(current)
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        balances = self.svc.balances()
        for i in range(max(1, len(balances))):
            self.tiles_frame.grid_columnconfigure(i, weight=1, uniform="fin")
        total = 0.0
        for i, (acc, bal) in enumerate(balances):
            tile = KpiTile(
                self.tiles_frame, f"{acc.name} ({acc.kind})", money(bal), accent="success" if bal >= 0 else "danger"
            )
            tile.grid(row=0, column=i, sticky="ew", padx=4)
            self.tiles.append(tile)
            total += bal
        if len(balances) > 1:
            self.tiles_frame.grid_columnconfigure(len(balances), weight=1, uniform="fin")
            tile = KpiTile(self.tiles_frame, "Total cash & bank", money(total), accent="accent")
            tile.grid(row=0, column=len(balances), sticky="ew", padx=4)
            self.tiles.append(tile)
        aid = self.view.account_id(current)
        if aid is None:
            self.table.clear()
            return
        try:
            opening, rows, closing = self.svc.cash_book(aid, self.d_from.get().strip(), self.d_to.get().strip())
        except (ValidationError, ValueError) as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.table.set_rows(rows, f"{len(rows)} entries · opening {money(opening)} · closing {money(closing)}")

    def _open(self, row) -> None:
        e = self.svc.get_entry(row[0])
        if e and e.customer_id:
            self.ctx.navigate("customers", customer_id=e.customer_id)

    def add_entry(self, kind: str) -> None:
        accounts = self.view.account_names()
        if not accounts:
            self.ctx.toast("Add a money account first (Setup tab)", "error")
            return
        current = self.account.get() if self.account.get() in accounts else accounts[0]
        fields = [Field("date", "Date", default=today_str())]
        if kind == "transfer":
            fields += [
                Field("from", "From account", "option", current, accounts),
                Field("to", "To account", "option", accounts[-1], accounts),
            ]
        else:
            fields.append(Field("account", "Money account", "option", current, accounts))
        if kind in ("expense", "income"):
            heads = self.view.head_names(kind)
            if not heads:
                self.ctx.toast(f"No {kind} heads - add one in Setup", "error")
                return
            fields.append(Field("head", "Head", "option", heads[0], heads))
        fields += [Field("amount", "Amount"), Field("description", "Description")]
        titles = {
            "expense": "Add expense",
            "income": "Add other income",
            "transfer": "Transfer between accounts",
            "owner_in": "Capital introduced",
            "owner_out": "Drawings (owner takes money out)",
        }

        def submit(v):
            u = self.ctx.username
            if kind == "transfer":
                self.svc.transfer(
                    v["date"],
                    self.view.account_id(v["from"]),
                    self.view.account_id(v["to"]),
                    v["amount"],
                    v["description"],
                    u,
                )
            elif kind == "expense":
                self.svc.add_expense(
                    v["date"],
                    self.view.account_id(v["account"]),
                    self.view.head_id(v["head"]),
                    v["amount"],
                    v["description"],
                    u,
                )
            elif kind == "income":
                self.svc.add_income(
                    v["date"],
                    self.view.account_id(v["account"]),
                    self.view.head_id(v["head"]),
                    v["amount"],
                    v["description"],
                    u,
                )
            else:
                self.svc.owner(
                    v["date"],
                    self.view.account_id(v["account"]),
                    v["amount"],
                    "in" if kind == "owner_in" else "out",
                    v["description"],
                    u,
                )

        if run_form(self, titles[kind], fields, submit):
            self.ctx.toast("Entry saved", "success")
            self.reload()

    def delete_entry(self) -> None:
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select an entry first", "warning")
            return
        note = (
            "\nThe ledger entry it came from is NOT deleted - remove that from the customer's ledger." if row[8] else ""
        )
        if confirm(self, "Delete entry", f"Delete entry #{row[0]} ({row[2]}, {money(row[4] or row[5])})?{note}"):
            self.svc.delete_entry(row[0], self.ctx.username)
            self.reload()

    def export(self) -> None:
        if not self.table.rows:
            self.ctx.toast("Nothing to export", "warning")
            return
        path = (
            self.ctx.settings.export_dir
            / f"cashbook_{safe_filename(self.account.get())}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        export_rows(path, self.table.export_columns(), self.table.export_rows(), f"Cash book - {self.account.get()}")
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)


# ------------------------------------------------------------------------------------------
class SetupPanel(ctk.CTkFrame):
    def __init__(self, master, view: FinanceView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        acc = Card(body, "Money accounts")
        acc.pack(fill="x", pady=(0, 8))
        bar = ctk.CTkFrame(acc, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 4))
        primary_button(bar, "+ Account", self.add_account, width=100).pack(side="left")
        secondary_button(bar, "Edit", self.edit_account, width=70).pack(side="left", padx=6)
        secondary_button(bar, "Set as default for Sales", self.set_default, width=180).pack(side="left", padx=6)
        secondary_button(bar, "Activate / deactivate", self.toggle_account, width=160).pack(side="left", padx=6)
        self.acc_table = DataTable(
            acc,
            [
                Column("id", "ID", 50, "e", "int"),
                Column("name", "Name", 200, stretch=True),
                Column("kind", "Kind", 80),
                Column("opening", "Opening", 110, "e", "money"),
                Column("date", "Since", 95),
                Column("bal", "Balance", 120, "e", "money"),
                Column("active", "Active", 60, "center"),
                Column("default", "Default", 70, "center"),
                Column("notes", "Notes", 200),
            ],
            height=5,
        )
        self.acc_table.pack(fill="x", padx=12, pady=(0, 12))

        heads = Card(body, "Expense / income heads")
        heads.pack(fill="x", pady=(0, 8))
        bar = ctk.CTkFrame(heads, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 4))
        primary_button(bar, "+ Head", self.add_head, width=90).pack(side="left")
        secondary_button(bar, "Rename", self.rename_head, width=80).pack(side="left", padx=6)
        secondary_button(bar, "Activate / deactivate", self.toggle_head, width=160).pack(side="left", padx=6)
        self.head_table = DataTable(
            heads,
            [
                Column("id", "ID", 50, "e", "int"),
                Column("name", "Name", 260, stretch=True),
                Column("kind", "Kind", 90),
                Column("active", "Active", 70, "center"),
            ],
            height=6,
        )
        self.head_table.pack(fill="x", padx=12, pady=(0, 12))

        rec = Card(body, "Recurring expenses (rent, salaries, EMI…)")
        rec.pack(fill="x")
        bar = ctk.CTkFrame(rec, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 4))
        primary_button(bar, "+ Recurring", self.add_recurring, width=110).pack(side="left")
        secondary_button(bar, "Post due now", self.post_due, width=110).pack(side="left", padx=6)
        secondary_button(bar, "On / off", self.toggle_recurring, width=80).pack(side="left", padx=6)
        danger_button(bar, "Delete", self.delete_recurring, width=80).pack(side="right")
        self.due_label = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color=theme.color("warning"))
        self.due_label.pack(side="left", padx=12)
        self.rec_table = DataTable(
            rec,
            [
                Column("id", "ID", 50, "e", "int"),
                Column("head", "Head", 180),
                Column("account", "Account", 120),
                Column("amount", "Amount", 110, "e", "money"),
                Column("day", "Day", 50, "e", "int"),
                Column("desc", "Description", 200, stretch=True),
                Column("start", "From", 80),
                Column("last", "Last posted", 95),
                Column("active", "Active", 60, "center"),
            ],
            height=5,
        )
        self.rec_table.pack(fill="x", padx=12, pady=(0, 12))

    def tables(self):
        return [self.acc_table, self.head_table, self.rec_table]

    def reload(self) -> None:
        default = self.svc.default_account_id()
        rows = [
            (
                a.id,
                a.name,
                a.kind,
                a.opening_balance,
                a.opening_date,
                self.svc.balance(a.id),
                "yes" if a.is_active else "no",
                "✓" if a.id == default else "",
                a.notes,
            )
            for a in self.svc.money_accounts(active_only=False)
        ]
        self.acc_table.set_rows(rows, f"{len(rows)} accounts")
        hrows = [(h.id, h.name, h.kind, "yes" if h.is_active else "no") for h in self.svc.heads(active_only=False)]
        self.head_table.set_rows(hrows, f"{len(hrows)} heads")
        rrows = [
            (
                r.id,
                r.head_name,
                r.account_name,
                r.amount,
                r.day_of_month,
                r.description,
                r.start_month,
                r.last_posted or "",
                "yes" if r.is_active else "no",
            )
            for r in self.svc.recurring()
        ]
        self.rec_table.set_rows(rrows, f"{len(rrows)} recurring")
        due = self.svc.due_recurring()
        self.due_label.configure(text=f"{sum(len(m) for _, m in due)} due" if due else "")

    # accounts
    def _selected_account(self):
        row = self.acc_table.selected_row()
        if row is None:
            self.ctx.toast("Select an account first", "warning")
            return None
        return self.svc.get_account(row[0])

    def add_account(self) -> None:
        fields = [
            Field("name", "Name (e.g. CASH BOX, SBI CURRENT, PHONEPE)"),
            Field("kind", "Kind", "option", "cash", ACCOUNT_KINDS),
            Field("opening", "Opening balance", default="0"),
            Field("date", "Opening date", default=today_str()),
            Field("notes", "Notes"),
        ]
        if run_form(
            self,
            "New money account",
            fields,
            lambda v: self.svc.add_account(
                v["name"], v["kind"], v["opening"], v["date"], v["notes"], self.ctx.username
            ),
            "Create",
        ):
            self.reload()
            self.view.reload_book()

    def edit_account(self) -> None:
        a = self._selected_account()
        if a is None:
            return
        fields = [
            Field("name", "Name", default=a.name),
            Field("kind", "Kind", "option", a.kind, ACCOUNT_KINDS),
            Field("opening", "Opening balance", default=f"{a.opening_balance:g}"),
            Field("date", "Opening date", default=a.opening_date),
            Field("notes", "Notes", default=a.notes),
        ]
        if run_form(
            self,
            f"Edit {a.name}",
            fields,
            lambda v: self.svc.update_account(
                a.id,
                self.ctx.username,
                name=v["name"],
                kind=v["kind"],
                opening_balance=v["opening"],
                opening_date=v["date"],
                notes=v["notes"],
            ),
        ):
            self.reload()
            self.view.reload_book()

    def set_default(self) -> None:
        a = self._selected_account()
        if a:
            self.svc.set_default_account(a.id)
            self.ctx.toast(f"{a.name} is now the default money account on the Sales screen", "success")
            self.reload()

    def toggle_account(self) -> None:
        a = self._selected_account()
        if a and confirm(self, "Account", f"{'Deactivate' if a.is_active else 'Activate'} {a.name}?"):
            self.svc.update_account(a.id, self.ctx.username, is_active=not a.is_active)
            self.reload()
            self.view.reload_book()

    # heads
    def _selected_head(self):
        row = self.head_table.selected_row()
        if row is None:
            self.ctx.toast("Select a head first", "warning")
            return None
        return self.svc.get_head(row[0])

    def add_head(self) -> None:
        fields = [Field("name", "Name"), Field("kind", "Kind", "option", "expense", ["expense", "income"])]
        if run_form(
            self, "New head", fields, lambda v: self.svc.add_head(v["name"], v["kind"], self.ctx.username), "Create"
        ):
            self.reload()

    def rename_head(self) -> None:
        h = self._selected_head()
        if h and run_form(
            self,
            f"Rename {h.name}",
            [Field("name", "Name", default=h.name)],
            lambda v: self.svc.rename_head(h.id, v["name"], self.ctx.username),
        ):
            self.reload()

    def toggle_head(self) -> None:
        h = self._selected_head()
        if h:
            self.svc.set_head_active(h.id, not h.is_active, self.ctx.username)
            self.reload()

    # recurring
    def add_recurring(self) -> None:
        heads, accounts = self.view.head_names("expense"), self.view.account_names()
        if not heads or not accounts:
            self.ctx.toast("Need an expense head and a money account first", "error")
            return
        today = dt.date.today()
        fields = [
            Field("head", "Head", "option", heads[0], heads),
            Field("account", "Paid from", "option", accounts[0], accounts),
            Field("amount", "Amount"),
            Field("day", "Day of month (1-28)", default="1"),
            Field("start", "First month (YYYY-MM)", default=today.strftime("%Y-%m")),
            Field("description", "Description"),
        ]
        if run_form(
            self,
            "New recurring expense",
            fields,
            lambda v: self.svc.add_recurring(
                self.view.head_id(v["head"]),
                self.view.account_id(v["account"]),
                v["amount"],
                v["day"],
                v["description"],
                v["start"],
                self.ctx.username,
            ),
            "Create",
        ):
            self.reload()

    def post_due(self) -> None:
        due = self.svc.due_recurring()
        n = sum(len(m) for _, m in due)
        if not n:
            self.ctx.toast("Nothing due", "info")
            return
        lines = "\n".join(f"{r.head_name} {money(r.amount)} x {len(m)} ({m[0]}..{m[-1]})" for r, m in due)
        if confirm(self, "Post recurring expenses", f"Post {n} expense entries?\n\n{lines}"):
            posted = self.svc.post_due(self.ctx.username)
            self.ctx.toast(f"{posted} expenses posted", "success")
            self.reload()
            self.view.reload_book()

    def toggle_recurring(self) -> None:
        row = self.rec_table.selected_row()
        if row:
            self.svc.set_recurring_active(row[0], row[8] != "yes", self.ctx.username)
            self.reload()

    def delete_recurring(self) -> None:
        row = self.rec_table.selected_row()
        if row and confirm(self, "Delete", f"Delete recurring {row[1]} {money(row[3])}? (posted entries stay)"):
            self.svc.delete_recurring(row[0], self.ctx.username)
            self.reload()


# ------------------------------------------------------------------------------------------
FIN_REPORTS = {
    "Cash flow": [
        Column("line", "Line", 300, stretch=True),
        Column("amount", "Amount", 140, "e", "money"),
        Column("note", "", 200),
    ],
    "Profit & loss": [
        Column("line", "Line", 300, stretch=True),
        Column("amount", "Amount", 140, "e", "money"),
        Column("note", "", 200),
    ],
    "Expenses by head": [
        Column("head", "Head", 300, stretch=True),
        Column("amount", "Amount", 140, "e", "money"),
        Column("pct", "% of total", 100, "e", "qty"),
    ],
    "Monthly expenses": [
        Column("month", "Month", 100),
        Column("exp", "Expenses", 140, "e", "money"),
        Column("inc", "Other income", 140, "e", "money"),
        Column("net", "Net", 140, "e", "money"),
    ],
    "Account balances": [
        Column("name", "Account", 200, stretch=True),
        Column("opening", "Opening", 120, "e", "money"),
        Column("in", "In", 120, "e", "money"),
        Column("out", "Out", 120, "e", "money"),
        Column("closing", "Closing", 120, "e", "money"),
    ],
}


class FinanceReportsPanel(ctk.CTkFrame):
    def __init__(self, master, view: FinanceView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 4))
        self.which = ctk.CTkOptionMenu(
            bar, values=list(FIN_REPORTS), font=theme.font(13), height=34, width=180, command=lambda _v: self.run()
        )
        self.which.pack(side="left")
        ctk.CTkLabel(bar, text="From", font=theme.font(12), text_color=theme.color("muted")).pack(
            side="left", padx=(12, 4)
        )
        self.d_from = ctk.CTkEntry(bar, width=105, height=34, font=theme.font(13))
        self.d_from.insert(0, dt.date.today().replace(day=1).strftime("%Y-%m-%d"))
        self.d_from.pack(side="left")
        ctk.CTkLabel(bar, text="To", font=theme.font(12), text_color=theme.color("muted")).pack(
            side="left", padx=(8, 4)
        )
        self.d_to = ctk.CTkEntry(bar, width=105, height=34, font=theme.font(13))
        self.d_to.insert(0, today_str())
        self.d_to.pack(side="left")
        primary_button(bar, "Run", self.run, width=70).pack(side="left", padx=8)
        secondary_button(bar, "Export", self.export, width=80).pack(side="right")
        self.host = ctk.CTkFrame(self, fg_color="transparent")
        self.host.pack(fill="both", expand=True)
        self.table: DataTable | None = None

    def tables(self):
        return [self.table] if self.table else []

    def reload(self) -> None:
        self.run()

    def run(self) -> None:
        name = self.which.get()
        if self.table:
            self.table.destroy()
        self.table = DataTable(
            self.host,
            FIN_REPORTS[name],
            row_tags=lambda r: (
                ["bold"]
                if str(r[0]).isupper()
                and len(str(r[0])) > 3
                and r[0] == str(r[0]).upper()
                and not str(r[0]).startswith("  ")
                else []
            ),
        )
        self.table.pack(fill="both", expand=True)
        f, t = self.d_from.get().strip(), self.d_to.get().strip()
        try:
            if name == "Cash flow":
                cf = self.svc.cash_flow(f, t)
                rows = [("MONEY IN", cf.total_in, "")] + [(f"  {k}", v, "") for k, v in cf.inflows.items()]
                rows += [("MONEY OUT", cf.total_out, "")] + [(f"  {k}", v, "") for k, v in cf.outflows.items()]
                rows += [(f"    {h}", a, "expense head") for h, a in cf.expenses_by_head]
                rows += [("NET CASH FLOW", cf.net, "in - out")]
                for n, o, i, oo, c in cf.accounts:
                    rows.append((f"  {n}", c, f"opening {money(o)} · in {money(i)} · out {money(oo)}"))
                footer = f"{f} to {t}"
            elif name == "Profit & loss":
                pl = self.svc.profit_and_loss(f, t)
                rows = [
                    ("ITEM SALES", pl.item_revenue, "sale value of stock items"),
                    ("  cost of goods sold", pl.item_cogs, "qty x item cost"),
                    ("ITEM MARGIN", pl.item_margin, ""),
                    ("CROP SALES", pl.crop_revenue, ""),
                    ("  crop cost (FIFO)", pl.crop_cost, ""),
                    ("CROP MARGIN", pl.crop_margin, ""),
                    ("GROSS MARGIN", pl.gross_margin, ""),
                    ("OTHER INCOME", pl.other_income, ""),
                ]
                rows += [(f"  {h}", a, "expense") for h, a in pl.expenses]
                rows += [
                    ("TOTAL EXPENSES", pl.total_expenses, ""),
                    ("NET PROFIT", pl.net_profit, "gross + other income - expenses"),
                ]
                footer = f"{f} to {t} · interest on customer balances is not included (accrued, not received)"
            elif name == "Expenses by head":
                data = self.svc.expenses_by_head(f, t)
                total = sum(a for _, a in data) or 1
                rows = [(h, a, round(a / total * 100, 1)) for h, a in data]
                footer = f"total {money(sum(a for _, a in data))}"
            elif name == "Monthly expenses":
                rows = [(m, e, i, round(i - e, 2)) for m, e, i in self.svc.monthly_expenses(12)]
                footer = "last 12 months"
            else:
                rows = list(self.svc.cash_flow(f, t).accounts)
                footer = f"{f} to {t}"
        except (ValidationError, ValueError) as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.table.set_rows(rows, footer)

    def export(self) -> None:
        if not self.table or not self.table.rows:
            self.ctx.toast("Nothing to export", "warning")
            return
        path = (
            self.ctx.settings.export_dir
            / f"finance_{safe_filename(self.which.get())}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        export_rows(path, self.table.export_columns(), self.table.export_rows(), f"Finance - {self.which.get()}")
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)
