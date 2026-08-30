"""Crop trading screen: Purchase, Sale, Stock & rates, Reports."""

from __future__ import annotations

import datetime as dt
from tkinter import filedialog

import customtkinter as ctk

from hth.domain.constants import TAG_CHOICES, Tag
from hth.domain.units import compatible_units, normalize
from hth.modules.crop_trading.rates import PROVIDERS, CsvRateProvider
from hth.modules.crop_trading.service import CASH_BUYER, QUALITY_GRADES, CropService
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import days_ago_str, money, open_path, today_str
from hth.ui.format import qty as fmt_qty
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, confirm, info, run_form
from hth.ui.widgets.forms import (
    Card,
    DateField,
    LabeledEntry,
    LabeledOption,
    LabeledWidget,
    danger_button,
    primary_button,
    secondary_button,
)
from hth.ui.widgets.searchbox import SearchBox


def _tabview(master) -> ctk.CTkTabview:
    tabs = ctk.CTkTabview(master, fg_color=theme.color("surface"), corner_radius=10)
    try:
        tabs._segmented_button.configure(font=theme.font(13, "bold"))  # noqa: SLF001
    except Exception:  # noqa: BLE001
        pass
    return tabs


class CropTradingView(BaseView):
    key = "crops"
    title = "Crop Trade"
    permission = Permission.CROP_TRADING

    def build(self) -> None:
        self.svc = CropService(self.ctx.db)
        self.tabs = _tabview(self)
        self.tabs.pack(fill="both", expand=True, padx=4, pady=4)
        for name in ("Purchase", "Sale", "Stock & rates", "Reports"):
            self.tabs.add(name)
        self.purchase = PurchasePanel(self.tabs.tab("Purchase"), self)
        self.purchase.pack(fill="both", expand=True)
        self.sale = SalePanel(self.tabs.tab("Sale"), self)
        self.sale.pack(fill="both", expand=True)
        self.stock = StockPanel(self.tabs.tab("Stock & rates"), self)
        self.stock.pack(fill="both", expand=True)
        self.reports = CropReportsPanel(self.tabs.tab("Reports"), self)
        self.reports.pack(fill="both", expand=True)

    def on_show(self, **kwargs) -> None:
        for p in (self.purchase, self.sale, self.stock, self.reports):
            p.reload()

    def on_theme_change(self) -> None:
        for p in (self.purchase, self.sale, self.stock, self.reports):
            for t in p.tables():
                t.restyle()

    # shared helpers ------------------------------------------------------------------------
    def crop_choices(self):
        return [(c.id, c.display) for c in self.svc.crops()]

    def party_choices(self):
        return [(c.id, c.display) for c in self.svc.parties()]

    def quick_add_crop(self, box: SearchBox) -> None:
        fields = [
            Field("name", "Crop name"),
            Field("unit", "Stock unit", "option", "KG", ["KG", "QTL", "LTR", "PCS", "BAG"]),
        ]
        created = {}

        def submit(v):
            created["item"] = self.svc.add_crop(v["name"], v["unit"], self.ctx.username)

        if run_form(self, "New crop", fields, submit, "Create") and created:
            box.refresh()
            box.set(created["item"].id)
            self.ctx.toast(f"Crop {created['item'].name} added", "success")

    def quick_add_party(self, box: SearchBox, label: str) -> None:
        created = {}

        def submit(v):
            created["c"] = self.svc.add_party(v["name"], v["details"], self.ctx.username)

        if (
            run_form(
                self, f"New {label}", [Field("name", "Name"), Field("details", "Village / details")], submit, "Create"
            )
            and created
        ):
            box.refresh()
            box.set(created["c"].id)
            self.ctx.toast(f"{label.title()} {created['c'].name} added (account #{created['c'].id})", "success")


