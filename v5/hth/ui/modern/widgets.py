"""Small building blocks of the new layout, drawn from the design on the canvas."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from collections.abc import Callable, Sequence

import customtkinter as ctk

from hth import i18n
from hth.ui import theme
from hth.ui.format import money


class Freshness:
    """Does a screen still show the books as they are?  Yes while nothing has been written
    since it was filled and it is the same day (interest and "days late" move with the date).
    Coming back to an unchanged screen then costs nothing instead of a full reload."""

    def __init__(self, db):
        self.db = db
        self._filled_at: tuple[int, dt.date] | None = None

    def stale(self) -> bool:
        return self._filled_at != (self.db.version, dt.date.today())

    def filling(self) -> None:
        """Call as a reload starts: a write that lands while it reads still counts as new."""
        self._filled_at = (self.db.version, dt.date.today())

    def forget(self) -> None:
        self._filled_at = None


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


def period_split(rows, balance: float) -> tuple[float, float]:
    """(entered, interest) of a balance: the principal of the current period (after the last
    settlement) and the interest on top of it.  The ledger shows interest unsigned, so it
    is worked out as balance - principal rather than summed."""
    last_settle = max((i for i, r in enumerate(rows) if r.tag == "0"), default=-1)
    principal = sum(r.amount if r.type == "P" else -r.amount for r in rows[last_settle + 1 :] if r.tag != "0")
    return round(principal, 2), round(balance - principal, 2)


def style_option(menu: ctk.CTkOptionMenu) -> ctk.CTkOptionMenu:
    """Drop-downs in the new layout's quiet grey, not customtkinter's default blue."""
    menu.configure(
        fg_color=theme.color("surface2"),
        button_color=theme.color("surface3"),
        button_hover_color=theme.color("surface3"),
        text_color=theme.color("text"),
    )
    return menu


def dropdown_menu(widget) -> tk.Menu:
    """A right-click / drop-down menu in the theme's colours."""
    return tk.Menu(
        widget,
        tearoff=0,
        bg=theme.current("surface"),
        fg=theme.current("text"),
        activebackground=theme.current("accent_soft"),
        activeforeground=theme.current("text"),
        font=theme.table_font(),
    )


def popup(menu: tk.Menu, button) -> None:
    try:
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height() + 2)
    finally:
        menu.grab_release()


# Buttons: primary (teal), outline (teal edge) or plain (white with a hairline).
def button(master, text: str, command, primary: bool = False, outline: bool = False, **kw) -> ctk.CTkButton:
    if primary:
        colors = {
            "fg_color": theme.color("accent"),
            "hover_color": theme.color("accent_hover"),
            "text_color": theme.color("accent_text"),
        }
    elif outline:
        colors = {
            "fg_color": "transparent",
            "border_width": 1,
            "border_color": theme.color("accent"),
            "hover_color": theme.color("accent_soft"),
            "text_color": theme.color("accent"),
        }
    else:
        colors = {
            "fg_color": theme.color("surface"),
            "border_width": 1,
            "border_color": theme.color("line"),
            "hover_color": theme.color("surface_hover"),
            "text_color": theme.color("text"),
        }
    kw.setdefault("height", 36)
    kw.setdefault("width", 10)
    return ctk.CTkButton(
        master, text=text, command=command, corner_radius=9, font=theme.font(13, "bold"), **colors, **kw
    )
