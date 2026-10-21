"""Crop trading screen: Purchase, Sale, Stock & rates, Reports."""

from __future__ import annotations

import datetime as dt
from tkinter import filedialog

import customtkinter as ctk

from hth.domain.units import normalize
from hth.modules.crop_trading.rates import PROVIDERS, CsvRateProvider
from hth.modules.crop_trading.service import CropService
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import days_ago_str, money, open_path, today_str
from hth.ui.format import qty as fmt_qty
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, confirm, run_form
from hth.ui.widgets.forms import (
    Card,
    DateField,
    LabeledEntry,
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
        for name in ("Lots & sales", "Stock & rates", "Reports"):
            self.tabs.add(name)
        self.lots = LotsPanel(self.tabs.tab("Lots & sales"), self)
        self.lots.pack(fill="both", expand=True)
        self.stock = StockPanel(self.tabs.tab("Stock & rates"), self)
        self.stock.pack(fill="both", expand=True)
        self.reports = CropReportsPanel(self.tabs.tab("Reports"), self)
        self.reports.pack(fill="both", expand=True)

    def on_show(self, report: str | None = None, **kwargs) -> None:
        for p in (self.lots, self.stock, self.reports):
            p.reload()
        if report in REPORTS:  # opened from a report catalogue
            self.tabs.set("Reports")
            self.reports.which.set(report)
            self.reports.run()

    def on_theme_change(self) -> None:
        for p in (self.lots, self.stock, self.reports):
            for t in p.tables():
                t.restyle()

    def crop_choices(self):
        return [(c.id, c.display) for c in self.svc.crops()]


# ------------------------------------------------------------------------------------------
class LotsPanel(ctk.CTkFrame):
    """Purchase lots and sales - entered on the Sales screen, reviewed (and deleted) here."""

    def __init__(self, master, view: CropTradingView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 4))
        ctk.CTkLabel(
            bar,
            text="Record crop purchases and sales on the Sales screen (pick a crop item).",
            font=theme.font(12),
            text_color=theme.color("muted"),
        ).pack(side="left")
        primary_button(bar, "Go to Sales", lambda: self.ctx.navigate("sales"), width=110).pack(side="left", padx=10)
        secondary_button(bar, "+ New crop", self.new_crop, width=100).pack(side="left")
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right")

        # two equal halves (pack would give the first table everything and crush the second)
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.grid_columnconfigure(0, weight=1)
        split.grid_rowconfigure((0, 1), weight=1, uniform="half")
        lots_card = Card(split)
        lots_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        lb = ctk.CTkFrame(lots_card, fg_color="transparent")
        lb.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(lb, text="Purchase lots", font=theme.font(17, "bold")).pack(side="left")
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(lb, "Delete lot", self.delete_lot, width=100).pack(side="right")
        self.lots_table = DataTable(
            lots_card,
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
        self.lots_table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        sales_card = Card(split)
        sales_card.grid(row=1, column=0, sticky="nsew")
        sb = ctk.CTkFrame(sales_card, fg_color="transparent")
        sb.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(sb, text="Sales", font=theme.font(17, "bold")).pack(side="left")
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(sb, "Delete sale", self.delete_sale, width=100).pack(side="right")
        self.sales_table = DataTable(
            sales_card,
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
            on_double_click=lambda r: self.ctx.navigate("customers", customer_id=r[11]) if r[11] else None,
            row_tags=lambda r: ["neg"] if r[8] < 0 else (["warn"] if r[10] > 0 else ["pos"]),
        )
        self.sales_table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def tables(self):
        return [self.lots_table, self.sales_table]

    def reload(self) -> None:
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
        self.lots_table.set_rows(
            rows, f"{len(rows)} lots · {money(sum(r[9] for r in rows))} · double-click opens the ledger"
        )
        sales = self.svc.sales(limit=300)
        srows = [
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
                s.buyer_id,
            )
            for s in sales
        ]
        self.sales_table.set_rows(
            srows,
            f"{len(srows)} sales · revenue {money(sum(r[6] for r in srows))}"
            f" · margin {money(sum(r[8] for r in srows))}",
        )

    def new_crop(self) -> None:
        fields = [
            Field("name", "Crop name"),
            Field("unit", "Stock unit", "option", "KG", ["KG", "QTL", "LTR", "PCS", "BAG"]),
        ]
        created = {}

        def submit(v):
            created["item"] = self.svc.add_crop(v["name"], v["unit"], self.ctx.username)

        if run_form(self, "New crop", fields, submit, "Create") and created:
            self.ctx.toast(f"Crop {created['item'].name} added - pick it on the Sales screen", "success")
            self.view.stock.reload()

    def delete_lot(self) -> None:
        row = self.lots_table.selected_row()
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

    def delete_sale(self) -> None:
        row = self.sales_table.selected_row()
        if row and confirm(
            self,
            "Delete sale",
            f"Delete sale #{row[0]} ({row[2]}, {fmt_qty(row[4])} {row[3]})?\n"
            "Stock returns to its lots; ledger entry removed.",
        ):
            self.svc.delete_sale(row[0], self.ctx.username)
            self.reload()
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
