"""Inventory: add items, browse stock, open movement history, (admin) edit records."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.domain.constants import ITEM_TYPES, PAKKA_KACHA, UNITS
from hth.domain.units import normalize
from hth.services.accounts import ValidationError
from hth.services.export import export_rows, safe_filename
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money, open_path, qty
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


class ItemsView(BaseView):
    key = "items"
    title = "Items"
    permission = Permission.ADD_ITEM

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=2, uniform="i")
        self.grid_columnconfigure(1, weight=5, uniform="i")
        self.grid_rowconfigure(0, weight=1)

        form = Card(self, "New item")
        form.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)
        inner = ctk.CTkScrollableFrame(form, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        inner.grid_columnconfigure((0, 1), weight=1)

        self.name = LabeledEntry(inner, "Item name")
        self.name.grid(row=0, column=0, columnspan=2, sticky="ew", pady=4)
        self.source = LabeledEntry(inner, "Source / supplier")
        self.source.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        self.date = DateField(inner)
        self.date.grid(row=2, column=0, sticky="ew", pady=4, padx=(0, 6))
        self.opening = LabeledEntry(inner, "Opening quantity", placeholder="0")
        self.opening.grid(row=2, column=1, sticky="ew", pady=4, padx=(6, 0))
        self.stock_value = LabeledEntry(inner, "Stock value (cost)", placeholder="0.00")
        self.stock_value.grid(row=3, column=0, sticky="ew", pady=4, padx=(0, 6))
        self.last_value = LabeledEntry(inner, "Last sale price", placeholder="0.00")
        self.last_value.grid(row=3, column=1, sticky="ew", pady=4, padx=(6, 0))
        self.unit = LabeledOption(inner, "Stock unit (KG/LTR for loose sales)", UNITS)
        self.unit.grid(row=4, column=0, sticky="ew", pady=4, padx=(0, 6))
        self.batch = LabeledEntry(inner, "Batch", default="NA")
        self.batch.grid(row=4, column=1, sticky="ew", pady=4, padx=(6, 0))
        self.expiry = LabeledEntry(inner, "Expiry (YYYY-MM-DD or NA)", default="NA")
        self.expiry.grid(row=5, column=0, sticky="ew", pady=4, padx=(0, 6))
        self.gst = LabeledEntry(inner, "GST %", placeholder="0")
        self.gst.grid(row=5, column=1, sticky="ew", pady=4, padx=(6, 0))
        self.item_type = LabeledOption(inner, "Type (F/P/S/O)", ITEM_TYPES, "O")
        self.item_type.grid(row=6, column=0, sticky="ew", pady=4, padx=(0, 6))
        self.pk = LabeledOption(inner, "Pakka / Kacha", PAKKA_KACHA, "P")
        self.pk.grid(row=6, column=1, sticky="ew", pady=4, padx=(6, 0))
        primary_button(inner, "Add item", self.add_item).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 0))

        self.right = ctk.CTkFrame(self, fg_color="transparent")
        self.right.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        self.list_panel = ItemListPanel(self.right, self)
        self.history_panel = ItemHistoryPanel(self.right, self)
        self.list_panel.pack(fill="both", expand=True)

    def on_show(self, item_id: int | None = None, **kwargs) -> None:
        if item_id is not None:
            self.show_history(item_id)
        else:
            self.list_panel.reload()

    def on_theme_change(self) -> None:
        self.list_panel.table.restyle()
        self.history_panel.table.restyle()

    def show_history(self, item_id: int) -> None:
        self.list_panel.pack_forget()
        self.history_panel.pack(fill="both", expand=True)
        self.history_panel.load(item_id)

    def show_list(self) -> None:
        self.history_panel.pack_forget()
        self.list_panel.pack(fill="both", expand=True)
        self.list_panel.reload()

    def add_item(self) -> None:
        try:
            item = self.ctx.inventory.add_item(
                self.name.get(),
                self.stock_value.get() or 0,
                self.last_value.get() or 0,
                self.unit.get(),
                self.batch.get(),
                self.expiry.get(),
                self.gst.get() or 0,
                self.item_type.get(),
                self.pk.get(),
                self.date.get(),
                self.opening.get() or 0,
                self.source.get(),
                self.ctx.username,
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(f"Item #{item.id} {item.name} added", "success")
        for w in (
            self.name,
            self.source,
            self.opening,
            self.stock_value,
            self.last_value,
            self.gst,
        ):
            w.set("")
        self.batch.set("NA")
        self.expiry.set("NA")
        self.date.set_today()
        self.show_list()
        self.name.focus()


class ItemListPanel(ctk.CTkFrame):
    def __init__(self, master, view: ItemsView):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10)
        self.view, self.ctx, self._all = view, view.ctx, []
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bar, text="Stock", font=theme.font(17, "bold")).pack(side="left")
        secondary_button(bar, "↻", self.reload, width=40).pack(side="right", padx=(6, 0))
        self.search = ctk.CTkEntry(
            bar,
            placeholder_text="Filter by id, name, batch…",
            width=280,
            height=34,
            font=theme.font(13),
        )
        self.search.pack(side="right")
        self.search.bind("<KeyRelease>", lambda e: self._filter())
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 55, "e", "int"),
                Column("name", "Name", 220, stretch=True),
                Column("batch", "Batch", 90),
                Column("unit", "Unit", 60),
                Column("stock", "In stock", 90, "e", "qty"),
                Column("value", "Cost", 90, "e", "money"),
                Column("total", "Stock value", 110, "e", "money"),
                Column("last", "Last price", 90, "e", "money"),
                Column("expiry", "Expiry", 100),
                Column("gst", "GST%", 60, "e", "qty"),
                Column("type", "Type", 50, "center"),
                Column("pk", "P/K", 45, "center"),
                Column("cat", "Cat", 45, "center"),
            ],
            on_double_click=lambda r: self.view.show_history(r[0]),
            row_tags=lambda r: (["muted"] if r[12] == "E" else []) + (["warn"] if r[4] <= 0 else []),
        )
        ctk.CTkLabel(
            self,
            text="Double-click an item to see its movements.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="bottom", padx=12, pady=(0, 10), anchor="w")
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 4))

    def reload(self) -> None:
        self._all = [
            (
                s.item.id,
                s.item.name,
                s.item.batch,
                s.item.unit,
                s.in_stock,
                s.item.stock_value,
                s.total_value,
                s.item.last_value,
                s.item.expiry_date,
                s.item.gst_rate,
                s.item.item_type,
                s.item.pakka_kacha,
                s.item.category,
            )
            for s in self.ctx.inventory.summaries()
        ]
        self._filter()

    def _filter(self) -> None:
        term = self.search.get().strip().lower()
        rows = [r for r in self._all if not term or term in f"{r[0]} {r[1]} {r[2]}".lower()]
        self.table.set_rows(rows, f"{len(rows)} items · total stock value {money(sum(r[6] for r in rows))}")


class ItemHistoryPanel(ctk.CTkFrame):
    def __init__(self, master, view: ItemsView):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10)
        self.view, self.ctx, self.item = view, view.ctx, None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 4))
        secondary_button(head, "← Back", self.view.show_list, width=80).pack(side="left")
        self.name_label = ctk.CTkLabel(head, text="", font=theme.font(17, "bold"))
        self.name_label.pack(side="left", padx=12)
        self.stock_label = ctk.CTkLabel(head, text="", font=theme.font(17, "bold"))
        self.stock_label.pack(side="right")
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=12, pady=(0, 4))
        secondary_button(tools, "Export Excel", self.export, width=110).pack(side="left")
        if self.ctx.can(Permission.EDIT_RECORDS):
            secondary_button(tools, "Add movement", self.add_movement, width=120).pack(side="left", padx=(12, 6))
            secondary_button(tools, "Edit movement", self.edit_movement, width=120).pack(side="left", padx=6)
            secondary_button(tools, "Edit item", self.edit_item, width=100).pack(side="left", padx=6)
            secondary_button(tools, "Category", self.set_category, width=90).pack(side="left", padx=6)
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(tools, "Delete movement", self.delete_movement, width=130).pack(side="right", padx=(6, 0))
            danger_button(tools, "Delete item", self.delete_item, width=110).pack(side="right")
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 60, "e", "int"),
                Column("date", "Date", 100),
                Column("received", "Received", 100, "e", "qty"),
                Column("sale", "Sold", 100, "e", "qty"),
                Column("balance", "Balance", 100, "e", "qty"),
                Column("description", "Description", 300, stretch=True),
                Column("tags", "Tags", 80),
            ],
            on_double_click=lambda r: self.edit_movement() if self.ctx.can(Permission.EDIT_RECORDS) else None,
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def load(self, item_id: int) -> None:
        self.item = self.ctx.inventory.get_item(item_id)
        if self.item is None:
            self.view.show_list()
            return
        lock = " 🔒" if self.item.category_locked else ""
        self.name_label.configure(
            text=f"#{self.item.id}  {self.item.name}  ·  {self.item.batch}  ·  {self.item.unit}"
            f"  ·  category {self.item.category}{lock}"
        )
        rows, running = [], 0.0
        for t in self.ctx.inventory.get_item_transactions(item_id):
            running += t.received - t.sale
            rows.append((t.id, t.date, t.received, t.sale, running, t.description, t.tags))
        self.table.set_rows(
            rows,
            f"{len(rows)} movements · cost {money(self.item.stock_value)} · last price {money(self.item.last_value)}",
        )
        self.stock_label.configure(text=f"In stock {qty(running)} {self.item.unit}")

    def export(self) -> None:
        path = (
            self.ctx.settings.export_dir
            / f"item_{safe_filename(self.item.name)}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        export_rows(
            path,
            self.table.export_columns(),
            self.table.export_rows(),
            f"Stock movements - {self.item.name}",
        )
        self.ctx.toast(f"Saved {path.name}", "success")
        if confirm(self, "Export", f"Saved to\n{path}\n\nOpen it now?"):
            open_path(path)

    def _selected(self):
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select a movement first", "warning")
            return None
        return self.ctx.inventory.get_item_transaction(row[0])

    def add_movement(self) -> None:
        fields = [
            Field("date", "Date", default=dt.date.today().isoformat()),
            Field("received", "Received", default="0"),
            Field("sale", "Sold", default="0"),
            Field("description", "Description"),
            Field("tags", "Tags"),
        ]
        run_form(
            self,
            "Add stock movement",
            fields,
            lambda v: self.ctx.inventory.add_item_transaction(
                self.item.id,
                v["date"],
                v["received"],
                v["sale"],
                v["description"],
                v["tags"],
                self.ctx.username,
            ),
        )
        self.load(self.item.id)

    def edit_movement(self) -> None:
        t = self._selected()
        if t is None:
            return
        fields = [
            Field("date", "Date", default=t.date),
            Field("received", "Received", default=f"{t.received:g}"),
            Field("sale", "Sold", default=f"{t.sale:g}"),
            Field("description", "Description", default=t.description),
            Field("tags", "Tags", default=t.tags),
        ]
        run_form(
            self,
            f"Edit movement #{t.id}",
            fields,
            lambda v: self.ctx.inventory.update_item_transaction(
                t.id,
                v["date"],
                v["received"],
                v["sale"],
                v["description"],
                v["tags"],
                self.ctx.username,
            ),
        )
        self.load(self.item.id)

    def delete_movement(self) -> None:
        t = self._selected()
        if t and confirm(
            self,
            "Delete movement",
            f"Delete movement #{t.id} ({t.date}, +{t.received:g} / -{t.sale:g})?",
        ):
            self.ctx.inventory.delete_item_transaction(t.id, self.ctx.username)
            self.load(self.item.id)

    def edit_item(self) -> None:
        i = self.item
        fields = [
            Field("name", "Name", default=i.name),
            Field("stock_value", "Stock value (cost) per unit", default=f"{i.stock_value:g}"),
            Field("last_value", "Last price per unit", default=f"{i.last_value:g}"),
            Field(
                "unit", "Unit  (changing it converts the whole history)", "option", normalize(i.unit) or "PCS", UNITS
            ),
            Field("batch", "Batch", default=i.batch),
            Field("expiry_date", "Expiry", default=i.expiry_date),
            Field("gst_rate", "GST %", default=f"{i.gst_rate:g}"),
            Field("item_type", "Type", "option", i.item_type, ITEM_TYPES),
            Field("pakka_kacha", "Pakka/Kacha", "option", i.pakka_kacha, PAKKA_KACHA),
        ]
        values = run_form(
            self,
            f"Edit item #{i.id}",
            fields,
            lambda v: self.ctx.inventory.update_item(
                i.id, self.ctx.username, **{k: x for k, x in v.items() if k != "unit"}
            ),
        )
        if values and normalize(values["unit"]) != normalize(i.unit):
            self._change_unit(normalize(values["unit"]))
        self.load(i.id)

    def _change_unit(self, new_unit: str) -> None:
        i = self.item
        old_unit = normalize(i.unit)
        factor = self.ctx.inventory.conversion_factor(i.id, new_unit)
        if factor is not None:
            if not confirm(
                self,
                "Convert unit",
                f"Change {i.name} from {old_unit} to {new_unit}?\n\n"
                f"1 {old_unit} = {factor:g} {new_unit}. Every movement, lot and rate will be converted;\n"
                "money amounts stay the same.",
            ):
                return
        else:
            result = run_form(
                self,
                f"{old_unit} → {new_unit}",
                [Field("factor", f"How many {new_unit} is 1 {old_unit}?  (blank = relabel only, no conversion)")],
                lambda v: None,
                "Continue",
            )
            if result is None:
                return
            text = result["factor"].strip()
            if not text:
                self.ctx.inventory.update_item(i.id, self.ctx.username, unit=new_unit)
                self.ctx.toast(f"Unit relabelled to {new_unit}; history not converted", "warning")
                return
            try:
                factor = float(text)
            except ValueError:
                self.ctx.toast("Factor must be a number", "error")
                return
        try:
            used = self.ctx.inventory.change_unit(i.id, new_unit, self.ctx.username, factor)
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast(f"{i.name}: {old_unit} → {new_unit} (x{used:g}), history converted", "success")

    def set_category(self) -> None:
        i = self.item
        fields = [
            Field(
                "category",
                "Category (E = discontinued, kept out of stock reports)",
                "option",
                i.category,
                ["A", "B", "C", "D", "E"],
            ),
            Field(
                "mode", "After saving", "option", "Keep (locked)", ["Keep (locked)", "Let auto-categorise change it"]
            ),
        ]

        def submit(v):
            self.ctx.inventory.set_category(i.id, v["category"], self.ctx.username, locked=v["mode"].startswith("Keep"))

        if run_form(self, f"Category of {i.name}", fields, submit):
            self.ctx.toast("Category updated", "success")
            self.load(i.id)

    def delete_item(self) -> None:
        if confirm(self, "Delete item", f"Delete #{self.item.id} {self.item.name} and all its movements?"):
            self.ctx.inventory.delete_item(self.item.id, self.ctx.username)
            self.ctx.toast("Item deleted", "success")
            self.view.show_list()
