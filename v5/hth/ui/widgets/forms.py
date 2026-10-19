"""Small form building blocks with consistent spacing."""

from __future__ import annotations

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
    def __init__(self, master, label: str = "Date", default: str | None = None, **kwargs):
        super().__init__(master, label, default=default or today_str(), **kwargs)

    def get(self) -> str:
        value = super().get()
        try:
            return parse_date(value).strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValidationError(f"Invalid date '{value}' (use YYYY-MM-DD).") from exc

    def set_today(self) -> None:
        self.set(today_str())


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
    kwargs.setdefault("hover_color", ("#991B1B", "#DC2626"))
    kwargs.setdefault("text_color", "#FFFFFF")
    return ctk.CTkButton(master, text=text, command=command, **kwargs)
