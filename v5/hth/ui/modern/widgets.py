"""Small building blocks of the new layout, drawn from the design on the canvas."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import customtkinter as ctk

from hth import i18n
from hth.ui import theme
from hth.ui.format import money


def segmented(master, values: Sequence[str], command: Callable[[str], None] | None = None, height: int = 34):
    """A white pill on a grey track - section switches and small choices (Cash | UPI …)."""
    return ctk.CTkSegmentedButton(
        master,
        values=list(values),
        command=command,
        height=height,
        font=theme.font(13, "bold"),
        corner_radius=9,
        border_width=3,
        fg_color=theme.color("surface2"),
        selected_color=theme.color("surface"),
        selected_hover_color=theme.color("surface"),
        unselected_color=theme.color("surface2"),
        unselected_hover_color=theme.color("surface3"),
        text_color=theme.color("text"),
    )


def card(master, **kwargs) -> ctk.CTkFrame:
    kwargs.setdefault("fg_color", theme.color("surface"))
    kwargs.setdefault("corner_radius", 12)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("border_color", theme.color("line"))
    return ctk.CTkFrame(master, **kwargs)


def caption(master, text: str, **kwargs) -> ctk.CTkLabel:
    """Small grey capitals above a group (LAST ENTRIES, THIS SALE …)."""
    kwargs.setdefault("anchor", "w")
    return ctk.CTkLabel(
        master, text=i18n.tr(text).upper(), font=theme.font(11, "bold"), text_color=theme.color("muted"), **kwargs
    )


def rupees(value: float | None) -> str:
    return f"₹{money(abs(value or 0))}"


def balance_state(balance: float) -> tuple[str, str, str]:
    """(words, colour, soft colour) for a balance: never colour alone - the words go with it."""
    if balance > 0.004:
        return "OWES US", "owe", "owe_soft"
    if balance < -0.004:
        return "WE OWE", "weowe", "weowe_soft"
    return "SETTLED", "muted", "surface2"


_PILLS = {
    "late": ("owe_soft", "owe"),
    "due": ("warn_soft", "warning"),
    "soon": ("surface2", "text"),
    "ok": ("weowe_soft", "weowe"),
    "info": ("accent_soft", "accent"),
}


def pill(master, text: str = "", kind: str = "soon") -> ctk.CTkLabel:
    label = ctk.CTkLabel(master, text="", height=22, corner_radius=11, font=theme.font(11, "bold"))
    set_pill(label, text, kind)
    return label


def set_pill(label: ctk.CTkLabel, text: str, kind: str = "soon") -> None:
    bg, fg = _PILLS.get(kind, _PILLS["soon"])
    label.configure(text=f"  {text}  " if text else "", fg_color=theme.color(bg), text_color=theme.color(fg))


class MoneyBlock(ctk.CTkFrame):
    """OWES US / WE OWE / SETTLED, the amount, and a line under it."""

    def __init__(self, master, size: int = 26):
        super().__init__(master, corner_radius=10, fg_color=theme.color("surface2"))
        self.words = ctk.CTkLabel(self, text="", font=theme.font(11, "bold"), anchor="w", height=16)
        self.words.pack(fill="x", padx=14, pady=(10, 0))
        self.amount = ctk.CTkLabel(self, text="", font=theme.font(size, "bold"), anchor="w")
        self.amount.pack(fill="x", padx=14)
        self.note = ctk.CTkLabel(
            self, text="", font=theme.font(11), anchor="w", text_color=theme.color("muted"), height=16
        )
        self.note.pack(fill="x", padx=14, pady=(0, 10))

    def show(self, balance: float, note: str = "") -> None:
        words, color, soft = balance_state(balance)
        self.configure(fg_color=theme.color(soft))
        self.words.configure(text=words, text_color=theme.color(color))
        self.amount.configure(text=rupees(balance), text_color=theme.color(color if color != "muted" else "text"))
        self.note.configure(text=note)


class StatRow(ctk.CTkFrame):
    """``label ........ value`` with a hairline under it (the Counter's summary)."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        self.label = ctk.CTkLabel(row, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w")
        self.label.pack(side="left")
        self.value = ctk.CTkLabel(row, text="", font=theme.font(14, "bold"), anchor="e")
        self.value.pack(side="right")
        ctk.CTkFrame(self, height=1, fg_color=theme.color("line")).pack(fill="x", pady=(6, 0))

    def set(self, label: str, value: str, color: str = "text", big: bool = False) -> None:
        self.label.configure(text=label)
        self.value.configure(text=value, text_color=theme.color(color), font=theme.font(19 if big else 14, "bold"))
