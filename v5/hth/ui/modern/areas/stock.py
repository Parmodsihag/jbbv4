"""Stock - items, crops and market rates in the new layout.

*Items*: the list on the left with Running low / Out / Expiring / Not selling filters, one
page per item on the right - stock, last rate, what sold in 30 days and how long it lasts,
its movements and details.  Buying and selling happen at the Counter (the buttons open it
with the item picked); corrections are admin-only on the More menu and a movement's
right-click.  *Crops & rates*: the crop trading module's own screen, hosted here.
"""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth import i18n
from hth.domain.units import normalize
from hth.modules import discover
from hth.services.insights import InsightsService
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import qty as fmt_qty
from hth.ui.modern import item_actions
from hth.ui.modern.widgets import button as _button
from hth.ui.modern.widgets import card, pill, rupees, segmented, set_pill
from hth.ui.modern.widgets import dropdown_menu as _menu
from hth.ui.modern.widgets import popup as _popup
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable

FILTERS = ["All", "Running low", "Out", "Expiring", "Not selling"]
EXPIRY_DAYS = 60
DEAD_DAYS = 90


class StockView(BaseView):
    key = "stock"
    title = "Stock"
    permission = Permission.ADD_ITEM

    def build(self) -> None:
        # modules that live in Stock (crop trading) show as further pages, by their own factory
        self.module_pages = {
            (s.tab or s.label): s
            for s in discover()
            if getattr(s, "area", None) == "stock" and self.ctx.can(s.permission)
        }
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        self.names = ["Items", *self.module_pages]
        self.switch = segmented(head, self.names, command=lambda v: self.show_page(v))
        self.switch.pack(side="left")
        self.summary = ctk.CTkLabel(head, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.summary.pack(side="left", padx=14)
        if self.ctx.can(Permission.ADD_ITEM):
            _button(head, "+ New item", self.new_item, outline=True).pack(side="right")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.items = ItemsPage(self.body, self)
        self.hosted: dict[str, BaseView] = {}
        self.current: str | None = None

    def show_page(self, name: str, **kwargs) -> None:
        for page in (self.items, *self.hosted.values()):
            page.pack_forget()
        if name in self.module_pages:
            view = self.hosted.get(name)
            if view is None:
                view = self.module_pages[name].view_factory(self.body, self.ctx)
                self.hosted[name] = view
            view.pack(fill="both", expand=True)
            self.current = self.module_pages[name].key
            self.switch.set(name)
            view.on_show(**kwargs)
            return
        self.items.pack(fill="both", expand=True)
        self.current = "items"
        self.switch.set("Items")
        self.items.on_show(**kwargs)

    def child(self, key: str):
        if key == "items":
            return self.items
        name = next((n for n, s in self.module_pages.items() if s.key == key), None)
        return self.hosted.get(name) if name else None

    def on_show(self, tab: str | None = None, item_id: int | None = None, **kwargs) -> None:
        module = next((n for n, s in self.module_pages.items() if s.key == tab), None)
        if module:
            self.show_page(module, **kwargs)
        elif tab == "items" or item_id is not None or self.current in (None, "items"):
            self.show_page("Items", item_id=item_id)
        else:
            name = next((n for n, s in self.module_pages.items() if s.key == self.current), "Items")
            self.show_page(name)

    def on_theme_change(self) -> None:
        self.items.restyle()
        for view in self.hosted.values():
            view.on_theme_change()

    def on_day_change(self) -> None:
        for view in self.hosted.values():
            view.on_day_change()

    def new_item(self) -> None:
        item = item_actions.new_item(self, self.ctx)
        if item is not None:
            self.show_page("Items", item_id=item.id)


# --------------------------------------------------------------------------------------
class ItemsPage(ctk.CTkFrame):
    def __init__(self, master, view: StockView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx = view, view.ctx
        self._all: list[tuple] = []
        self._pending = None
        self.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = card(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.search = ctk.CTkEntry(left, placeholder_text="Item name, batch or #id", height=36, font=theme.font(13))
        self.search.pack(fill="x", padx=12, pady=(12, 8))
        self.search.bind("<KeyRelease>", lambda e: self._filter())
        self.chips = segmented(left, FILTERS, command=lambda _v: self._filter(), height=30)
        self.chips.set("All")
        self.chips.pack(anchor="w", padx=12)
        self.table = DataTable(
            left,
            [
                Column("name", "Item", 170, stretch=True),
                Column("stock", "In stock", 95, "e"),
                Column("rate", "Rate", 80, "e", "money"),
                Column("state", "", 92),
            ],
            on_select=self._on_select,
            row_tags=lambda r: (
                (["neg"] if r[7] <= 0 else (["warn"] if r[3] and r[3] != "Crop" else []))
                + (["muted"] if r[8] == "E" else [])
            ),
        )
        self.table.pack(fill="both", expand=True, padx=8, pady=8)

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.page = ItemPage(right, view)
        self.empty = ctk.CTkLabel(
            right, text="Pick an item on the left.", font=theme.font(14), text_color=theme.color("muted")
        )
        self.empty.pack(expand=True)

    def restyle(self) -> None:
        self.table.restyle()
        self.page.restyle()

    def on_show(self, item_id: int | None = None, **kwargs) -> None:
        self.reload()
        if item_id is not None:
            self.open(item_id)
        elif self.page.item is not None:
            self.open(self.page.item.id)
        self.after(80, self.search.focus_set)

    def reload(self) -> None:
        self.table.set_footer("Loading stock…")
        ctx = self.ctx

        def work():
            today = dt.date.today()
            soon = (today + dt.timedelta(days=EXPIRY_DAYS)).isoformat()
            dead_from = (today - dt.timedelta(days=DEAD_DAYS)).isoformat()
            reorder = {r.item_id: r for r in InsightsService(ctx.db).reorder_suggestions(today=today)}
            last_sale = ctx.inventory.last_sale_dates()
            return ctx.inventory.summaries(), reorder, last_sale, soon, dead_from

        self.view.run_async(work, self._loaded)

    def _loaded(self, data) -> None:
        summaries, reorder, last_sale, soon, dead_from = data
        rows = []
        for s in summaries:
            item = s.item
            unit = normalize(item.unit)
            expiry = item.expiry_date if len(item.expiry_date or "") == 10 and item.expiry_date[4] == "-" else ""
            line = reorder.get(item.id)
            if item.item_type == "C":
                state = "Crop"
            elif s.in_stock <= 0:
                state = "Out"
            elif line is not None and line.days_left is not None:
                state = f"{line.days_left:g} days"
            elif expiry and expiry <= soon and s.in_stock > 0:
                state = f"Expires {expiry[5:]}"
            else:
                state = ""
            flags = {
                "low": line is not None,
                "expiring": bool(expiry and expiry <= soon and s.in_stock > 0),
                "dead": s.in_stock > 0 and (last_sale.get(item.id) or "") < dead_from and item.item_type != "C",
            }
            label = f"{item.name}" + (f"  ·  {item.batch}" if item.batch and item.batch != "NA" else "")
            rows.append(
                (
                    label,
                    f"{fmt_qty(s.in_stock)} {unit}",
                    item.last_value,
                    state,
                    item.id,
                    f"{item.id} {item.name} {item.batch}",
                    flags,
                    s.in_stock,
                    item.category,
                    s.total_value,
                )
            )
        self._all = rows
        total = sum(r[9] for r in rows)
        self.view.summary.configure(text=f"{len(rows)} items · stock worth {rupees(total)} at cost")
        self._filter()

    def _filter(self) -> None:
        words = self.search.get().strip().lower().split()
        chip = self.chips.get()
        rows = [
            r
            for r in self._all
            if all(w in r[5].lower() for w in words)
            and (
                chip == "All"
                or (chip == "Running low" and r[6]["low"])
                or (chip == "Out" and r[7] <= 0)
                or (chip == "Expiring" and r[6]["expiring"])
                or (chip == "Not selling" and r[6]["dead"])
            )
        ]
        self.table.set_rows(rows, f"{len(rows)} items")

    def _on_select(self, row) -> None:
        if row is None:
            return
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(160, lambda iid=row[4]: self.open(iid))

    def open(self, item_id: int) -> None:
        self._pending = None
        if not self.page.load(item_id):
            return
        self.empty.pack_forget()
        if not self.page.winfo_manager():
            self.page.pack(fill="both", expand=True)


# --------------------------------------------------------------------------------------
class ItemPage(ctk.CTkFrame):
    def __init__(self, master, view: StockView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx = view, view.ctx
        self.item = None
        can = self.ctx.can

        head = card(self)
        head.pack(fill="x")
        top = ctk.CTkFrame(head, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        names = ctk.CTkFrame(top, fg_color="transparent")
        names.pack(side="left", fill="x", expand=True)
        self.name_label = ctk.CTkLabel(names, text="", font=theme.font(20, "bold"), anchor="w", height=26)
        self.name_label.pack(fill="x")
        pills = ctk.CTkFrame(names, fg_color="transparent")
        pills.pack(fill="x", pady=(4, 0))
        self.type_pill = pill(pills, "", "soon")
        self.type_pill.pack(side="left")
        self.cat_pill = pill(pills, "", "info")
        self.cat_pill.pack(side="left", padx=6)
        self.id_pill = pill(pills, "", "soon")
        self.id_pill.pack(side="left")
        bar = ctk.CTkFrame(top, fg_color="transparent")
        bar.pack(side="right", anchor="n")
        if can(Permission.RECORD_SALE):
            _button(bar, "Purchase · stock in", lambda: self._counter("purchase"), primary=True).pack(side="left")
            _button(bar, "Sale", lambda: self._counter("sale")).pack(side="left", padx=6)
        if can(Permission.EDIT_RECORDS) or can(Permission.DELETE_RECORDS):
            self.more_button = _button(bar, "⋯ More", self._more_menu)
            self.more_button.pack(side="left")

        tiles = ctk.CTkFrame(head, fg_color="transparent")
        tiles.pack(fill="x", padx=16, pady=(0, 14))
        tiles.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="t")
        self.tiles = {}
        for i, label in enumerate(("In stock", "Last rate", "Sold, last 30 days", "Lasts about")):
            t = ctk.CTkFrame(tiles, fg_color=theme.color("stripe"), corner_radius=10)
            t.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0))
            ctk.CTkLabel(t, text=label, font=theme.font(11), text_color=theme.color("muted"), anchor="w").pack(
                fill="x", padx=12, pady=(8, 0)
            )
            value = ctk.CTkLabel(t, text="", font=theme.font(17, "bold"), anchor="w")
            value.pack(fill="x", padx=12, pady=(0, 8))
            self.tiles[label] = (t, value)

        body = card(self)
        body.pack(fill="both", expand=True, pady=(12, 0))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 6))
        self.tabs = segmented(row, ["Movements", "Details"], command=lambda v: self.show_tab(v))
        self.tabs.set("Movements")
        self.tabs.pack(side="left")
        self.mov_note = ctk.CTkLabel(row, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.mov_note.pack(side="right")
        self.movements = DataTable(
            body,
            [
                Column("date", "Date", 92),
                Column("description", "Entry", 230, stretch=True),
                Column("in", "In", 80, "e", "qty"),
                Column("out", "Out", 80, "e", "qty"),
                Column("after", "Stock after", 100, "e", "qty"),
                Column("tags", "Tags", 70),
            ],
            row_actions=self._row_actions,
            on_double_click=(lambda r: self._edit_movement(r)) if can(Permission.EDIT_RECORDS) else None,
        )
        self.details = ctk.CTkFrame(body, fg_color="transparent")
        self.detail_rows: dict[str, ctk.CTkLabel] = {}
        for i, label in enumerate(
            ("Name", "Hindi name", "Unit", "Batch", "Expiry", "GST %", "Pakka / Kacha", "Cost per unit", "Category")
        ):
            name = ctk.CTkLabel(self.details, text=label, font=theme.font(13), text_color=theme.color("muted"))
            name.grid(row=i, column=0, sticky="w", padx=(18, 24), pady=3)
            value = ctk.CTkLabel(self.details, text="", font=theme.font(13, "bold"), anchor="w")
            value.grid(row=i, column=1, sticky="w", pady=3)
            self.detail_rows[label] = value
        self.show_tab("Movements")

    def restyle(self) -> None:
        self.movements.restyle()

    def show_tab(self, name: str) -> None:
        self.movements.pack_forget()
        self.details.pack_forget()
        if name == "Details":
            self.details.pack(fill="both", expand=True, pady=(4, 10))
        else:
            self.movements.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def load(self, item_id: int) -> bool:
        item = self.ctx.inventory.get_item(item_id)
        if item is None:
            return False
        self.item = item
        unit = normalize(item.unit)
        self.name_label.configure(text=i18n.tr_cell(item.name))
        type_name = item_actions.TYPE_NAMES.get(item.item_type, item.item_type)
        set_pill(self.type_pill, f"{type_name} · GST {item.gst_rate:g}%", "soon")
        set_pill(self.cat_pill, f"Category {item.category}" + (" 🔒" if item.category_locked else ""), "info")
        set_pill(self.id_pill, f"#{item.id} · {unit}", "soon")

        moves = self.ctx.inventory.get_item_transactions(item.id)
        rows, running = [], 0.0
        for t in moves:
            running += t.received - t.sale
            shown = i18n.tr_cell(t.description)
            rows.append((t.date, shown, t.received or None, t.sale or None, running, t.tags, t.id))
        rows.reverse()  # newest first
        self.movements.set_rows(rows, f"{len(rows)} movements")
        today = dt.date.today()
        sold, _value, _n = self.ctx.inventory.sales_between(
            item.id, (today - dt.timedelta(days=30)).isoformat(), today.isoformat()
        )
        rate = sold / 30 if sold else 0
        days = running / rate if rate and running > 0 else None
        self._tile("In stock", f"{fmt_qty(running)} {unit}", "owe" if running <= 0 else "text")
        self._tile("Last rate", rupees(item.last_value))
        self._tile("Sold, last 30 days", f"{fmt_qty(sold)} {unit}")
        if days is None:
            self._tile("Lasts about", "—" if not sold else "out", "muted" if not sold else "owe")
        else:
            self._tile("Lasts about", f"{days:.0f} days", "warning" if days < 14 else "text", soft=days < 14)
        self.mov_note.configure(text="newest first · double-click to correct (admin)")
        for key, value in {
            "Name": item.name,
            "Hindi name": (item.name_hi or "-") + ("  ✓" if item.hi_manual else ""),
            "Unit": unit,
            "Batch": item.batch,
            "Expiry": item.expiry_date,
            "GST %": f"{item.gst_rate:g}",
            "Pakka / Kacha": item.pakka_kacha,
            "Cost per unit": rupees(item.stock_value),
            "Category": item.category + ("  (locked)" if item.category_locked else ""),
        }.items():
            self.detail_rows[key].configure(text=value)
        return True

    def _tile(self, label: str, value: str, color: str = "text", soft: bool = False) -> None:
        frame, val = self.tiles[label]
        frame.configure(fg_color=theme.color("warn_soft") if soft else theme.color("stripe"))
        val.configure(text=value, text_color=theme.color(color))

    # Actions ---------------------------------------------------------------------------
    def _counter(self, intent: str) -> None:
        if self.item is not None:
            self.ctx.navigate("counter", intent=intent, item_id=self.item.id)

    def _more_menu(self) -> None:
        can, tr = self.ctx.can, i18n.tr
        menu = _menu(self)
        if can(Permission.EDIT_RECORDS):
            menu.add_command(label=tr("Edit item"), command=self._edit_item)
            menu.add_command(label=tr("Category"), command=self._category)
            menu.add_command(label=tr("Add stock movement"), command=self._add_movement)
        if can(Permission.DELETE_RECORDS):
            menu.add_separator()
            menu.add_command(label=tr("Delete item…"), command=self._delete_item)
        _popup(menu, self.more_button)

    def _row_actions(self, row):
        out = []
        if self.ctx.can(Permission.EDIT_RECORDS):
            out.append(("Correct…", lambda r=row: self._edit_movement(r)))
        if self.ctx.can(Permission.DELETE_RECORDS):
            out.append(("Delete…", lambda r=row: self._delete_movement(r)))
        return out

    def _reload(self) -> None:
        if self.item is not None:
            self.load(self.item.id)
            self.view.items.reload()

    def _edit_item(self) -> None:
        if item_actions.edit_item(self, self.ctx, self.item.id):
            self._reload()

    def _category(self) -> None:
        if item_actions.set_category(self, self.ctx, self.item.id):
            self._reload()

    def _add_movement(self) -> None:
        if item_actions.add_movement(self, self.ctx, self.item.id):
            self._reload()

    def _edit_movement(self, row) -> None:
        if item_actions.edit_movement(self, self.ctx, row[6]):
            self._reload()

    def _delete_movement(self, row) -> None:
        if item_actions.delete_movement(self, self.ctx, row[6]):
            self._reload()

    def _delete_item(self) -> None:
        if item_actions.delete_item(self, self.ctx, self.item.id):
            self.item = None
            self.pack_forget()
            self.view.items.empty.pack(expand=True)
            self.view.items.reload()
