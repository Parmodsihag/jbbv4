"""Counter - where every entry is made in the new layout.

Four tabs say what is happening in shop words: Sale, Purchase, Payment in, Payment out.
Underneath they are the same two ledger kinds as ever (P debit, M credit) and the same
service calls as the classic Sales screen; the small print under Save says what is booked.
A crop picked under Sale or Purchase brings its own fields (FIFO cost, or kaat and quality)
exactly as before.
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass

import customtkinter as ctk

from hth import i18n
from hth.domain.constants import ANNUAL_INTEREST_RATE_PERCENT
from hth.domain.units import ALL_UNITS, UnitError, compatible_units, convert, normalize
from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.services.sales import CROP_ITEM_TYPE, SaleLine, crop_handler, money_flow_handler
from hth.ui import theme
from hth.ui.format import qty as fmt_qty
from hth.ui.modern import actions
from hth.ui.modern.widgets import (
    Freshness,
    MoneyBlock,
    StatRow,
    balance_state,
    caption,
    card,
    period_split,
    pill,
    rupees,
    segmented,
    set_pill,
    style_option,
)
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import confirm
from hth.ui.widgets.forms import DateField, LabeledEntry, LabeledOption
from hth.ui.widgets.searchbox import SearchBox

UNDO_MINUTES = 15  # how long the last entry can be undone from here (as on the classic screen)
SIDE_WIDTH = 290  # the customer and summary columns: fixed, so the middle never moves
QUALITY = ["A", "B", "C", "MIX"]
INTEREST = f"Charged · {ANNUAL_INTEREST_RATE_PERCENT:g}% a year"
NO_INTEREST = "No interest"
FALLBACK_METHODS = ["CASH", "UPI", "BANK"]  # without the finance module: names only


@dataclass(frozen=True)
class Intent:
    key: str
    label: str
    hint: str
    kind: str  # P = debit (customer owes more), M = credit (customer owes less)
    goods: bool  # items and lines - or an amount of money


INTENTS = (
    Intent("sale", "Sale", "goods go out", "P", True),
    Intent("purchase", "Purchase", "goods or crop come in", "M", True),
    Intent("in", "Payment in", "they pay us", "M", False),
    Intent("out", "Payment out", "we pay them", "P", False),
)


def _number(text: str) -> float:
    """'5,000' / '5000.50' -> float; '' -> 0.  Raises ValidationError on anything else."""
    text = (text or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError as exc:
        raise ValidationError(f"Invalid amount '{text}'.") from exc


def _two(head: str, words: str) -> str:
    """ "Balance now · owes us" - each half looked up on its own (a whole-phrase pattern like
    "Balance {}" would otherwise take the lot)."""
    return f"{i18n.tr(head)} · {i18n.tr(words)}"


class IntentTab(ctk.CTkFrame):
    def __init__(self, master, intent: Intent, command):
        super().__init__(master, corner_radius=10, border_width=1, cursor="hand2")
        self.title_label = ctk.CTkLabel(self, text=intent.label, font=theme.font(15, "bold"), anchor="w", height=22)
        self.title_label.pack(fill="x", padx=14, pady=(9, 0))
        self.hint = ctk.CTkLabel(self, text=intent.hint, font=theme.font(11), anchor="w", height=16)
        self.hint.pack(fill="x", padx=14, pady=(0, 9))
        for w in (self, self.title_label, self.hint):
            w.bind("<Button-1>", lambda e: command())
        self.set_active(False)

    def set_active(self, on: bool) -> None:
        self.configure(
            fg_color=theme.color("accent") if on else theme.color("surface"),
            border_color=theme.color("accent") if on else theme.color("line"),
        )
        self.title_label.configure(text_color=theme.color("accent_text") if on else theme.color("text"))
        self.hint.configure(text_color=theme.color("accent_soft") if on else theme.color("muted"))


class CounterView(BaseView):
    key = "counter"
    title = "Counter"
    permission = Permission.RECORD_SALE

    def build(self) -> None:
        self.intent = INTENTS[0]
        self.customer_id: int | None = None
        self._balance = 0.0
        self._promise: str | None = None  # the open promise date of the picked customer
        self._item = None  # the picked stock item (None = typed text)
        self._lines: list[tuple[SaleLine, float]] = []  # lines waiting to be saved together
        self._last: tuple[list, str, float, int] | None = None  # (results, message, time, customer)
        self._money: dict[str, tuple[int, str]] = {}  # account name -> (id, what the ledger calls it)
        self.fresh = Freshness(self.ctx.db)
        self.grid_columnconfigure(0, weight=0, minsize=290)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=290)
        self.grid_rowconfigure(0, weight=1)
        self._build_customer()
        self._build_entry()
        self._build_summary()
        self._build_footer()
        self._bind_keys()
        self.set_intent("sale", focus=False)

    # Layout ----------------------------------------------------------------------------
    def _build_customer(self) -> None:
        box = card(self, width=SIDE_WIDTH)
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        box.pack_propagate(False)  # a long name or entry must not widen it and squeeze the middle
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)
        caption(inner, "Customer · farmer · supplier").pack(fill="x")
        self.cust = SearchBox(
            inner, self._accounts, "Name, village or #id", on_select=lambda k, _l: self.pick_customer(k, focus=True)
        )
        self.cust.pack(fill="x", pady=(4, 0))
        self.cust.var.trace_add("write", lambda *_: self._on_customer_text())
        ctk.CTkButton(
            inner,
            text="+ New customer",
            anchor="w",
            height=26,
            width=10,
            fg_color="transparent",
            hover_color=theme.color("surface_hover"),
            text_color=theme.color("accent"),
            font=theme.font(12, "bold"),
            command=self.new_customer,
        ).pack(anchor="w", pady=(2, 6))
        self.empty = ctk.CTkLabel(
            inner,
            text="Pick a customer to see their balance, promise and last entries.",
            font=theme.font(12),
            text_color=theme.color("muted"),
            wraplength=240,
            justify="left",
            anchor="w",
        )
        self.empty.pack(fill="x", pady=8)

        self.snap = ctk.CTkFrame(inner, fg_color="transparent")
        head = ctk.CTkFrame(self.snap, fg_color="transparent")
        head.pack(fill="x")
        self.avatar = ctk.CTkLabel(
            head,
            text="",
            width=42,
            height=42,
            corner_radius=21,
            fg_color=theme.color("surface2"),
            font=theme.font(13, "bold"),
        )
        self.avatar.pack(side="left")
        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.name_label = ctk.CTkLabel(names, text="", font=theme.font(15, "bold"), anchor="w", height=20)
        self.name_label.pack(fill="x")
        self.detail_label = ctk.CTkLabel(
            names,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=190,
        )
        self.detail_label.pack(fill="x")
        self.money_block = MoneyBlock(self.snap)
        self.money_block.pack(fill="x", pady=(12, 8))
        facts = ctk.CTkFrame(self.snap, fg_color="transparent")
        facts.pack(fill="x")
        facts.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(facts, text="Promised", font=theme.font(12), text_color=theme.color("muted")).grid(
            row=0, column=0, sticky="w"
        )
        self.promise_pill = pill(facts, "")
        self.promise_pill.grid(row=0, column=1, sticky="e", pady=2)
        ctk.CTkLabel(facts, text="Last payment", font=theme.font(12), text_color=theme.color("muted")).grid(
            row=1, column=0, sticky="w"
        )
        self.last_paid = ctk.CTkLabel(facts, text="", font=theme.font(12, "bold"), anchor="e")
        self.last_paid.grid(row=1, column=1, sticky="e", pady=2)
        caption(self.snap, "Last entries").pack(fill="x", pady=(12, 2))
        self.recent: list[tuple[ctk.CTkLabel, ctk.CTkLabel, ctk.CTkLabel]] = []
        for _ in range(3):
            row = ctk.CTkFrame(self.snap, fg_color="transparent")
            row.pack(fill="x")
            d = ctk.CTkLabel(row, text="", font=theme.font(12), text_color=theme.color("muted"), width=50, anchor="w")
            d.pack(side="left")
            a = ctk.CTkLabel(row, text="", font=theme.font(12, "bold"), anchor="e")
            a.pack(side="right")
            p = ctk.CTkLabel(row, text="", font=theme.font(12), anchor="w")
            p.pack(side="left", fill="x", expand=True)
            self.recent.append((d, p, a))
        buttons = ctk.CTkFrame(self.snap, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(10, 0))
        for text, command in (
            ("Open khata", self.open_khata),
            ("WhatsApp", lambda: self._with_customer(actions.whatsapp_balance)),
            ("Promise", self.promise),
        ):
            self._small_button(buttons, text, command).pack(side="left", padx=(0, 6))

    def _build_entry(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=0, column=1, sticky="nsew")
        tabs = ctk.CTkFrame(col, fg_color="transparent")
        tabs.pack(fill="x")
        self.tabs: dict[str, IntentTab] = {}
        for i, it in enumerate(INTENTS):
            tab = IntentTab(tabs, it, lambda k=it.key: self.set_intent(k))
            tab.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            tabs.grid_columnconfigure(i, weight=1, uniform="t")
            self.tabs[it.key] = tab
        self.form = card(col)
        self.form.pack(fill="both", expand=True, pady=(10, 0))

        bottom = ctk.CTkFrame(self.form, fg_color="transparent")
        bottom.pack(fill="x", side="bottom", padx=16, pady=(4, 14))
        self.interest = LabeledOption(bottom, "Interest", [INTEREST, NO_INTEREST], INTEREST, command=self._recalc_cmd)
        style_option(self.interest.menu)
        self.interest.pack(side="left")
        self.date = DateField(bottom, "Date  (Alt+Up / Alt+Down)")
        self.date.pack(side="left", padx=(12, 0))
        self.total_label = ctk.CTkLabel(bottom, text="", font=theme.font(15, "bold"))
        self.total_label.pack(side="right", anchor="s", pady=(0, 6))

        self.goods = ctk.CTkFrame(self.form, fg_color="transparent")
        self.money_form = ctk.CTkFrame(self.form, fg_color="transparent")
        self._build_goods(self.goods)
        self._build_money(self.money_form)

    def _build_goods(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(16, 0))
        for c, w in enumerate((5, 2, 2, 2, 0)):
            row.grid_columnconfigure(c, weight=w)
        item_box = ctk.CTkFrame(row, fg_color="transparent")
        item_box.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(item_box, text="Item", font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
            fill="x"
        )
        self.item = SearchBox(
            item_box,
            self._items,
            "Type an item - or anything, e.g. LABOUR",
            on_select=lambda k, _l: self._on_item(k),
            allow_free_text=True,
        )
        self.item.pack(fill="x", pady=(2, 0))
        self.item.var.trace_add("write", lambda *_: self._on_item_text())
        self.qty = LabeledEntry(row, "Qty", placeholder="0")
        self.qty.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.unit = LabeledOption(row, "Unit", ALL_UNITS, "KG", command=self._recalc_cmd)
        style_option(self.unit.menu)
        self.unit.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        self.rate = LabeledEntry(row, "Rate ₹", placeholder="0.00")
        self.rate.grid(row=0, column=3, sticky="ew", padx=(8, 0))
        self.add_button = ctk.CTkButton(
            row,
            text="Add line",
            width=90,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=theme.color("accent"),
            text_color=theme.color("accent"),
            hover_color=theme.color("accent_soft"),
            font=theme.font(13, "bold"),
            command=self.add_line,
        )
        self.add_button.grid(row=0, column=4, sticky="sew", padx=(8, 0))
        for w in (self.qty, self.rate):
            w.var.trace_add("write", lambda *_: self.recalc())
        self.qty.entry.bind("<Return>", lambda e: self.rate.focus())
        self.rate.entry.bind("<Return>", lambda e: self._rate_enter())
        self.hint = ctk.CTkLabel(
            parent,
            text="Loose sale? 500 G of a KG item is converted. Rate fills in from the last sale.",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
        )
        self.hint.pack(fill="x", padx=16, pady=(6, 0))

        # crop fields - shown when the picked item is a crop
        self.crop = ctk.CTkFrame(parent, fg_color=theme.color("surface2"), corner_radius=10)
        self.crop_buy = ctk.CTkFrame(self.crop, fg_color="transparent")
        self.crop_buy.grid_columnconfigure((0, 1, 2), weight=1, uniform="c")
        self.kaat = LabeledEntry(self.crop_buy, "Kaat (deduction)", default="0")
        self.kaat.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        net_box = ctk.CTkFrame(self.crop_buy, fg_color="transparent")
        net_box.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(net_box, text="Net", font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
            fill="x"
        )
        self.net_label = ctk.CTkLabel(net_box, text="-", font=theme.font(14, "bold"), anchor="w", height=36)
        self.net_label.pack(fill="x")
        q_box = ctk.CTkFrame(self.crop_buy, fg_color="transparent")
        q_box.grid(row=0, column=2, sticky="ew")
        ctk.CTkLabel(q_box, text="Quality", font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
            fill="x"
        )
        self.quality = segmented(q_box, QUALITY, height=32)
        self.quality.set("A")
        self.quality.pack(anchor="w", pady=(2, 0))
        self.kaat.var.trace_add("write", lambda *_: self.recalc())
        self.crop_sell = ctk.CTkFrame(self.crop, fg_color="transparent")
        self.fifo = ctk.CTkLabel(self.crop_sell, text="", font=theme.font(12), anchor="w", justify="left")
        self.fifo.pack(fill="x")
        self.allow_short = ctk.CTkCheckBox(
            self.crop_sell, text="Allow selling more than in stock", font=theme.font(12), command=self.recalc
        )
        self.allow_short.pack(anchor="w", pady=(6, 0))
        self.notes = LabeledEntry(self.crop, "Notes (moisture, bags, vehicle…)")

        self.lines_box = ctk.CTkFrame(parent, fg_color="transparent")
        self.lines_box.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.lines_table = DataTable(
            self.lines_box,
            [
                Column("item", "Item", 220, stretch=True),
                Column("qty", "Qty", 90, "e"),
                Column("rate", "Rate", 90, "e", "money"),
                Column("amount", "Amount", 110, "e", "money"),
            ],
            height=5,
        )
        self.lines_table.pack(fill="both", expand=True)
        bar = ctk.CTkFrame(self.lines_box, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))
        self._small_button(bar, "Remove line", self.remove_line).pack(side="left")
        self._small_button(bar, "Clear all", self.clear_lines).pack(side="left", padx=6)
        self.lines_note = ctk.CTkLabel(
            bar, text="Enter on the rate adds the line", font=theme.font(11), text_color=theme.color("muted")
        )
        self.lines_note.pack(side="right", padx=4)

    def _build_money(self, parent) -> None:
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)
        self.amount_label = ctk.CTkLabel(inner, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.amount_label.pack(anchor="w")
        self.amount = ctk.CTkEntry(inner, height=54, font=theme.font(26, "bold"), placeholder_text="0")
        self.amount.pack(fill="x", pady=(2, 14))
        self.amount.bind("<KeyRelease>", lambda e: self.recalc())
        caption(inner, "How").pack(fill="x")
        self.method = segmented(inner, FALLBACK_METHODS, command=self._recalc_cmd)
        self.method.set(FALLBACK_METHODS[0])
        self.method.pack(anchor="w", pady=(4, 14))
        self.keep_promise = ctk.CTkCheckBox(inner, text="", font=theme.font(13), command=self.recalc)
        self.settle = ctk.CTkCheckBox(
            inner, text="Settle the account", font=theme.font(13, "bold"), command=self.recalc
        )
        self.settle_hint = ctk.CTkLabel(
            inner,
            text="",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=480,
        )
        self.settle_row = (self.settle, self.settle_hint)

    def _build_summary(self) -> None:
        box = card(self, width=SIDE_WIDTH)
        box.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        box.pack_propagate(False)
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)
        # packed first, from the bottom up: Save always keeps its room on a small screen
        self.books = ctk.CTkLabel(
            inner,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            wraplength=250,
            justify="left",
            anchor="w",
        )
        self.books.pack(fill="x", side="bottom", pady=(6, 0))
        self.print_after = ctk.CTkCheckBox(inner, text="Print slip after saving", font=theme.font(12))
        self.print_after.pack(anchor="w", side="bottom", pady=(8, 0))
        self.save_button = ctk.CTkButton(
            inner,
            text="Save",
            height=50,
            corner_radius=10,
            font=theme.font(16, "bold"),
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
            command=self.save,
        )
        self.save_button.pack(fill="x", side="bottom")
        self.sum_title = caption(inner, "This sale")
        self.sum_title.pack(fill="x", pady=(0, 6))
        self.stat_rows = [StatRow(inner) for _ in range(4)]
        self.paid_box = ctk.CTkFrame(inner, fg_color=theme.color("surface2"), corner_radius=10)
        ctk.CTkLabel(
            self.paid_box, text="Paid now", font=theme.font(12), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x", padx=12, pady=(8, 0))
        self.paid = ctk.CTkEntry(self.paid_box, height=34, font=theme.font(15, "bold"), placeholder_text="0")
        self.paid.pack(fill="x", padx=12, pady=(2, 6))
        self.paid.bind("<KeyRelease>", lambda e: self.recalc())
        self.paid_method = segmented(self.paid_box, FALLBACK_METHODS, command=self._recalc_cmd, height=30)
        self.paid_method.set(FALLBACK_METHODS[0])
        self.paid_method.pack(anchor="w", padx=12, pady=(0, 8))
        self.sum_spacer = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        self.sum_spacer.pack(fill="both", expand=True)

    def _build_footer(self) -> None:
        bar = card(self, corner_radius=10)
        bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.today_label = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.today_label.pack(side="left", padx=(14, 8), pady=8)
        ctk.CTkButton(
            bar,
            text="Today's entries",
            width=10,
            height=28,
            fg_color="transparent",
            hover_color=theme.color("surface_hover"),
            text_color=theme.color("accent"),
            font=theme.font(12, "bold"),
            command=self.show_today,
        ).pack(side="left")
        self.slip_button = self._small_button(bar, "Print slip", self.print_slip)
        self.slip_button.pack(side="right", padx=(6, 12))
        self.undo_button = self._small_button(bar, "↶ Undo  Ctrl+Z", self.undo_last)
        self.undo_button.pack(side="right")
        self.last_label = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.last_label.pack(side="right", padx=10)
        self._forget_last()

    def _small_button(self, master, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            master,
            text=text,
            width=10,
            height=30,
            corner_radius=8,
            fg_color=theme.color("surface"),
            border_width=1,
            border_color=theme.color("line"),
            hover_color=theme.color("surface_hover"),
            text_color=theme.color("text"),
            font=theme.font(12, "bold"),
            command=command,
        )

    def _bind_keys(self) -> None:
        top = self.winfo_toplevel()

        def guarded(fn):
            return lambda e: fn() if self.winfo_exists() and self.winfo_ismapped() else None

        # replace, not add: a rebuilt Counter must not leave callbacks to its old self
        top.bind("<Control-Return>", guarded(self.save))
        top.bind("<Control-Shift-Return>", guarded(self._save_credit))
        top.bind("<Control-z>", guarded(self.undo_last))
        for n, it in enumerate(INTENTS, start=1):
            top.bind(f"<Alt-Key-{n}>", guarded(lambda k=it.key: self.set_intent(k)))

    # Data ------------------------------------------------------------------------------
    def _accounts(self):
        return [(c.id, c.display) for c in self.ctx.accounts.list_customers()]

    def _items(self):
        return [(i.id, i.display) for i in self.ctx.inventory.list_items()]

    def _refresh_money(self) -> None:
        """Money accounts from Finance (CASH, SBI, PHONEPE …); the default one first chosen."""
        self._money = {}
        names, default = [], None
        flow = money_flow_handler(self.ctx.db)
        if flow is not None:
            try:
                default_id = flow.default_account_id()
                for a in flow.money_accounts():
                    self._money[a.name] = (a.id, (a.kind or a.name).upper())
                    names.append(a.name)
                    if a.id == default_id:
                        default = a.name
            except Exception:  # noqa: BLE001 - finance tables missing on a partial install
                names = []
        names = names or list(FALLBACK_METHODS)
        for seg in (self.method, self.paid_method):
            keep = seg.get()
            seg.configure(values=names)
            seg.set(keep if keep in names else (default or names[0]))

    def _method(self, seg) -> tuple[int | None, str]:
        """(money account id, what the ledger line says) for the chosen chip."""
        name = seg.get() or FALLBACK_METHODS[0]
        if name in self._money:
            return self._money[name]
        return None, name

    def _refresh_today(self) -> None:
        t = self.ctx.reports.day_totals()
        self.today_label.configure(text=f"Today: {t.entries} entries · gave {rupees(t.debit)} · got {rupees(t.credit)}")

    # Showing ---------------------------------------------------------------------------
    def on_show(
        self, customer_id: int | None = None, intent: str | None = None, item_id: int | None = None, **kwargs
    ) -> None:
        stale = self.fresh.stale()
        if stale:
            self.fresh.filling()
            self.cust.refresh()
            self.item.refresh()
            self._refresh_money()
            self._refresh_today()
        if intent:
            self.set_intent(intent, focus=False)
        if item_id is not None and self.intent.goods:  # from Stock: Purchase / Sale of this item
            self.item.set(item_id)
            self._on_item(item_id, focus=False)
        if customer_id is not None:
            self.pick_customer(customer_id)
        elif self.customer_id is not None and stale:
            self.pick_customer(self.customer_id)  # the balance may have changed elsewhere
        self.after(100, self._focus_next)

    def on_theme_change(self) -> None:
        self.lines_table.restyle()

    def on_day_change(self) -> None:
        super().on_day_change()
        self._refresh_today()

    def set_intent(self, key: str, focus: bool = True) -> None:
        self.intent = next((i for i in INTENTS if i.key == key), INTENTS[0])
        for k, tab in self.tabs.items():
            tab.set_active(k == self.intent.key)
        if self.intent.goods:
            self.money_form.pack_forget()
            self.goods.pack(fill="both", expand=True)
        else:
            self.goods.pack_forget()
            self.money_form.pack(fill="both", expand=True)
            self.amount_label.configure(text="Amount received ₹" if self.intent.key == "in" else "Amount paid out ₹")
        self.interest.set(NO_INTEREST if self._is_crop() else INTEREST)
        if self._item is None:
            self.hint.configure(text=self._idle_hint(), text_color=theme.color("muted"))
        self._update_crop_mode()
        self._update_payment_options()
        if self.intent.key == "sale":
            self.paid_box.pack(fill="x", pady=(8, 0), before=self.sum_spacer)
        else:
            self.paid_box.pack_forget()
        self.recalc()
        if focus:
            self._focus_next()

    def _focus_next(self) -> None:
        if not self.winfo_exists():
            return
        if self.customer_id is None:
            self.cust.entry.focus_set()
        elif self.intent.goods:
            self.item.entry.focus_set()
        else:
            self.amount.focus_set()

    # Customer --------------------------------------------------------------------------
    def _on_customer_text(self) -> None:
        key = self.cust.get_key()
        if key == self.customer_id:
            return  # nothing picked and still nothing, or the same customer
        if key is not None:
            self.pick_customer(key)
        else:
            self._clear_customer()

    def _clear_customer(self) -> None:
        self.customer_id = None
        self._balance = 0.0
        self._promise = None
        self.snap.pack_forget()
        self.empty.pack(fill="x", pady=8)
        self._update_payment_options()
        self.recalc()

    def pick_customer(self, customer_id: int, focus: bool = False) -> None:
        c = self.ctx.accounts.get_customer(customer_id)
        if c is None:
            self._clear_customer()
            return
        self.customer_id = c.id
        if self.cust.get_key() != c.id:
            self.cust.refresh()
            self.cust.set(c.id)
        rows = self.ctx.accounts.ledger(c.id)
        self._balance = bal = self.ctx.accounts.get_balance(c.id)
        _entered, interest = period_split(rows, bal)

        name = i18n.tr_cell(c.name)
        self.avatar.configure(text="".join(p[0] for p in c.name.split()[:2]).upper() or "?")
        self.name_label.configure(text=name)
        details = i18n.tr_cell(c.other_details) if c.other_details and c.other_details != "NA" else ""
        self.detail_label.configure(text=" · ".join(x for x in (details, f"#{c.id}", f"Cat {c.category}") if x))
        self.money_block.show(bal, f"includes {rupees(interest)} interest to today" if abs(interest) >= 0.01 else "")

        dates = self.ctx.krar.unsettled_dates(c.id)
        self._promise = max(dates) if dates else None
        if self._promise:
            days = (dt.date.fromisoformat(self._promise) - dt.date.today()).days
            when = f"{-days} days late" if days < 0 else ("today" if days == 0 else f"in {days} days")
            set_pill(self.promise_pill, f"{self._promise} · {when}", "late" if days < 0 else "due")
        else:
            set_pill(self.promise_pill, "none", "soon")
        paid = [r for r in rows if r.type == "M" and r.particulars not in ("Settled Amount", "Discount")]
        self.last_paid.configure(text=f"{paid[-1].date} · {rupees(paid[-1].amount)}" if paid else "none yet")
        recent = [r for r in rows if r.tag != "0"][-3:][::-1]
        for i, (d, p, a) in enumerate(self.recent):
            if i < len(recent):
                r = recent[i]
                d.configure(text=r.date[5:])
                p.configure(text=i18n.tr_cell(r.particulars)[:28])
                sign, color = ("+", "owe") if r.type == "P" else ("−", "weowe")
                a.configure(text=f"{sign}{rupees(r.amount)[1:]}", text_color=theme.color(color))
            else:
                d.configure(text="")
                p.configure(text="")
                a.configure(text="")
        self.empty.pack_forget()
        self.snap.pack(fill="both", expand=True)
        self._update_payment_options()
        self.recalc()
        if focus:
            self.after(60, self._focus_next)

    def new_customer(self) -> None:
        typed = "" if self.cust.get_key() is not None else self.cust.get_text()
        c = actions.new_customer(self, self.ctx, typed)
        if c is not None:
            self.cust.refresh()
            self.pick_customer(c.id, focus=True)

    def _with_customer(self, fn) -> None:
        if self.customer_id is None:
            self.ctx.toast("Pick a customer first", "warning")
            return
        fn(self, self.ctx, self.customer_id)

    def open_khata(self) -> None:
        if self.customer_id is not None:
            self.ctx.navigate("customers", customer_id=self.customer_id)

    def promise(self) -> None:
        if self.customer_id is not None and actions.promise(self, self.ctx, self.customer_id):
            self.pick_customer(self.customer_id)

    # Items and lines -------------------------------------------------------------------
    def _is_crop(self) -> bool:
        return self._item is not None and self._item.item_type == CROP_ITEM_TYPE and self.intent.goods

    def _on_item(self, item_id, focus: bool = True) -> None:
        item = self.ctx.inventory.get_item(item_id)
        self._item = item
        if item is None:
            return
        units = compatible_units(item.unit) or ALL_UNITS
        self.unit.set_values(units)
        self.unit.set(units[0])
        self.rate.set(f"{item.last_value:g}")
        stock = self.ctx.inventory.quantity(item.id)
        unit = normalize(item.unit)
        self.hint.configure(
            text=f"{fmt_qty(stock)} {unit} in stock · rate is per {unit}"
            + ("  ·  crop - entered on its own" if item.item_type == CROP_ITEM_TYPE else ""),
            text_color=theme.color("owe") if stock <= 0 and self.intent.key == "sale" else theme.color("muted"),
        )
        self.interest.set(NO_INTEREST if self._is_crop() else INTEREST)
        self._update_crop_mode()
        self.recalc()
        if focus:
            self.qty.focus()

    def _on_item_text(self) -> None:
        key = self.item.get_key()
        if self._item is None and key is not None:
            self._on_item(key, focus=False)
            return
        if self._item is not None and key != self._item.id:
            self._item = None
            self.unit.set_values(ALL_UNITS)
            self.hint.configure(text="Not a stock item - it goes on the khata only", text_color=theme.color("muted"))
            self.interest.set(INTEREST)
            self._update_crop_mode()
            self.recalc()

    def _update_crop_mode(self) -> None:
        crop = self._is_crop()
        if crop:
            buy = self.intent.key == "purchase"
            self.crop_buy.pack_forget()
            self.crop_sell.pack_forget()
            self.notes.pack_forget()
            (self.crop_buy if buy else self.crop_sell).pack(fill="x", padx=12, pady=(10, 0))
            self.notes.pack(fill="x", padx=12, pady=(6, 12))
            if not self.crop.winfo_manager():
                self.crop.pack(fill="x", padx=16, pady=(10, 0), after=self.hint)
            self.add_button.configure(state="disabled")
            self.lines_note.configure(text="A crop trade is saved on its own")
        else:
            if self.crop.winfo_manager():
                self.crop.pack_forget()
            self.add_button.configure(state="normal")
            self.lines_note.configure(text="Enter on the rate adds the line")

    def _stock_qty(self, text: str | None = None) -> tuple[float, str] | None:
        try:
            q = float((self.qty.get() if text is None else text) or 0)
        except ValueError:
            return None
        unit = normalize(self.unit.get())
        if self._item is None:
            return q, unit
        try:
            return convert(q, unit, self._item.unit), normalize(self._item.unit)
        except UnitError:
            return None

    def _current_amount(self) -> float:
        """What the line being typed comes to (0 when it is empty or not valid yet)."""
        conv = self._stock_qty()
        try:
            price = float(self.rate.get() or 0)
        except ValueError:
            return 0.0
        if conv is None:
            return 0.0
        q, _unit = conv
        if self._is_crop() and self.intent.key == "purchase":
            q = max(0.0, q - self._kaat(q))
        return round(price * q, 2)

    def _kaat(self, _gross: float) -> float:
        try:
            k = float(self.kaat.get() or 0)
            return convert(k, self.unit.get(), self._item.unit) if self._item else k
        except (ValueError, UnitError):
            return 0.0

    def _item_name(self) -> str:
        """What the ledger records: the stock item's English label even when Hindi is shown."""
        if self._item is not None and self.item.get_key() == self._item.id:
            return self._item.display
        return self.item.get_text()

    def _current_line(self, required: bool) -> tuple[SaleLine, float] | None:
        name = self._item_name()
        if not (name or self.qty.get() or self.rate.get()):
            if required:
                raise ValidationError("Enter an item, quantity and rate.")
            return None
        if not name:
            raise ValidationError("Item is required.")
        if not (self.qty.get() and self.rate.get()):
            raise ValidationError("Quantity and rate are required.")
        if self._stock_qty() is None:
            raise ValidationError(f"{self.unit.get()} cannot be converted to {self._item.unit if self._item else ''}.")
        try:
            float(self.rate.get())
        except ValueError as exc:
            raise ValidationError(f"Invalid rate '{self.rate.get()}'.") from exc
        line = SaleLine(name, self.qty.get(), self.rate.get(), self.item.get_key(), self.unit.get())
        return line, self._current_amount()

    def _rate_enter(self) -> None:
        if self._is_crop():
            self.save_button.focus_set()
        else:
            self.add_line()

    def add_line(self) -> None:
        if self._is_crop():
            return
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
            (self._shown_name(line), f"{line.quantity} {line.unit or ''}".strip(), line.price, amount, i)
            for i, (line, amount) in enumerate(self._lines)
        ]
        self.lines_table.set_rows(rows, f"{len(rows)} line(s)" if rows else "")
        self.recalc()

    def _idle_hint(self) -> str:
        if self.intent.key == "purchase":
            return "Stock bought in goes up. Pick a crop to weigh it as a lot (kaat, quality)."
        return "Loose sale? 500 G of a KG item is converted. Rate fills in from the last sale."

    def _shown_name(self, line: SaleLine) -> str:
        item = self.ctx.inventory.get_item(line.item_id) if line.item_id is not None else None
        return i18n.tr_cell(item.name) if item is not None else line.item_name

    def _clear_item_fields(self) -> None:
        self.item.clear()
        self._item = None
        self.qty.set("")
        self.rate.set("")
        self.kaat.set("0")
        self.notes.set("")
        self.allow_short.deselect()
        self.unit.set_values(ALL_UNITS)
        self.hint.configure(text=self._idle_hint(), text_color=theme.color("muted"))
        self._update_crop_mode()

    # Money -----------------------------------------------------------------------------
    def _update_payment_options(self) -> None:
        for w in (self.keep_promise, *self.settle_row):
            w.pack_forget()
        if self.intent.key != "in":
            return
        if self._promise:
            self.keep_promise.configure(text=f"Mark the promise of {self._promise} as kept")
            self.keep_promise.select()
            self.keep_promise.pack(anchor="w", pady=(0, 10))
        if self.customer_id is not None and self._balance > 0:
            self.settle.pack(anchor="w")
            self.settle_hint.pack(fill="x", padx=(28, 0), pady=(0, 6))

    def _tag(self) -> str:
        return "2" if self.interest.get() == NO_INTEREST else "1"

    # Summary ---------------------------------------------------------------------------
    def _recalc_cmd(self, _value=None) -> None:
        self.recalc()

    def recalc(self) -> None:
        it = self.intent
        have = self.customer_id is not None
        bal = self._balance
        tag = self._tag()
        rows: list[tuple[str, str, str]] = []
        if it.goods:
            lines_total = sum(a for _l, a in self._lines)
            cur = self._current_amount()
            total = round(lines_total + cur, 2)
            n = len(self._lines) + (1 if cur else 0)
            if it.key == "sale":
                try:
                    paid = _number(self.paid.get())
                except ValidationError:
                    paid = 0.0
                _acct, how = self._method(self.paid_method)
                rows = [("Items total", rupees(total), "text")]
                if paid:
                    rows += [
                        (f"Paid now ({how.lower()})", f"− {rupees(paid)}", "weowe"),
                        ("Goes on khata", rupees(total - paid), "text"),
                    ]
                after = bal + total - paid
                title, button = "This sale", "Save sale"
                if self._is_crop():
                    books = f"Books a Debit (P), tag {tag}, costed from the oldest lots first."
                else:
                    books = f"Books {max(n, 1)} line(s) as Debit (P), tag {tag}"
                    books += f", and {rupees(paid)} as Credit (M) into {self.paid_method.get()}." if paid else "."
            else:
                rows = [("Total", rupees(total), "text")]
                if self._is_crop():
                    conv = self._stock_qty()
                    if conv:
                        net = max(0.0, conv[0] - self._kaat(conv[0]))
                        unit = normalize(self._item.unit)
                        self.net_label.configure(text=f"{fmt_qty(net)} {unit}")
                        rows.insert(0, ("Net weight", f"{fmt_qty(net)} {unit}", "text"))
                    rows.append(("New lot", f"grade {self.quality.get()}", "text"))
                    books = f"Books a Credit (M), tag {tag}, and adds a crop lot to stock."
                else:
                    books = f"Books {max(n, 1)} line(s) as Credit (M), tag {tag}; stock goes up."
                after = bal - total
                title, button = "This purchase", "Save purchase"
            self.total_label.configure(text=f"{n} item(s) · {rupees(total)}" if n else "")
            self._update_fifo()
        else:
            try:
                amt = _number(self.amount.get())
            except ValidationError:
                amt = 0.0
            words = balance_state(bal)[0].lower()
            rows = [(_two("Balance now", words), rupees(bal), "text")]
            account = self.method.get()
            if it.key == "in":
                settle = bool(self.settle.get()) and self.settle.winfo_manager()
                rows.append(("Received", f"− {rupees(amt)}", "weowe"))
                after = 0.0 if settle else bal - amt
                if settle:
                    rows.append(("Written off as discount", rupees(bal - amt), "muted"))
                self.settle_hint.configure(
                    text=f"Closes this period. The rest ({rupees(bal - amt)}) is written off as discount "
                    "and the balance starts again at zero."
                )
                books = f"Books a Credit (M), tag {'0' if settle else tag}, into {account}"
                if settle:
                    books += "; closes the period"
                if self._promise and self.keep_promise.get():
                    books += "; marks the promise kept"
                books += "."
                title, button = "This payment", "Save payment"
            else:
                rows.append(("Paid out", f"+ {rupees(amt)}", "owe"))
                after = bal + amt
                books = f"Books a Debit (P), tag {tag}, out of {account}."
                title, button = "This payment", "Save payment out"
            self.total_label.configure(text="")
        if have:
            words, color, _soft = balance_state(after)
            rows.append((_two("Balance after", words.lower()), rupees(after), color if color != "muted" else "text"))
        else:
            rows.append(("Balance after", "pick a customer", "muted"))
        for i, (label, value, color) in enumerate(rows[: len(self.stat_rows)]):
            self.stat_rows[i].set(label, value, color, big=i == len(rows) - 1)
        self._lay_out_stats(min(len(rows), len(self.stat_rows)))
        self.sum_title.configure(text=i18n.tr(title).upper())
        self.save_button.configure(text=f"{button}   Ctrl+Enter")
        self.books.configure(text=books)

    def _lay_out_stats(self, count: int) -> None:
        """Show ``count`` summary rows above the paid-now box - re-packed only when the
        shape changes, not on every key press."""
        paid_shown = bool(self.paid_box.winfo_manager())
        if getattr(self, "_stat_shape", None) == (count, paid_shown):
            return
        self._stat_shape = (count, paid_shown)
        for stat in self.stat_rows:
            stat.pack_forget()
        anchor = self.paid_box if paid_shown else self.sum_spacer
        for stat in self.stat_rows[:count]:
            stat.pack(fill="x", pady=(0, 6), before=anchor)

    def _update_fifo(self) -> None:
        if not (self._is_crop() and self.intent.key == "sale"):
            return
        conv = self._stock_qty()
        crop = crop_handler(self.ctx.db)
        if not conv or conv[0] <= 0 or crop is None:
            self.fifo.configure(text="Cost is worked out from the oldest lots first.")
            return
        q, unit = conv
        pv = crop.preview_cost(self._item.id, q)
        try:
            price = float(self.rate.get() or 0)
        except ValueError:
            price = 0.0
        margin = price * q - pv.cost
        short = f"   ·   {fmt_qty(pv.short_qty)} {unit} more than in stock" if pv.short_qty > 0 else ""
        self.fifo.configure(
            text=f"Cost {rupees(pv.cost)} from {len(pv.allocations)} lot(s)   ·   margin {rupees(margin)}{short}",
            text_color=theme.color("owe") if pv.short_qty > 0 else theme.color("text"),
        )

    # Saving ----------------------------------------------------------------------------
    def _save_credit(self) -> None:
        """Ctrl+Shift+Enter was Credit on the classic screen: it never saves a sale here."""
        if self.intent.kind == "M":
            self.save()
        else:
            self.ctx.toast(
                "Ctrl+Shift+Enter saves a Purchase or a Payment in - pick that tab (Alt+2 / Alt+3)", "warning"
            )

    def save(self) -> None:
        try:
            if self.customer_id is None:
                raise ValidationError("Pick a customer first.")
            date = self.date.get()
            results, msg = self._save_goods(date) if self.intent.goods else self._save_money(date)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self._after_post(results, msg)

    def _save_goods(self, date: str) -> tuple[list, str]:
        it, cid, user, tag = self.intent, self.customer_id, self.ctx.username, self._tag()
        if self._is_crop():
            if self._lines:
                raise ValidationError("A crop trade is saved on its own - save or clear the other lines first.")
            if not (self.qty.get() and self.rate.get()):
                raise ValidationError("Quantity and rate are required.")
            buy = it.key == "purchase"
            r = self.ctx.sales.record(
                it.kind,
                date,
                cid,
                self._item_name(),
                self.qty.get(),
                self.rate.get(),
                tag,
                user,
                item_id=self._item.id,
                unit=self.unit.get(),
                deduction=(self.kaat.get() or 0) if buy else None,
                quality=self.quality.get() if buy else "",
                notes=self.notes.get(),
                allow_short=bool(self.allow_short.get()) and not buy,
            )
            if r.crop_lot_id is not None:
                msg = f"Lot #{r.crop_lot_id}: {fmt_qty(r.stock_quantity)} {r.stock_unit} bought for {rupees(r.amount)}"
            else:
                short = f" ({fmt_qty(r.short_qty)} short)" if r.short_qty else ""
                msg = f"Crop sale #{r.crop_sale_id}: {rupees(r.amount)} · margin {rupees(r.margin or 0)}{short}"
            self._clear_item_fields()
            return [r], msg
        current = self._current_line(required=not self._lines)
        lines = [line for line, _a in self._lines] + ([current[0]] if current else [])
        if it.key == "sale":
            paid = _number(self.paid.get())
            account_id, paid_as = self._method(self.paid_method)
            results = self.ctx.sales.record_sale_with_payment(date, cid, lines, tag, user, paid, paid_as, account_id)
            total = sum(r.amount for r in results if r.kind == "P")
            msg = f"Sale of {rupees(total)} saved" + (f" · {rupees(paid)} paid" if paid else "")
            self.paid.delete(0, "end")
        else:
            results = self.ctx.sales.record_lines("M", date, cid, lines, tag, user)
            msg = f"Purchase of {rupees(sum(r.amount for r in results))} saved"
        self._lines.clear()
        self._clear_item_fields()
        self._refresh_lines()
        return results, msg

    def _save_money(self, date: str) -> tuple[list, str]:
        it, cid, user = self.intent, self.customer_id, self.ctx.username
        amount = _number(self.amount.get())
        if amount <= 0:
            raise ValidationError("Enter the amount.")
        account_id, label = self._method(self.method)
        settle = it.key == "in" and bool(self.settle.get()) and self.settle.winfo_manager()
        keep = it.key == "in" and self._promise is not None and bool(self.keep_promise.get())
        r = self.ctx.sales.record(
            it.kind, date, cid, label, "1", amount, "0" if settle else self._tag(), user, money_account_id=account_id
        )
        if keep:
            self.ctx.krar.settle(cid, user)
        self.amount.delete(0, "end")
        self.settle.deselect()
        verb = "received" if it.key == "in" else "paid out"
        return [r], f"{rupees(r.amount)} {verb}" + (" · account settled" if settle else "")

    def _after_post(self, results: list, msg: str) -> None:
        self.ctx.toast(msg + "  ·  Ctrl+Z to undo", "success")
        self.ctx.status(msg)
        self._last = (results, msg, time.monotonic(), self.customer_id)
        self.undo_button.configure(state="normal")
        self.slip_button.configure(state="normal")
        self.last_label.configure(text=f"Saved {time.strftime('%H:%M')} — {msg}")
        if self.print_after.get():
            self.print_slip()
        self.pick_customer(self.customer_id)
        self._refresh_today()
        # the next person: typing replaces the name, Tab carries on with the same customer
        self.cust.entry.focus_set()
        self.cust.entry.select_range(0, "end")

    def undo_last(self) -> None:
        if self._last is None:
            return
        results, msg, at, cid = self._last
        if time.monotonic() - at > UNDO_MINUTES * 60:
            self.ctx.toast(
                f"Undo is only offered for {UNDO_MINUTES} minutes - ask an admin to correct the khata", "warning"
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
        if cid is not None and cid == self.customer_id:
            self.pick_customer(cid)
        self._refresh_today()

    def _forget_last(self) -> None:
        self._last = None
        self.undo_button.configure(state="disabled")
        self.slip_button.configure(state="disabled")
        self.last_label.configure(text="")

    def print_slip(self) -> None:
        if self._last is None:
            return
        from hth.services.slips import SlipService
        from hth.ui.format import open_path

        results, _msg, _at, cid = self._last
        if cid is None:
            return
        try:
            path = SlipService(self.ctx.db).write(results, cid, self.ctx.settings.export_dir, self.ctx.username)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        open_path(path)

    def show_today(self) -> None:
        TodayEntries(self, self.ctx)


class TodayEntries(ctk.CTkToplevel):
    """Every sale, receipt and crop trade made today, with who made it."""

    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.title("Today's entries")
        self.geometry("860x460")
        table = DataTable(
            self,
            [
                Column("time", "Time", 70),
                Column("kind", "Type", 90),
                Column("msg", "Details", 520, stretch=True),
                Column("user", "By", 80),
            ],
            row_tags=lambda r: ["pos"] if r[1] in ("Receive", "Purchase") else [],
        )
        table.pack(fill="both", expand=True, padx=12, pady=12)
        from hth.ui.format import today_str

        rows = []
        for e in ctx.audit.entries(today_str(), today_str(), limit=500):
            if e.code not in ("03", "04", "10"):
                continue
            if e.code == "10":
                kind = "Purchase" if e.message.startswith("purchase") else "Crop sale"
            else:
                kind = "Sale" if e.code == "03" else "Receive"
            rows.append((e.ts[11:16], kind, e.message, e.username))
        table.set_rows(rows, f"{len(rows)} entries today")
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.after(50, self.focus_set)
