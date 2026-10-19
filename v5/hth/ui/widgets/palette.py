"""Ctrl+K search palette."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from hth.services.search import SearchHit, SearchService
from hth.ui import theme


class SearchPalette(ctk.CTkToplevel):
    def __init__(self, parent, service: SearchService, kinds: set[str], on_pick: Callable[[SearchHit], None]):
        super().__init__(parent)
        self.service, self.kinds, self.on_pick = service, kinds, on_pick
        self.hits: list[SearchHit] = []
        self.overrideredirect(True)
        self.configure(fg_color=theme.color("surface"))
        w, h = 640, 360
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + 90
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        frame = ctk.CTkFrame(
            self,
            fg_color=theme.color("surface"),
            corner_radius=12,
            border_width=1,
            border_color=theme.color("surface3"),
        )
        frame.pack(fill="both", expand=True)
        self.var = tk.StringVar()
        self.entry = ctk.CTkEntry(
            frame,
            textvariable=self.var,
            placeholder_text="Search accounts, items, bills…  (Esc to close)",
            font=theme.font(15),
            height=42,
        )
        self.entry.pack(fill="x", padx=12, pady=(12, 6))
        self.listbox = tk.Listbox(
            frame,
            font=(theme.FONT_FAMILY, 13),
            bg=theme.current("surface"),
            fg=theme.current("text"),
            selectbackground=theme.current("select"),
            selectforeground=theme.current("text"),
            relief="flat",
            highlightthickness=0,
            activestyle="none",
            exportselection=False,
        )
        self.listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.var.trace_add("write", lambda *_: self.refresh())
        for w_ in (self.entry, self.listbox, self):
            w_.bind("<Escape>", lambda e: self.close())
        self.entry.bind("<Return>", lambda e: self.pick())
        self.entry.bind("<Down>", lambda e: self._move(1))
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.listbox.bind("<Return>", lambda e: self.pick())
        self.listbox.bind("<Double-Button-1>", lambda e: self.pick())
        self.bind("<FocusOut>", lambda e: self.after(150, self._maybe_close))
        self.after(50, self.entry.focus_set)
        self.grab_set()

    def refresh(self) -> None:
        self.hits = self.service.search(self.var.get(), kinds=self.kinds)
        self.listbox.delete(0, tk.END)
        for h in self.hits:
            self.listbox.insert(tk.END, h.label)
        if self.hits:
            self.listbox.selection_set(0)

    def _move(self, delta: int) -> str:
        if not self.hits:
            return "break"
        cur = self.listbox.curselection()
        idx = (cur[0] if cur else 0) + delta
        idx = max(0, min(len(self.hits) - 1, idx))
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.see(idx)
        return "break"

    def pick(self) -> None:
        cur = self.listbox.curselection()
        if not cur or not self.hits:
            return
        hit = self.hits[cur[0]]
        self.close()
        self.on_pick(hit)

    def _maybe_close(self) -> None:
        try:
            focused = self.focus_get()
        except Exception:  # noqa: BLE001
            focused = None
        if focused is None or focused.winfo_toplevel() is not self:
            self.close()

    def close(self) -> None:
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()
