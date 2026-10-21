"""Small form building blocks with consistent spacing."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from collections.abc import Sequence

import customtkinter as ctk

from hth.domain.interest import parse_date
from hth.services.accounts import ValidationError
from hth.ui import theme
from hth.ui.format import today_str


class Card(ctk.CTkFrame):
    def __init__(self, master, title: str | None = None, **kwargs):
        kwargs.setdefault("fg_color", theme.color("surface"))
        kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **kwargs)
        if title:
            ctk.CTkLabel(self, text=title, font=theme.font(17, "bold"), anchor="w").pack(
                fill="x", padx=18, pady=(14, 4)
            )


class SectionLabel(ctk.CTkLabel):
    def __init__(self, master, text: str, **kwargs):
        kwargs.setdefault("font", theme.font(12, "bold"))
        kwargs.setdefault("text_color", theme.color("muted"))
        kwargs.setdefault("anchor", "w")
        super().__init__(master, text=text.upper(), **kwargs)


class LabeledEntry(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label: str,
        default: str = "",
        placeholder: str = "",
        show: str | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.var = tk.StringVar(value=default)
        ctk.CTkLabel(self, text=label, font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(fill="x")
        entry_kwargs = {"textvariable": self.var, "font": theme.font(13), "height": 36}
        if placeholder and not default:
            entry_kwargs["placeholder_text"] = placeholder
        if show:
            entry_kwargs["show"] = show
        self.entry = ctk.CTkEntry(self, **entry_kwargs)
        self.entry.pack(fill="x", pady=(2, 0))

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value) -> None:
        self.var.set("" if value is None else str(value))

    def focus(self) -> None:  # type: ignore[override]
        self.entry.focus_set()


class DateField(LabeledEntry):
    """Date entry that defaults to today.

    While it still shows the date it was auto-filled with, :meth:`refresh_today` moves it to
    the new day - so a screen left open overnight does not book the morning's entries on
    yesterday.  A date the user typed is left alone.
    """

    def __init__(self, master, label: str = "Date", default: str | None = None, **kwargs):
        self._auto_value = today_str() if default is None else None
        super().__init__(master, label, default=default or today_str(), **kwargs)
        self.entry.bind("<Alt-Down>", lambda e: self._step(-1))
        self.entry.bind("<Alt-Up>", lambda e: self._step(1))

    def get(self) -> str:
        value = super().get()
        try:
            return parse_date(value).strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValidationError(f"Invalid date '{value}' (use YYYY-MM-DD).") from exc

    def set_today(self) -> None:
        self._auto_value = today_str()
        self.set(self._auto_value)

    def refresh_today(self) -> bool:
        """Roll an untouched auto-filled date forward to today; True if it changed."""
        if self._auto_value is not None and self.var.get().strip() == self._auto_value != today_str():
            self.set_today()
            return True
        return False

    def _step(self, days: int):
        """Alt+Up / Alt+Down: next / previous day."""
        try:
            day = parse_date(self.var.get()) + dt.timedelta(days=days)
        except ValueError:
            return "break"
        self.set(day.strftime("%Y-%m-%d"))
        return "break"


class LabeledOption(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label: str,
        values: Sequence[str],
        default: str | None = None,
        command=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.var = tk.StringVar(value=default or (values[0] if values else ""))
        ctk.CTkLabel(self, text=label, font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(fill="x")
        self.menu = ctk.CTkOptionMenu(
            self,
            values=list(values),
            variable=self.var,
            font=theme.font(13),
            height=36,
            command=command,
        )
        self.menu.pack(fill="x", pady=(2, 0))

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)

    def set_values(self, values: Sequence[str]) -> None:
        self.menu.configure(values=list(values))


class LabeledWidget(ctk.CTkFrame):
    """Label above any custom widget (e.g. a SearchBox)."""

    def __init__(self, master, label: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=label, font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(fill="x")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x", pady=(2, 0))


def primary_button(master, text: str, command, **kwargs) -> ctk.CTkButton:
    kwargs.setdefault("font", theme.font(13, "bold"))
    kwargs.setdefault("height", 38)
    kwargs.setdefault("fg_color", theme.color("accent"))
    kwargs.setdefault("hover_color", theme.color("accent_hover"))
    kwargs.setdefault("text_color", theme.color("accent_text"))
    return ctk.CTkButton(master, text=text, command=command, **kwargs)


def secondary_button(master, text: str, command, **kwargs) -> ctk.CTkButton:
    kwargs.setdefault("font", theme.font(13))
    kwargs.setdefault("height", 34)
    kwargs.setdefault("fg_color", theme.color("surface2"))
    kwargs.setdefault("hover_color", theme.color("surface3"))
    kwargs.setdefault("text_color", theme.color("text"))
    return ctk.CTkButton(master, text=text, command=command, **kwargs)


def danger_button(master, text: str, command, **kwargs) -> ctk.CTkButton:
    kwargs.setdefault("font", theme.font(13))
    kwargs.setdefault("height", 34)
    kwargs.setdefault("fg_color", theme.color("danger"))
    kwargs.setdefault("hover_color", theme.color("danger_hover"))
    kwargs.setdefault("text_color", theme.color("on_status"))
    return ctk.CTkButton(master, text=text, command=command, **kwargs)
