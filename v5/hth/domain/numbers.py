"""Number formatting with Indian (12,34,567.00) or international (1,234,567.00) grouping.

The style is shop-wide (Settings -> Appearance) and applied once at start-up with
:func:`set_style`; screens, statements, reminders and search results all format through
:func:`amount` so they agree.
"""

from __future__ import annotations

STYLES = ("indian", "international")
_style = "indian"


def set_style(style: str) -> None:
    global _style
    _style = style if style in STYLES else "indian"


def get_style() -> str:
    return _style


def group(digits: str, style: str | None = None) -> str:
    """Insert separators into a string of digits (no sign, no decimals)."""
    if (style or _style) == "international" or len(digits) <= 3:
        return f"{int(digits):,}" if digits else digits
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join([*pairs, tail])


def amount(value: float | int | str | None, decimals: int = 2, style: str | None = None) -> str:
    """``1234567.5`` -> ``12,34,567.50`` (Indian) or ``1,234,567.50`` (international)."""
    if value is None or value == "":
        return ""
    v = round(float(value), decimals)
    if v == 0:
        v = 0.0  # no "-0.00"
    sign = "-" if v < 0 else ""
    text = f"{abs(v):.{decimals}f}"
    whole, _, frac = text.partition(".")
    return f"{sign}{group(whole, style)}{'.' + frac if frac else ''}"


def quantity(value: float | int | None, style: str | None = None) -> str:
    """Quantities: grouped, up to 3 decimals, trailing zeros dropped."""
    if value is None or value == "":
        return ""
    v = float(value)
    if v.is_integer():
        return amount(v, 0, style)
    return amount(v, 3, style).rstrip("0").rstrip(".")
