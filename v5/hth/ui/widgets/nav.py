"""Sidebar navigation item: icon, label and a muted shortcut hint, with an active state."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from hth.ui import icons, theme


class NavItem(ctk.CTkFrame):
    def __init__(self, master, key: str, label: str, hint: str, command: Callable[[], None]):
        super().__init__(master, fg_color="transparent", corner_radius=8, height=40, cursor="hand2")
        self.key, self.label_text, self.command = key, label, command
        self._active = False
        self._compact = False
        self.pack_propagate(False)
        self.bar = ctk.CTkFrame(self, width=4, height=22, corner_radius=2, fg_color="transparent")
        self.bar.pack(side="left", padx=(2, 0))
        self.icon = ctk.CTkLabel(
            self, text=icons.icon(key), font=icons.font(16), width=34, text_color=theme.color("sidebar_text")
        )
        self.icon.pack(side="left", padx=(6, 4))
        self.text = ctk.CTkLabel(
            self, text=label, font=theme.font(13), anchor="w", text_color=theme.color("sidebar_text")
        )
        self.text.pack(side="left", fill="x", expand=True)
        self.hint = ctk.CTkLabel(
            self, text=hint, font=theme.font(10), text_color=theme.color("sidebar_muted"), width=44
        )
        self.hint.pack(side="right", padx=(0, 8))
        for w in (self, self.bar, self.icon, self.text, self.hint):
            w.bind("<Button-1>", lambda e: self.command())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on: bool) -> None:
        if not self._active:
            self.configure(fg_color=theme.color("sidebar_hover") if on else "transparent")

    def set_active(self, on: bool) -> None:
        self._active = on
        self.configure(fg_color=theme.color("sidebar_active") if on else "transparent")
        self.bar.configure(fg_color=theme.color("sidebar_accent") if on else "transparent")
        color = theme.color("sidebar_accent") if on else theme.color("sidebar_text")
        self.icon.configure(text_color=color)
        self.text.configure(text_color=theme.color("sidebar_text"), font=theme.font(13, "bold" if on else "normal"))

    def set_compact(self, compact: bool) -> None:
        """Icon-only mode for narrow screens."""
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            self.text.pack_forget()
            self.hint.pack_forget()
        else:
            self.text.pack(side="left", fill="x", expand=True)
            self.hint.pack(side="right", padx=(0, 8))
