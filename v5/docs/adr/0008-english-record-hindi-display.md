# 0008. English is the record; Hindi is a display layer

* Status: Accepted
* Date: 2026-10-20 (5.1.0)

## Context

The shop wanted the whole program in Hindi, including customer and item names. The code,
the ledger descriptions, the GST bills, the v3 import, search and many comparisons in the
code use English text (`"Sale"`, `"KG"`, tab names read back with `get()`). Translating
values the code compares would break logic in hundreds of places. Customer names were typed
in English letters for years.

## Decision

* **English stays the record of truth** in the database, ledgers, bills, search and exports
  of the data itself.
* Interface text is translated at display time: `hth.i18n.tr(text)` looks it up in one
  phrase table, `hth/i18n/hi.py` (English → Hindi, `{}` holes for numbers). A hook in
  `hth/i18n/widgets.py` makes customtkinter translate labels, buttons, tabs, menus,
  placeholders and titles as they are shown, while values the code reads back stay English.
* Names get a **stored Hindi copy** (`name_hi`, `details_hi`), made offline by
  transliteration (`hth/i18n/translit.py` with a word list of names, gotras, places, brands
  and crops). A copy corrected by hand is marked (`hi_manual = 1`) and never regenerated.
* The language is a shop-wide preference, switched live.

## Consequences

* Switching back to English loses nothing.
* Adding or changing a Hindi word is an edit to `hi.py` only. `HTH_I18N_MISSES=<file>`
  lists text shown in Hindi mode that has no entry yet.
* Charts keep Latin text: matplotlib cannot shape Devanagari.
* Each new English string needs its Hindi entry; `tests/test_hindi.py` checks that every
  pattern fills.

## Alternatives considered

* **gettext `.po` files.** The standard, but needs a build step and tooling for one
  language maintained by one developer; a Python dict is enough.
* **Store Hindi as the record.** Would break the bills, search and the v3 import.
* **Transliterate names at display time.** Slower, and corrections would have nowhere to
  live.
