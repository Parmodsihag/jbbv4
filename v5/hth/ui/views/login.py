"""Sign-in screen."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from hth import __app_name__, __company__, __version__
from hth.services.auth import AuthError
from hth.ui import icons, theme
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
        try:
            user = self.ctx.auth.authenticate(self.username.get(), self.password.get())
        except AuthError as exc:
            self.error.configure(text=str(exc))
            self.password.set("")
            return
        if user is None:
            self.error.configure(text="Invalid username or password.")
            self.password.set("")
            return
        self.ctx.app.on_login(user)


class LockView(BaseView):
    """Screen lock: the signed-in user's work stays as it is behind a password prompt."""

    key = "lock"
    title = "Locked"

    def build(self) -> None:
        self.configure(fg_color=theme.color("bg"))
        user = self.ctx.user
        card = ctk.CTkFrame(self, fg_color=theme.color("surface"), corner_radius=16, width=420)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text=icons.icon("lock"), font=icons.font(34), text_color=theme.color("accent")).pack(
            pady=(30, 4), padx=40
        )
        ctk.CTkLabel(card, text="Screen locked", font=theme.font(22, "bold")).pack(padx=40)
        ctk.CTkLabel(
            card,
            text=f"{user.full_name or user.username}  (@{user.username}) - enter your password to continue",
            font=theme.font(12),
            text_color=theme.color("muted"),
            wraplength=340,
        ).pack(pady=(2, 16), padx=40)
        self.password = tk.StringVar()
        self.pass_entry = ctk.CTkEntry(
            card, textvariable=self.password, font=theme.font(14), height=40, width=340, show="•"
        )
        self.pass_entry.pack(padx=40, pady=(2, 4))
        self.pass_entry.bind("<Return>", lambda e: self.submit())
        self.error = ctk.CTkLabel(card, text="", text_color=theme.color("danger"), font=theme.font(12))
        self.error.pack(padx=40)
        primary_button(card, "Unlock", self.submit, width=340, height=42).pack(padx=40, pady=(6, 8))
        ctk.CTkButton(
            card,
            text="Sign in as someone else",
            width=340,
            height=34,
            font=theme.font(12),
            fg_color="transparent",
            hover_color=theme.color("surface2"),
            text_color=theme.color("muted"),
            command=self.ctx.app.logout,
        ).pack(padx=40, pady=(0, 26))

    def on_show(self, **kwargs) -> None:
        self.after(100, self.pass_entry.focus_set)

    def submit(self) -> None:
        user = self.ctx.user
        try:
            ok = self.ctx.auth.authenticate(user.username, self.password.get())
        except AuthError as exc:
            self.error.configure(text=str(exc))
            self.password.set("")
            return
        if ok is None:
            self.error.configure(text="Wrong password.")
            self.password.set("")
            return
        self.ctx.app.unlock()
