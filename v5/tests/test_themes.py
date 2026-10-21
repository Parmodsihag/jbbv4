"""Colour themes: every theme is complete, readable, switches in place and is remembered."""

from __future__ import annotations

import re

import customtkinter as ctk
import pytest

from hth.services.preferences import COLOR_THEMES, Preferences
from hth.ui import theme

HEX = re.compile(r"^#[0-9A-F]{6}$")

# (foreground, background, minimum WCAG contrast) - checked in light and dark
READABLE = [
    ("text", "bg", 7),
    ("text", "surface", 7),
    ("text", "surface_hover", 7),
    ("text", "stripe", 7),
    ("text", "field", 7),
    ("text", "topbar", 7),
    ("text", "select", 4.5),
    ("text", "surface2", 4.5),
    ("text", "accent_soft", 4.5),
    ("muted", "surface", 4.5),
    ("muted", "field", 4.5),
    ("muted", "topbar", 4.5),
    ("accent", "surface", 4.5),
    ("accent", "accent_soft", 4.5),  # selected section, "info" pills
    ("accent_text", "accent", 4.5),
    ("accent_text", "accent_hover", 4.5),
    ("accent_text", "muted", 4.5),  # unselected segments of a switch
    ("success", "surface", 4.5),
    ("danger", "surface", 4.5),
    ("warning", "surface", 4.5),
    ("owe", "surface", 4.5),
    ("weowe", "surface", 4.5),
    ("owe", "owe_soft", 4.5),  # "late" pills, OWES US blocks
    ("weowe", "weowe_soft", 4.5),
    ("warning", "warn_soft", 4.5),  # "due today" pills
    ("on_status", "success", 4.5),
    ("on_status", "success_hover", 4.5),
    ("on_status", "danger", 4.5),
    ("on_status", "danger_hover", 4.5),
    ("on_status", "warning", 4.5),
    ("sidebar_text", "sidebar", 7),
    ("sidebar_text", "sidebar_hover", 4.5),
    ("sidebar_text", "sidebar_active", 4.5),
    ("sidebar_muted", "sidebar", 4.5),
    ("sidebar_muted", "sidebar_hover", 4.5),
    ("sidebar_accent", "sidebar", 4.5),
    ("sidebar_accent", "sidebar_active", 4.5),
]


def _luminance(hex_color: str) -> float:
    channels = []
    for i in (1, 3, 5):
        c = int(hex_color[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.fixture(autouse=True)
def _restore_default():
    yield
    theme._load(theme.DEFAULT_THEME)


def test_every_theme_defines_every_token():
    tokens = set(theme.THEMES[theme.DEFAULT_THEME].colors)
    assert tuple(theme.THEMES) == COLOR_THEMES  # the preference accepts exactly these
    for t in theme.THEMES.values():
        assert set(t.colors) == tokens, t.key
        for token, pair in t.colors.items():
            assert len(pair) == 2 and all(HEX.match(c) for c in pair), (t.key, token, pair)


@pytest.mark.parametrize("key", list(theme.THEMES))
def test_theme_is_readable_in_both_modes(key):
    colors = theme.THEMES[key].colors
    for idx, mode in enumerate(("light", "dark")):
        for fg, bg, need in READABLE:
            ratio = _contrast(colors[fg][idx], colors[bg][idx])
            assert ratio >= need, f"{key} {mode}: {fg} on {bg} is {ratio:.2f}, needs {need}"


def test_switching_rewrites_the_shared_lists_in_place():
    accent = theme.color("accent")
    theme._load("forest")
    assert theme.color("accent") is accent  # widgets holding the list see the change
    assert tuple(accent) == theme.THEMES["forest"].colors["accent"]
    assert theme.active_theme() == "forest"
    theme._load("no-such-theme")
    assert theme.active_theme() == theme.DEFAULT_THEME
    assert tuple(accent) == theme.THEMES[theme.DEFAULT_THEME].colors["accent"]


def test_ctk_defaults_follow_the_palette():
    theme.init_theme("dark", "plum")
    tm = ctk.ThemeManager.theme
    assert tm["CTkButton"]["fg_color"] is theme.color("accent")
    assert tm["CTkEntry"]["fg_color"] is theme.color("field")
    assert tm["CTkSegmentedButton"]["text_color"] is theme.color("accent_text")
    assert tuple(tm["CTk"]["fg_color"]) == theme.THEMES["plum"].colors["bg"]


def test_colour_theme_preference(db):
    prefs = Preferences(db)
    assert prefs.color_theme() == "slate"
    prefs.set_color_theme("paper")
    assert Preferences(db).color_theme() == "paper"
    with pytest.raises(ValueError):
        prefs.set_color_theme("neon")
    prefs.settings.set("ui.color_theme", "gone-in-a-later-version")
    assert prefs.color_theme() == "slate"
