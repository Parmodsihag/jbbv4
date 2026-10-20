"""Design tokens (light, dark) and ttk styling so Treeview matches customtkinter."""

from __future__ import annotations

import sys
from tkinter import ttk

import customtkinter as ctk

FONT_FAMILY = (
    "Segoe UI" if sys.platform.startswith("win") else ("Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")
)
MONO_FAMILY = "Consolas" if sys.platform.startswith("win") else "Menlo"
LATIN_FAMILY = FONT_FAMILY


def set_language_font(hindi: bool) -> None:
    """Nirmala UI draws Devanagari (and Latin) cleanly on Windows; other systems fall back
    to whatever font has the glyphs."""
    global FONT_FAMILY
    FONT_FAMILY = "Nirmala UI" if hindi and sys.platform.startswith("win") else LATIN_FAMILY


# (light, dark)
PALETTE: dict[str, tuple[str, str]] = {
    "bg": ("#EEF2F6", "#0F172A"),
    "surface": ("#FFFFFF", "#1E293B"),
    "surface_hover": ("#F1F5F9", "#243247"),
    "surface2": ("#E2E8F0", "#334155"),
    "surface3": ("#CBD5E1", "#475569"),
    "text": ("#0F172A", "#F1F5F9"),
    "muted": ("#64748B", "#94A3B8"),
    "accent": ("#0E7490", "#22D3EE"),
    "accent_hover": ("#155E75", "#06B6D4"),
    "accent_text": ("#FFFFFF", "#0F172A"),
    "success": ("#15803D", "#4ADE80"),
    "danger": ("#B91C1C", "#F87171"),
    "warning": ("#B45309", "#FBBF24"),
    "sidebar": ("#0F172A", "#020617"),
    "sidebar_hover": ("#1A2540", "#0F172A"),
    "sidebar_active": ("#22304F", "#16213A"),
    "sidebar_text": ("#E2E8F0", "#E2E8F0"),
    "stripe": ("#F8FAFC", "#16213A"),
    "select": ("#CFFAFE", "#164E63"),
    "chart1": ("#0E7490", "#22D3EE"),
    "chart2": ("#15803D", "#4ADE80"),
    "chart3": ("#B45309", "#FBBF24"),
    "chart4": ("#B91C1C", "#F87171"),
    "chart5": ("#6D28D9", "#A78BFA"),
    # new layout (v5.5) - added, never changed above, so the classic screens look the same
    "accent_soft": ("#E0F2F7", "#123A47"),
    "line": ("#E4E7EC", "#334155"),
    "owe": ("#B42318", "#F97066"),  # money due to the shop
    "owe_soft": ("#FEF3F2", "#3A1518"),
    "weowe": ("#067647", "#47CD89"),  # money in / due from the shop
    "weowe_soft": ("#ECFDF3", "#0E2E21"),
    "warn_soft": ("#FFFAEB", "#3A2A0A"),
    "topbar": ("#FFFFFF", "#111A2E"),
}


def color(key: str) -> tuple[str, str]:
    """(light, dark) pair for customtkinter widgets."""
    return PALETTE[key]


def current(key: str) -> str:
    """Resolved colour for the active appearance mode (for tk/ttk/matplotlib)."""
    idx = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
    return PALETTE[key][idx]


_fonts: dict[tuple, ctk.CTkFont] = {}


def font(size: int = 13, weight: str = "normal", family: str | None = None) -> ctk.CTkFont:
    key = (family or FONT_FAMILY, size, weight)
    if key not in _fonts:
        _fonts[key] = ctk.CTkFont(family=key[0], size=size, weight=weight)  # type: ignore[arg-type]
    return _fonts[key]


TEXT_SCALES = (0.9, 1.0, 1.15, 1.3)
_text_scale = 1.0


def set_text_scale(scale: float) -> None:
    """Shop-wide text size: customtkinter widgets and the ttk tables grow together."""
    global _text_scale
    _text_scale = scale if scale in TEXT_SCALES else 1.0
    ctk.set_widget_scaling(_text_scale)


def text_scale() -> float:
    return _text_scale


def table_font(bold: bool = False) -> tuple:
    size = max(9, round(12 * _text_scale))
    return (FONT_FAMILY, size, "bold") if bold else (FONT_FAMILY, size)


def style_treeview() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:  # noqa: BLE001 - theme missing on exotic builds
        pass
    style.configure(
        "HTH.Treeview",
        background=current("surface"),
        fieldbackground=current("surface"),
        foreground=current("text"),
        rowheight=round(30 * _text_scale),
        borderwidth=0,
        relief="flat",
        font=table_font(),
    )
    style.configure(
        "HTH.Treeview.Heading",
        background=current("surface2"),
        foreground=current("text"),
        font=table_font(bold=True),
        relief="flat",
        padding=(8, 6),
    )
    style.map(
        "HTH.Treeview",
        background=[("selected", current("select"))],
        foreground=[("selected", current("text"))],
    )
    style.map("HTH.Treeview.Heading", background=[("active", current("surface3"))])
    style.layout("HTH.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])


def apply_appearance(mode: str) -> None:
    """mode: 'light' | 'dark' | 'system'"""
    ctk.set_appearance_mode(mode)
    style_treeview()


def init_theme(mode: str = "dark") -> None:
    ctk.set_default_color_theme("blue")
    ctk.set_appearance_mode(mode if mode in ("light", "dark", "system") else "dark")
