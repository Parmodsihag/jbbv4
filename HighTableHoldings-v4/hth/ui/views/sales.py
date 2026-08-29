"""Sale / Receive entry."""

from __future__ import annotations

import customtkinter as ctk

from hth.domain.constants import TAG_CHOICES, Tag
from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.forms import (
    Card,
    DateField,
    LabeledEntry,
    LabeledOption,
    LabeledWidget,
    primary_button,
)
from hth.ui.widgets.searchbox import SearchBox


class SalesView(BaseView):
    key = "sales"
    title = "Sales"
    permission = Permission.RECORD_SALE

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=2, uniform="s")
        self.grid_columnconfigure(1, weight=3, uniform="s")
        self.grid_rowconfigure(0, weight=1)

        form = Card(self, "New entry")
        form.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)
        inner = ctk.CTkFrame(form, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=(4, 16))

        self.date = DateField(inner)
        self.date.pack(fill="x", pady=4)

        acc = LabeledWidget(inner, "Account")
        acc.pack(fill="x", pady=4)
        self.account = SearchBox(
            acc.body,
            self._accounts,
            "Search account by id / name / village",
            on_select=lambda k, _l: self._show_balance(k),
        )
        self.account.pack(fill="x")
        self.balance_label = ctk.CTkLabel(
            inner, text="", font=theme.font(12), anchor="w", text_color=theme.color("muted")
        )
        self.balance_label.pack(fill="x")

        item = LabeledWidget(inner, "Item  (pick from stock, or type anything e.g. CASH)")
        item.pack(fill="x", pady=4)
        self.item = SearchBox(
            item.body,
            self._items,
            "Search item",
            on_select=lambda k, _l: self._fill_price(k),
            allow_free_text=True,
        )
        self.item.pack(fill="x")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=4)
        row.grid_columnconfigure((0, 1), weight=1)
        self.quantity = LabeledEntry(row, "Quantity", placeholder="0")
        self.quantity.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.price = LabeledEntry(row, "Price", placeholder="0.00")
        self.price.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        for w in (self.quantity, self.price):
            w.var.trace_add("write", lambda *_: self._update_amount())

        self.tag = LabeledOption(inner, "Tag", TAG_CHOICES, Tag.NORMAL.label)
        self.tag.pack(fill="x", pady=4)

        self.amount_label = ctk.CTkLabel(inner, text="Amount: 0.00", font=theme.font(18, "bold"), anchor="w")
        self.amount_label.pack(fill="x", pady=(10, 4))

        buttons = ctk.CTkFrame(inner, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 0))
        buttons.grid_columnconfigure((0, 1), weight=1)
        primary_button(buttons, "Sale  (debit)", lambda: self.submit("P")).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        primary_button(
            buttons,
            "Receive  (credit)",
            lambda: self.submit("M"),
            fg_color=theme.color("success"),
            hover_color=("#166534", "#22C55E"),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(
            inner,
            text="Ctrl+Enter = Sale   ·   Ctrl+Shift+Enter = Receive",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(pady=(8, 0))
        top = self.winfo_toplevel()
        top.bind("<Control-Return>", lambda e: self._shortcut("P"))
        top.bind("<Control-Shift-Return>", lambda e: self._shortcut("M"))

        right = Card(self, "Today's entries")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        self.recent = DataTable(
            right,
            [
                Column("time", "Time", 70),
                Column("kind", "Type", 80),
                Column("msg", "Details", 420, stretch=True),
                Column("user", "By", 80),
            ],
            row_tags=lambda r: ["pos"] if r[1] == "Receive" else [],
        )
        self.recent.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    # Data ------------------------------------------------------------------------------
    def _accounts(self):
        return [(c.id, c.display) for c in self.ctx.accounts.list_customers()]

    def _items(self):
        return [(i.id, i.display) for i in self.ctx.inventory.list_items()]

    def on_show(self, **kwargs) -> None:
        self.account.refresh()
        self.item.refresh()
        self._load_recent()
        self.after(100, self.account.entry.focus_set)

    def on_theme_change(self) -> None:
        self.recent.restyle()

    def _load_recent(self) -> None:
        from hth.ui.format import today_str

        entries = [e for e in self.ctx.audit.entries(today_str(), today_str(), limit=300) if e.code in ("03", "04")]
        rows = [(e.ts[11:16], "Sale" if e.code == "03" else "Receive", e.message, e.username) for e in entries]
        self.recent.set_rows(rows, f"{len(rows)} entries today")

    def _show_balance(self, customer_id) -> None:
        bal = self.ctx.accounts.get_balance(customer_id)
        state = "owes" if bal > 0 else ("credit" if bal < 0 else "settled")
        self.balance_label.configure(
            text=f"Current balance: {money(abs(bal))}  ({state})",
            text_color=theme.color("danger") if bal > 0 else theme.color("success"),
        )

    def _fill_price(self, item_id) -> None:
        self.price.set(f"{self.ctx.inventory.get_last_value(item_id):g}")
        self.quantity.focus()

    def _update_amount(self) -> None:
        try:
            amount = float(self.quantity.get() or 0) * float(self.price.get() or 0)
        except ValueError:
            amount = 0
        self.amount_label.configure(text=f"Amount: {money(amount)}")

    def _shortcut(self, kind: str) -> None:
        if self.winfo_ismapped():
            self.submit(kind)

    # Submit ----------------------------------------------------------------------------
    def submit(self, kind: str) -> None:
        try:
            date = self.date.get()
            customer_id = self.account.get_key()
            if customer_id is None:
                raise ValidationError("Pick an account from the list.")
            item_id = self.item.get_key()
            item_name = self.item.get_text()
            if not (self.quantity.get() and self.price.get()):
                raise ValidationError("Quantity and price are required.")
            result = self.ctx.sales.record(
                kind,
                date,
                customer_id,
                item_name,
                self.quantity.get(),
                self.price.get(),
                self.tag.get()[0],
                self.ctx.username,
                item_id=item_id,
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        label = "Sale" if kind == "P" else "Receipt"
        note = "" if result.inventory_updated else " (stock not updated - item not in inventory)"
        self.ctx.toast(f"{label} of {money(result.amount)} recorded{note}", "success")
        self.ctx.status(f"{label} #{result.transaction_ids[0]} · {money(result.amount)}{note}")
        self._show_balance(customer_id)
        self.item.clear()
        self.quantity.set("")
        self.price.set("")
        self.tag.set(Tag.NORMAL.label)
        self._load_recent()
        self.item.entry.focus_set()
