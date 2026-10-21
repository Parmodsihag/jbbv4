"""Design tokens, colour themes and ttk styling so Treeview matches customtkinter.

Every token is a ``[light, dark]`` pair, so each colour theme works in both appearance
modes.  ``PALETTE`` holds one *mutable* list per token and customtkinter keeps a reference
to the list it was given, so switching colour theme rewrites the lists in place and asks
customtkinter to redraw: every open screen recolours without being rebuilt or losing what
was typed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
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


MODES = ("light", "dark", "system")


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    blurb: str
    colors: dict[str, tuple[str, str]]  # token -> (light, dark)


# Token roles - every theme defines all of them:
#   bg / surface / surface_hover / surface2 / surface3   window, cards, hover, secondary fills
#   field / border / line                 entry background, entry outline, card outline
#   text / muted                          body text, secondary text
#   accent / accent_hover / accent_text / accent_soft   primary buttons, selection, tinted chips
#   success / danger / warning (+_hover)  used as text AND as fills;  on_status = text on the fills
#   owe / weowe (+_soft), warn_soft       money due to / from the shop, and their pill backgrounds
#   topbar                                the new layout's top bar
#   sidebar*                              the classic layout's menu column
#   stripe / select                       alternate table rows, selected row
#   chart1..chart5                        chart series
# Slate is the original look: its values are the ones every screen was designed with.
THEMES: dict[str, Theme] = {
    t.key: t
    for t in (
        Theme(
            "slate",
            "Slate",
            "The original teal and grey",
            {
                "bg": ("#EEF2F6", "#0F172A"),
                "surface": ("#FFFFFF", "#1E293B"),
                "surface_hover": ("#F1F5F9", "#243247"),
                "surface2": ("#E2E8F0", "#334155"),
                "surface3": ("#CBD5E1", "#475569"),
                "field": ("#F8FAFC", "#0F172A"),
                "border": ("#94A3B8", "#5B6B82"),
                "line": ("#E4E7EC", "#334155"),
                "text": ("#0F172A", "#F1F5F9"),
                "muted": ("#64748B", "#94A3B8"),
                "accent": ("#0E7490", "#22D3EE"),
                "accent_hover": ("#155E75", "#06B6D4"),
                "accent_text": ("#FFFFFF", "#0F172A"),
                "accent_soft": ("#E0F2F7", "#123A47"),
                "success": ("#15803D", "#4ADE80"),
                "success_hover": ("#166534", "#22C55E"),
                "danger": ("#B91C1C", "#F87171"),
                "danger_hover": ("#991B1B", "#EF4444"),
                "warning": ("#B45309", "#FBBF24"),
                "on_status": ("#FFFFFF", "#0F172A"),
                "owe": ("#B42318", "#F97066"),
                "owe_soft": ("#FEF3F2", "#3A1518"),
                "weowe": ("#067647", "#47CD89"),
                "weowe_soft": ("#ECFDF3", "#0E2E21"),
                "warn_soft": ("#FFFAEB", "#3A2A0A"),
                "topbar": ("#FFFFFF", "#111A2E"),
                "sidebar": ("#0F172A", "#020617"),
                "sidebar_hover": ("#1A2540", "#0F172A"),
                "sidebar_active": ("#22304F", "#16213A"),
                "sidebar_text": ("#E2E8F0", "#E2E8F0"),
                "sidebar_muted": ("#94A3B8", "#94A3B8"),
                "sidebar_accent": ("#22D3EE", "#22D3EE"),
                "stripe": ("#F8FAFC", "#16213A"),
                "select": ("#CFFAFE", "#164E63"),
                "chart1": ("#0E7490", "#22D3EE"),
                "chart2": ("#15803D", "#4ADE80"),
                "chart3": ("#B45309", "#FBBF24"),
                "chart4": ("#B91C1C", "#F87171"),
                "chart5": ("#6D28D9", "#A78BFA"),
            },
        ),
        Theme(
            "forest",
            "Forest",
            "Calm field greens",
            {
                "bg": ("#EDF3EE", "#0D1912"),
                "surface": ("#FFFFFF", "#15251B"),
                "surface_hover": ("#F2F7F3", "#1C3024"),
                "surface2": ("#DDE8E0", "#203629"),
                "surface3": ("#C4D5C9", "#2D4A39"),
                "field": ("#F7FAF8", "#0D1912"),
                "border": ("#8AA393", "#3E5E4A"),
                "line": ("#DCE5DE", "#2D4A39"),
                "text": ("#12221A", "#E6F2EA"),
                "muted": ("#566B5D", "#93AE9C"),
                "accent": ("#25704A", "#5DD39E"),
                "accent_hover": ("#1B5638", "#86E0B7"),
                "accent_text": ("#FFFFFF", "#0A1A11"),
                "accent_soft": ("#DDF0E5", "#143826"),
                "success": ("#3F7A12", "#A3E635"),
                "success_hover": ("#2F5E0C", "#BEF264"),
                "danger": ("#B42318", "#F87171"),
                "danger_hover": ("#912018", "#FCA5A5"),
                "warning": ("#A85207", "#FBBF24"),
                "on_status": ("#FFFFFF", "#0A1A11"),
                "owe": ("#B42318", "#F97066"),
                "owe_soft": ("#FEF3F2", "#3A1518"),
                "weowe": ("#3F7A12", "#A3E635"),
                "weowe_soft": ("#F0F7E6", "#1F2E0E"),
                "warn_soft": ("#FFF7E6", "#3A2A0A"),
                "topbar": ("#FFFFFF", "#112019"),
                "sidebar": ("#14301F", "#07110B"),
                "sidebar_hover": ("#21452F", "#15251B"),
                "sidebar_active": ("#2A5239", "#1B3324"),
                "sidebar_text": ("#E3F0E6", "#E3F0E6"),
                "sidebar_muted": ("#A3C1AC", "#8FAA98"),
                "sidebar_accent": ("#7DDCAE", "#5DD39E"),
                "stripe": ("#F4F8F5", "#192B20"),
                "select": ("#CFE8D8", "#1F5138"),
                "chart1": ("#25704A", "#5DD39E"),
                "chart2": ("#3F7A12", "#A3E635"),
                "chart3": ("#A85207", "#FBBF24"),
                "chart4": ("#B42318", "#F87171"),
                "chart5": ("#1D6FA3", "#60A5FA"),
            },
        ),
        Theme(
            "saffron",
            "Saffron",
            "Warm marigold and stone",
            {
                "bg": ("#F7F2EC", "#17110C"),
                "surface": ("#FFFFFF", "#221912"),
                "surface_hover": ("#FAF6F1", "#2B2018"),
                "surface2": ("#EFE6DB", "#33261C"),
                "surface3": ("#DDCDBB", "#47362A"),
                "field": ("#FCFAF7", "#17110C"),
                "border": ("#A69280", "#6E5747"),
                "line": ("#EADFD2", "#3D2E22"),
                "text": ("#2A1D12", "#F8EEE4"),
                "muted": ("#735F50", "#BCA593"),
                "accent": ("#C2410C", "#FB923C"),
                "accent_hover": ("#9A3412", "#FDBA74"),
                "accent_text": ("#FFFFFF", "#1C0F06"),
                "accent_soft": ("#FEF0E6", "#4A2610"),
                "success": ("#15803D", "#4ADE80"),
                "success_hover": ("#166534", "#86EFAC"),
                "danger": ("#BE123C", "#FB7185"),
                "danger_hover": ("#9F1239", "#FDA4AF"),
                "warning": ("#996007", "#FACC15"),
                "on_status": ("#FFFFFF", "#1C0F06"),
                "owe": ("#BE123C", "#FB7185"),
                "owe_soft": ("#FFF1F3", "#3D0F1A"),
                "weowe": ("#067647", "#47CD89"),
                "weowe_soft": ("#ECFDF3", "#0E2E21"),
                "warn_soft": ("#FEF9E7", "#3A300A"),
                "topbar": ("#FFFFFF", "#1D150F"),
                "sidebar": ("#2B1A10", "#0F0A06"),
                "sidebar_hover": ("#40291A", "#221912"),
                "sidebar_active": ("#4D3220", "#2E2219"),
                "sidebar_text": ("#F6E9DC", "#F6E9DC"),
                "sidebar_muted": ("#C9AE98", "#B89C87"),
                "sidebar_accent": ("#FDBA74", "#FB923C"),
                "stripe": ("#FBF7F3", "#281E16"),
                "select": ("#FCE1CC", "#5A2E12"),
                "chart1": ("#C2410C", "#FB923C"),
                "chart2": ("#15803D", "#4ADE80"),
                "chart3": ("#996007", "#FACC15"),
                "chart4": ("#BE123C", "#FB7185"),
                "chart5": ("#6D28D9", "#A78BFA"),
            },
        ),
        Theme(
            "indigo",
            "Indigo",
            "Calm blue-violet",
            {
                "bg": ("#EEF0F8", "#0C0E1F"),
                "surface": ("#FFFFFF", "#161A33"),
                "surface_hover": ("#F3F4FB", "#1D2240"),
                "surface2": ("#E0E4F2", "#232848"),
                "surface3": ("#C8CEE6", "#323862"),
                "field": ("#F8F9FD", "#0C0E1F"),
                "border": ("#8E97BD", "#525A92"),
                "line": ("#E0E3F0", "#2C3256"),
                "text": ("#141833", "#ECEEFF"),
                "muted": ("#5C6286", "#9EA3CC"),
                "accent": ("#4338CA", "#818CF8"),
                "accent_hover": ("#3730A3", "#A5B4FC"),
                "accent_text": ("#FFFFFF", "#0C0E1F"),
                "accent_soft": ("#E6E6FD", "#22265C"),
                "success": ("#15803D", "#4ADE80"),
                "success_hover": ("#166534", "#86EFAC"),
                "danger": ("#B91C1C", "#F87171"),
                "danger_hover": ("#991B1B", "#FCA5A5"),
                "warning": ("#B45309", "#FBBF24"),
                "on_status": ("#FFFFFF", "#0C0E1F"),
                "owe": ("#B42318", "#F97066"),
                "owe_soft": ("#FEF3F2", "#3A1518"),
                "weowe": ("#067647", "#47CD89"),
                "weowe_soft": ("#ECFDF3", "#0E2E21"),
                "warn_soft": ("#FFFAEB", "#3A2A0A"),
                "topbar": ("#FFFFFF", "#11142A"),
                "sidebar": ("#1A1B4B", "#070815"),
                "sidebar_hover": ("#2A2D66", "#161A33"),
                "sidebar_active": ("#33377A", "#1D2240"),
                "sidebar_text": ("#E4E6FA", "#E4E6FA"),
                "sidebar_muted": ("#AEB2DD", "#9499C4"),
                "sidebar_accent": ("#A5B4FC", "#818CF8"),
                "stripe": ("#F6F7FC", "#1B1F3B"),
                "select": ("#DCDEFB", "#2E3478"),
                "chart1": ("#4338CA", "#818CF8"),
                "chart2": ("#15803D", "#4ADE80"),
                "chart3": ("#B45309", "#FBBF24"),
                "chart4": ("#B91C1C", "#F87171"),
                "chart5": ("#BE185D", "#F472B6"),
            },
        ),
        Theme(
            "plum",
            "Plum",
            "Rich mauve and soft lilac",
            {
                "bg": ("#F5F0F6", "#170D19"),
                "surface": ("#FFFFFF", "#221425"),
                "surface_hover": ("#FAF5FA", "#2B1A2F"),
                "surface2": ("#ECE1EE", "#341F38"),
                "surface3": ("#D9C7DD", "#4A2D50"),
                "field": ("#FCF9FC", "#170D19"),
                "border": ("#A38DA8", "#714E77"),
                "line": ("#EADDEC", "#3E2742"),
                "text": ("#26142A", "#F8ECFA"),
                "muted": ("#6C5871", "#BFA5C4"),
                "accent": ("#86198F", "#E879F9"),
                "accent_hover": ("#6B1572", "#F0ABFC"),
                "accent_text": ("#FFFFFF", "#1E0A21"),
                "accent_soft": ("#F7E4F8", "#3F1545"),
                "success": ("#15803D", "#4ADE80"),
                "success_hover": ("#166534", "#86EFAC"),
                "danger": ("#B91C1C", "#F87171"),
                "danger_hover": ("#991B1B", "#FCA5A5"),
                "warning": ("#B45309", "#FBBF24"),
                "on_status": ("#FFFFFF", "#1E0A21"),
                "owe": ("#B42318", "#F97066"),
                "owe_soft": ("#FEF3F2", "#3A1518"),
                "weowe": ("#067647", "#47CD89"),
                "weowe_soft": ("#ECFDF3", "#0E2E21"),
                "warn_soft": ("#FFFAEB", "#3A2A0A"),
                "topbar": ("#FFFFFF", "#1D1120"),
                "sidebar": ("#2E1233", "#0E0710"),
                "sidebar_hover": ("#45204C", "#221425"),
                "sidebar_active": ("#552A5C", "#2B1A2F"),
                "sidebar_text": ("#F5E6F7", "#F5E6F7"),
                "sidebar_muted": ("#CDAED3", "#B596BB"),
                "sidebar_accent": ("#F0ABFC", "#E879F9"),
                "stripe": ("#FBF7FB", "#29182C"),
                "select": ("#F3D9F5", "#5B1F66"),
                "chart1": ("#86198F", "#E879F9"),
                "chart2": ("#15803D", "#4ADE80"),
                "chart3": ("#B45309", "#FBBF24"),
                "chart4": ("#B91C1C", "#F87171"),
                "chart5": ("#1D4ED8", "#60A5FA"),
            },
        ),
        Theme(
            "paper",
            "Paper",
            "Soft sepia, low glare",
            {
                "bg": ("#F1EADC", "#1A1511"),
                "surface": ("#FBF7EF", "#241D17"),
                "surface_hover": ("#F4EEE2", "#2D251E"),
                "surface2": ("#E8DECB", "#342A21"),
                "surface3": ("#D6C8AE", "#4A3C2F"),
                "field": ("#FFFCF6", "#1A1511"),
                "border": ("#A28F74", "#655341"),
                "line": ("#E2D6C0", "#3B3027"),
                "text": ("#33281C", "#EFE4D2"),
                "muted": ("#6B5C49", "#B4A38C"),
                "accent": ("#8A4B24", "#D9A066"),
                "accent_hover": ("#6F3B1B", "#E6B884"),
                "accent_text": ("#FFFFFF", "#1A1511"),
                "accent_soft": ("#F2E2D2", "#3D2C1C"),
                "success": ("#3D6820", "#9BC46D"),
                "success_hover": ("#2F521A", "#B3D68C"),
                "danger": ("#A3261C", "#E57A6E"),
                "danger_hover": ("#821D16", "#EE978D"),
                "warning": ("#8F5409", "#E3B341"),
                "on_status": ("#FFFFFF", "#1A1511"),
                "owe": ("#A3261C", "#E57A6E"),
                "owe_soft": ("#F8E6E0", "#3A1D18"),
                "weowe": ("#3D6820", "#9BC46D"),
                "weowe_soft": ("#E8F0DC", "#232E18"),
                "warn_soft": ("#F6EBD3", "#3A2E14"),
                "topbar": ("#FBF7EF", "#1F1914"),
                "sidebar": ("#3A2C1F", "#120E0B"),
                "sidebar_hover": ("#4F3D2C", "#241D17"),
                "sidebar_active": ("#5C4733", "#2D251E"),
                "sidebar_text": ("#F3E9D8", "#EFE4D2"),
                "sidebar_muted": ("#CDB89B", "#A8967F"),
                "sidebar_accent": ("#E6B884", "#D9A066"),
                "stripe": ("#F5EFE3", "#2A221B"),
                "select": ("#EDD7BB", "#4E3A26"),
                "chart1": ("#8A4B24", "#D9A066"),
                "chart2": ("#3D6820", "#9BC46D"),
                "chart3": ("#8F5409", "#E3B341"),
                "chart4": ("#A3261C", "#E57A6E"),
                "chart5": ("#3F5E8C", "#8FB3D9"),
            },
        ),
        Theme(
            "contrast",
            "High contrast",
            "Clearest text in bright light",
            {
                "bg": ("#E2E2E2", "#000000"),
                "surface": ("#FFFFFF", "#121212"),
                "surface_hover": ("#EDEDED", "#1F1F1F"),
                "surface2": ("#D2D2D2", "#2A2A2A"),
                "surface3": ("#B4B4B4", "#424242"),
                "field": ("#FFFFFF", "#000000"),
                "border": ("#4A4A4A", "#BDBDBD"),
                "line": ("#7A7A7A", "#8A8A8A"),
                "text": ("#000000", "#FFFFFF"),
                "muted": ("#3A3A3A", "#D0D0D0"),
                "accent": ("#0033CC", "#FFD400"),
                "accent_hover": ("#00218A", "#FFE45C"),
                "accent_text": ("#FFFFFF", "#000000"),
                "accent_soft": ("#D6E0FF", "#3D3300"),
                "success": ("#006B1F", "#3DF57A"),
                "success_hover": ("#004D16", "#85FFAA"),
                "danger": ("#B00000", "#FF6B6B"),
                "danger_hover": ("#800000", "#FF9A9A"),
                "warning": ("#8A4B00", "#FFB224"),
                "on_status": ("#FFFFFF", "#000000"),
                "owe": ("#B00000", "#FF6B6B"),
                "owe_soft": ("#FFE0E0", "#3D0000"),
                "weowe": ("#006B1F", "#3DF57A"),
                "weowe_soft": ("#DCF5E3", "#002E0D"),
                "warn_soft": ("#FFEFD1", "#3D2600"),
                "topbar": ("#FFFFFF", "#000000"),
                "sidebar": ("#000000", "#000000"),
                "sidebar_hover": ("#2A2A2A", "#242424"),
                "sidebar_active": ("#333333", "#2E2E2E"),
                "sidebar_text": ("#FFFFFF", "#FFFFFF"),
                "sidebar_muted": ("#D4D4D4", "#C8C8C8"),
                "sidebar_accent": ("#FFD400", "#FFD400"),
                "stripe": ("#F0F0F0", "#1E1E1E"),
                "select": ("#FFE066", "#00478F"),
                "chart1": ("#0033CC", "#FFD400"),
                "chart2": ("#006B1F", "#3DF57A"),
                "chart3": ("#8A4B00", "#FFB224"),
                "chart4": ("#B00000", "#FF6B6B"),
                "chart5": ("#7A00A3", "#5CC8FF"),
            },
        ),
    )
}
DEFAULT_THEME = "slate"

# One shared [light, dark] list per token - see the module docstring.
PALETTE: dict[str, list[str]] = {k: list(v) for k, v in THEMES[DEFAULT_THEME].colors.items()}
_active = DEFAULT_THEME


def color(key: str) -> list[str]:
    """[light, dark] pair for customtkinter widgets; follows colour-theme changes."""
    return PALETTE[key]


def current(key: str) -> str:
    """Resolved colour for the active appearance mode (for tk/ttk/matplotlib)."""
    idx = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
    return PALETTE[key][idx]


def active_theme() -> str:
    return _active


def _load(key: str) -> None:
    global _active
    _active = key if key in THEMES else DEFAULT_THEME
    for token, pair in THEMES[_active].colors.items():
        PALETTE[token][:] = pair


def _install_ctk_defaults() -> None:
    """Point customtkinter's built-in widget defaults at our tokens, so entries, checkboxes,
    switches, drop-downs and scrollbars made without explicit colours follow the theme
    instead of customtkinter's stock blue."""
    p = PALETTE
    overrides = {
        "CTk": {"fg_color": p["bg"]},
        "CTkToplevel": {"fg_color": p["bg"]},
        "CTkFrame": {"fg_color": p["surface"], "top_fg_color": p["surface2"], "border_color": p["surface3"]},
        "CTkButton": {
            "fg_color": p["accent"],
            "hover_color": p["accent_hover"],
            "border_color": p["border"],
            "text_color": p["accent_text"],
            "text_color_disabled": p["muted"],
        },
        "CTkLabel": {"text_color": p["text"]},
        "CTkEntry": {
            "fg_color": p["field"],
            "border_color": p["border"],
            "text_color": p["text"],
            "placeholder_text_color": p["muted"],
        },
        "CTkCheckBox": {
            "fg_color": p["accent"],
            "border_color": p["border"],
            "hover_color": p["accent_hover"],
            "checkmark_color": p["accent_text"],
            "text_color": p["text"],
            "text_color_disabled": p["muted"],
        },
        "CTkSwitch": {
            "fg_color": p["surface3"],
            "progress_color": p["accent"],
            "button_color": p["muted"],
            "button_hover_color": p["text"],
            "text_color": p["text"],
            "text_color_disabled": p["muted"],
        },
        "CTkRadioButton": {
            "fg_color": p["accent"],
            "border_color": p["border"],
            "hover_color": p["accent_hover"],
            "text_color": p["text"],
            "text_color_disabled": p["muted"],
        },
        "CTkProgressBar": {"fg_color": p["surface3"], "progress_color": p["accent"], "border_color": p["muted"]},
        "CTkSlider": {
            "fg_color": p["surface3"],
            "progress_color": p["muted"],
            "button_color": p["accent"],
            "button_hover_color": p["accent_hover"],
        },
        "CTkOptionMenu": {
            "fg_color": p["accent"],
            "button_color": p["accent_hover"],
            "button_hover_color": p["accent_hover"],
            "text_color": p["accent_text"],
            "text_color_disabled": p["muted"],
        },
        "CTkComboBox": {
            "fg_color": p["field"],
            "border_color": p["border"],
            "button_color": p["border"],
            "button_hover_color": p["muted"],
            "text_color": p["text"],
            "text_color_disabled": p["muted"],
        },
        "CTkScrollbar": {"button_color": p["surface3"], "button_hover_color": p["border"]},
        # One text colour serves both states, so unselected segments sit on `muted`,
        # which every theme keeps readable under `accent_text`.
        "CTkSegmentedButton": {
            "fg_color": p["muted"],
            "selected_color": p["accent"],
            "selected_hover_color": p["accent_hover"],
            "unselected_color": p["muted"],
            "unselected_hover_color": p["accent_hover"],
            "text_color": p["accent_text"],
            "text_color_disabled": p["surface3"],
        },
        "CTkTextbox": {
            "fg_color": p["field"],
            "border_color": p["border"],
            "text_color": p["text"],
            "scrollbar_button_color": p["surface3"],
            "scrollbar_button_hover_color": p["border"],
        },
        "CTkScrollableFrame": {"label_fg_color": p["surface2"]},
        "DropdownMenu": {"fg_color": p["surface"], "hover_color": p["select"], "text_color": p["text"]},
    }
    for widget, values in overrides.items():
        ctk.ThemeManager.theme.setdefault(widget, {}).update(values)


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


def apply_theme(key: str) -> None:
    """Switch colour theme live: rewrite the shared token lists, then redraw every widget."""
    _load(key)
    # Light/dark is unchanged, so skip customtkinter's Windows title-bar refresh: it hides and
    # re-shows every window on each redraw, which reads as a blink.
    flag = "_deactivate_windows_window_header_manipulation"
    windows = (ctk.CTk, ctk.CTkToplevel)
    saved = [getattr(w, flag, False) for w in windows]
    for w in windows:
        setattr(w, flag, True)
    try:
        ctk.AppearanceModeTracker.update_callbacks()
    finally:
        for w, value in zip(windows, saved, strict=True):
            setattr(w, flag, value)
    style_treeview()


def init_theme(mode: str = "dark", key: str = DEFAULT_THEME) -> None:
    """Call once, before the first widget exists."""
    ctk.set_default_color_theme("blue")
    _install_ctk_defaults()
    _load(key)
    ctk.set_appearance_mode(mode if mode in MODES else "dark")
