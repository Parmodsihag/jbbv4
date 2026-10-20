"""Khata - customers and what they owe, in the new layout.

*Customers*: the list on the left, one page per customer on the right - balance, promise,
the buttons for what you do with them, and their entries, promises, crop trades and
details.  *Collections* (the classic Karar screen): every open promise and everyone who
owes, with the reminder ready to send.  Entries are made at the Counter; corrections and
deletions (admin) are on the entry's right-click menu, with a plain warning of what changes.
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk

import customtkinter as ctk

from hth import i18n
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.services.sales import crop_handler
from hth.services.statements import financial_year_start
from hth.ui import theme
from hth.ui.format import open_path
from hth.ui.modern import actions
from hth.ui.modern.widgets import (
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

QUIET_DAYS = 180
PERIODS = ["Current period", "This FY", "Last 90 days", "All"]


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _menu(widget) -> tk.Menu:
    return tk.Menu(
        widget,
        tearoff=0,
        bg=theme.current("surface"),
        fg=theme.current("text"),
        activebackground=theme.current("accent_soft"),
        activeforeground=theme.current("text"),
        font=theme.table_font(),
    )


def _popup(menu: tk.Menu, button) -> None:
    try:
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height() + 2)
    finally:
        menu.grab_release()


def _button(master, text: str, command, primary: bool = False, outline: bool = False, **kw) -> ctk.CTkButton:
    if primary:
        colors = {
            "fg_color": theme.color("accent"),
            "hover_color": theme.color("accent_hover"),
            "text_color": theme.color("accent_text"),
        }
    elif outline:
        colors = {
            "fg_color": "transparent",
            "border_width": 1,
            "border_color": theme.color("accent"),
            "hover_color": theme.color("accent_soft"),
            "text_color": theme.color("accent"),
        }
    else:
        colors = {
            "fg_color": theme.color("surface"),
            "border_width": 1,
            "border_color": theme.color("line"),
            "hover_color": theme.color("surface_hover"),
            "text_color": theme.color("text"),
        }
    kw.setdefault("height", 36)
    kw.setdefault("width", 10)
    return ctk.CTkButton(
        master, text=text, command=command, corner_radius=9, font=theme.font(13, "bold"), **colors, **kw
    )


class KhataView(BaseView):
    key = "khata"
    title = "Khata"
    permission = Permission.ADD_CUSTOMER

    def build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        self.pages = ["Customers"] + (["Collections"] if self.ctx.can(Permission.MANAGE_KRAR) else [])
        self.switch = segmented(head, self.pages, command=lambda v: self.show_page(v))
        self.switch.pack(side="left")
        self.summary = ctk.CTkLabel(head, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.summary.pack(side="left", padx=14)
        _button(head, "+ New customer", self.new_customer, outline=True).pack(side="right")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self.customers = CustomersPage(body, self)
        self.collections = CollectionsPage(body, self) if "Collections" in self.pages else None
        self.current: str | None = None

    def show_page(self, name: str, **kwargs) -> None:
        page = self.collections if name == "Collections" and self.collections else self.customers
        other = self.customers if page is self.collections else self.collections
        if other is not None:
            other.pack_forget()
        page.pack(fill="both", expand=True)
        self.current = "karar" if page is self.collections else "customers"
        self.switch.set("Collections" if page is self.collections else "Customers")
        page.on_show(**kwargs)

    def child(self, key: str):
        """Lets ``find_view`` reach the pages by their classic keys."""
        return {"customers": self.customers, "karar": self.collections}.get(key)

    def on_show(self, tab: str | None = None, customer_id: int | None = None, **kwargs) -> None:
        if tab == "karar" and self.collections is not None:
            self.show_page("Collections", **kwargs)
        elif tab == "customers" or customer_id is not None or self.current is None:
            self.show_page("Customers", customer_id=customer_id)
        else:
            self.show_page("Collections" if self.current == "karar" else "Customers")

    def on_theme_change(self) -> None:
        self.customers.restyle()
        if self.collections is not None:
            self.collections.table.restyle()

    def new_customer(self) -> None:
        c = actions.new_customer(self, self.ctx)
        if c is not None:
            self.show_page("Customers", customer_id=c.id)


# --------------------------------------------------------------------------------------
class CustomersPage(ctk.CTkFrame):
    def __init__(self, master, view: KhataView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx = view, view.ctx
        self._all: list[tuple] = []
        self._pending = None
        self.grid_columnconfigure(0, weight=0, minsize=350)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = card(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.search = ctk.CTkEntry(left, placeholder_text="Name, village, phone or #id", height=36, font=theme.font(13))
        self.search.pack(fill="x", padx=12, pady=(12, 8))
        self.search.bind("<KeyRelease>", lambda e: self._filter())
        self.search.bind("<Down>", lambda e: (self.table.tree.focus_set(), self.table.select_first()))
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=12)
        self.chips = segmented(row, ["All", "Owe us", "We owe", "Quiet"], command=lambda _v: self._filter(), height=30)
        self.chips.set("All")
        self.chips.pack(side="left")
        self.cat = ctk.CTkOptionMenu(
            row,
            values=["Cat", "A", "B", "C", "D", "E"],
            width=70,
            height=30,
            font=theme.font(12),
            command=lambda _v: self._filter(),
        )
        self.cat.set("Cat")
        style_option(self.cat)
        self.cat.pack(side="right")
        self.table = DataTable(
            left,
            [
                Column("name", "Customer", 190, stretch=True),
                Column("balance", "Balance", 105, "e", "money"),
                Column("days", "Days", 56, "e", "int"),
            ],
            on_select=self._on_select,
            row_tags=lambda r: (
                (["muted"] if r[4] == "E" else []) + (["neg"] if r[1] > 0 else (["pos"] if r[1] < 0 else ["muted"]))
            ),
        )
        self.table.pack(fill="both", expand=True, padx=8, pady=(8, 8))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.page = CustomerPage(right, view)
        self.empty = ctk.CTkLabel(
            right,
            text="Pick a customer on the left to see their khata.",
            font=theme.font(14),
            text_color=theme.color("muted"),
        )
        self.empty.pack(expand=True)

    def restyle(self) -> None:
        self.table.restyle()
        self.page.restyle()

    def on_show(self, customer_id: int | None = None, **kwargs) -> None:
        self.reload()
        if customer_id is not None:
            self.open(customer_id)
        elif self.page.customer is not None:
            self.open(self.page.customer.id)
        self.after(80, self.search.focus_set)

    def reload(self) -> None:
        self.table.set_footer("Loading balances…")
        self.view.run_async(lambda: self.ctx.categories.customer_summaries(scope="all"), self._loaded)

    def _loaded(self, summaries) -> None:
        rows = []
        for s in sorted(summaries, key=lambda s: (s.days, s.name)):
            details = s.other_details if s.other_details and s.other_details != "NA" else ""
            label = f"{s.name}  ·  {details}" if details else s.name
            rows.append((label, s.balance, s.days, s.id, s.category, f"{s.id} {s.name} {details}"))
        self._all = rows
        receivable = sum(r[1] for r in rows if r[1] > 0)
        payable = -sum(r[1] for r in rows if r[1] < 0)
        self.view.summary.configure(text=f"Receivable {rupees(receivable)} · payable {rupees(payable)}")
        self._filter()

    def _filter(self) -> None:
        words = self.search.get().strip().lower().split()
        chip, cat = self.chips.get(), self.cat.get()
        rows = [
            r
            for r in self._all
            if all(w in r[5].lower() for w in words)
            and (cat == "Cat" or r[4] == cat)
            and (
                chip == "All"
                or (chip == "Owe us" and r[1] > 0)
                or (chip == "We owe" and r[1] < 0)
                or (chip == "Quiet" and r[1] > 0 and r[2] >= QUIET_DAYS)
            )
        ]
        self.table.set_rows(rows, f"{len(rows)} accounts · recent first")

    def _on_select(self, row) -> None:
        if row is None:
            return
        if self._pending is not None:
            self.after_cancel(self._pending)
        # arrow keys move fast through the list: load the page once the cursor rests
        self._pending = self.after(160, lambda cid=row[3]: self.open(cid))

    def open(self, customer_id: int) -> None:
        self._pending = None
        if not self.page.load(customer_id):
            return
        self.empty.pack_forget()
        if not self.page.winfo_manager():
            self.page.pack(fill="both", expand=True)


# --------------------------------------------------------------------------------------
class CustomerPage(ctk.CTkFrame):
    def __init__(self, master, view: KhataView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx = view, view.ctx
        self.customer = None
        self._rows: list = []
        can = self.ctx.can

        head = card(self)
        head.pack(fill="x")
        top = ctk.CTkFrame(head, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        self.avatar = ctk.CTkLabel(
            top,
            text="",
            width=48,
            height=48,
            corner_radius=24,
            fg_color=theme.color("surface2"),
            font=theme.font(15, "bold"),
        )
        self.avatar.pack(side="left", anchor="n")
        names = ctk.CTkFrame(top, fg_color="transparent")
        names.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.name_label = ctk.CTkLabel(names, text="", font=theme.font(20, "bold"), anchor="w", height=26)
        self.name_label.pack(fill="x")
        self.detail_label = ctk.CTkLabel(
            names, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w"
        )
        self.detail_label.pack(fill="x")
        pills = ctk.CTkFrame(names, fg_color="transparent")
        pills.pack(fill="x", pady=(4, 0))
        self.cat_pill = pill(pills, "", "info")
        self.cat_pill.pack(side="left")
        self.promise_pill = pill(pills, "", "late")
        self.promise_pill.pack(side="left", padx=6)
        money = ctk.CTkFrame(top, fg_color="transparent")
        money.pack(side="right", anchor="n")
        self.words = ctk.CTkLabel(money, text="", font=theme.font(11, "bold"), anchor="e", height=16)
        self.words.pack(fill="x")
        self.amount = ctk.CTkLabel(money, text="", font=theme.font(26, "bold"), anchor="e")
        self.amount.pack(fill="x")
        self.split = ctk.CTkLabel(money, text="", font=theme.font(11), text_color=theme.color("muted"), anchor="e")
        self.split.pack(fill="x")

        bar = ctk.CTkFrame(head, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=(0, 14))
        if can(Permission.RECORD_SALE):
            _button(bar, "↗  Sale", lambda: self._counter("sale"), primary=True).pack(side="left")
            _button(bar, "↙  Payment in", lambda: self._counter("in"), outline=True).pack(side="left", padx=6)
            self.other_button = _button(bar, "Other entry ▾", self._other_menu)
            self.other_button.pack(side="left")
        ctk.CTkFrame(bar, width=1, height=26, fg_color=theme.color("line")).pack(side="left", padx=10)
        if can(Permission.MANAGE_KRAR):
            _button(bar, "Promise", self.promise).pack(side="left")
        _button(bar, "WhatsApp", lambda: actions.whatsapp_balance(self, self.ctx, self.customer.id)).pack(
            side="left", padx=6
        )
        _button(bar, "Statement", lambda: actions.statement(self, self.ctx, self.customer.id)).pack(side="left")
        if can(Permission.EDIT_RECORDS) or can(Permission.DELETE_RECORDS):
            self.more_button = _button(bar, "⋯ More", self._more_menu)
            self.more_button.pack(side="left", padx=6)

        body = card(self)
        body.pack(fill="both", expand=True, pady=(12, 0))
        tabs = ["Entries", "Promises"] + (["Crop trades"] if crop_handler(self.ctx.db) else []) + ["Details"]
        tabs_row = ctk.CTkFrame(body, fg_color="transparent")
        tabs_row.pack(fill="x", padx=14, pady=(12, 6))
        self.tabs = segmented(tabs_row, tabs, command=lambda v: self.show_tab(v))
        self.tabs.set("Entries")
        self.tabs.pack(side="left")
        self.frames: dict[str, ctk.CTkFrame] = {name: ctk.CTkFrame(body, fg_color="transparent") for name in tabs}
        self._build_entries(self.frames["Entries"], tabs_row)
        self._build_promises(self.frames["Promises"])
        if "Crop trades" in self.frames:
            self._build_crops(self.frames["Crop trades"])
        self._build_details(self.frames["Details"])
        self.show_tab("Entries")

    # Tabs ------------------------------------------------------------------------------
    def _build_entries(self, parent, tabs_row) -> None:
        self.entry_tools = ctk.CTkFrame(tabs_row, fg_color="transparent")
        self.period = segmented(self.entry_tools, PERIODS, command=lambda _v: self._apply_period(), height=30)
        self.period.set(PERIODS[0])
        self.period.pack(side="left", padx=(12, 8))
        _button(self.entry_tools, "Excel", self.export, height=30).pack(side="right")
        self.find = ctk.CTkEntry(self.entry_tools, placeholder_text="Find in entries…", width=170, height=30)
        self.find.pack(side="right", padx=8)
        self.find.bind("<KeyRelease>", lambda e: self.ledger.filter(self.find.get()))
        admin = self.ctx.can(Permission.EDIT_RECORDS)
        self.ledger = DataTable(
            parent,
            [
                Column("date", "Date", 92),
                Column("particulars", "Particulars", 260, stretch=True),
                Column("debit", "Gave (Dr)", 105, "e", "money"),
                Column("credit", "Got (Cr)", 105, "e", "money"),
                Column("interest", "Interest", 90, "e", "money"),
                Column("balance", "Balance", 115, "e", "money"),
            ],
            row_tags=lambda r: ["muted", "bold"] if r[7] == "0" else [],
            on_double_click=(lambda r: self.correct(r)) if admin else None,
            row_actions=self._row_actions,
        )
        self.ledger.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_promises(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(4, 8))
        if self.ctx.can(Permission.MANAGE_KRAR):
            _button(bar, "New date", self.promise, height=32).pack(side="left")
            _button(bar, "Mark kept", self.mark_kept, height=32).pack(side="left", padx=6)
        self.promises = DataTable(
            parent,
            [
                Column("date", "Promised", 110),
                Column("status", "Status", 140),
                Column("note", "Note", 300, stretch=True),
            ],
            row_tags=lambda r: ["neg"] if r[1] == "Open · late" else (["muted"] if r[1].startswith("Closed") else []),
        )
        self.promises.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_crops(self, parent) -> None:
        self.crops = DataTable(
            parent,
            [
                Column("date", "Date", 92),
                Column("kind", "Trade", 120),
                Column("crop", "Crop", 140, stretch=True),
                Column("qty", "Quantity", 110, "e"),
                Column("rate", "Rate", 90, "e", "money"),
                Column("amount", "Amount", 110, "e", "money"),
            ],
        )
        self.crops.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def _build_details(self, parent) -> None:
        self.details_box = ctk.CTkFrame(parent, fg_color="transparent")
        self.details_box.pack(fill="both", expand=True, padx=18, pady=10)
        self.detail_rows: dict[str, ctk.CTkLabel] = {}
        for i, label in enumerate(("Name", "Details", "Hindi name", "Category", "First entry", "Entries", "Phone")):
            ctk.CTkLabel(
                self.details_box, text=label, font=theme.font(13), text_color=theme.color("muted"), anchor="w"
            ).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 24))
            value = ctk.CTkLabel(self.details_box, text="", font=theme.font(13, "bold"), anchor="w")
            value.grid(row=i, column=1, sticky="w", pady=4)
            self.detail_rows[label] = value
        if self.ctx.can(Permission.EDIT_RECORDS):
            _button(self.details_box, "Edit customer", self.edit_customer, height=32).grid(
                row=8, column=0, sticky="w", pady=(12, 0)
            )

    def show_tab(self, name: str) -> None:
        for frame in self.frames.values():
            frame.pack_forget()
        self.frames[name].pack(fill="both", expand=True)
        if name == "Entries":
            self.entry_tools.pack(side="left", fill="x", expand=True)
        else:
            self.entry_tools.pack_forget()

    def restyle(self) -> None:
        for t in (self.ledger, self.promises, getattr(self, "crops", None)):
            if t is not None:
                t.restyle()

    # Loading ---------------------------------------------------------------------------
    def load(self, customer_id: int) -> bool:
        c = self.ctx.accounts.get_customer(customer_id)
        if c is None:
            self.ctx.toast("Customer not found", "error")
            return False
        if self.customer is None or self.customer.id != c.id:
            self.period.set(PERIODS[0])
            if self.find.get():
                self.find.delete(0, "end")
        self.customer = c
        self._rows = self.ctx.accounts.ledger(c.id)
        bal = self.ctx.accounts.get_balance(c.id)
        self._balance = bal
        entered, interest = period_split(self._rows, bal)

        self.avatar.configure(text="".join(p[0] for p in c.name.split()[:2]).upper() or "?")
        self.name_label.configure(text=i18n.tr_cell(c.name))
        details = i18n.tr_cell(c.other_details) if c.other_details and c.other_details != "NA" else ""
        self.detail_label.configure(text=" · ".join(x for x in (details, f"#{c.id}") if x))
        set_pill(self.cat_pill, f"Category {c.category}" + (" 🔒" if c.category_locked else ""), "info")
        words, color, _soft = balance_state(bal)
        self.words.configure(text=i18n.tr(words), text_color=theme.color(color))
        self.amount.configure(text=rupees(bal), text_color=theme.color(color if color != "muted" else "text"))
        self.split.configure(
            text=f"{rupees(entered)} entered + {rupees(interest)} interest" if abs(interest) >= 0.01 else ""
        )
        dates = self.ctx.krar.unsettled_dates(c.id)
        if dates:
            days = (dt.date.fromisoformat(max(dates)) - dt.date.today()).days
            when = f"{-days} days late" if days < 0 else ("today" if days == 0 else f"in {days} days")
            set_pill(self.promise_pill, f"Promise {when}", "late" if days < 0 else "due")
            self.promise_pill.pack(side="left", padx=6)
        else:
            self.promise_pill.pack_forget()
        self._apply_period()
        self._load_promises(dates)
        self._load_crops()
        self._load_details()
        self.ctx.status(f"{c.name} · balance {rupees(bal)}")
        return True

    def _apply_period(self) -> None:
        rows = self._rows
        choice = self.period.get()
        if choice == "Current period":
            last = max((i for i, r in enumerate(rows) if r.tag == "0"), default=-1)
            rows = rows[last + 1 :] if last >= 0 else rows
        elif choice == "This FY":
            start = financial_year_start()
            rows = [r for r in rows if r.date >= start]
        elif choice == "Last 90 days":
            start = (dt.date.today() - dt.timedelta(days=90)).isoformat()
            rows = [r for r in rows if r.date >= start]
        index = {r.id: i for i, r in enumerate(self._rows)}
        gave = sum(r.debit or 0 for r in rows if r.tag != "0")
        got = sum(r.credit or 0 for r in rows if r.tag != "0")
        shown = f"{len(rows)} of {len(self._rows)} entries" if len(rows) != len(self._rows) else f"{len(rows)} entries"
        self.ledger.set_rows(
            [
                (r.date, r.particulars, r.debit, r.credit, r.interest, r.balance, r.id, r.tag, r.type, index[r.id])
                for r in rows
            ],
            f"{shown} · gave {rupees(gave)} · got {rupees(got)}",
        )
        if self.find.get():
            self.ledger.filter(self.find.get())

    def _load_promises(self, open_dates: list[str]) -> None:
        today = dt.date.today().isoformat()
        rows = []
        for n, d in enumerate(sorted(open_dates, reverse=True), start=1):
            if n == 1:
                status = "Open · late" if d < today else ("Open · today" if d == today else "Open")
                note = f"{_ordinal(len(open_dates))} date given" if len(open_dates) > 1 else ""
            else:
                status, note = "Moved", "replaced by a later date"
            rows.append((d, status, note))
        for _krar_id, count, first, last in self.ctx.krar.settled_history(self.customer.id):
            rows.append((last, "Closed", f"{count} date(s) given, first {first}"))
        rows.sort(key=lambda r: r[0], reverse=True)
        self.promises.set_rows(rows, f"{len(rows)} promise date(s)")

    def _load_crops(self) -> None:
        if "Crop trades" not in self.frames:
            return
        crop = crop_handler(self.ctx.db)
        rows = []
        if crop is not None:
            for lot in crop.lots(farmer_id=self.customer.id, limit=500):
                rows.append(
                    (
                        lot.date,
                        f"Bought · lot #{lot.id}",
                        lot.crop_name,
                        f"{lot.qty:g} {lot.unit}",
                        lot.rate,
                        lot.amount,
                    )
                )
            for sale in crop.sales(buyer_id=self.customer.id, limit=500):
                rows.append(
                    (
                        sale.date,
                        f"Sold · #{sale.id}",
                        sale.crop_name,
                        f"{sale.qty:g} {sale.unit}",
                        sale.rate,
                        sale.amount,
                    )
                )
        rows.sort(key=lambda r: r[0], reverse=True)
        self.crops.set_rows(rows, f"{len(rows)} crop trade(s)")

    def _load_details(self) -> None:
        from hth.services.reminders import extract_phone

        c = self.customer
        first = next((r.date for r in self._rows), "")
        values = {
            "Name": c.name,
            "Details": c.other_details,
            "Hindi name": (c.name_hi or "-") + ("  ✓" if c.hi_manual else ""),
            "Category": c.category + ("  (locked)" if c.category_locked else ""),
            "First entry": first or "-",
            "Entries": str(len(self._rows)),
            "Phone": extract_phone(c.other_details) or "-",
        }
        for key, value in values.items():
            self.detail_rows[key].configure(text=value)

    # Actions ---------------------------------------------------------------------------
    def _counter(self, intent: str) -> None:
        if self.customer is not None:
            self.ctx.navigate("counter", customer_id=self.customer.id, intent=intent)

    def _other_menu(self) -> None:
        menu = _menu(self)
        menu.add_command(label=i18n.tr("Purchase"), command=lambda: self._counter("purchase"))
        menu.add_command(label=i18n.tr("Payment out"), command=lambda: self._counter("out"))
        _popup(menu, self.other_button)

    def _more_menu(self) -> None:
        can, tr = self.ctx.can, i18n.tr
        menu = _menu(self)
        if can(Permission.EDIT_RECORDS):
            menu.add_command(label=tr("Edit customer"), command=self.edit_customer)
            menu.add_command(label=tr("Category"), command=self.set_category)
            menu.add_command(label=tr("Add ledger entry"), command=self.add_entry)
        if can(Permission.DELETE_RECORDS):
            menu.add_separator()
            menu.add_command(label=tr("Delete customer…"), command=self.delete_customer)
        _popup(menu, self.more_button)

    def _row_actions(self, row):
        out = []
        if self.ctx.can(Permission.EDIT_RECORDS):
            out.append(("Correct…", lambda r=row: self.correct(r)))
        if self.ctx.can(Permission.DELETE_RECORDS):
            out.append(("Delete…", lambda r=row: self.delete(r)))
        if not out:
            out.append(("Only an admin can change an entry", lambda: None))
        return out

    def _reload(self) -> None:
        if self.customer is not None:
            self.load(self.customer.id)
            self.view.customers.reload()

    def correct(self, row) -> None:
        if actions.correct_entry(self, self.ctx, row[6]):
            self._reload()

    def delete(self, row) -> None:
        i = row[9]
        r = self._rows[i]
        last_settle = max((k for k, x in enumerate(self._rows) if x.tag == "0"), default=-1)
        if r.tag == "0":
            note = "This is part of a settlement: the balance is worked out again from the settlement before it."
        elif i < last_settle:
            note = "This entry is in an earlier, settled period - today's balance does not change."
        else:
            prev = 0.0 if i == last_settle + 1 else self._rows[i - 1].balance
            after = self._balance - (r.balance - prev)
            note = (
                f"Balance: {rupees(self._balance)} {balance_state(self._balance)[0].lower()} → "
                f"{rupees(after)} {balance_state(after)[0].lower()}"
            )
        if actions.delete_entry(self, self.ctx, r.id, note):
            self._reload()

    def promise(self) -> None:
        if self.customer is not None and actions.promise(self, self.ctx, self.customer.id):
            self.load(self.customer.id)

    def mark_kept(self) -> None:
        if self.customer is not None and actions.mark_kept(self, self.ctx, self.customer.id):
            self.load(self.customer.id)

    def edit_customer(self) -> None:
        if self.customer is not None and actions.edit_customer(self, self.ctx, self.customer.id):
            self._reload()

    def set_category(self) -> None:
        if self.customer is not None and actions.set_category(self, self.ctx, self.customer.id):
            self._reload()

    def add_entry(self) -> None:
        if self.customer is not None and actions.add_entry(self, self.ctx, self.customer.id):
            self._reload()

    def delete_customer(self) -> None:
        if self.customer is not None and actions.delete_customer(self, self.ctx, self.customer.id):
            self.customer = None
            self.pack_forget()
            self.view.customers.empty.pack(expand=True)
            self.view.customers.reload()

    def export(self) -> None:
        if self.customer is None:
            return
        c = self.customer
        path = self.ctx.settings.export_dir / f"ledger_{safe_filename(c.name)}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        export_rows(
            path, self.ledger.export_columns(), self.ledger.export_rows(), f"Ledger - {c.name} ({c.other_details})"
        )
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)


# --------------------------------------------------------------------------------------
BUCKETS = ["Late", "Today", "Next 7 days", "Later", "Owe us, no promise"]


class CollectionsPage(ctk.CTkFrame):
    """The classic Karar screen, rebuilt: who promised, who is late, who owes and never
    promised - with the reminder, WhatsApp and what happened next on the right."""

    def __init__(self, master, view: KhataView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx = view, view.ctx
        self.selected: tuple | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=330)
        self.grid_rowconfigure(0, weight=1)

        main = card(self)
        main.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(12, 6))
        self.bucket = segmented(bar, BUCKETS, command=lambda _v: self.reload(), height=32)
        self.bucket.set("Late")
        self.bucket.pack(side="left")
        self.find = ctk.CTkEntry(bar, placeholder_text="Find…", width=150, height=32)
        self.find.pack(side="right")
        self.find.bind("<KeyRelease>", lambda e: self.table.filter(self.find.get()))
        self.counts = ctk.CTkLabel(main, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w")
        self.counts.pack(fill="x", padx=14)
        self.table = DataTable(
            main,
            [
                Column("name", "Customer", 190, stretch=True),
                Column("phone", "Phone", 105),
                Column("balance", "Balance", 110, "e", "money"),
                Column("promised", "Promised", 95),
                Column("status", "Status", 110),
                Column("times", "Promise", 70, "center"),
                Column("paid", "Last payment", 100),
            ],
            on_select=self._on_select,
            on_double_click=lambda r: self.ctx.navigate("customers", customer_id=r[7]),
            row_tags=lambda r: ["neg"] if "late" in r[4] else (["warn"] if r[4] == "Due today" else []),
        )
        self.table.pack(fill="both", expand=True, padx=8, pady=(6, 4))
        foot = ctk.CTkFrame(main, fg_color="transparent")
        foot.pack(fill="x", padx=12, pady=(0, 12))
        self.total_label = ctk.CTkLabel(foot, text="", font=theme.font(12, "bold"))
        self.total_label.pack(side="left")
        _button(foot, "Excel", self.export, height=32).pack(side="right")
        _button(foot, "Copy all reminders", self.copy_all, height=32).pack(side="right", padx=6)

        side = card(self)
        side.grid(row=0, column=1, sticky="nsew")
        self.side = ctk.CTkFrame(side, fg_color="transparent")
        self.side.pack(fill="both", expand=True, padx=14, pady=14)
        self.s_name = ctk.CTkLabel(self.side, text="", font=theme.font(16, "bold"), anchor="w")
        self.s_name.pack(fill="x")
        self.s_balance = ctk.CTkLabel(self.side, text="", font=theme.font(13, "bold"), anchor="w")
        self.s_balance.pack(fill="x")
        _button(
            self.side,
            "Open khata",
            lambda: self._with(lambda cid: self.ctx.navigate("customers", customer_id=cid)),
            height=28,
        ).pack(anchor="w", pady=(6, 10))
        caption(self.side, "Reminder").pack(fill="x")
        self.reminder = ctk.CTkTextbox(self.side, height=110, font=theme.font(12), wrap="word")
        self.reminder.pack(fill="x", pady=(4, 6))
        row = ctk.CTkFrame(self.side, fg_color="transparent")
        row.pack(fill="x")
        _button(row, "WhatsApp", self.whatsapp, primary=True).pack(side="left", fill="x", expand=True)
        _button(row, "Copy", self.copy_one).pack(side="left", padx=(6, 0))
        caption(self.side, "What happened?").pack(fill="x", pady=(14, 4))
        acts = ctk.CTkFrame(self.side, fg_color="transparent")
        acts.pack(fill="x")
        acts.grid_columnconfigure((0, 1, 2), weight=1, uniform="a")
        _button(
            acts,
            "Got payment",
            lambda: self._with(lambda cid: self.ctx.navigate("counter", customer_id=cid, intent="in")),
            height=32,
        ).grid(row=0, column=0, sticky="ew")
        _button(acts, "New date", self.new_date, height=32).grid(row=0, column=1, sticky="ew", padx=4)
        _button(acts, "Kept", self.kept, height=32).grid(row=0, column=2, sticky="ew")
        caption(self.side, "Promise history").pack(fill="x", pady=(14, 4))
        self.history = ctk.CTkLabel(self.side, text="", font=theme.font(12), anchor="w", justify="left")
        self.history.pack(fill="x")
        self._show_side(None)

    # Data ------------------------------------------------------------------------------
    def on_show(self, **kwargs) -> None:
        if not getattr(self, "_shown", False):
            self._shown = True  # open where the work is: late promises, else today's
            late = [e for e in self.ctx.krar.entries("past")]
            self.bucket.set("Late" if late else "Today")
        self.reload()

    def reload(self) -> None:
        today = dt.date.today()
        today_s = today.isoformat()
        week = (today + dt.timedelta(days=7)).isoformat()
        owing = {r.id: r for r in self.ctx.reports.collections(categories=None)}
        entries = self.ctx.krar.entries("all")
        balances = self.ctx.accounts.balances(customer_ids=[e.customer_id for e in entries])
        buckets: dict[str, list[tuple]] = {b: [] for b in BUCKETS}
        promised_ids = set()
        for e in entries:
            promised_ids.add(e.customer_id)
            last = e.last_date
            days = (dt.date.fromisoformat(last) - today).days if last else 0
            if last < today_s:
                bucket, status = "Late", f"{-days} days late"
            elif last == today_s:
                bucket, status = "Today", "Due today"
            elif last <= week:
                bucket, status = "Next 7 days", f"in {days} days"
            else:
                bucket, status = "Later", f"in {days} days"
            o = owing.get(e.customer_id)
            buckets[bucket].append(
                (
                    self._label(e.customer_name, e.other_details),
                    o.phone if o else "",
                    balances.get(e.customer_id, 0.0),
                    last,
                    status,
                    _ordinal(len(e.dates)),
                    o.last_payment if o else "",
                    e.customer_id,
                    days,
                )
            )
        for o in owing.values():
            if o.id not in promised_ids:
                buckets["Owe us, no promise"].append(
                    (self._label(o.name, o.details), o.phone, o.balance, "", "No promise", "", o.last_payment, o.id, 0)
                )
        buckets["Late"].sort(key=lambda r: r[8])
        buckets["Owe us, no promise"].sort(key=lambda r: -r[2])
        rows = buckets[self.bucket.get()]
        self.counts.configure(
            text="   ·   ".join(f"{b} {len(buckets[b])}" for b in BUCKETS if b != "Owe us, no promise")
            + f"   ·   no promise {len(buckets['Owe us, no promise'])}"
        )
        self.table.set_rows(rows, "")
        owed = sum(r[2] for r in rows if r[2] > 0)
        self.total_label.configure(text=f"{len(rows)} shown · {rupees(owed)} owed")
        if self.find.get():
            self.table.filter(self.find.get())
        keep = self.selected[7] if self.selected else None
        match = next((r for r in self.table.rows if r[7] == keep), None)
        self._show_side(match)

    @staticmethod
    def _label(name: str, details: str) -> str:
        details = details if details and details != "NA" else ""
        return f"{name}  ·  {details}" if details else name

    def _on_select(self, row) -> None:
        self._show_side(row)

    def _reminder_for(self, row):
        if row[2] <= 0:  # nothing owed: a plain balance message, not "please pay"
            return self.ctx.reminders.balance_message(row[7])
        return self.ctx.reminders.build(row[7], row[3] or None)

    def _show_side(self, row) -> None:
        self.selected = row
        if row is None:
            self.s_name.configure(text="Pick a row to see the reminder")
            self.s_balance.configure(text="")
            self.reminder.delete("1.0", "end")
            self.history.configure(text="")
            return
        cid = row[7]
        c = self.ctx.accounts.get_customer(cid)
        self.s_name.configure(text=i18n.tr_cell(c.name) if c else row[0])
        words, color, _soft = balance_state(row[2])
        self.s_balance.configure(text=f"{rupees(row[2])} · {i18n.tr(words.lower())}", text_color=theme.color(color))
        self.reminder.delete("1.0", "end")
        self.reminder.insert("1.0", self._reminder_for(row).text)
        lines = [f"{d}  ·  open" for d in self.ctx.krar.unsettled_dates(cid)[::-1]]
        lines += [f"{last}  ·  closed ({count} date(s))" for _k, count, _f, last in self.ctx.krar.settled_history(cid)]
        self.history.configure(text="\n".join(lines[:6]) or "no promises yet")

    # Actions ---------------------------------------------------------------------------
    def _with(self, fn) -> None:
        if self.selected is None:
            self.ctx.toast("Pick a row first", "warning")
            return
        fn(self.selected[7])

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def copy_one(self) -> None:
        if self.selected is not None:
            self._copy(self.reminder.get("1.0", "end").strip())
            self.ctx.toast("Reminder copied - paste it in WhatsApp / SMS", "success")

    def whatsapp(self) -> None:
        if self.selected is None:
            return
        r = self._reminder_for(self.selected)
        text = self.reminder.get("1.0", "end").strip() or r.text
        if not r.whatsapp_url:
            self._copy(text)
            self.ctx.toast("No phone number in the account details - text copied instead", "warning")
            return
        import urllib.parse
        import webbrowser

        webbrowser.open(f"https://wa.me/91{r.phone}?text={urllib.parse.quote(text)}")  # the text as edited here
        self.ctx.audit.log("07", f"whatsapp reminder to customer {r.customer_id}", self.ctx.username)

    def copy_all(self) -> None:
        rows = [r for r in self.table.rows if r[2] > 0]
        if not rows:
            self.ctx.toast("Nothing to copy", "warning")
            return
        self._copy("\n\n".join(self._reminder_for(r).text for r in rows))
        self.ctx.toast(f"{len(rows)} reminders copied", "success")

    def new_date(self) -> None:
        self._with(lambda cid: actions.promise(self, self.ctx, cid) and self.reload())

    def kept(self) -> None:
        self._with(lambda cid: actions.mark_kept(self, self.ctx, cid) and self.reload())

    def export(self) -> None:
        path = self.ctx.settings.export_dir / f"collections_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        export_rows(path, self.table.export_columns(), self.table.export_rows(), f"Collections - {self.bucket.get()}")
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)
