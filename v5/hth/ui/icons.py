"""Line icons for navigation and buttons.

Windows ships the Segoe MDL2 Assets icon font (Windows 10 and 11), which renders crisp,
consistent line icons in Tk.  Elsewhere the emoji fallback is used.
"""

from __future__ import annotations

import sys

_WINDOWS = sys.platform.startswith("win")
ICON_FAMILY = "Segoe MDL2 Assets" if _WINDOWS else None

# key -> (Segoe MDL2 code point, fallback)
_ICONS: dict[str, tuple[str, str]] = {
    "dashboard": ("", "⌂"),
    "sales": ("", "🛒"),
    "customers": ("", "👥"),
    "items": ("", "📦"),
    "karar": ("", "📅"),
    "reports": ("", "📊"),
    "users": ("", "👤"),
    "settings": ("", "⚙"),
    "bills": ("", "🧾"),
    "crops": ("", "🌾"),
    "finance": ("", "🏦"),
    "search": ("", "🔍"),
    "lock": ("", "🔒"),
    "signout": ("", "⏻"),
    "moon": ("", "☾"),
    "sun": ("", "☀"),
    "menu": ("", "☰"),
    "history": ("", "↺"),
    "export": ("", "⤓"),
    "calculator": ("", "🖩"),
    "assistant": ("", "💬"),
}


def icon(key: str) -> str:
    glyph, fallback = _ICONS.get(key, ("", "•"))
    return glyph if _WINDOWS and glyph else fallback


def font(size: int = 16):
    """A CTkFont for icons (system default font when the icon font is not available)."""
    from hth.ui import theme

    return theme.font(size, family=ICON_FAMILY) if ICON_FAMILY else theme.font(size)
