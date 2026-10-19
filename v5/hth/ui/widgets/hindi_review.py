"""Review and correct the Hindi copies of customer and item names."""

from __future__ import annotations

import customtkinter as ctk

from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, run_form


class HindiReview(ctk.CTkToplevel):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.title("Hindi names")
        self.geometry("1000x640")
        self.configure(fg_color=theme.color("bg"))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(12, 4))
        self.kind = ctk.CTkSegmentedButton(
            bar, values=["Customers", "Items"], command=lambda _v: self.reload(), font=theme.font(12)
        )
        self.kind.set("Customers")
        self.kind.pack(side="left")
        self.only_auto = ctk.CTkCheckBox(
            bar, text="Only automatic (not yet checked)", font=theme.font(12), command=self.reload
        )
        self.only_auto.pack(side="left", padx=12)
        self.find = ctk.CTkEntry(bar, placeholder_text="Find…", width=220, height=32, font=theme.font(12))
        self.find.pack(side="right")
        self.find.bind("<KeyRelease>", lambda e: self.table.filter(self.find.get()))
        self.table = DataTable(
            self,
            [
                Column("id", "ID", 60, "e", "int"),
                Column("en", "English", 300, "w", "raw", stretch=True),
                Column("hi", "Hindi", 300, stretch=True),
                Column("details", "Details (Hindi)", 220),
                Column("manual", "Checked", 80, "center"),
            ],
            on_double_click=self.edit,
            row_tags=lambda r: [] if r[4] == "✓" else ["muted"],
        )
        self.table.pack(fill="both", expand=True, padx=14, pady=4)
        ctk.CTkLabel(
            self,
            text="Double-click a row to correct it. A corrected name is marked ✓ and is never regenerated.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(anchor="w", padx=14, pady=(0, 12))
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())
        self.reload()

    def reload(self) -> None:
        kind = "customer" if self.kind.get() == "Customers" else "item"
        rows = [r for r in self.ctx.hindi.rows() if r.kind == kind]
        if self.only_auto.get():
            rows = [r for r in rows if not r.manual]
        self.table.set_rows(
            [(r.id, r.english, r.hindi, r.details_hi, "✓" if r.manual else "", r.kind) for r in rows],
            f"{len(rows)} {self.kind.get().lower()}",
        )
        if self.find.get():
            self.table.filter(self.find.get())

    def edit(self, row) -> None:
        if not self.ctx.can(Permission.EDIT_RECORDS):
            self.ctx.toast("Only an administrator can correct names", "warning")
            return
        record_id, english, hindi, details_hi, _manual, kind = row
        fields = [Field("hindi", f"Hindi for: {english}", default=hindi)]
        if kind == "customer":
            fields.append(Field("details", "Details in Hindi", default=details_hi))
        fields.append(Field("mode", "Save as", "option", "My correction", ["My correction", "Back to automatic"]))

        def submit(v):
            if v["mode"] == "Back to automatic":
                self.ctx.hindi.reset(kind, record_id, self.ctx.username)
            elif kind == "customer":
                self.ctx.hindi.set_customer(record_id, v["hindi"], v.get("details", ""), self.ctx.username)
            else:
                self.ctx.hindi.set_item(record_id, v["hindi"], self.ctx.username)

        try:
            if run_form(self, "Correct Hindi name", fields, submit):
                self.ctx.app.refresh_names()
                self.reload()
        except ValidationError as exc:
            self.ctx.toast(str(exc), "error")
