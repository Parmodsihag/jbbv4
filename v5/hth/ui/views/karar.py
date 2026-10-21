"""Krar: record promised payment dates and settle them."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import confirm
from hth.ui.widgets.forms import (
    Card,
    DateField,
    LabeledWidget,
    danger_button,
    primary_button,
    secondary_button,
)
from hth.ui.widgets.searchbox import SearchBox


class KararView(BaseView):
    key = "karar"
    title = "Karar"
    permission = Permission.MANAGE_KRAR

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=2, uniform="k")
        self.grid_columnconfigure(1, weight=5, uniform="k")
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)

        add = Card(left, "Add / reschedule krar")
        add.pack(fill="x", pady=(0, 8))
        inner = ctk.CTkFrame(add, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=(4, 16))
        acc = LabeledWidget(inner, "Account")
        acc.pack(fill="x", pady=4)
        self.account = SearchBox(
            acc.body,
            lambda: [(c.id, c.display) for c in self.ctx.accounts.list_customers()],
            "Search account",
        )
        self.account.pack(fill="x")
        self.date = DateField(inner, "Promised date")
        self.date.pack(fill="x", pady=4)
        primary_button(inner, "Add krar", self.add_krar).pack(fill="x", pady=(10, 0))

        settle = Card(left, "Settle krar")
        settle.pack(fill="x")
        inner2 = ctk.CTkFrame(settle, fg_color="transparent")
        inner2.pack(fill="x", padx=18, pady=(4, 16))
        acc2 = LabeledWidget(inner2, "Account with open krar")
        acc2.pack(fill="x", pady=4)
        self.settle_account = SearchBox(acc2.body, self._open_accounts, "Search open krar")
        self.settle_account.pack(fill="x")
        primary_button(
            inner2,
            "Mark settled",
            self.settle_krar,
            fg_color=theme.color("success"),
            hover_color=theme.color("success_hover"),
            text_color=theme.color("on_status"),
        ).pack(fill="x", pady=(10, 0))

        right = Card(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        self.bucket = ctk.CTkSegmentedButton(
            bar,
            values=["Overdue", "Today", "Upcoming", "All"],
            command=lambda _v: self.reload(),
            font=theme.font(13),
        )
        self.bucket.set("Today")
        self.bucket.pack(side="left")
        self._first_show = True
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right")
        self.find = ctk.CTkEntry(bar, placeholder_text="Find…", width=180, height=32, font=theme.font(12))
        self.find.pack(side="right", padx=8)
        self.find.bind("<KeyRelease>", lambda e: self.table.filter(self.find.get()))
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 4))
        secondary_button(actions, "Copy reminder", self.copy_reminder, width=130).pack(side="left")
        secondary_button(actions, "WhatsApp", self.whatsapp, width=100).pack(side="left", padx=6)
        secondary_button(actions, "Copy all shown", self.copy_all, width=130).pack(side="left")
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(actions, "Delete krar", self.delete_krar, width=110).pack(side="right")
        self.table = DataTable(
            right,
            [
                Column("krar", "Krar", 60, "e", "int"),
                Column("name", "Customer", 220, stretch=True),
                Column("details", "Details", 160),
                Column("last", "Promised", 100),
                Column("days", "Days", 70, "e", "int"),
                Column("balance", "Balance", 110, "e", "money"),
                Column("dates", "History", 200),
            ],
            row_tags=lambda r: ["neg"] if r[4] < 0 else (["warn"] if r[4] == 0 else []),
            on_double_click=lambda r: self.ctx.navigate("customers", customer_id=r[7]),
        )
        ctk.CTkLabel(
            right,
            text="Days: negative = overdue.  Double-click to open the ledger.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="bottom", padx=12, pady=(0, 10), anchor="w")
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 4))

    def _open_accounts(self):
        ids = self.ctx.krar.unsettled_customer_ids()
        return [(c.id, c.display) for c in self.ctx.accounts.list_customers() if c.id in set(ids)]

    def on_show(self, bucket: str | None = None, **kwargs) -> None:
        if bucket in ("Overdue", "Today", "Upcoming", "All"):
            self.bucket.set(bucket)
        elif self._first_show:
            # open where the work is: overdue promises first, else today's
            if self.ctx.krar.entries("past"):
                self.bucket.set("Overdue")
        self._first_show = False
        self.account.refresh()
        self.settle_account.refresh()
        self.reload()

    def on_theme_change(self) -> None:
        self.table.restyle()

    def reload(self) -> None:
        bucket = {"Overdue": "past", "Today": "today", "Upcoming": "future", "All": "all"}[self.bucket.get()]
        today = dt.date.today()
        entries = self.ctx.krar.entries(bucket)
        balances = self.ctx.accounts.balances(customer_ids=[e.customer_id for e in entries])
        rows = []
        for e in entries:
            days = (dt.date.fromisoformat(e.last_date) - today).days if e.last_date else 0
            rows.append(
                (
                    e.krar_id,
                    e.customer_name,
                    e.other_details,
                    e.last_date,
                    days,
                    balances.get(e.customer_id, 0.0),
                    ", ".join(e.dates),
                    e.customer_id,
                )
            )
        total = sum(r[5] for r in rows if r[5] > 0)
        self.table.set_rows(rows, f"{len(rows)} krar · receivable {money(total)}")
        if self.find.get():
            self.table.filter(self.find.get())

    def add_krar(self) -> None:
        customer_id = self.account.get_key()
        if customer_id is None:
            self.ctx.toast("Pick an account from the list", "error")
            return
        try:
            krar_id = self.ctx.krar.add_or_update(customer_id, self.date.get(), self.ctx.username)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(f"Krar #{krar_id} saved", "success")
        self.account.clear()
        self.settle_account.refresh()
        self.reload()

    def settle_krar(self) -> None:
        customer_id = self.settle_account.get_key()
        if customer_id is None:
            self.ctx.toast("Pick an account with an open krar", "error")
            return
        self.ctx.krar.settle(customer_id, self.ctx.username)
        self.ctx.toast("Krar settled", "success")
        self.settle_account.clear()
        self.settle_account.refresh()
        self.reload()

    def _selected_reminder(self):
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select a krar first", "warning")
            return None
        if row[5] <= 0:  # nothing owed: a plain balance message, not "please pay"
            return self.ctx.reminders.balance_message(row[7])
        return self.ctx.reminders.build(row[7], row[3])

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def copy_reminder(self) -> None:
        r = self._selected_reminder()
        if r:
            self._copy(r.text)
            self.ctx.toast(f"Reminder for {r.customer_name.title()} copied - paste it in WhatsApp / SMS", "success")

    def whatsapp(self) -> None:
        r = self._selected_reminder()
        if r is None:
            return
        if not r.whatsapp_url:
            self._copy(r.text)
            self.ctx.toast("No phone number in the account details - text copied instead", "warning")
            return
        import webbrowser

        webbrowser.open(r.whatsapp_url)
        self.ctx.audit.log("07", f"whatsapp reminder to customer {r.customer_id}", self.ctx.username)

    def copy_all(self) -> None:
        rows = self.table.rows
        if not rows:
            self.ctx.toast("Nothing to copy", "warning")
            return
        owing = [r for r in rows if r[5] > 0]
        skipped = len(rows) - len(owing)
        texts = [self.ctx.reminders.build(r[7], r[3]).text for r in owing]
        self._copy("\n\n".join(texts))
        note = f" ({skipped} with nothing owed left out)" if skipped else ""
        self.ctx.toast(f"{len(texts)} reminders copied{note}", "success")

    def delete_krar(self) -> None:
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select a krar first", "warning")
            return
        if confirm(self, "Delete krar", f"Delete krar #{row[0]} for {row[1]}?"):
            self.ctx.krar.delete_krar(row[0], self.ctx.username)
            self.reload()
