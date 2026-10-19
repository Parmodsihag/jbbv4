"""Sale / Receive entry - for stock items, free-text items and crops alike."""

from __future__ import annotations

import customtkinter as ctk

from hth.domain.constants import TAG_CHOICES, Tag
from hth.domain.units import ALL_UNITS, UnitError, compatible_units, convert, normalize
from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.services.sales import CROP_ITEM_TYPE, SaleLine, crop_handler, money_flow_handler
from hth.ui import theme
from hth.ui.format import money, today_str
from hth.ui.format import qty as fmt_qty
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import confirm
from hth.ui.widgets.forms import (
    Card,
    DateField,
    LabeledEntry,
    LabeledOption,
    LabeledWidget,
    primary_button,
    secondary_button,
)
from hth.ui.widgets.searchbox import SearchBox

QUALITY_GRADES = ["A", "B", "C", "MIX"]
UNDO_MINUTES = 15  # how long the last entry can be undone from this screen


class SalesView(BaseView):
    key = "sales"
    title = "Sales"
    permission = Permission.RECORD_SALE

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=2, uniform="s")
        self.grid_columnconfigure(1, weight=3, uniform="s")
        self.grid_rowconfigure(0, weight=1)
        self._item = None  # selected inventory item (None for free text)
        self._lines: list[tuple[SaleLine, float]] = []  # pending lines of a multi-item entry
        self._last: tuple[list, str, float] | None = None  # (results, summary, monotonic time)

        form = Card(self, "New entry")
        form.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)
        inner = ctk.CTkScrollableFrame(form, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.date = DateField(inner)
        self.date.pack(fill="x", pady=3)

        acc = LabeledWidget(inner, "Account  (customer, farmer or buyer)")
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

        # Crop-only fields (shown when the picked item is a crop)
        self.crop_box = ctk.CTkFrame(inner, fg_color=theme.color("surface2"), corner_radius=8)
        crop_inner = ctk.CTkFrame(self.crop_box, fg_color="transparent")
        crop_inner.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(
            crop_inner, text="CROP TRADE", font=theme.font(11, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x")
        cg = ctk.CTkFrame(crop_inner, fg_color="transparent")
        cg.pack(fill="x")
        cg.grid_columnconfigure((0, 1), weight=1)
        self.deduction = LabeledEntry(cg, "Deduction / kaat (on Credit)", default="0")
        self.deduction.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=2)
        self.quality = LabeledOption(cg, "Quality", QUALITY_GRADES, "A")
        self.quality.grid(row=0, column=1, sticky="ew", pady=2)
        self.notes = LabeledEntry(cg, "Notes (moisture, bags, vehicle…)")
        self.notes.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        self.allow_short = ctk.CTkCheckBox(cg, text="Allow selling short (on Debit)", font=theme.font(12))
        self.allow_short.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.crop_hint = ctk.CTkLabel(
            crop_inner, text="", font=theme.font(11), text_color=theme.color("muted"), anchor="w", justify="left"
        )
        self.crop_hint.pack(fill="x", pady=(4, 0))
        # (packed on demand by _set_crop_mode)

        self.tag = LabeledOption(inner, "Tag", TAG_CHOICES, Tag.NORMAL.label)
        self.tag.pack(fill="x", pady=3)

        # Money account (cash / bank / UPI) - only for entries that move money, not stock
        self.money = LabeledOption(inner, "Money account  (where the cash goes / comes from)", ["- none -"], "- none -")
        self._money_ids: dict[str, int] = {}
        self._refresh_money_accounts()
        self.money.pack(fill="x", pady=3)

        self.amount_label = ctk.CTkLabel(inner, text="Amount: 0.00", font=theme.font(18, "bold"), anchor="w")
        self.amount_label.pack(fill="x", pady=(8, 0))
        self.convert_label = ctk.CTkLabel(
            inner, text="", font=theme.font(11), anchor="w", text_color=theme.color("muted"), justify="left"
        )
        self.convert_label.pack(fill="x")

        for w in (self.quantity, self.price, self.deduction):
            w.var.trace_add("write", lambda *_: self._update_amount())
        self.quantity.entry.bind("<Return>", lambda e: self.price.focus())
        self.price.entry.bind("<Return>", lambda e: self.add_line())

        # Pending lines (several items for the same account, posted together)
        self.lines_box = ctk.CTkFrame(inner, fg_color=theme.color("surface2"), corner_radius=8)
        self.lines_table = DataTable(
            self.lines_box,
            [
                Column("item", "Item", 170, stretch=True),
                Column("qty", "Qty", 80, "e"),
                Column("price", "Price", 80, "e", "money"),
                Column("amount", "Amount", 95, "e", "money"),
            ],
            height=4,
        )
        self.lines_table.pack(fill="x", padx=6, pady=(6, 2))
        lb = ctk.CTkFrame(self.lines_box, fg_color="transparent")
        lb.pack(fill="x", padx=6, pady=(0, 6))
        secondary_button(lb, "Remove line", self.remove_line, width=110, height=28).pack(side="left")
        secondary_button(lb, "Clear all", self.clear_lines, width=90, height=28).pack(side="left", padx=6)
        self.lines_total = ctk.CTkLabel(lb, text="", font=theme.font(12, "bold"))
        self.lines_total.pack(side="right", padx=4)
        # (packed on demand by _refresh_lines)

        self.add_line_button = secondary_button(
            inner, "+ Add line  (Enter)  - several items for this account, posted together", self.add_line
        )
        self.add_line_button.pack(fill="x", pady=(8, 0))
        self.buttons = buttons = ctk.CTkFrame(inner, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 0))
        buttons.grid_columnconfigure((0, 1), weight=1)
        self.debit_button = primary_button(buttons, "Debit  ·  sale / pay out", lambda: self.submit("P"))
        self.debit_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.credit_button = primary_button(
            buttons,
            "Credit  ·  receive / purchase",
            lambda: self.submit("M"),
            fg_color=theme.color("success"),
            hover_color=("#166534", "#22C55E"),
        )
        self.credit_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(
            inner,
            text="Debit: customer owes more (a sale, or cash paid out to them).   "
            "Credit: customer owes less (a payment received, or goods bought from them).\n"
            "Ctrl+Enter = Debit   ·   Ctrl+Shift+Enter = Credit.   "
            "Loose sales: enter e.g. 100 G for a KG item - it is converted.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            justify="left",
            wraplength=420,
        ).pack(pady=(8, 4), anchor="w")
        top = self.winfo_toplevel()
        top.bind("<Control-Return>", lambda e: self._shortcut("P"))
        top.bind("<Control-Shift-Return>", lambda e: self._shortcut("M"))
        top.bind("<Control-z>", lambda e: self.undo_last() if self.winfo_ismapped() else None, add="+")

        right = Card(self, "Today's entries")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        undo_bar = ctk.CTkFrame(right, fg_color="transparent")
        undo_bar.pack(fill="x", padx=12)
        self.undo_label = ctk.CTkLabel(
            undo_bar, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w"
        )
        self.undo_label.pack(side="left", fill="x", expand=True)
        self.undo_button = secondary_button(undo_bar, "↶ Undo last entry", self.undo_last, width=150)
        self.undo_button.pack(side="right")
        self.undo_button.configure(state="disabled")
        self.recent = DataTable(
            right,
            [
                Column("time", "Time", 70),
                Column("kind", "Type", 80),
                Column("msg", "Details", 420, stretch=True),
                Column("user", "By", 80),
            ],
            row_tags=lambda r: ["pos"] if r[1] in ("Receive", "Purchase") else [],
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
        self._refresh_money_accounts()
        self._load_recent()
        if self._item is None:
            self._set_money_mode(True)
        self.after(100, self.account.entry.focus_set)

    def on_theme_change(self) -> None:
        self.recent.restyle()
        self.lines_table.restyle()

    def on_day_change(self) -> None:
        super().on_day_change()
        self._load_recent()

    def _load_recent(self) -> None:
        entries = [
            e for e in self.ctx.audit.entries(today_str(), today_str(), limit=300) if e.code in ("03", "04", "10")
        ]
        rows = []
        for e in entries:
            if e.code == "10":
                kind = (
                    "Purchase"
                    if e.message.startswith("purchase")
                    else ("Crop sale" if e.message.startswith("sale") else "Crop")
                )
            else:
                kind = "Sale" if e.code == "03" else "Receive"
            rows.append((e.ts[11:16], kind, e.message, e.username))
        self.recent.set_rows(rows, f"{len(rows)} entries today")

    def _show_balance(self, customer_id) -> None:
        bal = self.ctx.accounts.get_balance(customer_id)
        state = "owes us" if bal > 0 else ("we owe them" if bal < 0 else "settled")
        self.balance_label.configure(
            text=f"Current balance: {money(abs(bal))}  ({state})",
            text_color=theme.color("danger") if bal > 0 else theme.color("success"),
        )

    def _refresh_money_accounts(self) -> None:
        flow = money_flow_handler(self.ctx.db)
        self._money_ids = {}
        values = ["- none -"]
        default = "- none -"
        if flow is not None:
            try:
                default_id = flow.default_account_id()
                for a in flow.money_accounts():
                    self._money_ids[a.name] = a.id
                    values.append(a.name)
                    if a.id == default_id:
                        default = a.name
            except Exception:  # noqa: BLE001 - finance tables missing on a partial install
                pass
        self.money.set_values(values)
        # Keep an explicit choice; otherwise follow the default account from Finance -> Setup.
        if self.money.get() not in values or self.money.get() == "- none -":
            self.money.set(default)

    def _set_money_mode(self, on: bool) -> None:
        if on and not self.money.winfo_manager():
            self.money.pack(fill="x", pady=3, after=self.tag)
        elif not on and self.money.winfo_manager():
            self.money.pack_forget()

    @property
    def is_crop(self) -> bool:
        return self._item is not None and self._item.item_type == CROP_ITEM_TYPE

    def _set_crop_mode(self, on: bool) -> None:
        if on and not self.crop_box.winfo_manager():
            self.crop_box.pack(fill="x", pady=4, before=self.tag)
            self.tag.set(Tag.NO_INTEREST.label)
        elif not on and self.crop_box.winfo_manager():
            self.crop_box.pack_forget()

    def _on_item(self, item_id, focus: bool = True) -> None:
        item = self.ctx.inventory.get_item(item_id)
        self._item = item
        if item is None:
            return
        units = compatible_units(item.unit) or ALL_UNITS
        self.unit.set_values(units)
        self.unit.set(units[0])
        self.price.set(f"{item.last_value:g}")
        stock = self.ctx.inventory.quantity(item.id)
        self.stock_label.configure(
            text=f"In stock: {fmt_qty(stock)} {normalize(item.unit)}   ·   price is per {normalize(item.unit)}"
            + ("   ·   CROP" if item.item_type == CROP_ITEM_TYPE else ""),
            text_color=theme.color("danger") if stock <= 0 else theme.color("muted"),
        )
        self._set_crop_mode(item.item_type == CROP_ITEM_TYPE)
        self._set_money_mode(False)
        self._update_amount()
        if focus:
            self.quantity.focus()

    def _on_item_text(self) -> None:
        key = self.item.get_key()
        if self._item is None and key is not None:
            self._on_item(key, focus=False)
            return
        if self._item is not None and key != self._item.id:
            self._item = None
            self.unit.set_values(ALL_UNITS)
            self.stock_label.configure(text="Not a stock item - ledger only, any unit")
            self._set_crop_mode(False)
            self._set_money_mode(True)
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
        entered = normalize(self.unit.get())
        note = f"= {fmt_qty(q)} {unit} from stock" if self._item and entered != unit else ""
        if self.is_crop:
            self._update_crop_preview(q, unit, price, note)
            return
        self.amount_label.configure(text=f"Amount: {money(price * q)}")
        self.convert_label.configure(text=note, text_color=theme.color("muted"))

    def _update_crop_preview(self, q: float, unit: str, price: float, note: str) -> None:
        try:
            ded = float(self.deduction.get() or 0)
            ded = convert(ded, self.unit.get(), unit)
        except (ValueError, UnitError):
            ded = 0.0
        net = max(0.0, q - ded)
        self.amount_label.configure(
            text=f"Credit (purchase): {money(price * net)}   ·   Debit (sale): {money(price * q)}"
        )
        lines = [note] if note else []
        if ded > 0:
            lines.append(f"Purchase: net {fmt_qty(net)} {unit} after {fmt_qty(ded)} {unit} deduction")
        crop = crop_handler(self.ctx.db)
        if crop is not None and q > 0:
            pv = crop.preview_cost(self._item.id, q)
            margin = price * q - pv.cost
            short = f"  ⚠ {fmt_qty(pv.short_qty)} {unit} short" if pv.short_qty > 0 else ""
            lines.append(
                f"Sale: FIFO cost {money(pv.cost)} from {len(pv.allocations)} lot(s) → margin {money(margin)}{short}"
            )
        self.convert_label.configure(
            text="\n".join(lines),
            text_color=theme.color("danger") if any("short" in x for x in lines) else theme.color("muted"),
        )
        self.crop_hint.configure(
            text="Credit = bought from this farmer (adds a lot).   Debit = sold to this buyer (costed FIFO)."
        )

    def _shortcut(self, kind: str) -> None:
        if self.winfo_ismapped():
            self.submit(kind)

    # Lines -----------------------------------------------------------------------------
    def _current_line(self, required: bool) -> tuple[SaleLine, float] | None:
        """The line in the form, or None when the form is empty (``required`` = complain)."""
        item_name = self.item.get_text()
        if not (item_name or self.quantity.get() or self.price.get()):
            if required:
                raise ValidationError("Enter an item, quantity and price.")
            return None
        if not item_name:
            raise ValidationError("Item is required.")
        if not (self.quantity.get() and self.price.get()):
            raise ValidationError("Quantity and price are required.")
        if self.is_crop:
            raise ValidationError("Crop trades are entered one at a time - use Debit / Credit directly.")
        conv = self._stock_qty()
        try:
            price = float(self.price.get())
        except ValueError as exc:
            raise ValidationError(f"Invalid price '{self.price.get()}'.") from exc
        if conv is None:
            raise ValidationError(f"{self.unit.get()} cannot be converted to {self._item.unit if self._item else ''}.")
        line = SaleLine(item_name, self.quantity.get(), self.price.get(), self.item.get_key(), self.unit.get())
        return line, round(conv[0] * price, 2)

    def add_line(self) -> None:
        try:
            current = self._current_line(required=True)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self._lines.append(current)
        self._clear_item_fields()
        self._refresh_lines()
        self.item.entry.focus_set()

    def remove_line(self) -> None:
        row = self.lines_table.selected_row()
        if row is None:
            if not self._lines:
                return
            idx = len(self._lines) - 1
        else:
            idx = row[4]
        del self._lines[idx]
        self._refresh_lines()

    def clear_lines(self) -> None:
        self._lines.clear()
        self._refresh_lines()

    def _refresh_lines(self) -> None:
        rows = [
            (line.item_name, f"{line.quantity} {line.unit or ''}".strip(), line.price, amount, i)
            for i, (line, amount) in enumerate(self._lines)
        ]
        self.lines_table.set_rows(rows, "")
        n = len(self._lines)
        if n and not self.lines_box.winfo_manager():
            self.lines_box.pack(fill="x", pady=(6, 0), before=self.add_line_button)
        elif not n and self.lines_box.winfo_manager():
            self.lines_box.pack_forget()
        self.lines_total.configure(text=f"{n} line(s) · {money(sum(a for _l, a in self._lines))}" if n else "")
        suffix = f"  ({n} lines + this one)" if n else ""
        self.debit_button.configure(text=f"Debit  ·  sale / pay out{suffix}")
        self.credit_button.configure(text=f"Credit  ·  receive / purchase{suffix}")

    def _clear_item_fields(self) -> None:
        self.item.clear()
        self._item = None
        self._set_crop_mode(False)
        self._set_money_mode(True)
        self.stock_label.configure(text="")
        self.convert_label.configure(text="")
        self.quantity.set("")
        self.price.set("")
        self.deduction.set("0")
        self.notes.set("")
        self.allow_short.deselect()
        self.unit.set_values(ALL_UNITS)
        self.amount_label.configure(text="Amount: 0.00")

    # Submit ----------------------------------------------------------------------------
    def submit(self, kind: str) -> None:
        try:
            date = self.date.get()
            customer_id = self.account.get_key()
            if customer_id is None:
                raise ValidationError("Pick an account from the list.")
            if self._lines:
                current = self._current_line(required=False)
                lines = [line for line, _a in self._lines] + ([current[0]] if current else [])
                results = self.ctx.sales.record_lines(
                    kind,
                    date,
                    customer_id,
                    lines,
                    self.tag.get()[0],
                    self.ctx.username,
                    money_account_id=self._money_ids.get(self.money.get()),
                )
                label = "Debit" if kind == "P" else "Credit"
                msg = f"{label}: {len(results)} lines, {money(sum(r.amount for r in results))} recorded"
                self._lines.clear()
                self._refresh_lines()
                self._after_post(results, msg, customer_id)
                return
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
                deduction=self.deduction.get() or 0 if self.is_crop else None,
                quality=self.quality.get() if self.is_crop else "",
                notes=self.notes.get() if self.is_crop else "",
                allow_short=bool(self.allow_short.get()) if self.is_crop else False,
                money_account_id=self._money_ids.get(self.money.get()) if item_id is None else None,
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        if result.crop_lot_id is not None:
            msg = (
                f"Lot #{result.crop_lot_id}: {fmt_qty(result.stock_quantity)} {result.stock_unit}"
                f" bought for {money(result.amount)}"
            )
        elif result.crop_sale_id is not None:
            short = f" ({fmt_qty(result.short_qty)} short)" if result.short_qty else ""
            msg = (
                f"Crop sale #{result.crop_sale_id}: {money(result.amount)} · margin {money(result.margin or 0)}{short}"
            )
        else:
            label = "Debit" if kind == "P" else "Credit"
            note = "" if result.inventory_updated else " (stock not updated - item not in inventory)"
            msg = f"{label} of {money(result.amount)} recorded{note}"
        self._after_post([result], msg, customer_id)

    def _after_post(self, results: list, msg: str, customer_id: int) -> None:
        import time

        self.ctx.toast(msg + "  ·  Ctrl+Z to undo", "success")
        self.ctx.status(msg)
        self._last = (results, msg, time.monotonic())
        self.undo_button.configure(state="normal")
        self.undo_label.configure(text=f"Last: {msg}")
        self._show_balance(customer_id)
        self._clear_item_fields()
        self.tag.set(Tag.NORMAL.label)
        self._load_recent()
        self.item.entry.focus_set()

    def undo_last(self) -> None:
        import time

        if self._last is None:
            return
        results, msg, at = self._last
        if time.monotonic() - at > UNDO_MINUTES * 60:
            self.ctx.toast(
                f"Undo is only offered for {UNDO_MINUTES} minutes - ask an admin to edit the ledger", "warning"
            )
            self._forget_last()
            return
        if not confirm(self, "Undo last entry", f"Remove this entry?\n\n{msg}\n\nLedger, stock and cash book go back."):
            return
        try:
            n = self.ctx.sales.undo(results, self.ctx.username)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self._forget_last()
        self.ctx.toast(f"Undone ({n} entr{'y' if n == 1 else 'ies'})", "success")
        cid = results[0].customer_id if results else None
        if cid is not None:
            self._show_balance(cid)
        self._load_recent()

    def _forget_last(self) -> None:
        self._last = None
        self.undo_button.configure(state="disabled")
        self.undo_label.configure(text="")
