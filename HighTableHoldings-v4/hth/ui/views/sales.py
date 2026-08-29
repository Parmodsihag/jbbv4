"""Sale / Receive entry."""

from __future__ import annotations

import customtkinter as ctk

from hth.domain.constants import TAG_CHOICES, Tag
from hth.domain.units import ALL_UNITS, UnitError, compatible_units, convert, normalize
from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money, today_str
from hth.ui.format import qty as fmt_qty
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
        self._item = None  # selected inventory item (None for free text)

        form = Card(self, "New entry")
        form.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)
        # Scrollable so the buttons stay reachable on small / low-resolution screens.
        inner = ctk.CTkScrollableFrame(form, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.date = DateField(inner)
        self.date.pack(fill="x", pady=3)

        acc = LabeledWidget(inner, "Account")
        acc.pack(fill="x", pady=3)
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
        item.pack(fill="x", pady=3)
        self.item = SearchBox(
            item.body,
            self._items,
            "Search item",
            on_select=lambda k, _l: self._on_item(k),
            allow_free_text=True,
        )
        self.item.pack(fill="x")
        self.item.var.trace_add("write", lambda *_: self._on_item_text())
        self.stock_label = ctk.CTkLabel(
            inner, text="", font=theme.font(12), anchor="w", text_color=theme.color("muted")
        )
        self.stock_label.pack(fill="x")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=3)
        row.grid_columnconfigure(0, weight=3)
        row.grid_columnconfigure(1, weight=2)
        row.grid_columnconfigure(2, weight=3)
        self.quantity = LabeledEntry(row, "Quantity", placeholder="0")
        self.quantity.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.unit = LabeledOption(row, "Unit", ALL_UNITS, "KG", command=lambda _v: self._update_amount())
        self.unit.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.price = LabeledEntry(row, "Price per unit", placeholder="0.00")
        self.price.grid(row=0, column=2, sticky="ew")
        for w in (self.quantity, self.price):
            w.var.trace_add("write", lambda *_: self._update_amount())

        self.tag = LabeledOption(inner, "Tag", TAG_CHOICES, Tag.NORMAL.label)
        self.tag.pack(fill="x", pady=3)

        self.amount_label = ctk.CTkLabel(inner, text="Amount: 0.00", font=theme.font(18, "bold"), anchor="w")
        self.amount_label.pack(fill="x", pady=(8, 0))
        self.convert_label = ctk.CTkLabel(
            inner, text="", font=theme.font(11), anchor="w", text_color=theme.color("muted")
        )
        self.convert_label.pack(fill="x")

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
            text="Ctrl+Enter = Sale   ·   Ctrl+Shift+Enter = Receive\n"
            "Loose sales: pick the item, then enter e.g. 100 G for a KG item - it is converted.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            justify="left",
        ).pack(pady=(8, 4), anchor="w")
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

    def _on_item(self, item_id, focus: bool = True) -> None:
        item = self.ctx.inventory.get_item(item_id)
        self._item = item
        if item is None:
            return
        units = compatible_units(item.unit) or ALL_UNITS
        self.unit.set_values(units)
        self.unit.set(units[0])
        self.price.set(f"{item.last_value:g}")
        self.price.entry.configure(placeholder_text=f"per {units[0]}")
        stock = self.ctx.inventory.quantity(item.id)
        self.stock_label.configure(
            text=f"In stock: {fmt_qty(stock)} {normalize(item.unit)}   ·   price is per {normalize(item.unit)}",
            text_color=theme.color("danger") if stock <= 0 else theme.color("muted"),
        )
        self._update_amount()
        if focus:
            self.quantity.focus()

    def _on_item_text(self) -> None:
        key = self.item.get_key()
        if self._item is None and key is not None:
            # Exact item label typed (or set programmatically): adopt its unit and price.
            self._on_item(key, focus=False)
            return
        # Typing over a picked item turns it back into free text.
        if self._item is not None and key != self._item.id:
            self._item = None
            self.unit.set_values(ALL_UNITS)
            self.stock_label.configure(text="Not a stock item - ledger only, any unit")
            self._update_amount()

    def _stock_qty(self) -> tuple[float, str] | None:
        try:
            q = float(self.quantity.get() or 0)
        except ValueError:
            return None
        unit = normalize(self.unit.get())
        if self._item is None:
            return q, unit
        try:
            return convert(q, unit, self._item.unit), normalize(self._item.unit)
        except UnitError:
            return None

    def _update_amount(self) -> None:
        conv = self._stock_qty()
        try:
            price = float(self.price.get() or 0)
        except ValueError:
            price = 0
        if conv is None:
            self.amount_label.configure(text="Amount: -")
            self.convert_label.configure(
                text=f"{self.unit.get()} cannot be converted to {self._item.unit if self._item else ''}",
                text_color=theme.color("danger"),
            )
            return
        q, unit = conv
        self.amount_label.configure(text=f"Amount: {money(price * q)}")
        entered = normalize(self.unit.get())
        note = f"= {fmt_qty(q)} {unit} from stock" if self._item and entered != unit else ""
        self.convert_label.configure(text=note, text_color=theme.color("muted"))

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
                unit=self.unit.get(),
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
        self._item = None
        self.stock_label.configure(text="")
        self.convert_label.configure(text="")
        self.quantity.set("")
        self.price.set("")
        self.tag.set(Tag.NORMAL.label)
        self._load_recent()
        self.item.entry.focus_set()
