"""Entry with a filtered suggestion list.  Suggestions are (key, label) pairs."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from hth.ui import theme

Suggestion = tuple[Any, str]


def rank_matches(term: str, data: list[Suggestion]) -> list[Suggestion]:
    """Suggestions containing every word of ``term`` (any order), best first.

    "ram rohtak" finds "12 RAM KUMAR ROHTAK".  Order: exact id, label starting with the
    term, a word starting with it, then the rest - each group in the original order."""
    words = term.lower().split()
    if not words:
        return []
    out = []
    for pos, (key, label) in enumerate(data):
        low = label.lower()
        if not all(w in low for w in words):
            continue
        head = low.split(" ", 1)
        if str(key).lower() == term.strip().lower() or head[0] == words[0]:
            rank = 0
        elif len(head) > 1 and head[1].startswith(term):
            rank = 1
        elif any(part.startswith(words[0]) for part in low.split()):
            rank = 2
        else:
            rank = 3
        out.append((rank, pos, (key, label)))
    out.sort(key=lambda t: (t[0], t[1]))
    return [s for _r, _p, s in out]


class SearchBox(ctk.CTkFrame):
    MAX_ROWS = 8

    def __init__(
        self,
        master,
        fetch: Callable[[], list[Suggestion]],
        placeholder: str = "Type to search...",
        on_select: Callable[[Any, str], None] | None = None,
        allow_free_text: bool = False,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._fetch = fetch
        self._data: list[Suggestion] = []
        self._filtered: list[Suggestion] = []
        self._on_select = on_select
        self._allow_free_text = allow_free_text
        self._selected_key: Any = None

        self.var = tk.StringVar()
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.var,
            placeholder_text=placeholder,
            font=theme.font(13),
            height=36,
        )
        self.entry.pack(fill="x")
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", lambda e: self.after(150, self._maybe_hide))
        self.entry.bind("<Down>", self._focus_list)
        self.entry.bind("<Escape>", lambda e: self.hide())
        self.entry.bind("<Return>", self._on_return)

        self._listbox: tk.Listbox | None = None

    # Data ---------------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            self._data = list(self._fetch())
        except Exception:  # noqa: BLE001 - never let a data error break typing
            self._data = []

    def get_key(self) -> Any:
        """Key of the chosen suggestion, or None when the text is not an exact label."""
        text = self.var.get().strip()
        for key, label in self._data:
            if label == text:
                return key
        return None

    def get_text(self) -> str:
        return self.var.get().strip()

    def set(self, key: Any = None, text: str | None = None) -> None:
        if key is not None:
            for k, label in self._data:
                if k == key:
                    self.var.set(label)
                    self._selected_key = k
                    return
        self.var.set(text or "")
        self._selected_key = None

    def clear(self) -> None:
        self.var.set("")
        self._selected_key = None
        self.hide()

    # Events -------------------------------------------------------------------------
    def _on_focus_in(self, _event=None) -> None:
        self.refresh()

    def _on_key(self, event) -> None:
        if event.keysym in ("Return", "Up", "Down", "Escape", "Tab"):
            return
        term = self.var.get().strip().lower()
        if not term:
            self.hide()
            return
        self._filtered = rank_matches(term, self._data)[:200]
        if self._filtered:
            self._show()
        else:
            self.hide()

    def _on_return(self, _event=None):
        if self._listbox is not None and self._filtered:
            self._choose(0)
            return "break"
        return None

    def _focus_list(self, _event=None):
        if self._listbox is not None:
            self._listbox.focus_set()
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(0)
            self._listbox.activate(0)
        return "break"

    def _show(self) -> None:
        top = self.winfo_toplevel()
        if self._listbox is None:
            self._listbox = tk.Listbox(
                top,
                font=(theme.FONT_FAMILY, 12),
                bg=theme.current("surface"),
                fg=theme.current("text"),
                selectbackground=theme.current("select"),
                selectforeground=theme.current("text"),
                highlightthickness=1,
                highlightbackground=theme.current("surface3"),
                relief="flat",
                activestyle="none",
                exportselection=False,
            )
            self._listbox.bind("<Return>", lambda e: self._choose_active())
            self._listbox.bind("<Double-Button-1>", lambda e: self._choose_active())
            self._listbox.bind("<Escape>", lambda e: self.hide())
            self._listbox.bind("<FocusOut>", lambda e: self.after(150, self._maybe_hide))
        self._listbox.delete(0, tk.END)
        for _, label in self._filtered:
            self._listbox.insert(tk.END, label)
        rows = min(len(self._filtered), self.MAX_ROWS)
        self._listbox.configure(height=rows)
        self.update_idletasks()
        x = self.entry.winfo_rootx() - top.winfo_rootx()
        y = self.entry.winfo_rooty() - top.winfo_rooty() + self.entry.winfo_height()
        self._listbox.place(in_=top, x=x, y=y, width=self.entry.winfo_width())
        self._listbox.lift()

    def _choose_active(self) -> None:
        if self._listbox is None:
            return
        sel = self._listbox.curselection()
        self._choose(sel[0] if sel else 0)

    def _choose(self, index: int) -> None:
        if not (0 <= index < len(self._filtered)):
            return
        key, label = self._filtered[index]
        self.var.set(label)
        self._selected_key = key
        self.hide()
        self.entry.focus_set()
        self.entry.icursor(tk.END)
        if self._on_select:
            self._on_select(key, label)

    def _maybe_hide(self) -> None:
        focused = self.focus_get()
        if focused is not self._listbox and focused is not self.entry._entry:  # noqa: SLF001
            self.hide()

    def hide(self) -> None:
        if self._listbox is not None:
            self._listbox.place_forget()
            self._listbox.destroy()
            self._listbox = None
