"""Hindi interface, transliteration and Hindi copies of names."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from hth import i18n
from hth.i18n.hi import HI
from hth.i18n.translit import to_hindi
from hth.services.hindi import HindiNamesService


@pytest.fixture
def hindi():
    i18n.set_language("hi")
    yield
    i18n.set_language("en")
    i18n.set_names({}, {})


def test_english_is_untouched():
    assert i18n.tr("Dashboard") == "Dashboard"
    assert i18n.tr_cell("Overdue") == "Overdue"
    assert i18n.date_text(dt.date(2026, 10, 20), "%A, %d %B %Y") == "Tuesday, 20 October 2026"


def test_phrases_patterns_and_segments(hindi):
    assert i18n.tr("Dashboard") == "डैशबोर्ड"
    assert i18n.tr("ACCOUNTS") == "खाते"  # upper-cased headings
    assert i18n.tr("  Debit of 1,200.00 recorded  ") == "  नामे 1,200.00 दर्ज  "  # empty last hole, spaces kept
    assert i18n.tr("663 accounts · receivable 1,44,09,317.90 · payable 57,55,438.02") == (
        "663 खाते · लेनदारी 1,44,09,317.90 · देनदारी 57,55,438.02"
    )
    assert i18n.tr("12 entries today") == "आज 12 एंट्री"  # the longer pattern wins
    assert i18n.tr("Delete krar #5 for RAM?") == "RAM का करार #5 हटाएँ?"  # reordered holes
    assert i18n.tr("Something nobody translated") == "Something nobody translated"


def test_every_pattern_fills():
    for key, value in HI.items():
        holes = key.count("{}")
        if holes:
            value.format(*["x"] * holes)  # raises if the Hindi holes do not fit
            assert max((int(i) for i in re.findall(r"\{(\d+)\}", value)), default=-1) < holes, key
        else:
            assert not re.search(r"\{\d*\}", value), key


def test_names_and_cells(hindi):
    i18n.set_names({"RAMESH SIHAG": "रमेश सिहाग", "UREA 45KG": "यूरिया 45 किलो"}, {"ROHTAK": "रोहतक", "NA": "x"})
    assert i18n.tr_cell("RAMESH SIHAG") == "रमेश सिहाग"
    assert i18n.tr_cell("ROHTAK") == "रोहतक"
    assert i18n.tr_cell("NA") == "NA"  # "not available" is never renamed
    assert i18n.tr_cell("2 BAG = UREA 45KG") == "2 BAG = यूरिया 45 किलो"  # names inside free text
    assert i18n.tr_cell("ROHTAK ROAD") == "ROHTAK ROAD"  # details only match a whole cell
    assert i18n.tr_cell("No promise") == "कोई वादा नहीं"
    assert i18n.name("RAMESH SIHAG") == "रमेश सिहाग"
    assert i18n.tr("RAMESH SIHAG · balance 120.00") == "रमेश सिहाग · शेष 120.00"


def test_hindi_dates(hindi):
    assert i18n.date_text(dt.date(2026, 10, 20), "%A, %d %B %Y") == "मंगलवार, 20 अक्टूबर 2026"
    assert i18n.date_text(dt.datetime(2026, 1, 5, 9, 30), "%d %b %H:%M") == "05 जन 09:30"


@pytest.mark.parametrize(
    "english, hindi_text",
    [
        ("RAMESH SIHAG", "रमेश सिहाग"),
        ("OMPARKASH VERMA", "ओमप्रकाश वर्मा"),
        ("SITARAM PONIA", "सीताराम पूनिया"),
        ("AMARSINGH", "अमरसिंह"),  # compound: known ending
        ("RAGHUBIR", "रघुबीर"),  # short vowel before the ending
        ("SUNDER", "सुंदर"),  # unstressed -er-
        ("SHARMA", "शर्मा"),  # cluster with halant
        ("CHAND", "चंद"),  # anusvara
        ("JADIYA", "जाडिया"),
        ("9812345678 ROHTAK", "9812345678 रोहतक"),
        ("NA", "NA"),
    ],
)
def test_transliterate_names(english, hindi_text):
    assert to_hindi(english) == hindi_text


@pytest.mark.parametrize(
    "english, hindi_text",
    [
        ("CONFIDOR 250GM BAYER", "कॉन्फिडोर 250 ग्राम बायर"),
        ("UREA 45KG IFFCO", "यूरिया 45 किलो इफको"),
        ("CORAGEN 60ML FMC", "कोराजन 60 एमएल एफएमसी"),
        ("CYPERKILL 250ML", "साइपर्किल 250 एमएल"),  # soft c, y as "ai", doubled l
        ("METHI", "मेथी"),
        ("PROTECT 1263 500GM IPL", "प्रोटेक्ट 1263 500 ग्राम आईपीएल"),
    ],
)
def test_transliterate_items(english, hindi_text):
    assert to_hindi(english, item=True) == hindi_text


def test_hindi_copies_follow_renames_unless_corrected(accounts, inventory, db):
    svc = HindiNamesService(db)
    c = accounts.add_customer("ramesh sihag", "rohtak", 0)
    item = inventory.add_item("UREA 45KG IFFCO")
    assert accounts.get_customer(c.id).name_hi == "रमेश सिहाग"
    assert inventory.get_item(item.id).name_hi == "यूरिया 45 किलो इफको"
    accounts.update_customer(c.id, "suresh sihag", "rohtak", "admin")  # automatic copy follows the rename
    assert accounts.get_customer(c.id).name_hi == "सुरेश सिहाग"
    svc.set_customer(c.id, "सुरेश जी सिहाग", "रोहतक", "admin")  # corrected by hand ...
    accounts.update_customer(c.id, "suresh kumar", "rohtak", "admin")
    assert accounts.get_customer(c.id).name_hi == "सुरेश जी सिहाग"  # ... and kept
    svc.fill_missing("admin", regenerate=True)
    assert accounts.get_customer(c.id).name_hi == "सुरेश जी सिहाग"
    svc.reset("customer", c.id, "admin")
    assert accounts.get_customer(c.id).name_hi == "सुरेश कुमार" and not accounts.get_customer(c.id).hi_manual
    names, details = svc.lookup()
    assert names["SURESH KUMAR"] == "सुरेश कुमार" and details["ROHTAK"] == "रोहतक"
    assert names[f"{c.id} SURESH KUMAR ROHTAK"] == f"{c.id} सुरेश कुमार रोहतक"  # picker label
    with pytest.raises(Exception, match="required"):
        svc.set_item(item.id, "  ", "admin")


def test_fill_missing_only_touches_empty_copies(accounts, db):
    c = accounts.add_customer("ram", "", 0)
    db.execute("UPDATE customers SET name_hi = '', details_hi = '' WHERE id = ?", (c.id,))
    assert HindiNamesService(db).fill_missing() == (1, 0)
    assert HindiNamesService(db).fill_missing() == (0, 0)
    assert accounts.get_customer(c.id).name_hi == "राम"


def test_hindi_documents_and_reminders(hindi, accounts, krar, db):
    from hth.services.reminders import ReminderService
    from hth.services.statements import StatementService

    c = accounts.add_customer("ramesh sihag", "rohtak 9812345678", 1500, "2026-08-01")
    i18n.set_names(*HindiNamesService(db).lookup())
    html = StatementService(db).html(StatementService(db).build(c.id, "2026-08-01", "2026-08-31"))
    assert "खाता विवरण" in html and "रमेश सिहाग" in html and "शुरुआती शेष" in html
    krar.add_or_update(c.id, "2026-10-01")
    r = ReminderService(db)
    assert r.build(c.id).text.startswith("नमस्ते रमेश सिहाग जी")
    r.set_template("नमस्ते {name} जी - ₹{amount}")
    i18n.set_language("en")
    assert r.template().startswith("Namaste {name} ji")  # each language keeps its own template
    i18n.set_language("hi")
    assert r.template() == "नमस्ते {name} जी - ₹{amount}"
