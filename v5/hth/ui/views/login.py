"""Sign-in screen."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from hth import __app_name__, __company__, __version__
from hth.ui import theme
from hth.ui.views.base import BaseView
from hth.ui.widgets.forms import primary_button


class LoginView(BaseView):
    key = "login"
    title = "Sign in"

    def build(self) -> None:
        self.configure(fg_color=theme.color("bg"))
        card = ctk.CTkFrame(self, fg_color=theme.color("surface"), corner_radius=16, width=420)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text=__company__, font=theme.font(13, "bold"), text_color=theme.color("accent")).pack(
            pady=(34, 0), padx=40
        )
        ctk.CTkLabel(card, text=__app_name__, font=theme.font(26, "bold")).pack(padx=40)
        ctk.CTkLabel(card, text="Sign in to continue", font=theme.font(13), text_color=theme.color("muted")).pack(
            pady=(2, 18), padx=40
        )

        self.username = tk.StringVar()
        self.password = tk.StringVar()
        ctk.CTkLabel(card, text="Username", font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
            fill="x", padx=40
        )
        self.user_entry = ctk.CTkEntry(card, textvariable=self.username, font=theme.font(14), height=40, width=340)
        self.user_entry.pack(padx=40, pady=(2, 10))
        ctk.CTkLabel(card, text="Password", font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
            fill="x", padx=40
        )
        self.pass_entry = ctk.CTkEntry(
            card, textvariable=self.password, font=theme.font(14), height=40, width=340, show="•"
        )
        self.pass_entry.pack(padx=40, pady=(2, 4))
        self.error = ctk.CTkLabel(card, text="", text_color=theme.color("danger"), font=theme.font(12))
        self.error.pack(padx=40)
        primary_button(card, "Sign in", self.submit, width=340, height=42).pack(padx=40, pady=(6, 26))
        ctk.CTkLabel(
            card,
            text=f"v{__version__}  ·  data: {self.ctx.settings.data_dir}",
            font=theme.font(10),
            text_color=theme.color("muted"),
            wraplength=340,
        ).pack(padx=40, pady=(0, 18))

        for w in (self.user_entry, self.pass_entry):
            w.bind("<Return>", lambda e: self.submit())

    def on_show(self, **kwargs) -> None:
        self.password.set("")
        self.error.configure(text="")
        self.after(100, self.user_entry.focus_set)

    def submit(self) -> None:
        user = self.ctx.auth.authenticate(self.username.get(), self.password.get())
        if user is None:
            self.error.configure(text="Invalid username or password.")
            self.password.set("")
            return
        self.ctx.app.on_login(user)
