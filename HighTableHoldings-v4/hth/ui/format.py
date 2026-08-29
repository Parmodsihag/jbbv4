"""Display formatting helpers."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from hth.domain.constants import DATE_FMT


def money(value: float | None) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):,.2f}"


def qty(value: float | None) -> str:
    if value is None or value == "":
        return ""
    v = float(value)
    if v.is_integer():
        return f"{int(v):,}"
    return f"{v:,.3f}".rstrip("0").rstrip(".")


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
