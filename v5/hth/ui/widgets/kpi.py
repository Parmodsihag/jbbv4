"""Dashboard stat tile: title, big value, detail line; optionally clickable."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from hth.ui import theme


class KpiTile(ctk.CTkFrame):
    def __init__(
        self,
        master,
        title: str,
        value: str = "—",
        subtitle: str = "",
        accent: str = "accent",
        command: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10, height=96, **kwargs)
        self.pack_propagate(False)
        self.on_click = command
        # height must be set explicitly: a CTkFrame defaults to 200 px and would stretch the tile
        bar = ctk.CTkFrame(self, width=4, height=20, fg_color=theme.color(accent), corner_radius=2)
        bar.pack(side="left", fill="y", padx=(10, 0), pady=14)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(10, 10), pady=(10, 8))
        self.title_label = ctk.CTkLabel(
            body, text=title, font=theme.font(12), text_color=theme.color("muted"), anchor="w"
        )
        self.title_label.pack(fill="x")
        self.value_label = ctk.CTkLabel(body, text=value, font=theme.font(21, "bold"), anchor="w")
        self.value_label.pack(fill="x")
        self.sub_label = ctk.CTkLabel(
            body, text=subtitle, font=theme.font(11), text_color=theme.color("muted"), anchor="w"
        )
        self.sub_label.pack(fill="x")
        if command is not None:
            for w in (self, bar, body, self.title_label, self.value_label, self.sub_label):
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda e: self.on_click())
                w.bind("<Enter>", lambda e: self.configure(fg_color=theme.color("surface_hover")))
                w.bind("<Leave>", lambda e: self.configure(fg_color=theme.color("surface")))

    def set(self, value: str, subtitle: str | None = None, tone: str | None = None) -> None:
        """``tone``: None (normal text), or a palette key such as 'danger' / 'success'."""
        self.value_label.configure(text=value, text_color=theme.color(tone) if tone else theme.color("text"))
        if subtitle is not None:
            self.sub_label.configure(text=subtitle)
