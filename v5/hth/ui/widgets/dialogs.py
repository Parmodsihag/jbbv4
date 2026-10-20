"""Modal helpers: confirmations and a generic field-editor dialog."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from tkinter import messagebox

import customtkinter as ctk

from hth.services.accounts import ValidationError
from hth.services.auth import AuthError
from hth.ui import theme


def confirm(parent, title: str, message: str) -> bool:
    return bool(messagebox.askyesno(title, message, parent=parent))


def alert(parent, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=parent)


def info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=parent)


@dataclass
class Field:
    key: str
    label: str
    kind: str = "entry"  # entry | password | option | multiline
    default: str = ""
    options: Sequence[str] = field(default_factory=list)


class FormDialog(ctk.CTkToplevel):
    """Collects values for ``fields`` and calls ``on_submit(values)``.

    ``on_submit`` may raise ValidationError / AuthError to show a message and keep the
    dialog open.  ``result`` holds the submitted values after a successful save.
    """

    def __init__(
        self,
        parent,
        title: str,
        fields: Sequence[Field],
        on_submit: Callable[[dict[str, str]], None],
        submit_text: str = "Save",
        width: int = 420,
    ):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: dict[str, str] | None = None
        self._on_submit = on_submit
        self._vars: dict[str, tk.StringVar] = {}
        self._widgets: dict[str, ctk.CTkBaseClass] = {}

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(16, 8))
        ctk.CTkLabel(body, text=title, font=theme.font(16, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        first = None
        for f in fields:
            ctk.CTkLabel(body, text=f.label, font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
                fill="x", pady=(6, 0)
            )
            var = tk.StringVar(value=f.default)
            self._vars[f.key] = var
            if f.kind == "option":
                w = ctk.CTkOptionMenu(
                    body,
                    values=list(f.options),
                    variable=var,
                    font=theme.font(13),
                    height=34,
                    width=width - 40,
                )
            elif f.kind == "multiline":
                w = ctk.CTkTextbox(body, height=80, font=theme.font(13), width=width - 40)
                w.insert("1.0", f.default)
            else:
                w = ctk.CTkEntry(
                    body,
                    textvariable=var,
                    font=theme.font(13),
                    height=34,
                    width=width - 40,
                    show="•" if f.kind == "password" else "",
                )
            w.pack(fill="x", pady=(2, 0))
            self._widgets[f.key] = w
            first = first or w
        self.error = ctk.CTkLabel(
            body,
            text="",
            text_color=theme.color("danger"),
            font=theme.font(12),
            anchor="w",
            wraplength=width - 40,
        )
        self.error.pack(fill="x", pady=(8, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(
            buttons,
            text="Cancel",
            command=self.destroy,
            fg_color=theme.color("surface2"),
            hover_color=theme.color("surface3"),
            text_color=theme.color("text"),
            font=theme.font(13),
            width=100,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            buttons,
            text=submit_text,
            command=self._submit,
            font=theme.font(13, "bold"),
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
            width=120,
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.after(80, self._focus_first, first)
        self.grab_set()

    def _focus_first(self, widget) -> None:
        try:
            if widget is not None:
                widget.focus_set()
        except Exception:  # noqa: BLE001
            pass

    def values(self) -> dict[str, str]:
        out = {}
        for key, var in self._vars.items():
            w = self._widgets[key]
            out[key] = w.get("1.0", "end").strip() if isinstance(w, ctk.CTkTextbox) else var.get().strip()
        return out

    def _submit(self) -> None:
        values = self.values()
        try:
            self._on_submit(values)
        except (ValidationError, AuthError, ValueError) as exc:
            self.error.configure(text=str(exc))
            return
        self.result = values
        self.destroy()


def run_form(parent, title: str, fields: Sequence[Field], on_submit, submit_text: str = "Save") -> dict | None:
    dialog = FormDialog(parent, title, fields, on_submit, submit_text)
    parent.wait_window(dialog)
    return dialog.result


GENERAL_SHORTCUTS = [
    ("Ctrl+K", "Search accounts, items and bills"),
    ("Ctrl+L", "Lock the screen (your work stays)"),
    ("F1", "This sheet"),
]
SALES_SHORTCUTS = [
    ("Enter", "Quantity → price → add line"),
    ("Ctrl+Enter", "Debit (sale / pay out)"),
    ("Ctrl+Shift+Enter", "Credit (receive / purchase)"),
    ("Ctrl+Z", "Undo the last entry (15 minutes)"),
    ("Alt+Up / Alt+Down", "Next / previous day in a date field"),
]
COUNTER_SHORTCUTS = [  # the new layout's Counter (v5.5)
    ("Alt+1 … Alt+4", "Sale · Purchase · Payment in · Payment out"),
    ("Enter", "Quantity → rate → add line"),
    ("Ctrl+Enter", "Save the open tab"),
    ("Ctrl+Shift+Enter", "Save a Purchase or a Payment in"),
    ("Ctrl+Z", "Undo the last entry (15 minutes)"),
    ("Alt+Up / Alt+Down", "Next / previous day in a date field"),
]
TABLE_SHORTCUTS = [
    ("Double-click / Enter", "Open the row (ledger, item, bill)"),
    ("Ctrl+C", "Copy the selected row"),
    ("Right-click", "Copy row / copy all rows for Excel or WhatsApp"),
    ("Click a column title", "Sort; click again to reverse"),
]


class ShortcutSheet(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        screens: list[tuple[str, str]],
        entry_title: str = "Sales",
        entry_keys: list[tuple[str, str]] | None = None,
    ):
        super().__init__(parent)
        self.title("Keyboard shortcuts")
        self.resizable(False, False)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=18)
        ctk.CTkLabel(body, text="Keyboard shortcuts", font=theme.font(18, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )
        groups = [
            ("Screens", screens),
            ("Everywhere", GENERAL_SHORTCUTS),
            (entry_title, entry_keys or SALES_SHORTCUTS),
            ("Tables", TABLE_SHORTCUTS),
        ]
        for col, chunk in enumerate((groups[:2], groups[2:])):
            r = 1
            for title, items in chunk:
                ctk.CTkLabel(
                    body, text=title.upper(), font=theme.font(11, "bold"), text_color=theme.color("muted"), anchor="w"
                ).grid(row=r, column=col * 2, columnspan=2, sticky="w", pady=(10, 2))
                r += 1
                for keys, what in items:
                    ctk.CTkLabel(body, text=keys, font=theme.font(12, "bold"), anchor="w", width=150).grid(
                        row=r, column=col * 2, sticky="w", padx=(0, 8)
                    )
                    ctk.CTkLabel(body, text=what, font=theme.font(12), anchor="w").grid(
                        row=r, column=col * 2 + 1, sticky="w", padx=(0, 28)
                    )
                    r += 1
        ctk.CTkButton(self, text="Close", width=100, command=self.destroy, font=theme.font(13)).pack(pady=(0, 16))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F1>", lambda e: self.destroy())
        self.transient(parent)
        self.after(50, self.focus_set)
