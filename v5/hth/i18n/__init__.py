"""Interface language (English / हिन्दी).

English is the source language: every visible string in the code stays English and is
looked up here when Hindi is on, so switching back changes nothing and there is no
second copy of any screen to maintain.

* :func:`tr` - interface text.  Exact phrase first; then, for composite texts such as
  ``"12 entries · debit 1,200.00"``, each ``·``-separated / line segment on its own; then
  patterns written with ``{}`` holes (``"{} entries"`` -> ``"{} प्रविष्टियाँ"``).
* :func:`tr_cell` - a table cell: customer / item names first (their stored Hindi copy),
  then the same lookups, then known item and customer names inside free text
  (ledger particulars such as ``2 BAG = UREA``).
* :mod:`hth.i18n.widgets` installs the hook into customtkinter so labels, buttons, tabs,
  menus and placeholders translate themselves; values the code compares (a tab name, an
  option-menu choice) stay English underneath.

Nothing here touches the database - names are handed in with :func:`set_names`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

LANGUAGES = {"en": "English", "hi": "हिन्दी"}
DEVANAGARI_FONT = "Nirmala UI"  # ships with Windows 8+; Latin glyphs too

_lang = "en"
_exact: dict[str, str] = {}
_patterns: list[tuple[re.Pattern, str]] = []
_names: dict[str, str] = {}  # English customer / item text -> Hindi copy
_inline: list[tuple[str, str]] = []  # names replaced inside free text, longest first
_misses: set[str] = set()
_SEGMENT_SPLIT = re.compile(r"(\s+·\s+|\n|\s{3,})")
_HAS_LATIN = re.compile(r"[A-Za-z]{2,}")


def _load() -> None:
    from hth.i18n.hi import HI

    _exact.clear()
    _patterns.clear()
    for key, value in HI.items():
        if "{}" in key:
            body = re.escape(key).replace(r"\{\}", "(.*?)")  # a hole may be empty: "recorded{}"
            _patterns.append((re.compile(f"^{body}$", re.DOTALL), value))
        else:
            _exact[key] = value
    # longer patterns first: "{} entries today" before "{} entries"
    _patterns.sort(key=lambda p: -len(p[0].pattern))


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in LANGUAGES else "en"
    if _lang == "hi" and not _exact:
        _load()


def language() -> str:
    return _lang


def is_hindi() -> bool:
    return _lang == "hi"


# Names -----------------------------------------------------------------------------------
def set_names(names: dict[str, str], details: dict[str, str] | None = None) -> None:
    """English customer / item names and details with their Hindi copies (refreshed by the
    app).  Names are also replaced inside free text (ledger particulars); details only match
    a whole cell."""
    _names.clear()
    _names.update({k: v for k, v in (details or {}).items() if k and v and k != v and k != "NA"})
    clean = {k: v for k, v in names.items() if k and v and k != v}
    _names.update(clean)
    # replaced inside free text only when long enough not to hit parts of other words
    _inline[:] = sorted(((k, v) for k, v in clean.items() if len(k) >= 4), key=lambda kv: -len(kv[0]))


def name(text: str | None) -> str:
    """The Hindi copy of a customer / item name or details when Hindi is on."""
    if not text or _lang != "hi":
        return text or ""
    return _names.get(text, text)


# Lookup ------------------------------------------------------------------------------------
def _fill(template: str, groups: Iterable[str]) -> str:
    """Hindi templates use ``{}`` in order, or ``{0}`` / ``{1}`` when Hindi word order differs."""
    return template.format(*(tr(g) for g in groups))


def _one(text: str) -> str | None:
    """Translate one phrase, or None."""
    if text in _exact:
        return _exact[text]
    if text.isupper() and len(text) > 1:  # section headings are upper-cased in code
        hit = _exact.get(text.capitalize()) or _exact.get(text.title())
        if hit:
            return hit
    for pattern, template in _patterns:
        m = pattern.match(text)
        if m:
            return _fill(template, m.groups())
    return None


class Raw(str):
    """Text that is already in the language it should be shown in (assistant answers, a
    customer's own words) - ``tr`` passes it through untouched."""

    __slots__ = ()


def tr(text: str | None) -> str:
    """Interface text in the current language."""
    if isinstance(text, Raw):
        return str(text)
    if not text or _lang != "hi" or not isinstance(text, str):
        return text if isinstance(text, str) else ("" if text is None else str(text))
    core = text.strip()
    if not core:
        return text
    lead, trail = text[: len(text) - len(text.lstrip())], text[len(text.rstrip()) :]
    hit = _one(core)
    if hit is None and core in _names:
        hit = _names[core]
    if hit is None:
        parts = _SEGMENT_SPLIT.split(core)
        if len(parts) > 1:
            out = []
            for i, part in enumerate(parts):
                if i % 2:  # separator
                    out.append(part)
                else:
                    seg = part.strip()
                    got = (_one(seg) or _names.get(seg)) if seg else None
                    if got is None and seg:
                        _miss(seg)
                    out.append(part.replace(seg, got) if got is not None and seg else part)
            return lead + "".join(out) + trail
        _miss(core)
        return text
    return lead + hit + trail


def tr_cell(value) -> str:
    """A table cell: names first, then interface words, then names inside free text."""
    text = "" if value is None else str(value)
    if _lang != "hi" or not text:
        return text
    if text in _names:
        return _names[text]
    hit = _one(text)
    if hit is not None:
        return hit
    if _HAS_LATIN.search(text):
        out = text
        for en, hi in _inline:
            if en in out:
                out = out.replace(en, hi)
        return out
    return text


# Dates ---------------------------------------------------------------------------------------
_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
_MONTHS_SHORT = ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुला", "अग", "सित", "अक्टू", "नव", "दिस"]
_DAYS = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
_DAYS_SHORT = ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"]


def date_text(day, fmt: str) -> str:
    """``day.strftime(fmt)`` with Hindi month and weekday names when Hindi is on
    (``%A %a %B %b`` only; digits stay as they are)."""
    if _lang != "hi":
        return day.strftime(fmt)
    # Windows strftime rejects non-ASCII formats: format with markers, then put the names in
    marked = fmt.replace("%A", "\x01").replace("%B", "\x02").replace("%b", "\x03").replace("%a", "\x04")
    out = day.strftime(marked)
    return (
        out.replace("\x01", _DAYS[day.weekday()])
        .replace("\x04", _DAYS_SHORT[day.weekday()])
        .replace("\x02", _MONTHS[day.month - 1])
        .replace("\x03", _MONTHS_SHORT[day.month - 1])
    )


# Coverage helper ---------------------------------------------------------------------------
def _miss(text: str) -> None:
    if os.environ.get("HTH_I18N_MISSES") and _HAS_LATIN.search(text) and not text.isupper():
        _misses.add(text)


def dump_misses(path: str | None = None) -> list[str]:
    """Strings seen in Hindi mode with no translation (set HTH_I18N_MISSES=<file>)."""
    out = sorted(_misses)
    path = path or os.environ.get("HTH_I18N_MISSES")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(out) + ("\n" if out else ""))
    return out
