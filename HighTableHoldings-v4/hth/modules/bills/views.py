"""Bills screen: new invoice, month batch, browse."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.domain.constants import ITEM_TYPES
from hth.domain.units import ALL_UNITS
from hth.modules.bills.service import (
    DEFAULT_ADDRESS,
    MAX_RENDER_TOTAL,
    BillsService,
    compute_line,
    totals,
    word_available,
)
from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money, open_path
from hth.ui.format import qty as fmt_qty
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import confirm, info
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


class BillsView(BaseView):
    key = "bills"
    title = "Bills"
    permission = Permission.BILLING

    def build(self) -> None:
        self.svc = BillsService(self.ctx.db, self.ctx.settings)
        self.tabs = ctk.CTkTabview(
            self, fg_color=theme.color("surface"), corner_radius=10, segmented_button_font=theme.font(13, "bold")
        )
        self.tabs.pack(fill="both", expand=True, padx=4, pady=4)
        self.tabs.add("New invoice")
        self.tabs.add("Browse")
        if self.ctx.can(Permission.BILLING_BATCH):
            self.tabs.add("Month batch")
            self.batch = BatchPanel(self.tabs.tab("Month batch"), self)
            self.batch.pack(fill="both", expand=True)
        self.new = NewInvoicePanel(self.tabs.tab("New invoice"), self)
        self.new.pack(fill="both", expand=True)
        self.browse = BrowsePanel(self.tabs.tab("Browse"), self)
        self.browse.pack(fill="both", expand=True)

    def on_show(self, **kwargs) -> None:
        self.new.refresh()
        self.browse.reload()
        if hasattr(self, "batch"):
            self.batch.reload()

    def on_theme_change(self) -> None:
        for panel in (self.new, self.browse, getattr(self, "batch", None)):
            if panel is not None:
                for t in panel.tables():
                    t.restyle()


# ------------------------------------------------------------------------------------------
class NewInvoicePanel(ctk.CTkFrame):
    def __init__(self, master, view: BillsView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        self._lines: list[dict] = []
        self._item = None
        self.grid_columnconfigure(0, weight=2, uniform="b")
        self.grid_columnconfigure(1, weight=3, uniform="b")
        self.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        head = ctk.CTkFrame(form, fg_color="transparent")
        head.pack(fill="x")
        head.grid_columnconfigure((0, 1), weight=1)
        self.number = LabeledEntry(head, "Bill number")
        self.number.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.date = DateField(head)
        self.date.grid(row=0, column=1, sticky="ew")
        cust = LabeledWidget(form, "Customer (from accounts, optional)")
        cust.pack(fill="x", pady=3)
        self.customer = SearchBox(
            cust.body,
            lambda: [(c.id, c.display) for c in self.ctx.accounts.list_customers()],
            "Search account",
            on_select=self._on_customer,
        )
        self.customer.pack(fill="x")
        self.name = LabeledEntry(form, "Name on bill")
        self.name.pack(fill="x", pady=3)
        self.address = LabeledEntry(form, "Address", default=DEFAULT_ADDRESS)
        self.address.pack(fill="x", pady=3)

        ctk.CTkLabel(
            form, text="ADD ITEM", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x", pady=(10, 0))
        it = LabeledWidget(form, "Item (from stock, or type a name)")
        it.pack(fill="x", pady=3)
        self.item = SearchBox(
            it.body,
            lambda: [(i.id, i.display) for i in self.ctx.inventory.list_items()],
            "Search item",
            on_select=self._on_item,
            allow_free_text=True,
        )
        self.item.pack(fill="x")
        g = ctk.CTkFrame(form, fg_color="transparent")
        g.pack(fill="x")
        g.grid_columnconfigure((0, 1, 2), weight=1)
        self.qty = LabeledEntry(g, "Quantity", placeholder="0")
        self.qty.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.unit = LabeledOption(g, "Unit", ALL_UNITS, "PCS")
        self.unit.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.rate = LabeledEntry(g, "Rate", placeholder="0.00")
        self.rate.grid(row=0, column=2, sticky="ew", pady=3)
        self.item_type = LabeledOption(g, "Type (P 18% · F 5% · S/O 0%)", ITEM_TYPES, "O")
        self.item_type.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.batch = LabeledEntry(g, "Batch", default="NA")
        self.batch.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.expiry = LabeledEntry(g, "Expiry", default="NA")
        self.expiry.grid(row=1, column=2, sticky="ew", pady=3)
        secondary_button(form, "+ Add line", self.add_line).pack(fill="x", pady=(6, 0))
        self.qty.entry.bind("<Return>", lambda e: self.add_line())
        self.rate.entry.bind("<Return>", lambda e: self.add_line())

        right = Card(self)
        right.grid(row=0, column=1, sticky="nsew")
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bar, text="Invoice lines", font=theme.font(17, "bold")).pack(side="left")
        danger_button(bar, "Remove line", self.remove_line, width=110).pack(side="right")
        secondary_button(bar, "Clear", self.clear, width=70).pack(side="right", padx=6)
        self.table = DataTable(
            right,
            [
                Column("n", "#", 40, "e", "int"),
                Column("name", "Item", 220, stretch=True),
                Column("qty", "Qty", 70, "e", "qty"),
                Column("unit", "Unit", 60),
                Column("rate", "Rate", 90, "e", "money"),
                Column("amount", "Amount", 100, "e", "money"),
                Column("type", "T", 40, "center"),
                Column("gst", "GST%", 60, "e", "qty"),
                Column("cgst", "CGST", 90, "e", "money"),
                Column("sgst", "SGST", 90, "e", "money"),
            ],
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        self.total_label = ctk.CTkLabel(right, text="", font=theme.font(15, "bold"), anchor="w")
        self.total_label.pack(fill="x", padx=14)
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(6, 12))
        primary_button(actions, "Save & create DOCX", self.save, width=170).pack(side="left")
        if word_available():
            primary_button(actions, "Save & make PDF", lambda: self.save(pdf=True), width=150).pack(side="left", padx=8)
        ctk.CTkLabel(
            actions,
            text=f"Bills of {money(MAX_RENDER_TOTAL)} or more are flagged (cash-sale limit).",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="right")

    def tables(self):
        return [self.table]

    def refresh(self) -> None:
        self.customer.refresh()
        self.item.refresh()
        if not self.number.get():
            self.number.set(str(self.svc.next_bill_number()))

    def _on_customer(self, cid, _label) -> None:
        c = self.ctx.accounts.get_customer(cid)
        if c:
            self.name.set(c.name)
            if c.other_details:
                self.address.set(c.other_details)

    def _on_item(self, item_id, _label) -> None:
        item = self.ctx.inventory.get_item(item_id)
        self._item = item
        if item is None:
            return
        self.unit.set(item.unit)
        self.rate.set(f"{item.last_value:g}")
        self.item_type.set(item.item_type if item.item_type in ITEM_TYPES else "O")
        self.batch.set(item.batch)
        self.expiry.set(item.expiry_date)
        self.qty.focus()

    def add_line(self) -> None:
        name = self.item.get_text()
        if self._item is not None and self.item.get_key() == self._item.id:
            name = self._item.name
        try:
            line = compute_line(
                name,
                self.unit.get(),
                self.batch.get(),
                self.expiry.get(),
                self.rate.get() or 0,
                self.item_type.get(),
                self.qty.get() or 0,
            )
        except (ValidationError, ValueError) as exc:
            self.ctx.toast(str(exc), "error")
            return
        if not line.name:
            self.ctx.toast("Item name is required", "error")
            return
        self._lines.append(
            dict(
                name=line.name,
                unit=line.unit,
                batch=line.batch,
                expiry_date=line.expiry_date,
                rate=line.rate,
                item_type=line.item_type,
                quantity=line.quantity,
            )
        )
        self.item.clear()
        self._item = None
        self.qty.set("")
        self._render()
        self.item.entry.focus_set()

    def remove_line(self) -> None:
        row = self.table.selected_row()
        if row is None:
            return
        del self._lines[int(row[0]) - 1]
        self._render()

    def clear(self) -> None:
        self._lines = []
        self.customer.clear()
        self.name.set("")
        self.address.set(DEFAULT_ADDRESS)
        self.number.set(str(self.svc.next_bill_number()))
        self.date.set_today()
        self._render()

    def _render(self) -> None:
        computed = [compute_line(**line) for line in self._lines]
        rows = [
            (i + 1, x.name, x.quantity, x.unit, x.rate, x.amount, x.item_type, x.gst_rate, x.cgst, x.sgst)
            for i, x in enumerate(computed)
        ]
        taxable, cgst, sgst, grand = totals(computed)
        self.table.set_rows(rows, f"{len(rows)} lines")
        self.total_label.configure(
            text=f"Taxable {money(taxable)}   CGST {money(cgst)}   SGST {money(sgst)}   Total {money(grand)}",
            text_color=theme.color("danger") if grand >= MAX_RENDER_TOTAL else theme.color("text"),
        )

    def save(self, pdf: bool = False) -> None:
        try:
            number = int(self.number.get()) if self.number.get() else None
            bill = self.svc.create_bill(
                self.date.get(),
                self.name.get(),
                self.address.get(),
                self._lines,
                self.ctx.username,
                bill_number=number,
                customer_id=self.customer.get_key(),
            )
            path = self.svc.render_pdf(bill) if pdf else self.svc.render_docx(bill)
        except (ValidationError, ValueError) as exc:
            self.ctx.toast(str(exc), "error")
            return
        except Exception as exc:  # noqa: BLE001 - Word / template problems
            self.ctx.toast(f"Bill saved but not rendered: {exc}", "warning")
            self.clear()
            self.view.browse.reload()
            return
        self.ctx.toast(f"Bill {bill.bill_number} saved · {money(bill.grand_total)}", "success")
        self.clear()
        self.view.browse.reload()
        if confirm(self, "Bill created", f"Saved {path.name}\n\nOpen it now?"):
            open_path(path)


# ------------------------------------------------------------------------------------------
class BrowsePanel(ctk.CTkFrame):
    def __init__(self, master, view: BillsView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 4))
        ctk.CTkLabel(bar, text="Month", font=theme.font(12), text_color=theme.color("muted")).pack(side="left")
        self.month = ctk.CTkOptionMenu(
            bar, values=["All"], font=theme.font(13), height=34, width=120, command=lambda _v: self.reload()
        )
        self.month.pack(side="left", padx=(6, 12))
        self.search = ctk.CTkEntry(
            bar, placeholder_text="Bill number or name…", width=220, height=34, font=theme.font(13)
        )
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda e: self.reload())
        if self.ctx.can(Permission.DELETE_RECORDS):
            danger_button(bar, "Delete bill", self.delete_bill, width=100).pack(side="right")
        secondary_button(bar, "Open folder", lambda: open_path(self.svc.open_folder()), width=100).pack(
            side="right", padx=6
        )
        secondary_button(bar, "Open DOCX", self.open_docx, width=100).pack(side="right", padx=6)
        if word_available():
            secondary_button(bar, "Make PDF", self.make_pdf, width=90).pack(side="right", padx=6)
            merge = ctk.CTkFrame(bar, fg_color="transparent")
            merge.pack(side="right", padx=6)
            self.m_from = ctk.CTkEntry(merge, placeholder_text="from no.", width=90, height=34, font=theme.font(12))
            self.m_from.pack(side="left")
            self.m_to = ctk.CTkEntry(merge, placeholder_text="to no.", width=90, height=34, font=theme.font(12))
            self.m_to.pack(side="left", padx=4)
            secondary_button(merge, "PDF + merge range", self.merge_range, width=140).pack(side="left")

        self.table = DataTable(
            self,
            [
                Column("no", "Bill", 90, "e", "int"),
                Column("date", "Date", 100),
                Column("name", "Customer", 200, stretch=True),
                Column("addr", "Address", 120),
                Column("taxable", "Taxable", 100, "e", "money"),
                Column("gst", "GST", 90, "e", "money"),
                Column("total", "Total", 110, "e", "money"),
                Column("src", "Source", 70),
                Column("docx", "DOCX", 60, "center"),
            ],
            on_select=lambda r: self._show_lines(r),
            row_tags=lambda r: ["neg"] if r[6] >= MAX_RENDER_TOTAL else [],
        )
        self.table.pack(fill="both", expand=True, pady=(0, 4))
        self.lines = DataTable(
            self,
            [
                Column("name", "Item", 220, stretch=True),
                Column("qty", "Qty", 70, "e", "qty"),
                Column("unit", "Unit", 60),
                Column("batch", "Batch", 90),
                Column("exp", "Expiry", 90),
                Column("rate", "Rate", 90, "e", "money"),
                Column("amount", "Amount", 100, "e", "money"),
                Column("gst", "GST%", 60, "e", "qty"),
                Column("cgst", "CGST", 90, "e", "money"),
                Column("sgst", "SGST", 90, "e", "money"),
            ],
            height=6,
        )
        self.lines.pack(fill="x")

    def tables(self):
        return [self.table, self.lines]

    def reload(self) -> None:
        months = ["All"] + self.svc.month_years()
        current = self.month.get() if self.month.get() in months else "All"
        self.month.configure(values=months)
        self.month.set(current)
        bills = self.svc.list_bills(None if current == "All" else current, self.search.get().strip() or None)
        rows = [
            (
                b.bill_number,
                b.date,
                b.customer_name,
                b.customer_address,
                b.taxable,
                round(b.cgst + b.sgst, 2),
                b.grand_total,
                b.source,
                "yes" if self.svc.docx_path(b) else "",
                b.id,
            )
            for b in bills
        ]
        total = sum(r[6] for r in rows)
        self.table.set_rows(rows, f"{len(rows)} bills · total {money(total)}")
        self.lines.clear()

    def _selected(self):
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select a bill first", "warning")
            return None
        return self.svc.get_bill(row[9])

    def _show_lines(self, row) -> None:
        if row is None:
            return
        bill = self.svc.get_bill(row[9])
        if bill:
            self.lines.set_rows(
                [
                    (x.name, x.quantity, x.unit, x.batch, x.expiry_date, x.rate, x.amount, x.gst_rate, x.cgst, x.sgst)
                    for x in bill.lines
                ],
                f"Bill {bill.bill_number} · {bill.customer_name} · {money(bill.grand_total)}",
            )

    def open_docx(self) -> None:
        bill = self._selected()
        if bill:
            try:
                open_path(self.svc.render_docx(bill))
            except Exception as exc:  # noqa: BLE001
                self.ctx.toast(f"Could not render: {exc}", "error")

    def make_pdf(self) -> None:
        bill = self._selected()
        if bill:
            try:
                open_path(self.svc.render_pdf(bill))
            except Exception as exc:  # noqa: BLE001
                self.ctx.toast(str(exc), "error")

    def merge_range(self) -> None:
        try:
            a, b = int(self.m_from.get()), int(self.m_to.get())
        except ValueError:
            self.ctx.toast("Enter from / to bill numbers", "error")
            return
        bills = [x for x in self.svc.list_bills(limit=100000) if a <= x.bill_number <= b]
        if not bills:
            self.ctx.toast("No bills in that range", "warning")
            return
        if not confirm(
            self,
            "PDF + merge",
            f"Make PDFs for {len(bills)} bills ({a}-{b}) and merge them?\n"
            "This uses Microsoft Word and can take a while.",
        ):
            return
        self.ctx.status("Making PDFs…")

        def work():
            for x in bills:
                self.svc.render_pdf(self.svc.get_bill(x.id))
            return self.svc.merge_pdfs(a, b)

        self.view.run_async(
            work,
            lambda p: (self.ctx.toast(f"Merged: {p.name}", "success"), open_path(p)),
            lambda e: self.ctx.toast(str(e), "error"),
        )

    def delete_bill(self) -> None:
        bill = self._selected()
        if bill and confirm(
            self, "Delete bill", f"Delete bill {bill.bill_number} ({bill.customer_name}, {money(bill.grand_total)})?"
        ):
            self.svc.delete_bill(bill.id, self.ctx.username)
            self.reload()


# ------------------------------------------------------------------------------------------
class BatchPanel(ctk.CTkFrame):
    def __init__(self, master, view: BillsView):
        super().__init__(master, fg_color="transparent")
        self.view, self.ctx, self.svc = view, view.ctx, view.svc
        self._item = None
        self.grid_columnconfigure(0, weight=2, uniform="m")
        self.grid_columnconfigure(1, weight=3, uniform="m")
        self.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        today = dt.date.today()
        self.month = LabeledEntry(form, "Month (YYYY-MM)", default=f"{today.year}-{today.month:02d}")
        self.month.pack(fill="x", pady=3)
        self.month.entry.bind("<FocusOut>", lambda e: self.reload())
        self.month.entry.bind("<Return>", lambda e: self.reload())
        ctk.CTkLabel(
            form, text="ITEMS SOLD THIS MONTH", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x", pady=(10, 0))
        it = LabeledWidget(form, "Item")
        it.pack(fill="x", pady=3)
        self.item = SearchBox(
            it.body,
            lambda: [(i.id, i.display) for i in self.ctx.inventory.list_items()],
            "Search item",
            on_select=self._on_item,
            allow_free_text=True,
        )
        self.item.pack(fill="x")
        g = ctk.CTkFrame(form, fg_color="transparent")
        g.pack(fill="x")
        g.grid_columnconfigure((0, 1, 2), weight=1)
        self.qty = LabeledEntry(g, "Total quantity", placeholder="0")
        self.qty.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.unit = LabeledOption(g, "Unit", ALL_UNITS, "PCS")
        self.unit.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.rate = LabeledEntry(g, "Rate", placeholder="0.00")
        self.rate.grid(row=0, column=2, sticky="ew", pady=3)
        self.item_type = LabeledOption(g, "Type", ITEM_TYPES, "O")
        self.item_type.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.batch = LabeledEntry(g, "Batch", default="NA")
        self.batch.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.expiry = LabeledEntry(g, "Expiry", default="NA")
        self.expiry.grid(row=1, column=2, sticky="ew", pady=3)
        self.start = LabeledEntry(
            form, "Sell from date (first day this item may appear)", default=f"{today.year}-{today.month:02d}-01"
        )
        self.start.pack(fill="x", pady=3)
        secondary_button(form, "+ Add item to month", self.add_item).pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(
            form, text="GENERATE", font=theme.font(12, "bold"), text_color=theme.color("muted"), anchor="w"
        ).pack(fill="x", pady=(14, 0))
        g2 = ctk.CTkFrame(form, fg_color="transparent")
        g2.pack(fill="x")
        g2.grid_columnconfigure((0, 1), weight=1)
        self.count = LabeledEntry(g2, "Number of bills", default="80")
        self.count.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.start_no = LabeledEntry(g2, "Start bill number")
        self.start_no.grid(row=0, column=1, sticky="ew", pady=3)
        primary_button(form, "Generate bills for month", self.generate).pack(fill="x", pady=(6, 0))
        danger_button(form, "Delete this month's bills", self.delete_month).pack(fill="x", pady=(6, 0))
        self.status = ctk.CTkLabel(
            form,
            text="",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            wraplength=380,
            justify="left",
        )
        self.status.pack(fill="x", pady=(8, 0))

        right = Card(self)
        right.grid(row=0, column=1, sticky="nsew")
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        self.title = ctk.CTkLabel(bar, text="Items for month", font=theme.font(17, "bold"))
        self.title.pack(side="left")
        danger_button(bar, "Remove item", self.remove_item, width=110).pack(side="right")
        self.table = DataTable(
            right,
            [
                Column("id", "ID", 50, "e", "int"),
                Column("name", "Item", 220, stretch=True),
                Column("qty", "Qty", 80, "e", "qty"),
                Column("unit", "Unit", 60),
                Column("rate", "Rate", 90, "e", "money"),
                Column("type", "T", 40, "center"),
                Column("from", "From", 100),
                Column("batch", "Batch", 90),
                Column("exp", "Expiry", 90),
                Column("value", "Value", 100, "e", "money"),
            ],
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def tables(self):
        return [self.table]

    def _on_item(self, item_id, _label) -> None:
        item = self.ctx.inventory.get_item(item_id)
        self._item = item
        if item:
            self.unit.set(item.unit)
            self.rate.set(f"{item.last_value:g}")
            self.item_type.set(item.item_type if item.item_type in ITEM_TYPES else "O")
            self.batch.set(item.batch)
            self.expiry.set(item.expiry_date)
            self.qty.focus()

    def reload(self) -> None:
        try:
            items = self.svc.month_items(self.month.get())
        except ValidationError:
            self.table.clear()
            return
        rows = [
            (
                i.id,
                i.name,
                i.quantity,
                i.unit,
                i.rate,
                i.item_type,
                i.start_date,
                i.batch,
                i.expiry_date,
                round(i.rate * i.quantity, 2),
            )
            for i in items
        ]
        n, taxable, gst, grand = self.svc.month_summary(self.month.get())
        self.table.set_rows(
            rows,
            f"{len(rows)} items · value {money(sum(r[9] for r in rows))}"
            f"   |   bills this month: {n} · total {money(grand)}",
        )
        self.title.configure(text=f"Items for {self.month.get()}")
        if not self.start_no.get():
            self.start_no.set(str(self.svc.next_bill_number()))
        self.start.set(f"{self.month.get()}-01" if len(self.month.get()) == 7 else self.start.get())

    def add_item(self) -> None:
        name = self.item.get_text()
        item_id = None
        if self._item is not None and self.item.get_key() == self._item.id:
            name, item_id = self._item.name, self._item.id
        try:
            self.svc.add_month_item(
                self.month.get(),
                name,
                self.unit.get(),
                self.rate.get() or 0,
                self.item_type.get(),
                self.start.get(),
                self.batch.get(),
                self.expiry.get(),
                self.qty.get() or 0,
                item_id=item_id,
                username=self.ctx.username,
            )
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.item.clear()
        self._item = None
        self.qty.set("")
        self.reload()

    def remove_item(self) -> None:
        row = self.table.selected_row()
        if row and confirm(self, "Remove", f"Remove {row[1]} from {self.month.get()}?"):
            self.svc.delete_month_item(row[0], self.ctx.username)
            self.reload()

    def generate(self) -> None:
        month = self.month.get()
        try:
            count, start_no = int(self.count.get()), int(self.start_no.get())
        except ValueError:
            self.ctx.toast("Number of bills and start number must be whole numbers", "error")
            return
        if not confirm(
            self,
            "Generate bills",
            f"Create about {count} bills for {month} starting at {start_no}\nand render each to DOCX?",
        ):
            return
        self.status.configure(text="Generating…")

        def progress(i, n):
            self.after(0, lambda: self.status.configure(text=f"Rendering {i}/{n}…"))

        self.view.run_async(
            lambda: self.svc.generate_month(month, count, start_no, self.ctx.username, progress=progress),
            self._done,
            lambda e: (self.status.configure(text=str(e)), self.ctx.toast(str(e), "error")),
        )

    def _done(self, res) -> None:
        msg = f"Created {res.created} bills ({res.first_number}-{res.last_number}), rendered {res.rendered}."
        if res.not_rendered:
            msg += f"\nNot rendered ({money(MAX_RENDER_TOTAL)}+): {', '.join(map(str, res.not_rendered))}"
        if res.unsold:
            msg += "\nLeft over: " + ", ".join(f"{k} {fmt_qty(v)}" for k, v in res.unsold.items())
        self.status.configure(text=msg)
        self.ctx.toast(f"{res.created} bills created", "success")
        self.start_no.set(str(self.svc.next_bill_number()))
        self.reload()
        self.view.browse.reload()
        info(self, "Batch complete", msg + f"\n\nFiles: {self.svc.open_folder()}")

    def delete_month(self) -> None:
        month = self.month.get()
        if not self.svc.bills_exist_for_month(month):
            self.ctx.toast(f"No bills for {month}", "warning")
            return
        if confirm(self, "Delete bills", f"Delete ALL bills for {month} and their DOCX/PDF files?"):
            n = self.svc.delete_month(month, self.ctx.username)
            self.ctx.toast(f"{n} bills deleted", "success")
            self.reload()
            self.view.browse.reload()
