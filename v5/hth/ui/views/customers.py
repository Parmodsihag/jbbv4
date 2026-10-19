"""Accounts: create customers, browse balances, open a ledger, (admin) edit records."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.domain.constants import TAG_CHOICES, Tag
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.services.statements import financial_year_start
from hth.ui import theme
from hth.ui.format import money, open_path, today_str
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, confirm, run_form
from hth.ui.widgets.forms import (
    Card,
    DateField,
    LabeledEntry,
    LabeledOption,
    danger_button,
    primary_button,
    secondary_button,
)


class CustomersView(BaseView):
    key = "customers"
    title = "Accounts"
    permission = Permission.ADD_CUSTOMER

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=2, uniform="a")
        self.grid_columnconfigure(1, weight=5, uniform="a")
        self.grid_rowconfigure(0, weight=1)
        self._summaries = []

        # --- new account form
        form = Card(self, "New account")
        form.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)
        inner = ctk.CTkScrollableFrame(form, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.name = LabeledEntry(inner, "Name", placeholder="Customer name")
        self.name.pack(fill="x", pady=4)
        self.details = LabeledEntry(inner, "Other details", placeholder="Village / father's name / phone")
        self.details.pack(fill="x", pady=4)
        self.date = DateField(inner)
        self.date.pack(fill="x", pady=4)
        self.opening = LabeledEntry(inner, "Opening balance", placeholder="0 (leave blank if none)")
        self.opening.pack(fill="x", pady=4)
        self.description = LabeledEntry(inner, "Opening entry description", default="NEW ACCOUNT")
        self.description.pack(fill="x", pady=4)
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=4)
        row.grid_columnconfigure((0, 1), weight=1)
        self.tx_type = LabeledOption(row, "Opening type", ["P  (customer owes)", "M  (we owe)"])
        self.tx_type.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.tag = LabeledOption(row, "Tag", TAG_CHOICES, Tag.NORMAL.label)
        self.tag.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        primary_button(inner, "Add account", self.add_account).pack(fill="x", pady=(14, 0))

        # --- right pane: list or ledger
        self.right = ctk.CTkFrame(self, fg_color="transparent")
        self.right.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        self.list_panel = CustomerListPanel(self.right, self)
        self.ledger_panel = LedgerPanel(self.right, self)
        self.list_panel.pack(fill="both", expand=True)

    def on_show(self, customer_id: int | None = None, **kwargs) -> None:
        if customer_id is not None:
            self.show_ledger(customer_id)
        else:
            self.list_panel.reload()

    def on_theme_change(self) -> None:
        self.list_panel.table.restyle()
        self.ledger_panel.table.restyle()

    def show_ledger(self, customer_id: int) -> None:
        self.list_panel.pack_forget()
        self.ledger_panel.pack(fill="both", expand=True)
        self.ledger_panel.load(customer_id)

    def show_list(self, reload: bool = True) -> None:
        self.ledger_panel.pack_forget()
        self.list_panel.pack(fill="both", expand=True)
        if reload:
            self.list_panel.reload()

    def add_account(self) -> None:
        try:
            customer = self.ctx.accounts.add_customer(
                self.name.get(),
                self.details.get(),
                self.opening.get() or 0,
                self.date.get(),
                self.description.get() or "NEW ACCOUNT",
                self.tx_type.get()[0],
                self.tag.get()[0],
                self.ctx.username,
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(f"Account #{customer.id} {customer.name} created", "success")
        for w in (self.name, self.details, self.opening):
            w.set("")
        self.description.set("NEW ACCOUNT")
        self.date.set_today()
        self.show_list()
        self.name.focus()


class CustomerListPanel(ctk.CTkFrame):
    def __init__(self, master, view: CustomersView):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10)
        self.view = view
        self.ctx = view.ctx
        self._all = []
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bar, text="All accounts", font=theme.font(17, "bold")).pack(side="left")
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right", padx=(6, 0))
        self.search = ctk.CTkEntry(
            bar,
            placeholder_text="Filter by id, name, details…",
            width=280,
            height=34,
            font=theme.font(13),
        )
        self.search.pack(side="right")
        self.search.bind("<KeyRelease>", lambda e: self._filter())
        filters = ctk.CTkFrame(self, fg_color="transparent")  # own row: survives larger text
        filters.pack(fill="x", padx=12, pady=(0, 4))
        self.cat_filter = ctk.CTkOptionMenu(
            filters,
            values=["All", "A", "B", "C", "D", "E"],
            width=70,
            height=34,
            font=theme.font(13),
            command=lambda _v: self._filter(),
        )
        self.cat_filter.set("All")
        self.cat_filter.pack(side="left", padx=(8, 0))
        self.bal_filter = ctk.CTkSegmentedButton(
            filters,
            values=["All", "Owe us", "We owe", "Settled"],
            command=lambda _v: self._filter(),
            font=theme.font(12),
        )
        self.bal_filter.set("All")
        self.bal_filter.pack(side="left")
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 60, "e", "int"),
                Column("name", "Name", 240, stretch=True),
                Column("details", "Details", 200),
                Column("balance", "Balance", 120, "e", "money"),
                Column("days", "Days", 70, "e", "int"),
                Column("score", "Score", 70, "e", "text"),
                Column("cat", "Cat", 45, "center"),
            ],
            on_double_click=lambda r: self.view.show_ledger(r[0]),
            row_tags=lambda r: (
                (["muted"] if r[6] == "E" else []) + (["neg"] if r[3] > 0 else (["pos"] if r[3] < 0 else ["muted"]))
            ),
        )
        ctk.CTkLabel(
            self,
            text="Double-click an account to open its ledger.  Balance in red = customer owes.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="bottom", padx=12, pady=(0, 10), anchor="w")
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 4))

    def reload(self) -> None:
        self.table.set_footer("Loading balances…")
        self.view.run_async(lambda: self.ctx.categories.customer_summaries(scope="all"), self._loaded)

    def _loaded(self, summaries) -> None:
        self._all = [
            (s.id, s.name, s.other_details, s.balance, s.days, f"{s.score:.2f}" if s.scored else "-", s.category)
            for s in summaries
        ]
        self._filter()

    def _filter(self) -> None:
        words = self.search.get().strip().lower().split()
        cat = self.cat_filter.get()
        bal = self.bal_filter.get()
        rows = [
            r
            for r in self._all
            if all(w in f"{r[0]} {r[1]} {r[2]}".lower() for w in words)
            and (cat == "All" or r[6] == cat)
            and (
                bal == "All"
                or (bal == "Owe us" and r[3] > 0)
                or (bal == "We owe" and r[3] < 0)
                or (bal == "Settled" and r[3] == 0)
            )
        ]
        receivable = sum(r[3] for r in rows if r[3] > 0)
        payable = -sum(r[3] for r in rows if r[3] < 0)
        self.table.set_rows(
            rows,
            f"{len(rows)} accounts · receivable {money(receivable)} · payable {money(payable)}",
        )


class LedgerPanel(ctk.CTkFrame):
    def __init__(self, master, view: CustomersView):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10)
        self.view = view
        self.ctx = view.ctx
        self.customer = None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 4))
        secondary_button(head, "← Back", lambda: self.view.show_list(), width=80).pack(side="left")
        self.name_label = ctk.CTkLabel(head, text="", font=theme.font(17, "bold"))
        self.name_label.pack(side="left", padx=12)
        self.balance_label = ctk.CTkLabel(head, text="", font=theme.font(17, "bold"))
        self.balance_label.pack(side="right")

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=12, pady=(0, 4))
        if self.ctx.can(Permission.RECORD_SALE):
            primary_button(tools, "New entry ▸", self.new_entry, width=110).pack(side="left", padx=(0, 6))
        secondary_button(tools, "Export Excel", self.export, width=110).pack(side="left")
        secondary_button(tools, "Statement", self.statement, width=100).pack(side="left", padx=6)
        secondary_button(tools, "WhatsApp balance", self.whatsapp, width=140).pack(side="left", padx=6)
        if self.ctx.can(Permission.MANAGE_KRAR):
            secondary_button(tools, "Promise…", self.promise, width=90).pack(side="left", padx=6)
        secondary_button(tools, "↻", lambda: self.load(self.customer.id), width=40).pack(side="left", padx=6)
        if self.ctx.can(Permission.EDIT_RECORDS):
            secondary_button(tools, "Add entry", self.add_entry, width=100).pack(side="left", padx=(12, 6))
            secondary_button(tools, "Edit entry", self.edit_entry, width=100).pack(side="left", padx=6)
            secondary_button(tools, "Edit customer", self.edit_customer, width=120).pack(side="left", padx=6)
            secondary_button(tools, "Category", self.set_category, width=90).pack(side="left", padx=6)
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(tools, "Delete entry", self.delete_entry, width=100).pack(side="right", padx=(6, 0))
            danger_button(tools, "Delete customer", self.delete_customer, width=130).pack(side="right")

        view_bar = ctk.CTkFrame(self, fg_color="transparent")
        view_bar.pack(fill="x", padx=12, pady=(2, 0))
        self.period = ctk.CTkSegmentedButton(
            view_bar,
            values=["All", "Current period", "This FY", "Last 90 days"],
            command=lambda _v: self._apply_view(),
            font=theme.font(12),
        )
        self.period.set("All")
        self.period.pack(side="left")
        self.text_filter = ctk.CTkEntry(
            view_bar, placeholder_text="Find in ledger…", width=220, height=30, font=theme.font(12)
        )
        self.text_filter.pack(side="right")
        self.text_filter.bind("<KeyRelease>", lambda e: self.table.filter(self.text_filter.get()))
        self._rows: list = []
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 60, "e", "int"),
                Column("date", "Date", 100),
                Column("particulars", "Particulars", 300, stretch=True),
                Column("interest", "Interest", 100, "e", "money"),
                Column("debit", "Debit", 110, "e", "money"),
                Column("credit", "Credit", 110, "e", "money"),
                Column("balance", "Balance", 120, "e", "money"),
                Column("tag", "Tag", 50, "center"),
                Column("type", "P/M", 50, "center"),
            ],
            row_tags=lambda r: ["muted", "bold"] if r[7] == "0" else [],
            on_double_click=lambda r: self.edit_entry() if self.ctx.can(Permission.EDIT_RECORDS) else None,
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def load(self, customer_id: int) -> None:
        if self.customer is None or self.customer.id != customer_id:
            self.period.set("All")
            self.text_filter.delete(0, "end")
        self.customer = self.ctx.accounts.get_customer(customer_id)
        if self.customer is None:
            self.ctx.toast("Customer not found", "error")
            self.view.show_list()
            return
        lock = " 🔒" if self.customer.category_locked else ""
        self.name_label.configure(
            text=f"#{self.customer.id}  {self.customer.name}   {self.customer.other_details}"
            f"   ·   category {self.customer.category}{lock}"
        )
        self._rows = self.ctx.accounts.ledger(customer_id)
        balance = self.ctx.accounts.get_balance(customer_id)
        self._apply_view()
        self.balance_label.configure(
            text=f"Balance {money(balance)}",
            text_color=theme.color("danger") if balance > 0 else theme.color("success"),
        )
        self.ctx.status(f"{self.customer.name} · balance {money(balance)}")

    def _apply_view(self) -> None:
        """Show the period chosen above the table; totals are for what is shown."""
        from hth.services.statements import financial_year_start

        rows = self._rows
        choice = self.period.get()
        if choice == "Current period":
            last = max((i for i, r in enumerate(rows) if r.tag == "0"), default=-1)
            rows = rows[last + 1 :]
        elif choice == "This FY":
            start = financial_year_start()
            rows = [r for r in rows if r.date >= start]
        elif choice == "Last 90 days":
            start = (dt.date.today() - dt.timedelta(days=90)).isoformat()
            rows = [r for r in rows if r.date >= start]
        debit = sum(r.debit or 0 for r in rows if r.tag != "0" or r.particulars not in ("Settled Amount", "Discount"))
        credit = sum(r.credit or 0 for r in rows if r.tag != "0" or r.particulars not in ("Settled Amount", "Discount"))
        interest = sum(r.interest or 0 for r in rows if r.tag != "0")
        shown = f"{len(rows)} of {len(self._rows)} entries" if len(rows) != len(self._rows) else f"{len(rows)} entries"
        self.table.set_rows(
            [(r.id, r.date, r.particulars, r.interest, r.debit, r.credit, r.balance, r.tag, r.type) for r in rows],
            f"{shown} · debit {money(debit)} · credit {money(credit)} · interest shown {money(interest)}",
        )
        if self.text_filter.get():
            self.table.filter(self.text_filter.get())

    def promise(self) -> None:
        """Record (or move) the date this customer promised to pay - a krar."""
        if not self.customer:
            return
        c = self.customer
        dates = self.ctx.krar.unsettled_dates(c.id)
        current = f"  (currently {max(dates)})" if dates else ""
        default = (dt.date.today() + dt.timedelta(days=7)).isoformat()
        fields = [Field("date", f"Promised date{current}", default=default)]
        if run_form(
            self,
            f"Promise from {c.name}",
            fields,
            lambda v: self.ctx.krar.add_or_update(c.id, v["date"], self.ctx.username),
            "Save promise",
        ):
            self.ctx.toast("Promise saved - it shows on Karar and the dashboard", "success")

    def new_entry(self) -> None:
        if self.customer:
            self.ctx.navigate("sales", customer_id=self.customer.id)

    def whatsapp(self) -> None:
        if not self.customer:
            return
        r = self.ctx.reminders.balance_message(self.customer.id)
        self.clipboard_clear()
        self.clipboard_append(r.text)
        if r.whatsapp_url:
            import webbrowser

            webbrowser.open(r.whatsapp_url)
            self.ctx.audit.log("07", f"whatsapp balance to customer {r.customer_id}", self.ctx.username)
            self.ctx.toast("WhatsApp opened - the message is also on the clipboard", "success")
        else:
            self.ctx.toast("No 10-digit mobile number in the account details - message copied instead", "warning")

    def export(self) -> None:
        if not self.customer:
            return
        path = (
            self.ctx.settings.export_dir
            / f"ledger_{safe_filename(self.customer.name)}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        export_rows(
            path,
            self.table.export_columns(),
            self.table.export_rows(),
            f"Ledger - {self.customer.name} ({self.customer.other_details})",
        )
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)

    def statement(self) -> None:
        if not self.customer:
            return
        fields = [
            Field("from", "From", default=financial_year_start()),
            Field("to", "To", default=today_str()),
        ]
        out = {}

        def submit(v):
            st = self.ctx.statements.build(self.customer.id, v["from"], v["to"])
            out["path"] = self.ctx.statements.write(st, self.ctx.settings.export_dir)

        if run_form(self, f"Statement for {self.customer.name}", fields, submit, "Create") and out:
            self.ctx.toast(f"Statement saved: {out['path'].name}", "success")
            open_path(out["path"])

    # Admin edits ---------------------------------------------------------------------
    def _selected_tx(self):
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select an entry first", "warning")
            return None
        return self.ctx.accounts.get_transaction(row[0])

    def add_entry(self) -> None:
        fields = [
            Field("date", "Date", default=dt.date.today().isoformat()),
            Field("description", "Description"),
            Field("amount", "Amount"),
            Field("type", "Type", "option", "P", ["P", "M"]),
            Field("tag", "Tag", "option", "1", ["0", "1", "2"]),
        ]
        run_form(
            self,
            "Add ledger entry",
            fields,
            lambda v: self.ctx.accounts.add_transaction(
                self.customer.id,
                v["date"],
                v["description"],
                v["amount"],
                v["type"],
                v["tag"],
                self.ctx.username,
            ),
        )
        self.load(self.customer.id)

    def edit_entry(self) -> None:
        tx = self._selected_tx()
        if tx is None:
            return
        fields = [
            Field("date", "Date", default=tx.date),
            Field("description", "Description", default=tx.description),
            Field("amount", "Amount", default=f"{tx.amount:g}"),
            Field("type", "Type", "option", tx.type, ["P", "M"]),
            Field("tag", "Tag", "option", tx.tag, ["0", "1", "2"]),
        ]
        run_form(
            self,
            f"Edit entry #{tx.id}",
            fields,
            lambda v: self.ctx.accounts.update_transaction(
                tx.id,
                v["date"],
                v["description"],
                v["amount"],
                v["type"],
                v["tag"],
                self.ctx.username,
            ),
        )
        self.load(self.customer.id)

    def delete_entry(self) -> None:
        tx = self._selected_tx()
        if tx is None:
            return
        if confirm(
            self,
            "Delete entry",
            f"Delete entry #{tx.id}\n{tx.date}  {tx.description}  {money(tx.amount)} ?",
        ):
            try:
                self.ctx.accounts.delete_transaction(tx.id, self.ctx.username)
            except ValidationError as exc:
                self.ctx.toast(str(exc), "error")
                return
            self.ctx.toast("Entry deleted", "success")
            self.load(self.customer.id)

    def edit_customer(self) -> None:
        c = self.customer
        fields = [
            Field("name", "Name", default=c.name),
            Field("details", "Other details", default=c.other_details),
        ]
        run_form(
            self,
            f"Edit customer #{c.id}",
            fields,
            lambda v: self.ctx.accounts.update_customer(c.id, v["name"], v["details"], self.ctx.username),
        )
        self.load(c.id)

    def set_category(self) -> None:
        c = self.customer
        fields = [
            Field(
                "category",
                "Category (E = defaulter, kept out of reports and scoring)",
                "option",
                c.category,
                ["A", "B", "C", "D", "E"],
            ),
            Field("mode", "After saving", "option", "Keep (locked)", ["Keep (locked)", "Let re-score change it"]),
        ]

        def submit(v):
            if v["mode"].startswith("Keep"):
                self.ctx.categories.set_customer_category(c.id, v["category"], self.ctx.username)
            else:
                self.ctx.accounts.set_category(c.id, v["category"], self.ctx.username, locked=False)

        if run_form(self, f"Category of {c.name}", fields, submit):
            self.ctx.toast("Category updated", "success")
            self.load(c.id)

    def delete_customer(self) -> None:
        c = self.customer
        if confirm(
            self,
            "Delete customer",
            f"Delete #{c.id} {c.name} and ALL its ledger entries?\nThis cannot be undone.",
        ):
            try:
                self.ctx.accounts.delete_customer(c.id, self.ctx.username)
            except ValidationError as exc:
                self.ctx.toast(str(exc), "error")
                return
            self.ctx.toast(f"Customer {c.name} deleted", "success")
            self.view.show_list()
