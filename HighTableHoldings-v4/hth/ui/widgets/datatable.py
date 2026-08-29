"""Sortable, striped ttk.Treeview that looks at home next to customtkinter widgets."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from tkinter import ttk
from typing import Any

import customtkinter as ctk

from hth.ui import theme
from hth.ui.format import money, qty


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    width: int = 120
    anchor: str = "w"
    kind: str = "text"  # text | money | qty | int
    stretch: bool = False


def _fmt(value: Any, kind: str) -> str:
    if value is None:
        return ""
    if kind == "money":
        return money(value) if value != "" else ""
    if kind == "qty":
        return qty(value) if value != "" else ""
    if kind == "int":
        return "" if value == "" else str(int(float(value)))
    return str(value)


def _sort_key(value: Any, kind: str):
    if value is None or value == "":
        return (1, 0)
    if kind in ("money", "qty", "int"):
        try:
            return (0, float(value))
        except (TypeError, ValueError):
            return (1, 0)
    return (0, str(value).lower())


class DataTable(ctk.CTkFrame):
    def __init__(
        self,
        master,
        columns: Sequence[Column],
        on_double_click: Callable[[Sequence[Any]], None] | None = None,
        on_select: Callable[[Sequence[Any] | None], None] | None = None,
        row_tags: Callable[[Sequence[Any]], Sequence[str]] | None = None,
        height: int | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=8, **kwargs)
        self.columns = list(columns)
        self._rows: list[Sequence[Any]] = []
        self._on_double_click = on_double_click
        self._on_select = on_select
        self._row_tags = row_tags
        self._sort_col: int | None = None
        self._sort_desc = False

        self.tree = ttk.Treeview(
            self,
            columns=[c.key for c in self.columns],
            show="headings",
            style="HTH.Treeview",
            selectmode="browse",
            height=height or 20,
        )
        for idx, col in enumerate(self.columns):
            self.tree.heading(col.key, text=col.title, anchor=col.anchor, command=lambda i=idx: self.sort_by(i))
            self.tree.column(col.key, width=col.width, minwidth=40, anchor=col.anchor, stretch=col.stretch)
        vsb = ctk.CTkScrollbar(self, command=self.tree.yview)
        hsb = ctk.CTkScrollbar(self, command=self.tree.xview, orientation="horizontal")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(6, 0))
        vsb.grid(row=0, column=1, sticky="ns", pady=(6, 0))
        hsb.grid(row=1, column=0, sticky="ew", padx=(6, 0))
        self.footer = ctk.CTkLabel(self, text="", anchor="w", font=theme.font(12), text_color=theme.color("muted"))
        self.footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 6))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._dbl)
        self.tree.bind("<<TreeviewSelect>>", self._sel)
        self.restyle()

    # Styling -------------------------------------------------------------------------
    def restyle(self) -> None:
        self.tree.tag_configure("odd", background=theme.current("stripe"))
        self.tree.tag_configure("even", background=theme.current("surface"))
        self.tree.tag_configure("neg", foreground=theme.current("danger"))
        self.tree.tag_configure("pos", foreground=theme.current("success"))
        self.tree.tag_configure("warn", foreground=theme.current("warning"))
        self.tree.tag_configure("muted", foreground=theme.current("muted"))
        self.tree.tag_configure("bold", font=(theme.FONT_FAMILY, 12, "bold"))

    # Data ----------------------------------------------------------------------------
    def set_rows(self, rows: Sequence[Sequence[Any]], footer: str | None = None) -> None:
        self._rows = [tuple(r) for r in rows]
        self._sort_col = None
        self._render()
        if footer is not None:
            self.footer.configure(text=footer)

    def set_footer(self, text: str) -> None:
        self.footer.configure(text=text)

    def clear(self) -> None:
        self.set_rows([], "")

    @property
    def rows(self) -> list[Sequence[Any]]:
        return list(self._rows)

    def selected_row(self) -> Sequence[Any] | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self._rows[int(sel[0])]

    def select_first(self) -> None:
        kids = self.tree.get_children()
        if kids:
            self.tree.selection_set(kids[0])

    def sort_by(self, col_index: int) -> None:
        if self._sort_col == col_index:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col, self._sort_desc = col_index, False
        kind = self.columns[col_index].kind
        self._rows.sort(key=lambda r: _sort_key(r[col_index], kind), reverse=self._sort_desc)
        self._render()

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self._rows):
            tags = ["odd" if i % 2 else "even"]
            if self._row_tags:
                tags.extend(self._row_tags(row))
            # Rows may carry hidden trailing values (ids used by double-click handlers),
            # so only the first len(columns) values are rendered.
            values = [_fmt(v, c.kind) for v, c in zip(row, self.columns, strict=False)]
            self.tree.insert("", "end", iid=str(i), values=values, tags=tags)
        for idx, col in enumerate(self.columns):
            marker = ""
            if idx == self._sort_col:
                marker = " ▼" if self._sort_desc else " ▲"
            self.tree.heading(col.key, text=col.title + marker)

    def export_columns(self) -> list[str]:
        return [c.title for c in self.columns]

    def export_rows(self) -> list[list[Any]]:
        return [list(r[: len(self.columns)]) for r in self._rows]

    # Events --------------------------------------------------------------------------
    def _dbl(self, _event) -> None:
        row = self.selected_row()
        if row is not None and self._on_double_click:
            self._on_double_click(row)

    def _sel(self, _event) -> None:
        if self._on_select:
            self._on_select(self.selected_row())