# ------------------------------------------------------------------------------------------
class PurchasePanel(ctk.CTkFrame):
    def __init__(self, master, view: CropTradingView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        self._crop = None
        self.grid_columnconfigure(0, weight=2, uniform="p")
        self.grid_columnconfigure(1, weight=3, uniform="p")
        self.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(
            form, text="BUY FROM FARMER", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x")
        self.date = DateField(form)
        self.date.pack(fill="x", pady=3)
        fw = LabeledWidget(form, "Farmer (account)")
        fw.pack(fill="x", pady=3)
        self.farmer = SearchBox(fw.body, self.view.party_choices, "Search farmer / account")
        self.farmer.pack(side="left", fill="x", expand=True)
        secondary_button(fw.body, "+", lambda: self.view.quick_add_party(self.farmer, "farmer"), width=36).pack(
            side="left", padx=(6, 0)
        )
        cw = LabeledWidget(form, "Crop")
        cw.pack(fill="x", pady=3)
        self.crop = SearchBox(cw.body, self.view.crop_choices, "Search crop", on_select=self._on_crop)
        self.crop.pack(side="left", fill="x", expand=True)
        secondary_button(cw.body, "+", lambda: self.view.quick_add_crop(self.crop), width=36).pack(
            side="left", padx=(6, 0)
        )
        self.crop.var.trace_add("write", lambda *_: self._on_crop_text())
        g = ctk.CTkFrame(form, fg_color="transparent")
        g.pack(fill="x")
        g.grid_columnconfigure((0, 1, 2), weight=1)
        self.gross = LabeledEntry(g, "Gross qty", placeholder="0")
        self.gross.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.unit = LabeledOption(g, "Unit", ["KG", "QTL", "G"], "KG", command=lambda _v: self._calc())
        self.unit.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.deduction = LabeledEntry(g, "Deduction (kaat)", default="0")
        self.deduction.grid(row=0, column=2, sticky="ew", pady=3)
        self.rate = LabeledEntry(g, "Rate per stock unit", placeholder="0.00")
        self.rate.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.quality = LabeledOption(g, "Quality", QUALITY_GRADES, "A")
        self.quality.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.tag = LabeledOption(g, "Ledger tag", TAG_CHOICES, Tag.NO_INTEREST.label)
        self.tag.grid(row=1, column=2, sticky="ew", pady=3)
        self.notes = LabeledEntry(form, "Notes (moisture, bags, vehicle…)")
        self.notes.pack(fill="x", pady=3)
        for w in (self.gross, self.deduction, self.rate):
            w.var.trace_add("write", lambda *_: self._calc())
        self.calc_label = ctk.CTkLabel(form, text="Net: 0   Amount: 0.00", font=theme.font(16, "bold"), anchor="w")
        self.calc_label.pack(fill="x", pady=(8, 0))
        primary_button(form, "Record purchase", self.submit).pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(
            form, text="PAY FARMER", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x", pady=(18, 0))
        pw = LabeledWidget(form, "Farmer")
        pw.pack(fill="x", pady=3)
        self.pay_farmer = SearchBox(
            pw.body, self.view.party_choices, "Search farmer", on_select=lambda k, _l: self._show_owed(k)
        )
        self.pay_farmer.pack(fill="x")
        self.owed_label = ctk.CTkLabel(form, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w")
        self.owed_label.pack(fill="x")
        g2 = ctk.CTkFrame(form, fg_color="transparent")
        g2.pack(fill="x")
        g2.grid_columnconfigure((0, 1), weight=1)
        self.pay_date = DateField(g2)
        self.pay_date.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.pay_amount = LabeledEntry(g2, "Amount", placeholder="0.00")
        self.pay_amount.grid(row=0, column=1, sticky="ew", pady=3)
        secondary_button(form, "Record payment", self.pay).pack(fill="x", pady=(6, 0))

        right = Card(self)
        right.grid(row=0, column=1, sticky="nsew")
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bar, text="Recent lots", font=theme.font(17, "bold")).pack(side="left")
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(bar, "Delete lot", self.delete_lot, width=100).pack(side="right")
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right", padx=6)
        self.table = DataTable(
            right,
            [
                Column("id", "Lot", 55, "e", "int"),
                Column("date", "Date", 95),
                Column("farmer", "Farmer", 170, stretch=True),
                Column("crop", "Crop", 130),
                Column("gross", "Gross", 80, "e", "qty"),
                Column("ded", "Kaat", 60, "e", "qty"),
                Column("net", "Net", 80, "e", "qty"),
                Column("left", "Left", 80, "e", "qty"),
                Column("rate", "Rate", 80, "e", "money"),
                Column("amount", "Amount", 100, "e", "money"),
                Column("q", "Q", 45, "center"),
            ],
            on_double_click=lambda r: self.ctx.navigate("customers", customer_id=r[11]),
            row_tags=lambda r: ["muted"] if r[7] <= 0 else [],
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def tables(self):
        return [self.table]

    def reload(self) -> None:
        self.farmer.refresh()
        self.crop.refresh()
        self.pay_farmer.refresh()
        lots = self.svc.lots(limit=300)
        rows = [
            (
                x.id,
                x.date,
                x.farmer_name,
                x.crop_name,
                x.gross_qty,
                x.deduction_qty,
                x.qty,
                x.remaining_qty,
                x.rate,
                x.amount,
                x.quality,
                x.farmer_id,
            )
            for x in lots
        ]
        self.table.set_rows(
            rows, f"{len(rows)} lots · {money(sum(r[9] for r in rows))} · double-click opens the farmer's ledger"
        )

    def _on_crop(self, item_id, _label=None) -> None:
        self._crop = self.ctx.inventory.get_item(item_id)
        if self._crop:
            units = compatible_units(self._crop.unit)
            self.unit.set_values(units)
            self.unit.set(units[0])
            self._calc()

    def _on_crop_text(self) -> None:
        key = self.crop.get_key()
        if key is not None and (self._crop is None or self._crop.id != key):
            self._on_crop(key)

    def _calc(self) -> None:
        try:
            gross = float(self.gross.get() or 0)
            ded = float(self.deduction.get() or 0)
            rate = float(self.rate.get() or 0)
        except ValueError:
            self.calc_label.configure(text="Net: -   Amount: -")
            return
        net = gross - ded
        unit = normalize(self.unit.get())
        text = f"Net: {fmt_qty(net)} {unit}"
        if self._crop and unit != normalize(self._crop.unit):
            from hth.domain.units import UnitError, convert

            try:
                net_stock = convert(net, unit, self._crop.unit)
                text += f" = {fmt_qty(net_stock)} {normalize(self._crop.unit)}"
                net = net_stock
            except UnitError:
                text += " (unit mismatch)"
        self.calc_label.configure(
            text=f"{text}   Amount: {money(net * rate)}",
            text_color=theme.color("danger") if ded > gross else theme.color("text"),
        )

    def _show_owed(self, farmer_id) -> None:
        bal = self.ctx.accounts.get_balance(farmer_id)
        self.owed_label.configure(
            text=f"We owe {money(-bal)}" if bal < 0 else f"Farmer owes us {money(bal)}" if bal > 0 else "Settled"
        )

    def submit(self) -> None:
        try:
            farmer_id, crop_id = self.farmer.get_key(), self.crop.get_key()
            if farmer_id is None:
                raise ValidationError("Pick a farmer from the list (or add one with +).")
            if crop_id is None:
                raise ValidationError("Pick a crop from the list (or add one with +).")
            lot = self.svc.record_purchase(
                self.date.get(),
                farmer_id,
                crop_id,
                self.gross.get() or 0,
                self.deduction.get() or 0,
                self.rate.get() or 0,
                self.unit.get(),
                self.ctx.username,
                self.quality.get(),
                self.notes.get(),
                self.tag.get()[0],
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(
            f"Lot #{lot.id}: {fmt_qty(lot.qty)} {lot.unit} {lot.crop_name} for {money(lot.amount)}", "success"
        )
        for w in (self.gross, self.rate, self.notes):
            w.set("")
        self.deduction.set("0")
        self.reload()
        self.view.sale.reload()
        self.view.stock.reload()

    def pay(self) -> None:
        try:
            fid = self.pay_farmer.get_key()
            if fid is None:
                raise ValidationError("Pick a farmer.")
            self.svc.pay_farmer(fid, self.pay_date.get(), self.pay_amount.get() or 0, self.ctx.username)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast("Payment recorded", "success")
        self.pay_amount.set("")
        self._show_owed(fid)

    def delete_lot(self) -> None:
        row = self.table.selected_row()
        if row and confirm(
            self,
            "Delete lot",
            f"Delete lot #{row[0]} ({row[2]}, {fmt_qty(row[6])} {row[3]})?\n"
            "The ledger and stock entries are removed too.",
        ):
            try:
                self.svc.delete_lot(row[0], self.ctx.username)
            except ValidationError as exc:
                self.ctx.toast(str(exc), "error")
                return
            self.reload()
            self.view.stock.reload()


# ------------------------------------------------------------------------------------------
class SalePanel(ctk.CTkFrame):
    def __init__(self, master, view: CropTradingView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        self._crop = None
        self.grid_columnconfigure(0, weight=2, uniform="s")
        self.grid_columnconfigure(1, weight=3, uniform="s")
        self.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(
            form, text="SELL TO BUYER", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x")
        self.date = DateField(form)
        self.date.pack(fill="x", pady=3)
        bw = LabeledWidget(form, "Buyer (account) - leave empty for a cash sale")
        bw.pack(fill="x", pady=3)
        self.buyer = SearchBox(bw.body, self.view.party_choices, "Search buyer / account", allow_free_text=True)
        self.buyer.pack(side="left", fill="x", expand=True)
        secondary_button(bw.body, "+", lambda: self.view.quick_add_party(self.buyer, "buyer"), width=36).pack(
            side="left", padx=(6, 0)
        )
        cw = LabeledWidget(form, "Crop")
        cw.pack(fill="x", pady=3)
        self.crop = SearchBox(cw.body, self.view.crop_choices, "Search crop", on_select=self._on_crop)
        self.crop.pack(fill="x")
        self.crop.var.trace_add("write", lambda *_: self._on_crop_text())
        self.stock_label = ctk.CTkLabel(form, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w")
        self.stock_label.pack(fill="x")
        g = ctk.CTkFrame(form, fg_color="transparent")
        g.pack(fill="x")
        g.grid_columnconfigure((0, 1, 2), weight=1)
        self.qty = LabeledEntry(g, "Quantity", placeholder="0")
        self.qty.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.unit = LabeledOption(g, "Unit", ["KG", "QTL", "G"], "KG", command=lambda _v: self._calc())
        self.unit.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.rate = LabeledEntry(g, "Rate per stock unit", placeholder="0.00")
        self.rate.grid(row=0, column=2, sticky="ew", pady=3)
        self.tag = LabeledOption(g, "Ledger tag", TAG_CHOICES, Tag.NO_INTEREST.label)
        self.tag.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.allow_short = ctk.CTkCheckBox(g, text="Allow selling short", font=theme.font(12))
        self.allow_short.grid(row=1, column=1, columnspan=2, sticky="w", pady=(14, 0))
        self.notes = LabeledEntry(form, "Notes")
        self.notes.pack(fill="x", pady=3)
        for w in (self.qty, self.rate):
            w.var.trace_add("write", lambda *_: self._calc())
        self.calc_label = ctk.CTkLabel(form, text="Amount: 0.00", font=theme.font(16, "bold"), anchor="w")
        self.calc_label.pack(fill="x", pady=(8, 0))
        self.margin_label = ctk.CTkLabel(
            form, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w", justify="left"
        )
        self.margin_label.pack(fill="x")
        primary_button(form, "Record sale", self.submit).pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(
            form, text="RECEIVE FROM BUYER", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x", pady=(18, 0))
        rw = LabeledWidget(form, "Buyer")
        rw.pack(fill="x", pady=3)
        self.recv_buyer = SearchBox(
            rw.body, self.view.party_choices, "Search buyer", on_select=lambda k, _l: self._show_due(k)
        )
        self.recv_buyer.pack(fill="x")
        self.due_label = ctk.CTkLabel(form, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w")
        self.due_label.pack(fill="x")
        g2 = ctk.CTkFrame(form, fg_color="transparent")
        g2.pack(fill="x")
        g2.grid_columnconfigure((0, 1), weight=1)
        self.recv_date = DateField(g2)
        self.recv_date.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.recv_amount = LabeledEntry(g2, "Amount", placeholder="0.00")
        self.recv_amount.grid(row=0, column=1, sticky="ew", pady=3)
        secondary_button(form, "Record receipt", self.receive).pack(fill="x", pady=(6, 0))

        right = Card(self)
        right.grid(row=0, column=1, sticky="nsew")
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bar, text="Recent sales", font=theme.font(17, "bold")).pack(side="left")
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(bar, "Delete sale", self.delete_sale, width=100).pack(side="right")
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right", padx=6)
        self.table = DataTable(
            right,
            [
                Column("id", "Sale", 55, "e", "int"),
                Column("date", "Date", 95),
                Column("buyer", "Buyer", 160, stretch=True),
                Column("crop", "Crop", 130),
                Column("qty", "Qty", 80, "e", "qty"),
                Column("rate", "Rate", 80, "e", "money"),
                Column("amount", "Amount", 100, "e", "money"),
                Column("cost", "Cost", 100, "e", "money"),
                Column("margin", "Margin", 100, "e", "money"),
                Column("pct", "%", 60, "e", "qty"),
                Column("short", "Short", 60, "e", "qty"),
            ],
            row_tags=lambda r: ["neg"] if r[8] < 0 else (["warn"] if r[10] > 0 else ["pos"]),
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def tables(self):
        return [self.table]

    def reload(self) -> None:
        self.buyer.refresh()
        self.crop.refresh()
        self.recv_buyer.refresh()
        sales = self.svc.sales(limit=300)
        rows = [
            (
                s.id,
                s.date,
                s.buyer_name,
                s.crop_name,
                s.qty,
                s.rate,
                s.amount,
                s.cost,
                s.margin,
                s.margin_pct,
                s.short_qty,
            )
            for s in sales
        ]
        self.table.set_rows(
            rows,
            f"{len(rows)} sales · revenue {money(sum(r[6] for r in rows))} · margin {money(sum(r[8] for r in rows))}",
        )
        if self._crop:
            self._on_crop(self._crop.id)

    def _on_crop(self, item_id, _label=None) -> None:
        self._crop = self.ctx.inventory.get_item(item_id)
        if self._crop is None:
            return
        units = compatible_units(self._crop.unit)
        self.unit.set_values(units)
        self.unit.set(units[0])
        stock = next((s for s in self.svc.stock() if s.item.id == self._crop.id), None)
        if stock:
            rate_txt = f" · market {money(stock.market_rate)} ({stock.market_date})" if stock.market_rate else ""
            self.stock_label.configure(
                text=f"In stock {fmt_qty(stock.qty)} {normalize(self._crop.unit)}"
                f" · avg cost {money(stock.avg_cost)}{rate_txt}"
            )
        self._calc()

    def _on_crop_text(self) -> None:
        key = self.crop.get_key()
        if key is not None and (self._crop is None or self._crop.id != key):
            self._on_crop(key)

    def _calc(self) -> None:
        try:
            q = float(self.qty.get() or 0)
            rate = float(self.rate.get() or 0)
        except ValueError:
            self.calc_label.configure(text="Amount: -")
            return
        if not self._crop:
            self.calc_label.configure(text=f"Amount: {money(q * rate)}")
            return
        from hth.domain.units import UnitError, convert

        try:
            q_stock = convert(q, self.unit.get(), self._crop.unit)
        except UnitError:
            self.calc_label.configure(text="Amount: - (unit mismatch)")
            return
        amount = q_stock * rate
        self.calc_label.configure(text=f"Amount: {money(amount)}")
        if q_stock > 0:
            pv = self.svc.preview_cost(self._crop.id, q_stock)
            margin = amount - pv.cost
            short = f"   ⚠ {fmt_qty(pv.short_qty)} short" if pv.short_qty > 0 else ""
            self.margin_label.configure(
                text=f"FIFO cost {money(pv.cost)} from {len(pv.allocations)} lot(s) → margin {money(margin)}{short}",
                text_color=theme.color("danger") if pv.short_qty > 0 or margin < 0 else theme.color("success"),
            )
        else:
            self.margin_label.configure(text="")

    def _show_due(self, buyer_id) -> None:
        bal = self.ctx.accounts.get_balance(buyer_id)
        self.due_label.configure(
            text=f"Buyer owes {money(bal)}" if bal > 0 else f"We owe {money(-bal)}" if bal < 0 else "Settled"
        )

    def submit(self) -> None:
        try:
            crop_id = self.crop.get_key()
            if crop_id is None:
                raise ValidationError("Pick a crop from the list.")
            sale = self.svc.record_sale(
                self.date.get(),
                crop_id,
                self.qty.get() or 0,
                self.rate.get() or 0,
                self.unit.get(),
                self.ctx.username,
                buyer_id=self.buyer.get_key(),
                buyer_name=self.buyer.get_text() or CASH_BUYER,
                tag=self.tag.get()[0],
                notes=self.notes.get(),
                allow_short=bool(self.allow_short.get()),
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(
            f"Sale #{sale.id}: {money(sale.amount)} · margin {money(sale.margin)} ({sale.margin_pct:g}%)", "success"
        )
        for w in (self.qty, self.rate, self.notes):
            w.set("")
        self.reload()
        self.view.purchase.reload()
        self.view.stock.reload()

    def receive(self) -> None:
        try:
            bid = self.recv_buyer.get_key()
            if bid is None:
                raise ValidationError("Pick a buyer.")
            self.svc.receive_from_buyer(bid, self.recv_date.get(), self.recv_amount.get() or 0, self.ctx.username)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast("Receipt recorded", "success")
        self.recv_amount.set("")
        self._show_due(bid)

    def delete_sale(self) -> None:
        row = self.table.selected_row()
        if row and confirm(
            self,
            "Delete sale",
            f"Delete sale #{row[0]} ({row[2]}, {fmt_qty(row[4])} {row[3]})?\n"
            "Stock returns to its lots; ledger entry removed.",
        ):
            self.svc.delete_sale(row[0], self.ctx.username)
            self.reload()
            self.view.purchase.reload()
            self.view.stock.reload()


# ------------------------------------------------------------------------------------------
class StockPanel(ctk.CTkFrame):
    def __init__(self, master, view: CropTradingView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        self._selected_item = None
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 4))
        ctk.CTkLabel(bar, text="Stock valuation", font=theme.font(17, "bold")).pack(side="left")
        secondary_button(bar, "Export", self.export, width=80).pack(side="right")
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right", padx=6)
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 50, "e", "int"),
                Column("crop", "Crop", 180, stretch=True),
                Column("qty", "In stock", 100, "e", "qty"),
                Column("unit", "Unit", 55),
                Column("lots", "Lots", 50, "e", "int"),
                Column("cost", "Cost value", 110, "e", "money"),
                Column("avg", "Avg cost", 90, "e", "money"),
                Column("mrate", "Market rate", 100, "e", "money"),
                Column("mdate", "As of", 95),
                Column("mvalue", "Market value", 110, "e", "money"),
                Column("gain", "Unrealized", 110, "e", "money"),
                Column("est", "Est. 7d", 90, "e", "money"),
                Column("inv", "Inv. qty", 90, "e", "qty"),
            ],
            on_select=self._on_select,
            row_tags=lambda r: ["neg"] if (r[10] or 0) < 0 else (["pos"] if (r[10] or 0) > 0 else []),
        )
        self.table.pack(fill="both", expand=True, pady=(0, 6))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x")
        bottom.grid_columnconfigure(0, weight=2)
        bottom.grid_columnconfigure(1, weight=3)
        form = Card(bottom, "Market rate")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        g = ctk.CTkFrame(form, fg_color="transparent")
        g.pack(fill="x", padx=14, pady=(0, 12))
        g.grid_columnconfigure((0, 1, 2), weight=1)
        cw = LabeledWidget(g, "Crop")
        cw.grid(row=0, column=0, columnspan=3, sticky="ew", pady=3)
        self.rate_crop = SearchBox(cw.body, self.view.crop_choices, "Search crop")
        self.rate_crop.pack(fill="x")
        self.rate_date = DateField(g)
        self.rate_date.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.rate_value = LabeledEntry(g, "Rate per unit", placeholder="0.00")
        self.rate_value.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=3)
        primary_button(g, "Save rate", self.save_rate, width=100).grid(row=1, column=2, sticky="ew", pady=(20, 3))
        btns = ctk.CTkFrame(g, fg_color="transparent")
        btns.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        secondary_button(btns, "Import CSV (crop,date,rate)", self.import_csv, width=200).pack(side="left")
        if PROVIDERS:
            secondary_button(btns, "Fetch today's rates", self.fetch_rates, width=150).pack(side="left", padx=6)
        else:
            ctk.CTkLabel(
                btns,
                text="No rate API configured yet (see rates.py)",
                font=theme.font(11),
                text_color=theme.color("muted"),
            ).pack(side="left", padx=8)

        hist = Card(bottom, "Rate history")
        hist.grid(row=0, column=1, sticky="nsew")
        self.history = DataTable(
            hist,
            [Column("date", "Date", 100), Column("rate", "Rate", 100, "e", "money"), Column("src", "Source", 90)],
            height=5,
        )
        self.history.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(hist, "Delete selected rate", self.delete_rate, width=160).pack(
                side="bottom", anchor="e", padx=12, pady=(0, 10)
            )

    def tables(self):
        return [self.table, self.history]

    def reload(self) -> None:
        self.rate_crop.refresh()
        rows = []
        for s in self.svc.stock():
            est = self.svc.rates.estimate_rate(s.item.id)
            rows.append(
                (
                    s.item.id,
                    s.item.name,
                    s.qty,
                    normalize(s.item.unit),
                    s.lots,
                    s.cost_value,
                    s.avg_cost,
                    s.market_rate,
                    s.market_date or "",
                    s.market_value,
                    s.unrealized,
                    est.rate if est else None,
                    s.inventory_qty,
                )
            )
        cost = sum(r[5] for r in rows)
        mv = sum(r[9] or 0 for r in rows)
        self.table.set_rows(
            rows,
            f"{len(rows)} crops · cost {money(cost)} · market {money(mv)} · unrealized {money(mv - cost)}   "
            "(Est. 7d = straight-line trend of recent quotes, rough only)",
        )
        if self._selected_item:
            self._load_history(self._selected_item)

    def _on_select(self, row) -> None:
        if row:
            self._selected_item = row[0]
            self.rate_crop.set(row[0])
            self._load_history(row[0])

    def _load_history(self, item_id) -> None:
        rows = self.svc.rates.history(item_id)
        self.history.set_rows(rows, f"{len(rows)} quotes")

    def save_rate(self) -> None:
        try:
            item_id = self.rate_crop.get_key()
            if item_id is None:
                raise ValidationError("Pick a crop.")
            self.svc.rates.set_rate(
                item_id, self.rate_date.get(), self.rate_value.get() or 0, "manual", self.ctx.username
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast("Rate saved", "success")
        self.rate_value.set("")
        self._selected_item = item_id
        self.reload()

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Rates CSV (crop,date,rate)", filetypes=[("CSV", "*.csv"), ("All", "*.*")], parent=self
        )
        if not path:
            return
        try:
            quotes = CsvRateProvider(path).fetch(self.svc.crops(), dt.date.today())
            n = self.svc.rates.apply_quotes(quotes, self.ctx.username)
        except (ValidationError, OSError) as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(f"{n} rates imported", "success")
        self.reload()

    def fetch_rates(self) -> None:
        crops = self.svc.crops()
        total = 0
        for name, provider in PROVIDERS.items():
            try:
                total += self.svc.rates.apply_quotes(provider.fetch(crops, dt.date.today()), self.ctx.username)
            except Exception as exc:  # noqa: BLE001
                self.ctx.toast(f"{name}: {exc}", "error")
        self.ctx.toast(f"{total} rates fetched", "success")
        self.reload()

    def delete_rate(self) -> None:
        row = self.history.selected_row()
        if (
            row
            and self._selected_item
            and confirm(self, "Delete rate", f"Delete the {row[0]} quote ({money(row[1])})?")
        ):
            self.svc.rates.delete_rate(self._selected_item, row[0], row[2], self.ctx.username)
            self.reload()

    def export(self) -> None:
        path = self.ctx.settings.export_dir / f"crop_stock_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        export_rows(path, self.table.export_columns(), self.table.export_rows(), "Crop stock valuation")
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)


# ------------------------------------------------------------------------------------------
REPORTS = {
    "Summary": ([Column("metric", "Metric", 260), Column("value", "Value", 160, "e")], "summary"),
    "Margin by crop": (
        [
            Column("id", "ID", 50, "e", "int"),
            Column("crop", "Crop", 180, stretch=True),
            Column("n", "Sales", 60, "e", "int"),
            Column("qty", "Qty", 90, "e", "qty"),
            Column("unit", "Unit", 55),
            Column("rev", "Revenue", 110, "e", "money"),
            Column("cost", "Cost", 110, "e", "money"),
            Column("margin", "Margin", 110, "e", "money"),
            Column("pct", "%", 60, "e", "qty"),
            Column("avg_sell", "Avg sell", 90, "e", "money"),
            Column("avg_cost", "Avg cost", 90, "e", "money"),
        ],
        "margin_by_crop",
    ),
    "Margin by buyer": (
        [
            Column("id", "ID", 50, "e"),
            Column("buyer", "Buyer", 200, stretch=True),
            Column("n", "Sales", 60, "e", "int"),
            Column("qty", "Qty", 90, "e", "qty"),
            Column("rev", "Revenue", 110, "e", "money"),
            Column("cost", "Cost", 110, "e", "money"),
            Column("margin", "Margin", 110, "e", "money"),
            Column("pct", "%", 60, "e", "qty"),
        ],
        "margin_by_buyer",
    ),
    "Purchases by farmer": (
        [
            Column("id", "ID", 50, "e", "int"),
            Column("farmer", "Farmer", 180, stretch=True),
            Column("details", "Details", 120),
            Column("n", "Lots", 60, "e", "int"),
            Column("gross", "Gross", 90, "e", "qty"),
            Column("ded", "Kaat", 70, "e", "qty"),
            Column("net", "Net", 90, "e", "qty"),
            Column("amount", "Amount", 110, "e", "money"),
            Column("avg", "Avg rate", 90, "e", "money"),
            Column("crops", "Crops", 160),
        ],
        "purchases_by_farmer",
    ),
    "Purchases by quality": (
        [
            Column("crop", "Crop", 180, stretch=True),
            Column("grade", "Grade", 70),
            Column("n", "Lots", 60, "e", "int"),
            Column("qty", "Qty", 90, "e", "qty"),
            Column("amount", "Amount", 110, "e", "money"),
            Column("avg", "Avg rate", 90, "e", "money"),
            Column("lo", "Min rate", 90, "e", "money"),
            Column("hi", "Max rate", 90, "e", "money"),
        ],
        "purchases_by_quality",
    ),
    "Open lots": (
        [
            Column("id", "Lot", 55, "e", "int"),
            Column("date", "Date", 95),
            Column("farmer", "Farmer", 170, stretch=True),
            Column("crop", "Crop", 130),
            Column("left", "Left", 90, "e", "qty"),
            Column("rate", "Rate", 80, "e", "money"),
            Column("value", "Cost value", 100, "e", "money"),
            Column("q", "Q", 45, "center"),
            Column("age", "Days", 60, "e", "int"),
        ],
        "open_lots",
    ),
}


class CropReportsPanel(ctk.CTkFrame):
    def __init__(self, master, view: CropTradingView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 4))
        self.which = ctk.CTkOptionMenu(
            bar, values=list(REPORTS), font=theme.font(13), height=34, width=200, command=lambda _v: self.run()
        )
        self.which.pack(side="left")
        ctk.CTkLabel(bar, text="From", font=theme.font(12), text_color=theme.color("muted")).pack(
            side="left", padx=(12, 4)
        )
        self.d_from = ctk.CTkEntry(bar, width=110, height=34, font=theme.font(13))
        self.d_from.insert(0, days_ago_str(90))
        self.d_from.pack(side="left")
        ctk.CTkLabel(bar, text="To", font=theme.font(12), text_color=theme.color("muted")).pack(
            side="left", padx=(8, 4)
        )
        self.d_to = ctk.CTkEntry(bar, width=110, height=34, font=theme.font(13))
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
        columns, method = REPORTS[name]
        if self.table:
            self.table.destroy()
        self.table = DataTable(self.host, columns, on_double_click=self._open)
        self.table.pack(fill="both", expand=True)
        f, t = self.d_from.get().strip(), self.d_to.get().strip()
        try:
            if method == "summary":
                s = self.svc.summary(f, t)
                labels = [
                    ("Lots purchased", s["purchases"]),
                    ("Quantity purchased", fmt_qty(s["purchased_qty"])),
                    ("Purchase amount", money(s["purchased_amount"])),
                    ("Sales", s["sales"]),
                    ("Quantity sold", fmt_qty(s["sold_qty"])),
                    ("Revenue", money(s["sold_amount"])),
                    ("Cost of goods sold", money(s["sold_cost"])),
                    ("Realized margin", money(s["margin"])),
                    ("Margin %", f"{s['margin_pct']:g}%"),
                    ("Stock at cost (now)", money(s["stock_cost"])),
                    ("Stock at market (now)", money(s["stock_market"])),
                    ("Unrealized gain (now)", money(s["unrealized"])),
                ]
                rows = labels
                footer = f"{f} to {t}"
            elif method == "open_lots":
                today = dt.date.today()
                rows = [
                    (
                        x.id,
                        x.date,
                        x.farmer_name,
                        x.crop_name,
                        x.remaining_qty,
                        x.rate,
                        round(x.remaining_qty * x.rate, 2),
                        x.quality,
                        (today - dt.date.fromisoformat(x.date)).days,
                        x.farmer_id,
                    )
                    for x in self.svc.lots(open_only=True)
                ]
                footer = f"{len(rows)} open lots · {money(sum(r[6] for r in rows))} at cost"
            else:
                rows = getattr(self.svc, method)(f, t)
                footer = f"{len(rows)} rows · {f} to {t}"
        except Exception as exc:  # noqa: BLE001
            self.ctx.toast(str(exc), "error")
            return
        self.table.set_rows(rows, footer)

    def _open(self, row) -> None:
        name = self.which.get()
        if name in ("Purchases by farmer", "Margin by buyer") and row[0]:
            self.ctx.navigate("customers", customer_id=int(row[0]))
        elif name == "Open lots":
            self.ctx.navigate("customers", customer_id=int(row[9]))
        elif name == "Margin by crop":
            self.ctx.navigate("items", item_id=int(row[0]))

    def export(self) -> None:
        if not self.table or not self.table.rows:
            self.ctx.toast("Nothing to export", "warning")
            return
        path = (
            self.ctx.settings.export_dir
            / f"crop_{safe_filename(self.which.get())}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        export_rows(path, self.table.export_columns(), self.table.export_rows(), f"Crop trade - {self.which.get()}")
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)


_ = info  # re-exported helper kept for dialogs parity
