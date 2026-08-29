"""Accounts: create customers, browse balances, open a ledger, (admin) edit records."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.domain.constants import TAG_CHOICES, Tag
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money, open_path
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
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 60, "e", "int"),
                Column("name", "Name", 240, stretch=True),
                Column("details", "Details", 200),
                Column("balance", "Balance", 120, "e", "money"),
                Column("days", "Days", 70, "e", "int"),
                Column("score", "Score", 70, "e", "text"),
            ],
            on_double_click=lambda r: self.view.show_ledger(r[0]),
            row_tags=lambda r: ["neg"] if r[3] > 0 else (["pos"] if r[3] < 0 else ["muted"]),
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        ctk.CTkLabel(
            self,
            text="Double-click an account to open its ledger.  Balance in red = customer owes.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(padx=12, pady=(0, 10), anchor="w")

    def reload(self) -> None:
        self.table.set_footer("Loading balances…")
        self.view.run_async(self.ctx.accounts.summaries, self._loaded)

    def _loaded(self, summaries) -> None:
        self._all = [(s.id, s.name, s.other_details, s.balance, s.days, f"{s.score:.2f}") for s in summaries]
        self._filter()

    def _filter(self) -> None:
        term = self.search.get().strip().lower()
        rows = [r for r in self._all if not term or term in f"{r[0]} {r[1]} {r[2]}".lower()]
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
        secondary_button(tools, "Export Excel", self.export, width=110).pack(side="left")
        secondary_button(tools, "↻", lambda: self.load(self.customer.id), width=40).pack(side="left", padx=6)
        if self.ctx.can(Permission.EDIT_RECORDS):
            secondary_button(tools, "Add entry", self.add_entry, width=100).pack(side="left", padx=(12, 6))
            secondary_button(tools, "Edit entry", self.edit_entry, width=100).pack(side="left", padx=6)
            secondary_button(tools, "Edit customer", self.edit_customer, width=120).pack(side="left", padx=6)
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(tools, "Delete entry", self.delete_entry, width=100).pack(side="right", padx=(6, 0))
            danger_button(tools, "Delete customer", self.delete_customer, width=130).pack(side="right")

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
        self.customer = self.ctx.accounts.get_customer(customer_id)
        if self.customer is None:
            self.ctx.toast("Customer not found", "error")
            self.view.show_list()
            return
        self.name_label.configure(text=f"#{self.customer.id}  {self.customer.name}   {self.customer.other_details}")
        rows = self.ctx.accounts.ledger(customer_id)
        table_rows = [
            (r.id, r.date, r.particulars, r.interest, r.debit, r.credit, r.balance, r.tag, r.type) for r in rows
        ]
        balance = self.ctx.accounts.get_balance(customer_id)
        debit = sum(r.debit or 0 for r in rows)
        credit = sum(r.credit or 0 for r in rows)
        interest = sum(r.interest or 0 for r in rows if r.tag != "0")
        self.table.set_rows(
            table_rows,
            f"{len(rows)} entries · debit {money(debit)} · credit {money(credit)}"
            f" · interest (current period) {money(interest)}",
        )
        self.balance_label.configure(
            text=f"Balance {money(balance)}",
            text_color=theme.color("danger") if balance > 0 else theme.color("success"),
        )
        self.ctx.status(f"{self.customer.name} · balance {money(balance)}")

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
            self.ctx.accounts.delete_transaction(tx.id, self.ctx.username)
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

    def delete_customer(self) -> None:
        c = self.customer
        if confirm(
            self,
            "Delete customer",
            f"Delete #{c.id} {c.name} and ALL its ledger entries?\nThis cannot be undone.",
        ):
            self.ctx.accounts.delete_customer(c.id, self.ctx.username)
            self.ctx.toast(f"Customer {c.name} deleted", "success")
            self.view.show_list()
