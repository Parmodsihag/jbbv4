"""Transient bottom-right notifications."""

from __future__ import annotations

import customtkinter as ctk

from hth.ui import theme

KIND_COLORS = {
    "info": "accent",
    "success": "success",
    "error": "danger",
    "warning": "warning",
}


class ToastHost:
    def __init__(self, root):
        self.root = root
        self._label: ctk.CTkLabel | None = None
        self._job = None

    def show(self, message: str, kind: str = "info", ms: int = 3500) -> None:
        self.hide()
        color = theme.color(KIND_COLORS.get(kind, "accent"))
        self._label = ctk.CTkLabel(
            self.root,
            text=f"  {message}  ",
            font=theme.font(13, "bold"),
            fg_color=color,
            text_color=theme.color("on_status"),
            corner_radius=8,
            height=40,
        )
        self._label.place(relx=0.99, rely=0.965, anchor="se")
        self._label.lift()
        self._job = self.root.after(ms, self.hide)

    def hide(self) -> None:
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None
        if self._label is not None:
            self._label.destroy()
            self._label = None
