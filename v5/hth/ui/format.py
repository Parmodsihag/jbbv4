"""Display formatting helpers."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from hth.domain import numbers
from hth.domain.constants import DATE_FMT


def money(value: float | None) -> str:
    """Two decimals with the shop's digit grouping (Indian by default: 12,34,567.00)."""
    return numbers.amount(value, 2)


def qty(value: float | None) -> str:
    return numbers.quantity(value)


def compact_money(value: float | None) -> str:
    """Short form for tiles and chart labels: 1.44 Cr, 12.5 L, 45.2 K (Indian) or M / K."""
    if value is None or value == "":
        return ""
    v = float(value)
    a = abs(v)
    if numbers.get_style() == "indian":
        steps = ((1e7, "Cr"), (1e5, "L"), (1e3, "K"))
    else:
        steps = ((1e9, "B"), (1e6, "M"), (1e3, "K"))
    for size, suffix in steps:
        if a >= size:
            return f"{v / size:.2f}".rstrip("0").rstrip(".") + f" {suffix}"
    return money(v)


def today_str() -> str:
    return dt.date.today().strftime(DATE_FMT)


def days_ago_str(days: int) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).strftime(DATE_FMT)


def open_path(path: Path | str) -> None:
    """Open a file or folder with the OS default handler."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
