"""Dashboard stat tile."""

from __future__ import annotations

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
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10, **kwargs)
        bar = ctk.CTkFrame(self, width=5, fg_color=theme.color(accent), corner_radius=3)
        bar.pack(side="left", fill="y", padx=(8, 0), pady=10)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(10, 12), pady=10)
        ctk.CTkLabel(body, text=title, font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(fill="x")
        self.value_label = ctk.CTkLabel(body, text=value, font=theme.font(20, "bold"), anchor="w")
        self.value_label.pack(fill="x")
        self.sub_label = ctk.CTkLabel(
            body, text=subtitle, font=theme.font(11), text_color=theme.color("muted"), anchor="w"
        )
        self.sub_label.pack(fill="x")

    def set(self, value: str, subtitle: str | None = None) -> None:
        self.value_label.configure(text=value)
        if subtitle is not None:
            self.sub_label.configure(text=subtitle)
