"""Colour-theme chooser: one clickable miniature window per theme."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from hth.ui import theme

COLUMNS = 4


class ThemePicker(ctk.CTkFrame):
    def __init__(self, master, selected: str, on_pick: Callable[[str], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_pick = on_pick
        self._selected = ""
        self._tiles: dict[str, ctk.CTkFrame] = {}
        self._names: dict[str, ctk.CTkLabel] = {}
        for i, t in enumerate(theme.THEMES.values()):
            self._tile(t).grid(row=i // COLUMNS, column=i % COLUMNS, sticky="nsew", padx=(0, 10), pady=(0, 10))
        for col in range(COLUMNS):
            self.grid_columnconfigure(col, weight=1, uniform="tile")
        self.select(selected)

    def _tile(self, t: theme.Theme) -> ctk.CTkFrame:
        # The miniature uses the theme's own fixed (light, dark) pairs, not the live palette,
        # so each tile always shows *that* theme - in whichever mode is on.
        c = t.colors
        tile = ctk.CTkFrame(self, fg_color=theme.color("bg"), border_width=2, corner_radius=10)
        window = ctk.CTkFrame(tile, fg_color=c["bg"], corner_radius=7, height=78)
        window.pack(fill="x", padx=8, pady=(8, 6))
        window.pack_propagate(False)

        top = ctk.CTkFrame(window, fg_color=c["topbar"], corner_radius=4, height=14)
        top.pack(fill="x", padx=5, pady=(5, 0))
        top.pack_propagate(False)
        ctk.CTkFrame(top, fg_color=c["accent"], corner_radius=3, width=10, height=8).pack(side="left", padx=4)
        for w in (20, 16, 18):
            ctk.CTkFrame(top, fg_color=c["muted"], corner_radius=2, width=w, height=3).pack(side="left", padx=2)

        card = ctk.CTkFrame(window, fg_color=c["surface"], corner_radius=5, border_width=1, border_color=c["line"])
        card.pack(fill="both", expand=True, padx=5, pady=5)
        for key, h, w, top_pad in (("text", 5, 64, 7), ("muted", 4, 42, 4)):
            line = ctk.CTkFrame(card, fg_color=c[key], corner_radius=2, height=h, width=w)
            line.pack(anchor="w", padx=8, pady=(top_pad, 0))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkFrame(row, fg_color=c["accent"], corner_radius=4, height=13, width=36).pack(side="left")
        for k in ("weowe", "warning", "owe"):
            ctk.CTkFrame(row, fg_color=c[k], corner_radius=5, height=10, width=10).pack(side="left", padx=(6, 0))

        name = ctk.CTkLabel(tile, text=t.name, font=theme.font(13, "bold"), anchor="w")
        name.pack(fill="x", padx=12)
        ctk.CTkLabel(
            tile,
            text=t.blurb,
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=150,
        ).pack(fill="x", padx=12, pady=(0, 10))
        self._tiles[t.key] = tile
        self._names[t.key] = name
        self._clickable(tile, t.key)
        return tile

    def _clickable(self, widget: tk.Misc, key: str) -> None:
        # Raw tk bind on every widget in the tile, so a click lands on exactly one of them
        # (CTk's own bind() forwards to an inner canvas this walk reaches as well).
        tk.Misc.bind(widget, "<Button-1>", lambda _e: self._pick(key), "+")
        tk.Misc.configure(widget, cursor="hand2")
        for child in widget.winfo_children():
            self._clickable(child, key)

    def _pick(self, key: str) -> None:
        if key != self._selected:
            self.select(key)
            self._on_pick(key)

    def select(self, key: str) -> None:
        self._selected = key
        for k, tile in self._tiles.items():
            on = k == key
            tile.configure(border_color=theme.color("accent") if on else theme.color("line"))
            self._names[k].configure(text=f"{theme.THEMES[k].name}   ✓" if on else theme.THEMES[k].name)
