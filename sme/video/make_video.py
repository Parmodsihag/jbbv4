"""The project screencast: 1920x1080, about 2:45, voice-over and subtitles.

    python sme/video/make_video.py              # everything -> sme/video/out/high-table-holdings.mp4
    python sme/video/make_video.py capture      # only one step: capture | slides | voice | build

Windows only.  Every app picture is the real program, driven by this script on a made-up demo
shop in a throwaway folder (the shop's data is never opened).  The terminal part shows a real
fresh clone, install and test run (``fresh_run.txt``).  Narration is spoken by Windows' own
voices (Microsoft Ravi, English (India); the assistant's answer by Microsoft Kalpana, Hindi).
Team number and names for the title and closing slides come from ``team.json``.

Steps write into ``out/``: ``frames/`` (app captures), ``slides/``, ``voice/``, then the video.
Needs ffmpeg on PATH, Pillow, numpy, pywin32 and Microsoft Edge (renders the slides).
"""

from __future__ import annotations

import ctypes
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
V5 = ROOT / "v5"
OUT = HERE / "out"
FRAMES, SLIDES = OUT / "frames", OUT / "slides"
VOICE = OUT / "voice"  # per cut: see use_cut()
VIDEO = OUT / "high-table-holdings.mp4"
CUT = "tour"


def use_cut(cut: str) -> None:
    """tour: the feature tour; problems: the shop's problems and how each is solved."""
    global CUT, VOICE, VIDEO
    CUT = cut
    VOICE = OUT / ("voice" if cut == "tour" else f"voice-{cut}")
    VIDEO = OUT / ("high-table-holdings.mp4" if cut == "tour" else f"high-table-holdings-{cut}.mp4")

W, H, FPS = 1920, 1080, 30
APP_W, APP_H = 1366, 745  # the shop's 1366x768 screen, as readme_shots draws it
APP_BOX = (161, 78, 161 + 1598, 78 + 872)  # where the app sits on the 1920x1080 canvas
RATE = 22050  # narration sample rate

FONTS = Path("C:/Windows/Fonts")
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
ACCENT = (34, 211, 238)
INK = (241, 245, 249)
MUTED = (148, 163, 184)


# Storyboard ---------------------------------------------------------------------------------
@dataclass
class Line:
    show: str  # subtitle
    say: str | None = None  # what the voice reads, when it needs help with a word; None = show
    clip: str | None = None  # a prepared recording instead of the narrator (voice/<clip>.wav)
    pause: float = 0.35  # silence after it


@dataclass
class Shot:
    frame: str  # frames/<frame>.png
    at: tuple[int, float] = (0, 0.0)  # appears at (line index, fraction of that line)
    box: tuple[int, int, int, int] | None = None  # highlight, in app pixels
    zoom: float = 1.0  # > 1 moves the camera in on the box


@dataclass
class Scene:
    key: str
    chapter: str
    lines: list[Line]
    slide: str | None = None
    shots: list[Shot] = field(default_factory=list)
    terminal: list[tuple[str, str]] | None = None
    lead: float = 0.45
    tail: float = 0.55


def storyboard_tour() -> list[Scene]:
    return [
        Scene(
            "title",
            "",
            [
                Line(
                    "High Table Holdings: the shop computer of Jaat Beaj Bhander, an agri-input shop.",
                    "High Table Holdings. The shop computer of Jaat Beej Bhandaar, an agri input shop.",
                ),
                Line("Our Software Engineering and Management project.", pause=0.2),
            ],
            slide="title",
            lead=0.8,
        ),
        Scene(
            "problem",
            "The problem",
            [
                Line(
                    "The shop sells on credit at 24 % a year; farmers pay after the harvest, often in wheat.",
                    "The shop sells on credit at twenty four percent a year; farmers pay after the harvest, "
                    "often in wheat.",
                ),
                Line("The old program had one table per customer, no users and no tests."),
            ],
            slide="problem",
        ),
        Scene(
            "build",
            "Build and test",
            [
                Line("Build it from the public repository: clone, a virtual environment, the requirements."),
                Line(
                    "Then 280 tests check interest, settlement, stock, crop costing and migrations, in 40 seconds.",
                    "Then two hundred and eighty tests check interest, settlement, stock, crop costing and migrations, "
                    "in forty seconds.",
                ),
            ],
            terminal=BUILD_TERMINAL,
            lead=0.4,
        ),
        Scene(
            "run",
            "Run and sign in",
            [
                Line(
                    "python run.py starts it; on the shop PC a launcher does, with no console window.",
                    "Python, run dot pie, starts it. On the shop PC, a launcher does, with no console window.",
                ),
                Line("Everyone signs in as themselves, and every change is audited."),
            ],
            terminal=RUN_TERMINAL,
            shots=[
                Shot("login_0", (0, 0.6)),
                Shot("login_1", (1, 0.0), box=(498, 298, 868, 458), zoom=1.6),
                Shot("login_2", (1, 0.4), box=(498, 298, 868, 458), zoom=1.6),
            ],
            lead=0.3,
        ),
        Scene(
            "today",
            "Today",
            [
                Line("Today lists what needs the owner: promises due, with WhatsApp one click away,"),
                Line("stock about to run out, a missing backup, and who owes what, by age."),
            ],
            shots=[
                Shot("today", (0, 0.0)),
                Shot("today", (0, 0.25), box=(16, 143, 932, 415), zoom=1.3),
                Shot("today", (1, 0.0), box=(16, 430, 932, 738), zoom=1.3),
                Shot("today", (1, 0.6), box=(946, 370, 1350, 582), zoom=1.45),
            ],
        ),
        Scene(
            "counter",
            "Counter",
            [
                Line("The Counter speaks shop language: sale, purchase, payment in, payment out."),
                Line("Pick a customer: their balance, interest and promise appear."),
                Line("Add several items, and take part of the money now, in cash."),
                Line("One save writes the khata, the stock and the cash book together, or nothing at all."),
                Line("And a mistake can be undone.", pause=0.2),
            ],
            shots=[
                Shot("counter_0", (0, 0.0), box=(310, 70, 1052, 128), zoom=1.35),
                Shot("counter_1", (1, 0.0), box=(16, 72, 300, 400), zoom=1.45),
                Shot("counter_2", (2, 0.0), box=(310, 140, 1052, 520), zoom=1.25),
                Shot("counter_3", (2, 0.2), box=(310, 140, 1052, 520), zoom=1.25),
                Shot("counter_4", (2, 0.4), box=(310, 140, 1052, 520), zoom=1.25),
                Shot("counter_5", (2, 0.7), box=(1062, 72, 1352, 420), zoom=1.45),
                Shot("counter_6", (3, 0.1), box=(960, 673, 1357, 724), zoom=1.4),
                Shot("counter_7", (4, 0.0), box=(1199, 673, 1357, 724), zoom=1.4),
            ],
        ),
        Scene(
            "khata",
            "Khata and collections",
            [
                Line(
                    "Interest is a daily rate, compounded each 31st of March, as the old program did.",
                    "Interest is a daily rate, compounded each thirty first of March, as the old program did.",
                ),
                Line("Collections sorts promises into late, today and coming, with the reminder already written."),
            ],
            shots=[
                Shot("khata", (0, 0.0)),
                Shot("khata", (0, 0.2), box=(1070, 120, 1350, 210), zoom=1.6),
                Shot("collections", (1, 0.0)),
                Shot("collections", (1, 0.45), box=(1020, 120, 1350, 600), zoom=1.35),
            ],
        ),
        Scene(
            "stock",
            "Stock, money, reports",
            [
                Line("Stock shows how many days each item will last, and Money keeps the cash book."),
                Line("Thirty-four reports search, filter and go to Excel."),
            ],
            shots=[
                Shot("stock", (0, 0.0), box=(1134, 192, 1334, 268), zoom=1.5),
                Shot("money", (0, 0.55)),
                Shot("reports_0", (1, 0.0)),
                Shot("reports_1", (1, 0.5)),
            ],
        ),
        Scene(
            "assistant",
            "Ask a question",
            [
                Line("Ask a question in Hindi, Hinglish or English, typed or spoken."),
                Line(
                    "“Sabse bade 5 bakayedar”, the five biggest debtors, comes back in Hindi.",
                    "Sabse bade paanch bakaayedaar. The five biggest debtors. It comes back in Hindi.",
                ),
                Line("If a name fits two customers it asks which one, then answers, aloud:"),
                Line("(the answer, spoken in Hindi)", clip="hindi_answer", pause=0.4),
                Line("Offline and read-only: it can never change the books."),
            ],
            shots=[
                Shot("assistant_1", (0, 0.0)),
                Shot("assistant_2", (2, 0.0)),
                Shot("assistant_3", (3, 0.0)),
            ],
        ),
        Scene(
            "hindi",
            "Hindi and themes",
            [
                Line("One switch puts everything in Hindi, names included, without changing the records."),
                Line("Seven colour themes, light and dark, each tested for readable contrast."),
            ],
            shots=[
                Shot("hindi_counter", (0, 0.0)),
                Shot("theme_forest", (1, 0.0)),
                Shot("theme_saffron", (1, 0.33)),
                Shot("theme_contrast", (1, 0.66)),
            ],
        ),
        Scene(
            "safety",
            "Safe with the books",
            [
                Line("Backups run every day, and restores are checked first."),
                Line("Updates come from GitHub, every file hash-checked, and can be undone."),
            ],
            shots=[
                Shot("settings_backup", (0, 0.0), box=(270, 70, 1330, 420), zoom=1.15),
                Shot("settings_updates", (1, 0.0), box=(270, 70, 1330, 360), zoom=1.15),
            ],
        ),
        Scene(
            "architecture",
            "How it is built",
            [
                Line("Screens call services, services hold the rules, and one SQLite file holds the books."),
                Line("Feature modules plug in, migrations are atomic, and every big decision is recorded."),
            ],
            slide="architecture",
        ),
        Scene(
            "quality",
            "Quality and documents",
            [
                Line("316 automated tests pass.", "Three hundred and sixteen automated tests pass."),
                Line(
                    "The repository also holds the SRS, diagrams, decision tables, algebraic specifications, "
                    "the PERT plan, test cases and guides."
                ),
            ],
            slide="quality",
        ),
        Scene(
            "end",
            "",
            [Line("Thank you. Code, tests and documents are on GitHub.", pause=0.2)],
            slide="end",
            tail=1.6,
        ),
    ]


# The terminal part: a real fresh clone on this PC (fresh_run.txt), shortened with "…".
BUILD_TERMINAL = [
    ("cmd", "git clone https://github.com/Parmodsihag/jbbv4.git"),
    ("out", "Cloning into 'jbbv4'..."),
    ("cmd", "cd jbbv4\\v5"),
    ("cmd", "python -m venv .venv"),
    ("cmd", ".venv\\Scripts\\activate"),
    ("venv", ""),
    ("cmd", "pip install -r requirements.txt"),
    ("out", "Collecting customtkinter>=5.2 (from -r requirements.txt (line 1))"),
    ("out", "Collecting matplotlib>=3.7 (from -r requirements.txt (line 2))"),
    ("out", "Collecting openpyxl>=3.1 (from -r requirements.txt (line 3))"),
    ("dim", "  \u2026"),
    ("ok", "Successfully installed customtkinter-6.0.0 docxtpl-0.20.2 matplotlib-3.10.9 numpy-2.2.6"),
    ("ok", "  openpyxl-3.1.5 pypdf-6.21.2 pywin32-311 sounddevice-0.5.3 vosk-0.3.45 \u2026"),
    ("cmd", "pip install -r requirements-dev.txt"),
    ("ok", "Successfully installed pytest-9.1.1 ruff-0.17.2 \u2026"),
    ("cmd", "pytest -rs"),
    ("dim", "  \u2026"),
    ("out", "........................................................................ [ 91%]"),
    ("out", "...........................s                                             [100%]"),
    ("dim", "SKIPPED [33] set HTH_UI_TESTS=1 to run UI tests   (the real-window tests)"),
    ("dim", "SKIPPED [2]  could not import 'docx2pdf'          (optional PDF through Word)"),
    ("dim", "SKIPPED [1]  set HTH_VOICE_MODEL=<folder> to run  (real voice model)"),
    ("pass", "280 passed, 36 skipped in 39.60s"),
]
RUN_TERMINAL = [("venv", ""), ("cmd", "python run.py")]


def storyboard_problems() -> list[Scene]:
    """The same program told as the shop's problems and how each one is solved."""

    def card(n, chapter, problem_lines, shots, **kw):
        return Scene(f"p{n}", f"Problem {n} · {chapter}", problem_lines, slide=f"p_card_{n}", shots=shots, **kw)

    return [
        Scene(
            "intro",
            "",
            [Line("Running an agri-input shop on credit is hard. High Table Holdings makes it simple.", pause=0.2)],
            slide="p_title",
            lead=0.8,
        ),
        Scene(
            "shop",
            "",
            [
                Line("Farmers take seed and fertiliser now and pay after the harvest; many sell their wheat back to the shop."),
                Line("The owner keeps every account, chases every promise and makes the GST bills, mostly by hand."),
            ],
            slide="p_shop",
        ),
        Scene(
            "list",
            "",
            [Line("That makes eight everyday problems. Here is how we solved each one.")],
            slide="p_problems",
        ),
        card(
            1,
            "Who owes what",
            [
                Line("One: who owes me what, exactly?"),
                Line(
                    "Every account earns 24 % a year, added each 31st of March. The program works it out to the paisa, every day,",
                    "Every account earns twenty four percent a year, added each thirty first of March. "
                    "The program works it out to the paisa, every day,",
                ),
                Line("and shows what was entered apart from the interest."),
            ],
            [
                Shot("khata", (1, 0.0)),
                Shot("khata", (2, 0.0), box=(1070, 120, 1350, 210), zoom=1.6),
            ],
        ),
        card(
            2,
            "Forgotten promises",
            [
                Line("Two: promises to pay get forgotten."),
                Line("Today lists every promise due or late, and Collections writes the reminder, with WhatsApp one click away."),
            ],
            [
                Shot("today", (1, 0.0), box=(16, 143, 932, 415), zoom=1.3),
                Shot("collections", (1, 0.5), box=(1020, 120, 1350, 600), zoom=1.35),
            ],
        ),
        card(
            3,
            "A busy counter",
            [
                Line("Three: a busy counter, and mistakes."),
                Line("Sale, purchase, payment in, payment out, in plain words; several items, part paid in cash."),
                Line("One save updates the account, the stock and the cash book together, and a mistake can be undone."),
            ],
            [
                Shot("counter_1", (1, 0.0), box=(310, 70, 1052, 128), zoom=1.35),
                Shot("counter_4", (1, 0.45), box=(310, 140, 1052, 520), zoom=1.25),
                Shot("counter_5", (1, 0.75), box=(1062, 72, 1352, 420), zoom=1.45),
                Shot("counter_6", (2, 0.0), box=(960, 673, 1357, 724), zoom=1.4),
                Shot("counter_7", (2, 0.72), box=(1199, 673, 1357, 724), zoom=1.4),
            ],
        ),
        card(
            4,
            "Stock runs out",
            [
                Line("Four: stock runs out, or expires on the shelf."),
                Line("Every item shows how many days it will last, and Today warns in time."),
            ],
            [
                Shot("stock", (1, 0.0), box=(1134, 192, 1334, 268), zoom=1.5),
                Shot("today", (1, 0.55), box=(16, 430, 470, 738), zoom=1.45),
            ],
        ),
        card(
            5,
            "Crops from farmers",
            [
                Line("Five: crops bought back from farmers."),
                Line("Wheat comes in as lots, with the deduction weighed off."),
                Line("When it is sold, the cost comes from the oldest lots, and the margin shows before saving."),
            ],
            [
                Shot("crop_buy", (1, 0.0), box=(322, 196, 1052, 470), zoom=1.3),
                Shot("crop_sell", (2, 0.0), box=(322, 196, 1052, 470), zoom=1.3),
            ],
        ),
        card(
            6,
            "Where the money went",
            [
                Line("Six: where did the money go?"),
                Line("The cash book keeps cash, bank and UPI, expenses, rent and profit; and GST bills take seconds."),
            ],
            [
                Shot("money", (1, 0.0)),
                Shot("bills", (1, 0.62), box=(16, 250, 1352, 560)),
            ],
        ),
        card(
            7,
            "Computers and English",
            [
                Line("Seven: not everyone is at home with computers, or with English."),
                Line("Everything switches to Hindi, names included."),
                Line(
                    "Or just ask, in Hindi, Hinglish or English: “sabse bade 5 bakayedar”.",
                    "Or just ask, in Hindi, Hinglish or English. Sabse bade paanch bakaayedaar.",
                ),
                Line("Ask by voice, and hear the answer:"),
                Line("(the answer, spoken in Hindi)", clip="hindi_answer", pause=0.4),
            ],
            [
                Shot("hindi_counter", (1, 0.0)),
                Shot("assistant_1", (2, 0.0)),
                Shot("assistant_3", (3, 0.0)),
            ],
        ),
        card(
            8,
            "Trust and safety",
            [
                Line("Eight: can I trust the records, and keep them safe?"),
                Line("Staff can sell but not change history, and every change records who made it."),
                Line("The screen locks when you step away, and the books are backed up every day."),
            ],
            [
                Shot("audit", (1, 0.0), box=(20, 240, 1350, 620), zoom=1.15),
                Shot("locked", (2, 0.0)),
                Shot("settings_backup", (2, 0.55), box=(270, 70, 1330, 420), zoom=1.15),
            ],
        ),
        Scene(
            "how",
            "",
            [Line("It runs on the shop's own PC, without internet, keeps everything in one file, and updates itself safely.")],
            slide="p_how",
        ),
        Scene(
            "setup",
            "Setting it up",
            [
                Line(
                    "Setting it up takes a few commands: clone, install and test; 280 tests pass in 40 seconds.",
                    "Setting it up takes a few commands: clone, install and test. "
                    "Two hundred and eighty tests pass in forty seconds.",
                ),
                Line("Then python run.py starts it.", "Then python, run dot pie, starts it."),
            ],
            terminal=BUILD_TERMINAL + RUN_TERMINAL[1:],
            shots=[Shot("login_0", (1, 0.75))],
            lead=0.4,
        ),
        Scene(
            "trust",
            "",
            [
                Line(
                    "Behind it: 316 automated tests, and full documentation, from requirements to test cases.",
                    "Behind it: three hundred and sixteen automated tests, and full documentation, from requirements to test cases.",
                )
            ],
            slide="p_quality",
        ),
        Scene(
            "bye",
            "",
            [Line("Fewer problems at the counter. Thank you.", pause=0.2)],
            slide="p_end",
            tail=1.8,
        ),
    ]


def storyboard_technical() -> list[Scene]:
    """For a Software Engineering & Management class: how it was specified, designed, tested and managed."""
    return [
        Scene(
            "intro",
            "",
            [Line("High Table Holdings, the engineering view: how we specified, designed, tested and managed it.", pause=0.2)],
            slide="t_title",
            lead=0.8,
        ),
        Scene(
            "scope",
            "",
            [Line("One shop, one PC, often offline. We worked iteratively, in twenty releases, writing the money rules test-first.")],
            slide="t_scope",
        ),
        Scene(
            "req",
            "",
            [
                Line(
                    "Requirements go from informal to formal: 42 user stories, 29 use cases,",
                    "Requirements go from informal to formal: forty two user stories, twenty nine use cases,",
                ),
                Line(
                    "then 80 numbered functional requirements and 15 non-functional ones.",
                    "then eighty numbered functional requirements, and fifteen non-functional ones.",
                ),
            ],
            slide="t_req",
        ),
        Scene(
            "models",
            "",
            [Line("Semi-formal models show behaviour: state diagrams for sign-in and promises,", pause=0.15)],
            slide="t_state",
            tail=0.3,
        ),
        Scene("seq", "", [Line("and sequence diagrams across the layers.")], slide="t_seq", lead=0.3),
        Scene(
            "dfd",
            "",
            [Line("Data flow diagrams run from the context diagram,", pause=0.15)],
            slide="t_dfd0",
            tail=0.3,
        ),
        Scene("dfd2", "", [Line("through level one, to level two for recording a sale.")], slide="t_dfd2", lead=0.3),
        Scene(
            "er",
            "",
            [Line("The data model is one SQLite file: twenty tables and six forward-only migrations, each atomic and backed up first.")],
            slide="t_er",
        ),
        Scene(
            "dt",
            "",
            [
                Line("Branching rules are 22 decision tables, complete and mutually exclusive.", "Branching rules are twenty two decision tables, complete and mutually exclusive."),
                Line("This one says exactly what a counter save writes."),
            ],
            slide="t_dt",
        ),
        Scene(
            "alg",
            "",
            [
                Line("The core types have algebraic specifications: a settlement always leaves a balance of zero,"),
                Line("and a save that fails writes nothing, while undo restores the books."),
            ],
            slide="t_alg",
        ),
        Scene(
            "arch",
            "",
            [Line("The architecture is strictly layered: screens, services, rules and data, and thirteen decision records explain each major choice.")],
            slide="t_arch",
        ),
        Scene(
            "code",
            "",
            [Line("Interest lives in one place, and every write is one transaction: commit, or roll everything back.")],
            slide="t_code",
        ),
        Scene(
            "trace",
            "Traceability · FR-9.1",
            [
                Line("One requirement, end to end: FR-9.1, several items and a payment, saved all or nothing.", "One requirement, end to end. F R nine point one: several items and a payment, saved all or nothing."),
                Line(
                    "Specified by decision tables and the entry spec, built in the sales service, verified by test case 83, and here on screen.",
                    "Specified by decision tables and the entry spec, built in the sales service, verified by test case eighty three, and here on screen.",
                ),
            ],
            slide="t_trace",
            shots=[
                Shot("counter_5", (1, 0.5), box=(1062, 72, 1352, 420), zoom=1.45),
                Shot("counter_6", (1, 0.85), box=(960, 673, 1357, 724), zoom=1.4),
            ],
        ),
        Scene(
            "test",
            "",
            [
                Line(
                    "Testing is risk-based: 316 automated tests from unit to UI level, every requirement traced, all passing.",
                    "Testing is risk-based: three hundred and sixteen automated tests, from unit to U I level, every requirement traced, all passing.",
                )
            ],
            slide="t_test",
        ),
        Scene(
            "wbs",
            "",
            [Line("Planning starts from a work breakdown structure,", pause=0.15)],
            slide="t_wbs",
            tail=0.3,
        ),
        Scene(
            "plan",
            "",
            [
                Line("then an activity network with PERT estimates: the baseline critical path was 57 working days.", "then an activity network with PERT estimates. The baseline critical path was fifty seven working days."),
                Line(
                    "Re-planned against actual progress, the rest is 8.3 days, 97 % likely by the 5th of November.",
                    "Re-planned against actual progress, the rest is eight point three days, ninety seven percent likely by the fifth of November.",
                ),
            ],
            slide="t_plan",
            lead=0.3,
        ),
        Scene(
            "pm",
            "",
            [Line("Configuration and change management: semantic versions, a separate update branch, a change log and a risk register.")],
            slide="t_pm",
        ),
        Scene(
            "deploy",
            "Deployment",
            [
                Line(
                    "Deployment is clone, install, test and run; on a fresh clone 280 tests pass in 40 seconds.",
                    "Deployment is clone, install, test, and run. On a fresh clone, two hundred and eighty tests pass in forty seconds.",
                ),
                Line("Updates are hash-checked, staged, applied before start-up, and can be undone."),
            ],
            terminal=BUILD_TERMINAL + RUN_TERMINAL[1:],
            shots=[Shot("settings_updates", (1, 0.2), box=(270, 70, 1330, 360), zoom=1.15)],
            lead=0.4,
        ),
        Scene(
            "bye",
            "",
            [Line("Every artefact is in the public repository. Thank you.", pause=0.2)],
            slide="t_end",
            tail=1.8,
        ),
    ]


CUTS = {"tour": storyboard_tour, "problems": storyboard_problems, "technical": storyboard_technical}


def storyboard(cut: str = "tour") -> list[Scene]:
    return CUTS[cut]()


# 1. Capture: drive the real app on a demo shop ------------------------------------------------
def capture() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="hth-video-"))
    os.environ["HTH_DATA_DIR"] = str(data)
    os.environ["HTH_NO_UPDATE_CHECK"] = "1"
    sys.path[:0] = [str(V5), str(V5 / "tools")]
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    import customtkinter as ctk

    ctk.deactivate_automatic_dpi_awareness()
    from PIL import ImageGrab

    import hth.assistant.voice as voice
    import readme_shots as rs
    from hth.assistant import speech
    from hth.config import get_settings
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.services.accounts import AccountsService
    from hth.services.auth import AuthService
    from hth.services.hindi import HindiNamesService
    from hth.services.preferences import Preferences
    from hth.services.sales import SalesService
    from hth.ui.views.setup import mark_setup

    voice.bundled_dir = lambda: data / "no-voice"
    settings = get_settings()
    db = Database(settings.db_path)
    initialize(db)
    AuthService(db).ensure_default_users()
    mark_setup(db, True)
    prefs = Preferences(db)
    prefs.set_layout("new")
    prefs.set_theme("light")
    prefs.set_language("en")
    people, stock = rs.demo_shop(db)
    # a second Ramesh, so the assistant has to ask which one
    saini = AccountsService(db).add_customer("RAMESH SAINI", "BHIWANI 9800000013", 0, _ago(150)).id
    urea = stock["UREA 45KG"]
    SalesService(db).record("P", _ago(30), saini, urea.display, 5, urea.last_value, "1", "emp1", item_id=urea.id, unit=urea.unit)
    HindiNamesService(db).fill_missing()
    from hth.modules.bills.service import BillsService

    bill_lines = [
        dict(name="UREA 45KG", unit="BAG", batch="NA", expiry_date="NA", rate=266.5, item_type="F", quantity=4),
        dict(name="DAP 50KG", unit="BAG", batch="NA", expiry_date="NA", rate=1350, item_type="F", quantity=2),
        dict(name="GLYPHOSATE 1L", unit="BTL", batch="NA", expiry_date="NA", rate=438, item_type="P", quantity=2),
    ]
    bills = BillsService(db, settings)
    bills.create_bill(_ago(9), "SURESH PAL", "SAMPLA", bill_lines[1:], "admin", customer_id=people["SURESH PAL"])
    bill = bills.create_bill(_ago(2), "RAMESH KUMAR", "KHARKHODA", bill_lines, "admin", customer_id=people["RAMESH KUMAR"])
    wheat_id = db.fetchone("SELECT id FROM items WHERE name = 'WHEAT'")["id"]

    import hth.ui.modern.areas.counter as counter_mod
    from hth.ui.app import App

    counter_mod.confirm = lambda *a, **k: True  # the undo question, answered yes
    app = App(db, settings)
    app.tk.call("tk", "scaling", 96 / 72)
    hidden = (str(data), str(V5), str(ROOT), str(Path.home()))
    notes: dict = {}

    def pump(n=40, s=0.02):
        for _ in range(n):
            app.update()
            time.sleep(s)

    def wait_for(cond, seconds=30):
        end = time.time() + seconds
        while time.time() < end:
            app.update()
            if cond():
                return True
            time.sleep(0.05)
        return False

    def tidy():
        """No folder names on screen (they name the Windows user)."""
        stack = [app]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if isinstance(w, ctk.CTkLabel):
                text = str(w.cget("text"))
                if any(h in text for h in hidden):
                    for h in hidden:
                        text = text.replace(h, "\u2026")
                    w.configure(text=text)

    def grab(name, settle=40):
        app.state("normal")
        app.geometry(f"{APP_W}x{APP_H}+0+0")
        pump(settle)
        tidy()
        pump(4)
        img = None
        for _ in range(5):
            img = rs.print_window(app)
            if img is None or rs.blank(img):
                x, y = app.winfo_rootx(), app.winfo_rooty()
                img = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height())).convert("RGB")
            if not rs.blank(img):
                break
            time.sleep(1)
        img.save(FRAMES / f"{name}.png")
        print("frame", name, img.size)

    try:
        app.geometry(f"{APP_W}x{APP_H}+0+0")
        app.attributes("-topmost", True)
        pump(30)
        login = app._login
        grab("login_0")
        login.username.set("admin")
        grab("login_1", 10)
        login.password.set("admin")
        grab("login_2", 10)
        login.submit()
        pump(30)
        today = app._views["today"]
        wait_for(lambda: today._data is not None)
        grab("today", 60)

        app.navigate("counter")
        view = app._views["counter"]
        view.set_intent("sale")
        grab("counter_0")
        view.pick_customer(people["RAMESH KUMAR"])
        view.item.refresh()
        grab("counter_1")
        # three lines, one picture after each
        for i, (name, qty) in enumerate((("UREA 45KG", "4"), ("DAP 50KG", "2"), ("WHEAT SEED HD-3086", "40"))):
            view.item.set(stock[name].id)
            view._on_item(stock[name].id, focus=False)
            view.qty.set(qty)
            view.add_line()
            grab(f"counter_{i + 2}", 20)
        view.paid.delete(0, "end")
        view.paid.insert(0, "2000")
        view.recalc()
        grab("counter_5")
        view.save()
        grab("counter_6", 15)
        view.undo_last()
        grab("counter_7", 15)
        # crops: a lot bought from a farmer, then part of the wheat sold to a buyer (neither is saved)
        view.set_intent("purchase", focus=False)
        view.pick_customer(people["MAHAVIR SANGWAN"])
        view.item.refresh()
        view.item.set(wheat_id)
        view._on_item(wheat_id, focus=False)
        view.qty.set("2500")
        view.rate.set("24.6")
        view.kaat.set("30")
        view.quality.set("A")
        view.recalc()
        grab("crop_buy")
        view.set_intent("sale", focus=False)
        view.pick_customer(people["KRISHAN DALAL"])
        view.item.set(wheat_id)
        view._on_item(wheat_id, focus=False)
        view.qty.set("1500")
        view.rate.set("25.6")
        view.recalc()
        grab("crop_sell")
        view.qty.set("")
        view.rate.set("")
        view.recalc()
        app.navigate("bills", bill_number=bill.bill_number)
        grab("bills")
        app.navigate("reports", report="audit")
        grab("audit", 60)

        app.navigate("customers", customer_id=people["RAMESH KUMAR"])
        page = app._views["khata"].customers
        wait_for(lambda: len(page.table.rows) > 5)
        page.page.period.set("All")
        page.page._apply_period()
        grab("khata")
        app.navigate("karar")
        app._views["khata"].collections.table.select_first()
        grab("collections")

        app.navigate("items", item_id=stock["DAP 50KG"].id)
        items = app._views["stock"].items
        wait_for(lambda: len(items.table.rows) > 5)
        grab("stock")
        app.navigate("finance")
        book = app._views["money"].book
        book.period.set("This month")
        book.reload()
        grab("money")
        app.navigate("reports")
        grab("reports_0")
        search = _find_attr(app, "search", lambda w: "Find a report" in str(getattr(w, "_placeholder_text", "")))
        if search is not None:
            search.insert(0, "gst")
            owner = _owner_with(app, "_render", search)
            if owner is not None:
                owner._render()
        grab("reports_1")

        app.navigate("assistant")
        assistant = app.find_view("assistant")
        replies = []
        answered = assistant._answered
        assistant._answered = lambda reply: (replies.append(reply), answered(reply))
        wait_for(lambda: getattr(assistant, "_ready", False), 240)
        assistant.new_chat()
        pump(20)
        for i, question in enumerate(("sabse bade 5 bakayedar", "ramesh ka balance batao", "kharkhoda wala")):
            assistant.ask(question)
            pump(10)
            wait_for(lambda: not getattr(assistant, "_busy", False), 90)
            pump(30)
            grab(f"assistant_{i + 1}")
        notes["spoken_answer"] = speech.summary(replies[-1]) if replies else ""
        notes["replies"] = [getattr(r, "kind", "") for r in replies]

        app.apply_language("hi")
        pump(30)
        app.navigate("counter")
        view = app._views["counter"]
        view.set_intent("sale")
        view.pick_customer(people["RAMESH KUMAR"])
        view.item.refresh()
        for name, qty in (("UREA 45KG", "4"), ("DAP 50KG", "2"), ("WHEAT SEED HD-3086", "40")):
            view.item.set(stock[name].id)
            view._on_item(stock[name].id, focus=False)
            view.qty.set(qty)
            view.add_line()
        view.paid.delete(0, "end")
        view.paid.insert(0, "2000")
        view.recalc()
        grab("hindi_counter")
        view.clear_lines()
        app.apply_language("en")
        pump(30)

        for key, mode, where, name in (
            ("forest", "dark", "today", "theme_forest"),
            ("saffron", "light", "customers", "theme_saffron"),
            ("contrast", "light", "karar", "theme_contrast"),
        ):
            app.apply_color_theme(key)
            app.apply_theme(mode)
            pump(20)
            if where == "customers":
                app.navigate("customers", customer_id=people["BALWAN SINGH"])
            else:
                app.navigate(where)
            if where == "today":
                today = app._views["today"]
                today.reload()
                wait_for(lambda: today._data is not None)
            grab(name, 60)
        app.apply_color_theme("slate")
        app.apply_theme("light")
        pump(20)

        app.navigate("settings")
        settings_view = app.find_view("settings") or app._views.get("settings")
        for section, name in (("Backup & data", "settings_backup"), ("Updates", "settings_updates")):
            settings_view.show_section(section)
            grab(name)
        app.lock()
        grab("locked")
    finally:
        app.destroy()
        db.close()
        shutil.rmtree(data, ignore_errors=True)
    (OUT / "capture.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    print("capture notes", notes)


def _ago(days: int) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


def _walk(root):
    stack = [root]
    while stack:
        w = stack.pop()
        yield w
        stack.extend(w.winfo_children())


def _find_attr(root, attr, test):
    for w in _walk(root):
        if test(w):
            return w
    return None


def _owner_with(root, method, child):
    w = child
    while w is not None:
        if hasattr(w, method) and callable(getattr(w, method)):
            return w
        w = getattr(w, "master", None)
    return None


# 2. Slides: HTML rendered by Edge ----------------------------------------------------------------
SLIDE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1920px; height: 1080px; overflow: hidden; }
html { background: #0b1220; }
body { position: relative; }  /* slide boxes measure against the 1920x1080 page, not the window */
body { font-family: 'Segoe UI', 'Nirmala UI', sans-serif; color: #f1f5f9;
       background: radial-gradient(1200px 700px at 78% 18%, #134e5e 0%, rgba(19,78,94,0) 60%),
                   linear-gradient(160deg, #0b1220 0%, #0f1b33 55%, #0b1220 100%); }
.wrap { position: absolute; inset: 0; padding: 70px 120px 190px; display: flex; flex-direction: column; justify-content: center; }
.kicker { font-size: 24px; letter-spacing: .12em; white-space: nowrap; text-transform: uppercase; color: #22d3ee; font-weight: 600; }
h1 { font-size: 92px; line-height: 1.02; font-weight: 700; letter-spacing: -.02em; margin-top: 18px; }
h2 { font-size: 64px; font-weight: 700; letter-spacing: -.01em; }
.lead { font-size: 34px; color: #cbd5e1; margin-top: 26px; line-height: 1.35; }
.muted { color: #94a3b8; }
.chip { display: inline-block; padding: 10px 20px; border-radius: 999px; border: 1px solid #334155;
        background: rgba(15,23,42,.6); font-size: 26px; margin: 0 10px 12px 0; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 26px; margin-top: 56px; }
.card { background: rgba(15,23,42,.72); border: 1px solid #1e293b; border-radius: 22px; padding: 34px 30px; }
.card .big { font-size: 50px; font-weight: 700; color: #22d3ee; }
.card .t { font-size: 30px; font-weight: 600; margin-top: 10px; }
.card .d { font-size: 24px; color: #94a3b8; margin-top: 10px; line-height: 1.35; }
.bar { margin-top: 40px; padding: 26px 32px; border-radius: 18px; background: rgba(127,29,29,.35);
       border: 1px solid #7f1d1d; font-size: 28px; color: #fecaca; }
.mono { font-family: 'Cascadia Mono', Consolas, monospace; }
"""


def slides(team: dict) -> None:
    SLIDES.mkdir(parents=True, exist_ok=True)
    hero = (ROOT / "docs" / "screenshots" / "hero.png").as_uri()
    members = [m for m in team.get("members", []) if m]
    team_line = ""
    if team.get("team_no") or members:
        bits = [f"Team {html.escape(str(team['team_no']))}"] if team.get("team_no") else []
        bits += [html.escape(m) for m in members]
        team_line = f'<div class="lead" style="font-size:28px;margin-top:18px">{" · ".join(bits)}</div>'
    repo = html.escape(team.get("repo", "github.com/Parmodsihag/jbbv4"))
    course_parts = [html.escape(c) for c in team.get("course", "").split(" · ")]
    course = course_parts[0]
    course_rest = " · ".join(course_parts[1:])
    pages = {
        "title": f"""
<div class="wrap">
  <div style="width:800px">
    <div class="kicker">{course}</div>
    <div class="muted" style="font-size:24px;margin-top:6px">{course_rest}</div>
    <h1>High Table<br>Holdings</h1>
    <div class="lead">The shop computer of <b>Jaat Beaj Bhander</b>: khata with interest, stock, promises,
      cash book, GST bills and crop trading, in English or हिन्दी.</div>
    {team_line}
    <div class="lead mono" style="font-size:26px;color:#22d3ee;margin-top:34px">{repo}</div>
  </div>
  <img src="{hero}" style="position:absolute;right:80px;top:240px;width:900px;border-radius:16px;
       box-shadow:0 30px 80px rgba(0,0,0,.55)">
</div>""",
        "problem": """
<div class="wrap">
  <div class="kicker">The problem</div>
  <h2 style="margin-top:14px">The shop runs on <i>khata</i></h2>
  <div class="cards">
    <div class="card"><div class="big">24 %</div><div class="t">Interest on credit</div>
      <div class="d">a daily rate, added to the amount every 31 March</div></div>
    <div class="card"><div class="big">करार</div><div class="t">Promises to pay</div>
      <div class="d">farmers pay after the harvest; someone has to chase them</div></div>
    <div class="card"><div class="big">FIFO</div><div class="t">Crops bought back</div>
      <div class="d">wheat in lots, with a deduction (kaat), sold oldest first</div></div>
    <div class="card"><div class="big">GST</div><div class="t">Tax invoices</div>
      <div class="d">CGST and SGST by item type, amount in Hindi words</div></div>
  </div>
  <div class="bar">The old program (v3): one table per customer &nbsp;·&nbsp; no users &nbsp;·&nbsp; no tests
    &nbsp;·&nbsp; "today" frozen at start-up</div>
</div>""",
        "architecture": _architecture_html(),
        "quality": """
<div class="wrap">
  <div class="kicker">Quality and documents</div>
  <div style="display:flex;gap:60px;align-items:flex-end;margin-top:30px">
    <div><div style="font-size:190px;font-weight:700;line-height:.9;color:#22d3ee">316</div>
      <div class="lead" style="margin-top:8px">automated tests, all passing</div></div>
    <div style="display:flex;gap:80px;margin-bottom:14px;margin-left:40px">
      <div><div style="font-size:64px;font-weight:700">20</div><div class="muted" style="font-size:24px">releases, 4.0 to 5.7</div></div>
      <div><div style="font-size:64px;font-weight:700">34</div><div class="muted" style="font-size:24px">reports</div></div>
      <div><div style="font-size:64px;font-weight:700">13</div><div class="muted" style="font-size:24px">decision records</div></div>
    </div>
  </div>
  <div style="margin-top:56px">
    <span class="chip">SRS: informal · semi-formal · formal</span><span class="chip">Data flow diagrams</span>
    <span class="chip">Decision tables</span><span class="chip">Algebraic specifications</span>
    <span class="chip">WBS · activity network · PERT · Gantt</span><span class="chip">Test cases &amp; traceability</span>
    <span class="chip">Test plan &amp; report</span><span class="chip">Architecture &amp; data dictionary</span>
    <span class="chip">User &amp; admin guides</span>
  </div>
</div>""",
        "end": f"""
<div class="wrap" style="display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding-bottom:200px">
  <div class="kicker">High Table Holdings</div>
  <h1 style="font-size:120px">Thank you</h1>
  {team_line}
  <div class="lead mono" style="font-size:36px;color:#22d3ee;margin-top:40px">{repo}</div>
</div>""",
    }
    pages.update(_problem_pages(hero, repo, course, course_rest, team_line))
    pages.update(_technical_pages(hero, repo, course, course_rest, team_line))
    from PIL import Image

    pages_dir, profile = OUT / "slides_html", OUT / "edge-profile"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for name, body in pages.items():
        page = pages_dir / f"{name}.html"
        diagrams = 'class="mermaid"' in body  # drawn by Mermaid (from the CDN) before the screenshot
        page.write_text(
            f"<!doctype html><html><head><meta charset='utf-8'><style>{SLIDE_CSS}{TECH_CSS}</style></head>"
            f"<body>{body}{MERMAID_SCRIPT if diagrams else ''}</body></html>",
            encoding="utf-8",
        )
        target = SLIDES / f"{name}.png"
        target.unlink(missing_ok=True)
        subprocess.run(
            [
                str(EDGE),
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--allow-file-access-from-files",
                f"--user-data-dir={profile}",
                "--window-size=1920,1240",  # taller than the slide: a scrollbar or bare edge falls outside the crop
                f"--virtual-time-budget={20000 if diagrams else 3000}",
                f"--screenshot={target}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        # msedge.exe hands the work to a browser process and returns at once: wait for the file
        end, size = time.time() + 90, -1
        while time.time() < end:
            if target.exists() and target.stat().st_size == size and size > 0:
                break
            size = target.stat().st_size if target.exists() else -1
            time.sleep(0.7)
        img = Image.open(target).convert("RGB")
        if img.size != (W, H):
            img = img.crop((0, 0, W, H))
        img.save(target)
        print("slide", name, img.size)


PROBLEMS = [
    (1, "Who owes me what, exactly, with interest?", "किसका कितना बाकी है, ब्याज समेत?",
     ["Khata", "interest to the paisa", "statements"]),
    (2, "Promises to pay get forgotten.", "करार की तारीख़ याद नहीं रहती।",
     ["Today", "Collections", "WhatsApp reminders"]),
    (3, "A busy counter, and mistakes.", "काउंटर पर भीड़, और ग़लतियाँ।",
     ["Sale · Purchase · Payment in · Payment out", "several items", "paid now", "undo"]),
    (4, "Stock runs out, or expires on the shelf.", "माल ख़त्म हो जाता है, या पड़ा-पड़ा ख़राब।",
     ["days left per item", "reorder list", "expiry alerts"]),
    (5, "Crops bought from farmers: what did we earn?", "किसान से ली फ़सल पर कितना बचा?",
     ["crop lots", "kaat", "oldest lots first", "margin before saving"]),
    (6, "Where did the money go?", "पैसा कहाँ गया?",
     ["cash · bank · UPI", "expenses and rent", "profit and loss", "GST bills"]),
    (7, "Not everyone is at home with computers, or English.", "हर कोई कंप्यूटर या अंग्रेज़ी में सहज नहीं।",
     ["पूरा प्रोग्राम हिन्दी में", "ask in Hinglish", "ask by voice, hear the answer"]),
    (8, "Can I trust the records, and keep them safe?", "हिसाब पर भरोसा, और उसकी हिफ़ाज़त।",
     ["owner and staff roles", "every change recorded", "screen lock", "daily backup"]),
]


def _problem_pages(hero: str, repo: str, course: str, course_rest: str, team_line: str) -> dict[str, str]:
    """Slides for the problem-first video."""
    pages = {
        "p_title": f"""
<div class="wrap">
  <div style="width:820px">
    <div class="kicker">{course}</div>
    <div class="muted" style="font-size:24px;margin-top:6px">{course_rest}</div>
    <h1 style="font-size:78px;margin-top:26px">Running a shop on credit is hard.<br><span style="color:#22d3ee">We made it simple.</span></h1>
    <div class="lead"><b>High Table Holdings</b>: the shop computer for an agri-input shop. Khata with interest,
      promises, stock, crops, cash and GST bills, in English or हिन्दी.</div>
    {team_line}
    <div class="lead mono" style="font-size:26px;color:#22d3ee;margin-top:30px">{repo}</div>
  </div>
  <img src="{hero}" style="position:absolute;right:80px;top:250px;width:880px;border-radius:16px;
       box-shadow:0 30px 80px rgba(0,0,0,.55)">
</div>""",
        "p_shop": """
<div class="wrap">
  <div class="kicker">The shop</div>
  <h2 style="margin-top:14px">Sold today, paid after the harvest</h2>
  <div class="cards" style="grid-template-columns:repeat(3,1fr)">
    <div class="card"><div class="big">उधार</div><div class="t">Everything on credit</div>
      <div class="d">fertiliser, seed and pesticide go home now; the account earns 24 % a year</div></div>
    <div class="card"><div class="big">करार</div><div class="t">Promises to pay</div>
      <div class="d">farmers promise a date after the harvest, and someone has to chase it</div></div>
    <div class="card"><div class="big">फ़सल</div><div class="t">Crops come back</div>
      <div class="d">the same farmers sell their wheat to the shop, in lots, with a deduction</div></div>
  </div>
  <div class="bar" style="background:rgba(15,23,42,.72);border-color:#334155;color:#cbd5e1">
    One owner, a helper at the counter, one PC, unreliable internet, and a notebook of accounts.</div>
</div>""",
        "p_problems": _problems_grid(),
        "p_how": """
<div class="wrap">
  <div class="kicker">How it works for the shop</div>
  <h2 style="margin-top:14px">Simple to run, safe to trust</h2>
  <div class="cards" style="grid-template-columns:repeat(3,1fr);margin-top:44px">
    <div class="card"><div class="t">On the shop's own PC</div><div class="d">works without internet; nothing leaves the shop</div></div>
    <div class="card"><div class="t">One data file</div><div class="d">backed up every day; a backup is checked before it is restored</div></div>
    <div class="card"><div class="t">Owner and staff</div><div class="d">each with their own sign-in; staff cannot change history</div></div>
    <div class="card"><div class="t">English or हिन्दी</div><div class="d">typed or spoken questions, answers read aloud</div></div>
    <div class="card"><div class="t">Updates itself</div><div class="d">every file checked, and an update can be undone</div></div>
    <div class="card"><div class="t">34 reports</div><div class="d">search, filter, and open in Excel</div></div>
  </div>
</div>""",
        "p_quality": """
<div class="wrap">
  <div class="kicker">Built to be trusted</div>
  <div style="display:flex;gap:70px;align-items:flex-end;margin-top:26px">
    <div><div style="font-size:190px;font-weight:700;line-height:.9;color:#22d3ee">316</div>
      <div class="lead" style="margin-top:8px">automated tests, all passing</div></div>
    <div style="font-size:30px;line-height:1.7;color:#cbd5e1;margin-bottom:10px">
      ✓ interest worked out to the paisa, and checked<br>
      ✓ a save is all or nothing<br>
      ✓ every change records who made it</div>
  </div>
  <div style="margin-top:50px">
    <span class="chip">Requirements (SRS)</span><span class="chip">Data flow diagrams</span>
    <span class="chip">Decision tables</span><span class="chip">Algebraic specifications</span>
    <span class="chip">WBS · PERT · Gantt</span><span class="chip">Test cases &amp; traceability</span>
    <span class="chip">Architecture</span><span class="chip">User &amp; admin guides</span>
  </div>
</div>""",
        "p_end": f"""
<div class="wrap" style="align-items:center;text-align:center">
  <div class="kicker">High Table Holdings</div>
  <h1 style="font-size:96px">Fewer problems at the counter.</h1>
  <div class="lead" style="font-size:40px">Thank you · धन्यवाद</div>
  {team_line}
  <div class="lead mono" style="font-size:34px;color:#22d3ee;margin-top:36px">{repo}</div>
</div>""",
    }
    for n, english, hindi, chips in PROBLEMS:
        tags = "".join(f'<span class="chip" style="border-color:#155e75;color:#a5f3fc">{c}</span>' for c in chips)
        pages[f"p_card_{n}"] = f"""
<div style="position:absolute;right:60px;top:40px;font-size:620px;font-weight:800;line-height:1;
     color:rgba(34,211,238,.07)">{n}</div>
<div class="wrap">
  <div class="kicker">Problem {n} of 8</div>
  <h1 style="font-size:84px;max-width:1500px;margin-top:22px">“{english}”</h1>
  <div class="lead" style="font-size:46px;color:#e2e8f0;margin-top:22px">{hindi}</div>
  <div style="margin-top:56px;font-size:24px;letter-spacing:.12em;text-transform:uppercase;color:#94a3b8">How we solved it</div>
  <div style="margin-top:16px">{tags}</div>
</div>"""
    return pages


def _problems_grid() -> str:
    tiles = "".join(
        f'<div class="card" style="padding:26px 26px"><div style="font-size:40px;font-weight:700;color:#22d3ee">{n}</div>'
        f'<div class="t" style="font-size:27px">{english}</div>'
        f'<div class="d" style="font-size:24px;color:#cbd5e1">{hindi}</div></div>'
        for n, english, hindi, _chips in PROBLEMS
    )
    return f"""
<div class="wrap">
  <div class="kicker">The problems</div>
  <h2 style="margin-top:14px">Eight everyday problems</h2>
  <div class="cards" style="grid-template-columns:repeat(4,1fr);gap:22px;margin-top:40px">{tiles}</div>
</div>"""


SME = ROOT / "sme"
DOCS = V5 / "docs"

MERMAID_SCRIPT = """
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs';
mermaid.initialize({startOnLoad: false, theme: 'base', securityLevel: 'loose',
  themeVariables: {darkMode: true, background: '#0b1220', fontFamily: 'Segoe UI', fontSize: '18px',
    primaryColor: '#10263a', primaryTextColor: '#f1f5f9', primaryBorderColor: '#22d3ee',
    secondaryColor: '#1e293b', secondaryTextColor: '#e2e8f0', secondaryBorderColor: '#475569',
    tertiaryColor: '#0f172a', tertiaryTextColor: '#e2e8f0', tertiaryBorderColor: '#334155',
    lineColor: '#7dd3fc', textColor: '#e2e8f0', mainBkg: '#10263a', nodeBorder: '#22d3ee',
    clusterBkg: 'rgba(15,23,42,.6)', clusterBorder: '#334155', titleColor: '#a5f3fc',
    edgeLabelBackground: '#0b1220', actorBkg: '#10263a', actorBorder: '#22d3ee', actorTextColor: '#f1f5f9',
    signalColor: '#7dd3fc', signalTextColor: '#e2e8f0', labelBoxBkgColor: '#10263a', noteBkgColor: '#1e293b',
    noteTextColor: '#e2e8f0', attributeBackgroundColorOdd: '#0f1b2d', attributeBackgroundColorEven: '#13233a',
    stateBkg: '#10263a', stateLabelColor: '#f1f5f9', nodeTextColor: '#f1f5f9', compositeBackground: '#0f172a',
    altBackground: '#0f172a'}});
await mermaid.run({querySelector: '.mermaid'});
for (const box of document.querySelectorAll('.mermaid')) {   // fit each diagram to its box
  const svg = box.querySelector('svg'); if (!svg) continue;
  const vb = svg.viewBox.baseVal, bw = box.clientWidth, bh = box.clientHeight;
  const s = Math.min(bw / vb.width, bh / vb.height);
  svg.style.maxWidth = 'none';
  svg.setAttribute('width', vb.width * s); svg.setAttribute('height', vb.height * s);
}
document.body.dataset.done = '1';
</script>"""

TECH_CSS = """
.mermaid { display: flex; align-items: center; justify-content: center; overflow: hidden; }
.panel { background: rgba(15,23,42,.72); border: 1px solid #1e293b; border-radius: 20px; padding: 26px 30px; }
.stat { font-size: 54px; font-weight: 700; color: #22d3ee; line-height: 1; }
.statl { font-size: 22px; color: #94a3b8; margin-top: 6px; }
.li { font-size: 26px; color: #cbd5e1; line-height: 1.55; }
.li b { color: #f1f5f9; }
table.dt { border-collapse: collapse; font-size: 19px; width: 100%; }
table.dt td, table.dt th { border-bottom: 1px solid #1e293b; padding: 5px 12px; text-align: center; }
table.dt td:first-child, table.dt th:first-child { text-align: left; color: #e2e8f0; }
table.dt th { color: #94a3b8; font-weight: 600; }
table.dt tr.sep td { color: #22d3ee; font-weight: 700; border-bottom: 2px solid #334155; }
.y { color: #4ade80; font-weight: 700; } .n { color: #f87171; font-weight: 700; } .x { color: #22d3ee; font-size: 28px; }
.dim { color: #475569; }
pre.spec { font-family: 'Cascadia Mono', Consolas, monospace; font-size: 21px; line-height: 1.5; color: #e2e8f0;
           white-space: pre; margin: 0; }
.code { font-family: 'Cascadia Mono', Consolas, monospace; font-size: 18px; line-height: 1.42; }
.code pre { margin: 0; background: transparent !important; }
.chain { display: flex; align-items: stretch; gap: 14px; margin-top: 40px; }
.chain .step { flex: 1; background: rgba(15,23,42,.8); border: 2px solid #155e75; border-radius: 18px; padding: 22px 20px; }
.chain .k { font-size: 20px; letter-spacing: .1em; text-transform: uppercase; color: #22d3ee; }
.chain .v { font-size: 25px; color: #f1f5f9; margin-top: 10px; line-height: 1.35; }
.chain .arrow { align-self: center; font-size: 40px; color: #475569; }
.hbar { display: flex; align-items: center; gap: 14px; margin: 6px 0; font-size: 21px; color: #cbd5e1; }
.wbs-root { margin: 22px auto 0; width: 560px; text-align: center; padding: 14px; border: 2px solid #22d3ee; border-radius: 16px; font-size: 26px; font-weight: 700; background: rgba(15,23,42,.8); }
.wbs-cols { display: grid; gap: 14px; margin-top: 26px; }
.wbs-area { border: 2px solid #a78bfa; border-radius: 14px; padding: 10px 12px; font-size: 21px; font-weight: 700; color: #ddd6fe; background: rgba(15,23,42,.8); margin-bottom: 10px; min-height: 64px; }
.wbs-leaf { border-left: 3px solid #155e75; padding: 5px 0 5px 10px; margin: 6px 0 6px 8px; font-size: 18px; color: #cbd5e1; }
.hbar .lab { width: 340px; text-align: right; } .hbar .fill { height: 24px; background: #22d3ee; border-radius: 6px; }
"""


def _mermaid(path: Path, marker: str) -> str:
    """The Mermaid block in ``path`` that contains ``marker`` - the diagram exactly as documented."""
    import re

    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```mermaid\n(.*?)```", text, flags=re.S):
        if marker in block:
            return html.escape(block)
    raise ValueError(f"no Mermaid block with {marker!r} in {path.name}")


def _diagram(path: Path, marker: str, w: int, h: int, direction: str | None = None) -> str:
    code = _mermaid(path, marker)
    if direction:  # same diagram, laid out the other way to fit the slide
        code = code.replace("flowchart TB", f"flowchart {direction}", 1)
    return f'<pre class="mermaid" style="width:{w}px;height:{h}px;margin:0">{code}</pre>'


def _wbs_chart(path: Path, marker: str) -> str:
    """The documented WBS (a Mermaid tree) drawn as a classic WBS chart: one column per work area."""
    import re

    text = path.read_text(encoding="utf-8")
    block = next(b for b in re.findall(r"```mermaid\n(.*?)```", text, flags=re.S) if marker in b)
    labels, children = {}, {}
    for a, b, label in re.findall(r"(\w+)\s*-->\s*(\w+)\[([^\]]+)\]", block):
        labels[b] = label
        children.setdefault(a, []).append(b)
    root = re.search(r"(\w+)\[([^\]]+)\]", block)
    cols = []
    for area in children.get(root.group(1), []):
        items = "".join(f'<div class="wbs-leaf">{html.escape(labels[c])}</div>' for c in children.get(area, []))
        cols.append(f'<div class="wbs-col"><div class="wbs-area">{html.escape(labels[area])}</div>{items}</div>')
    return (
        f'<div class="wbs-root">{html.escape(root.group(2))}</div>'
        f'<div class="wbs-cols" style="grid-template-columns:repeat({len(cols)},1fr)">{"".join(cols)}</div>'
    )


def _md_table(path: Path, heading: str) -> str:
    """The first Markdown table under ``heading``, as HTML (decision tables)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith(heading))
    rows = []
    for line in lines[i + 1 :]:
        if line.startswith("|"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif rows:
            break
    head, body = rows[0], [r for r in rows[2:]]

    def cell(c):
        mark = {"Y": '<span class="y">Y</span>', "N": '<span class="n">N</span>', "X": '<span class="x">✓</span>', "—": '<span class="dim">—</span>'}
        return mark.get(c, html.escape(c).replace("`", ""))

    out = ["<table class='dt'><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr>"]
    for r in body:
        cls = " class='sep'" if r[0].startswith("**") else ""
        out.append(f"<tr{cls}>" + "".join(f"<td>{cell(c.replace('**', ''))}</td>" for c in r) + "</tr>")
    return "".join(out) + "</table>"


def _spec_lines(name: str, keep: tuple[str, ...]) -> str:
    """Chosen lines of one algebraic specification, as written in chapter 4."""
    text = (SME / "06_Algebraic_Specifications.md").read_text(encoding="utf-8").splitlines()
    i = next(n for n, line in enumerate(text) if line.strip() == f"spec {name}")
    block = []
    for line in text[i:]:
        block.append(line)
        if line.strip() == "end":
            break
    shown = [block[0]] + [line for line in block[1:] if any(k in line for k in keep)] + ["end"]
    return html.escape("\n".join(shown))


def _code(path: Path, start: str, stop: str) -> str:
    """Source lines from ``start`` up to (not including) ``stop``, highlighted."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import PythonLexer

    lines = path.read_text(encoding="utf-8").splitlines()
    i = next(n for n, line in enumerate(lines) if start in line)
    j = next(n for n in range(i + 1, len(lines)) if stop in lines[n])
    import textwrap

    src = textwrap.dedent("\n".join(lines[i:j])).rstrip()
    style = "github-dark"
    try:
        fmt = HtmlFormatter(style=style, nowrap=False, noclasses=True)
    except Exception:  # noqa: BLE001 - an older Pygments
        fmt = HtmlFormatter(style="monokai", nowrap=False, noclasses=True)
    return highlight(src, PythonLexer(), fmt)


def _technical_pages(hero: str, repo: str, course: str, course_rest: str, team_line: str) -> dict[str, str]:
    adr_titles = []
    for line in (DOCS / "adr" / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| [0"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            adr_titles.append((parts[0].split("]")[0].strip("["), parts[1].replace("`", "")))
    adrs = "".join(f'<div class="li" style="font-size:20px;line-height:1.45"><b>{n}</b> {html.escape(t)}</div>' for n, t in adr_titles)
    area_counts = [
        ("Books: interest, ledger, settlement", 37), ("Counter, stock, units, crops", 28), ("Promises, reports, sign-in", 11),
        ("Migration of old data", 3), ("Bills, crops, finance modules", 27), ("Safety and data features", 32),
        ("Speed with identical figures", 8), ("Colour themes, contrast", 11), ("Hindi", 25), ("Assistant", 44),
        ("Voice", 41), ("Updates", 16), ("UI walkthroughs", 33),
    ]
    bars = "".join(
        f'<div class="hbar"><div class="lab">{html.escape(a)}</div><div class="fill" style="width:{n * 10}px"></div><div>{n}</div></div>'
        for a, n in area_counts
    )
    srs, dfd, plan = SME / "03_SRS.md", SME / "04_DFD_and_Data_Model.md", SME / "07_WBS_Activity_Network_PERT.md"
    return {
        "t_title": f"""
<div class="wrap">
  <div style="width:860px">
    <div class="kicker">{course}</div>
    <div class="muted" style="font-size:24px;margin-top:6px">{course_rest}</div>
    <h1 style="font-size:80px;margin-top:26px">High Table Holdings<br><span style="color:#22d3ee">the engineering view</span></h1>
    <div class="lead">Specification · design · testing · project management</div>
    {team_line}
    <div class="lead mono" style="font-size:26px;color:#22d3ee;margin-top:30px">{repo}</div>
  </div>
  <div class="panel" style="position:absolute;right:110px;top:250px;width:760px">
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:26px 20px">
      <div><div class="stat">42</div><div class="statl">user stories</div></div>
      <div><div class="stat">80</div><div class="statl">functional req.</div></div>
      <div><div class="stat">15</div><div class="statl">non-functional</div></div>
      <div><div class="stat">22</div><div class="statl">decision tables</div></div>
      <div><div class="stat">11</div><div class="statl">algebraic specs</div></div>
      <div><div class="stat">13</div><div class="statl">decision records</div></div>
      <div><div class="stat">166</div><div class="statl">test cases</div></div>
      <div><div class="stat">316</div><div class="statl">automated tests</div></div>
      <div><div class="stat">20</div><div class="statl">releases</div></div>
    </div>
  </div>
</div>""",
        "t_scope": """
<div class="wrap">
  <div class="kicker">Scope and process</div>
  <h2 style="margin-top:14px">One shop, built in increments</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:26px;margin-top:40px">
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Stakeholders</div>
      <div class="li">owner (admin) · counter staff<br>farmers and buyers (statements, slips)<br>developer · course evaluator</div></div>
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Constraints</div>
      <div class="li">one Windows PC, Celeron, 4 GB<br>often no internet: works offline<br>Python · customtkinter · SQLite</div></div>
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Process</div>
      <div class="li">iterative and incremental<br>money rules written test-first<br>20 releases, each installable</div></div>
  </div>
  <div class="panel" style="margin-top:26px;font-size:26px;color:#cbd5e1">
    requirements → decision tables · algebraic specs → design · ADRs → code → tests · traceability → release · CHANGELOG</div>
</div>""",
        "t_req": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:60px">
  <div class="kicker">Requirements: informal → semi-formal → formal</div>
  <div style="display:grid;grid-template-columns:600px 1fr;gap:30px;margin-top:22px">
    <div>
      <div class="panel"><div class="li"><b>Informal</b> · 42 user stories, glossary<br>
        <b>Semi-formal</b> · 29 use cases, activity, sequence and state diagrams<br>
        <b>Formal</b> · IEEE 830 SRS: 80 functional, 15 non-functional requirements, pre- and post-conditions</div></div>
      <pre class="spec" style="margin-top:22px;font-size:19px;white-space:pre-wrap">FR-9.1  One save may hold any number of lines
        for one account; all lines and any
        paid-now amount are written in one
        transaction: if any line fails
        validation, no row of the save is
        written.                       (M)</pre>
    </div>
    {_diagram(srs, "UC20[Record a multi-line sale", 1060, 760)}
  </div>
</div>""",
        "t_state": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:56px">
  <div class="kicker">Semi-formal models · state diagram</div>
  <div class="panel" style="padding:12px;margin-top:18px"><div class="statl" style="margin:4px 10px 6px">Sign-in, lockout and screen lock</div>
    {_diagram(srs, "SignedOut --> Waiting", 1650, 760)}</div>
</div>""",
        "t_seq": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:56px">
  <div class="kicker">Semi-formal models · sequence diagram</div>
  <div class="panel" style="padding:12px;margin-top:18px"><div class="statl" style="margin:4px 10px 6px">Recording a sale, across the layers</div>
    {_diagram(srs, "participant V as SalesView", 1650, 760)}</div>
</div>""",
        "t_dfd0": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:56px">
  <div class="kicker">Data flow diagrams · level 0</div>
  <div class="panel" style="padding:12px;margin-top:18px"><div class="statl" style="margin:4px 10px 6px">Context: the program, its users and outside systems</div>
    {_diagram(dfd, "P0((0<br/>High Table", 1650, 760)}</div>
</div>""",
        "t_dfd2": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:56px">
  <div class="kicker">Data flow diagrams · level 2</div>
  <div class="panel" style="padding:12px;margin-top:18px"><div class="statl" style="margin:4px 10px 6px">Process 3, record transaction</div>
    {_diagram(dfd, "P31((3.1", 1650, 760, "LR")}</div>
</div>""",
        "t_er": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:50px">
  <div class="kicker">Data model · 20 tables · 6 forward-only migrations · foreign keys enforced</div>
  <div class="panel" style="padding:10px;margin-top:18px">{_diagram(dfd, "erDiagram", 1660, 800)}</div>
</div>""",
        "t_dt": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:46px">
  <div class="kicker">Formal: decision tables · 22 in all</div>
  <h2 style="margin-top:12px;font-size:46px">DT-3 · What a valid counter entry writes</h2>
  <div class="panel" style="margin-top:26px;padding:18px 26px">{_md_table(SME / "05_Decision_Tables.md", "## 3.3 DT-3")}</div>
</div>""",
        "t_alg": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:70px">
  <div class="kicker">Formal: algebraic specifications · 11 abstract data types</div>
  <div style="display:grid;grid-template-columns:1fr;gap:18px;margin-top:22px">
    <div class="panel" style="padding:18px 28px"><pre class="spec" style="font-size:18px">{_spec_lines("LEDGER", ("[L7]", "[L11]", "[L12]", "[L13]", "invariants", "bal(settle", "size(settle"))}</pre></div>
    <div class="panel" style="padding:18px 28px"><pre class="spec" style="font-size:18px">{_spec_lines("ENTRY", ("[E2]", "[E3]", "[E5]", "[E6]", "invariants", "from E2", "from E6", "quantity and last price"))}</pre></div>
  </div>
</div>""",
        "t_arch": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:60px">
  <div class="kicker">Architecture · strict layers · 13 decision records</div>
  <div style="display:grid;grid-template-columns:1fr 520px;gap:28px;margin-top:22px">
    <div>
      {_arch_box("ui · screens (customtkinter)", ["New and Classic layouts", "widgets", "i18n hook"], "#22d3ee")}
      {ARCH_ARROW}
      <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:18px">
        {_arch_box("services · rules, no Tk", ["sales", "accounts", "inventory", "krar", "reports", "auth", "audit", "backup", "updates"], "#a78bfa")}
        {_arch_box("modules", ["bills", "crops", "finance"], "#f472b6")}
        {_arch_box("assistant", ["System 1", "tools", "voice"], "#fb923c")}
      </div>
      {ARCH_ARROW}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
        {_arch_box("domain · no I/O", ["interest", "units", "numbers"], "#34d399")}
        {_arch_box("db · SQLite", ["transactions", "migrations"], "#fbbf24")}
      </div>
    </div>
    <div class="panel" style="padding:18px 22px">{adrs}</div>
  </div>
</div>""",
        "t_code": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:64px">
  <div class="kicker">The code behind two promises</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:24px">
    <div><div class="statl" style="margin-bottom:10px">hth/domain/interest.py · the only place interest is computed</div>
      <div class="panel code">{_code(V5 / "hth/domain/interest.py", "def interest_schedule(", "@lru_cache")}</div></div>
    <div><div class="statl" style="margin-bottom:10px">hth/db/connection.py · every unit of work is one transaction</div>
      <div class="panel code">{_code(V5 / "hth/db/connection.py", "        active = getattr(self._local", "    # Convenience helpers")}</div></div>
  </div>
</div>""",
        "t_trace": """
<div class="wrap">
  <div class="kicker">Traceability · one requirement, end to end</div>
  <h2 style="margin-top:12px">Several items and a payment, all or nothing</h2>
  <div class="chain">
    <div class="step"><div class="k">Requirement</div><div class="v">FR-9.1, FR-9.2<br>one save, one transaction</div></div><div class="arrow">→</div>
    <div class="step"><div class="k">Decision tables</div><div class="v">DT-2 validate<br>DT-3 what is written</div></div><div class="arrow">→</div>
    <div class="step"><div class="k">Spec</div><div class="v">ENTRY<br>axioms E2, E6</div></div><div class="arrow">→</div>
    <div class="step"><div class="k">Code</div><div class="v">SalesService<br>record_lines<br>record_sale_with_payment</div></div><div class="arrow">→</div>
    <div class="step"><div class="k">Tests</div><div class="v">TC-83 atomic + undo<br>TC-84 paid now</div></div>
  </div>
  <div class="statl" style="margin-top:30px;font-size:24px">…and on screen ↓</div>
</div>""",
        "t_test": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:60px">
  <div class="kicker">Testing · risk-based, traced, automated</div>
  <div style="display:grid;grid-template-columns:1fr 600px;gap:30px;margin-top:20px">
    <div class="panel"><div class="statl" style="margin-bottom:12px">316 tests by area</div>{bars}</div>
    <div style="display:flex;flex-direction:column;gap:22px">
      <div class="panel"><div class="stat">316 / 316</div><div class="statl">passing · lint clean · a fresh clone passes on its own</div></div>
      <div class="panel"><div class="li" style="font-size:23px"><b>Levels</b> unit · integration · migration · regression · UI · non-functional · acceptance<br>
        <b>Techniques</b> equivalence classes, boundary values, decision-table and state-transition testing, fault injection, an oracle for interest<br>
        <b>Traceability</b> 80 FRs → 166 test cases</div></div>
    </div>
  </div>
</div>""",
        "t_wbs": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:56px">
  <div class="kicker">Planning · work breakdown structure</div>
  {_wbs_chart(plan, "R[High Table Holdings v4]")}
</div>""",
        "t_plan": f"""
<div class="wrap" style="justify-content:flex-start;padding-top:56px">
  <div class="kicker">Planning · activity network, CPM and PERT</div>
  <div style="display:grid;grid-template-columns:1180px 1fr;gap:26px;margin-top:20px">
    <div class="panel" style="padding:10px">{_diagram(plan, "St((Start<br/>23 Oct))", 1160, 560)}</div>
    <div style="display:flex;flex-direction:column;gap:20px">
      <div class="panel"><div class="statl">Baseline critical path</div><div class="stat">57 days</div><div class="statl">σ 2.38 · A→B→C→E→G→I→M→N→O→Q</div></div>
      <div class="panel"><div class="statl">Re-planned, 23 Oct</div><div class="stat">8.3 days</div><div class="statl">σ 0.91 · S→U→V→W→X→Q</div></div>
      <div class="panel"><div class="statl">P(done by 5 Nov)</div><div class="stat">97 %</div><div class="statl">deadline 11 Nov</div></div>
    </div>
  </div>
</div>""",
        "t_pm": """
<div class="wrap">
  <div class="kicker">Project management</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:30px">
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Configuration</div>
      <div class="li">semantic versions · CHANGELOG per release<br>feature branches → <b>main</b> → <b>v5</b>, the update channel<br>schema version in the database</div></div>
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Change control</div>
      <div class="li">10 change requests logged<br>8 accepted, 2 deferred with reasons<br>rules like interest change only with a test</div></div>
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Risks</div>
      <div class="li">11 risks, probability × impact<br>2 occurred: scope growth, toolkit versions<br>reviewed against the plan</div></div>
    <div class="panel"><div class="t" style="font-size:28px;color:#22d3ee">Quality</div>
      <div class="li">definition of done · code review<br>a regression test for every fix<br>same-figures check before books changes</div></div>
  </div>
</div>""",
        "t_end": f"""
<div class="wrap" style="align-items:center;text-align:center">
  <div class="kicker">High Table Holdings</div>
  <h1 style="font-size:92px">Specified · designed · tested · managed</h1>
  <div style="margin-top:34px">
    <span class="chip">SRS</span><span class="chip">DFDs · ER</span><span class="chip">Decision tables</span>
    <span class="chip">Algebraic specs</span><span class="chip">Architecture · ADRs</span><span class="chip">Test plan · report</span>
    <span class="chip">WBS · PERT · Gantt</span><span class="chip">Management plan</span></div>
  {team_line}
  <div class="lead mono" style="font-size:34px;color:#22d3ee;margin-top:30px">{repo}</div>
</div>""",
    }


def _arch_box(title, items, color, width="100%"):
    chips = "".join(f'<span class="chip" style="font-size:22px;padding:6px 14px">{i}</span>' for i in items)
    return (
        f'<div style="width:{width};border:2px solid {color};border-radius:20px;padding:18px 24px;'
        f'background:rgba(15,23,42,.75)"><div style="font-size:28px;font-weight:700;color:{color};'
        f'margin-bottom:12px">{title}</div>{chips}</div>'
    )


ARCH_ARROW = '<div style="text-align:center;font-size:34px;color:#475569;line-height:1;margin:8px 0">\u25bc</div>'


def _architecture_html() -> str:
    box, arrow = _arch_box, ARCH_ARROW
    return f"""
<div class="wrap">
  <div class="kicker">How it is built</div>
  <div style="display:grid;grid-template-columns:1fr 330px;gap:30px;margin-top:26px">
    <div>
      {box("Screens (customtkinter)", ["New layout: Today · Counter · Khata · Stock · Money · Reports", "Classic layout", "English / हिन्दी"], "#22d3ee")}
      {arrow}
      {box("Services: the business rules, no Tk", ["sales", "accounts", "inventory", "krar", "reports", "auth · permissions", "audit", "backup", "updates"], "#a78bfa")}
      {arrow}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
        {box("Domain rules (no I/O)", ["interest", "units", "numbers"], "#34d399")}
        {box("One SQLite file", ["hth.db", "versioned, atomic migrations"], "#fbbf24")}
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:22px;padding-top:4px">
      {box("Feature modules", ["GST bills", "crop trading", "finance"], "#f472b6")}
      {box("Assistant", ["System 1 classifier", "read-only tools", "Vosk voice, offline"], "#fb923c")}
      {box("Decisions", ["13 ADRs", "arc42 architecture"], "#94a3b8")}
    </div>
  </div>
</div>"""


# 3. Voice --------------------------------------------------------------------------------------
def voices(scenes: list[Scene]) -> None:
    import win32com.client

    VOICE.mkdir(parents=True, exist_ok=True)
    cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
    cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", False)
    tokens = {t.GetDescription(): t for t in cat.EnumerateTokens()}

    def say(who: str, text: str, path: Path, rate: int = 0) -> float:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voice.Voice = next(t for d, t in tokens.items() if who in d)
        voice.Rate = rate
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
        fmt.Type = 22  # 22 kHz, 16-bit, mono
        stream.Format = fmt
        stream.Open(str(path), 3)
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()
        return _wav_seconds(path)

    notes = json.loads((OUT / "capture.json").read_text(encoding="utf-8")) if (OUT / "capture.json").exists() else {}
    answer = (notes.get("spoken_answer") or "रमेश कुमार पर बकाया है").split(". ")[0]  # its first sentence
    print("hindi answer", round(say("Kalpana", answer, VOICE / "hindi_answer.wav"), 2), "s")
    total = 0.0
    for s in scenes:
        for i, line in enumerate(s.lines):
            if line.clip:
                continue
            secs = say("Ravi", line.say or line.show, VOICE / f"{s.key}_{i}.wav", rate=2)
            total += secs
    print(f"narration {total:.1f} s")


def _wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def _wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == RATE and w.getsampwidth() == 2 and w.getnchannels() == 1, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


# 4. Build: timeline, pictures, sound, ffmpeg ----------------------------------------------------
@dataclass
class Timed:
    scene: Scene
    start: float
    length: float
    line_starts: list[float]
    line_lengths: list[float]
    term: list[tuple[float, str, str]] | None = None


def timeline(scenes: list[Scene]) -> list[Timed]:
    out, t = [], 0.0
    for s in scenes:
        u, starts, lengths = s.lead, [], []
        for i, line in enumerate(s.lines):
            secs = _wav_seconds(VOICE / (f"{line.clip}.wav" if line.clip else f"{s.key}_{i}.wav"))
            starts.append(u)
            lengths.append(secs)
            u += secs + line.pause
        length = u + s.tail
        term = None
        if s.terminal:
            term = _terminal_times(s, starts, lengths)
            if not s.shots:
                length = max(length, term[-1][0] + 2.0)
        out.append(Timed(s, t, length, starts, lengths, term))
        t += length
    return out


def _terminal_times(s: Scene, starts, lengths) -> list[tuple[float, str, str]]:
    """When each terminal line appears; commands are typed at a steady pace."""
    if s.shots:
        a, f = s.shots[0].at
        end = max(starts[0] + 2.0, starts[a] + lengths[a] * f - 0.7)
    else:
        end = starts[-1] + lengths[-1] * 0.85
    weights = [max(4, len(text) * 0.6) if kind == "cmd" else (0.05 if kind == "venv" else 3) for kind, text in s.terminal]
    scale = (end - s.lead * 0.5) / sum(weights)
    t, out = s.lead * 0.5, []
    for (kind, text), wgt in zip(s.terminal, weights):
        out.append((t, kind, text))
        t += wgt * scale
    return out


class Canvas:
    """Draws every frame; caches what does not change."""

    def __init__(self):
        from PIL import Image, ImageDraw, ImageFilter, ImageFont

        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.font = lambda name, size: ImageFont.truetype(str(FONTS / name), size)
        self.f_sub = self.font("seguisb.ttf", 34)
        self.f_chap = self.font("seguisb.ttf", 24)
        self.f_mono = self.font("CascadiaMono.ttf", 25)
        self.f_mono_b = self.font("CascadiaMono.ttf", 25)
        bg = Image.new("RGB", (W, H))
        top, bottom = np.array((11, 18, 32), float), np.array((19, 32, 58), float)
        ramp = np.linspace(0, 1, H)[:, None, None]
        bg = Image.fromarray((top * (1 - ramp) + bottom * ramp).repeat(W, axis=1).astype(np.uint8))
        shadow = Image.new("L", (W, H), 0)
        x0, y0, x1, y1 = APP_BOX
        ImageDraw.Draw(shadow).rounded_rectangle((x0 + 6, y0 + 16, x1 + 6, y1 + 22), 18, fill=170)
        shadow = shadow.filter(ImageFilter.GaussianBlur(26))
        self.app_bg = Image.composite(Image.new("RGB", (W, H), (2, 6, 14)), bg, shadow)
        self.bg = bg
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), 14, fill=255)
        self.app_mask = mask
        self.frames: dict[str, object] = {}
        self.slides: dict[str, object] = {}
        self._sub_cache: dict[str, tuple] = {}
        self._chap_cache: dict[str, object] = {}

    def frame(self, name):
        if name not in self.frames:
            img = self.Image.open(FRAMES / f"{name}.png").convert("RGB")
            if img.size != (APP_W, APP_H):
                img = img.resize((APP_W, APP_H), self.Image.LANCZOS)
            self.frames[name] = img
        return self.frames[name]

    def slide(self, name):
        if name not in self.slides:
            self.slides[name] = self.Image.open(SLIDES / f"{name}.png").convert("RGB")
        return self.slides[name]

    # app pictures with a moving camera
    def app_view(self, img, rect, box, box_alpha):
        x0, y0, x1, y1 = APP_BOX
        dw, dh = x1 - x0, y1 - y0
        crop = img.resize((dw, dh), self.Image.BILINEAR, box=rect)
        if box is not None and box_alpha > 0:
            sx, sy = dw / (rect[2] - rect[0]), dh / (rect[3] - rect[1])
            bx = [(box[0] - rect[0]) * sx, (box[1] - rect[1]) * sy, (box[2] - rect[0]) * sx, (box[3] - rect[1]) * sy]
            dim = self.Image.new("L", (dw, dh), int(110 * box_alpha))
            self.ImageDraw.Draw(dim).rounded_rectangle(bx, 12, fill=0)
            crop = self.Image.composite(self.Image.new("RGB", (dw, dh), (8, 12, 22)), crop, dim)
            ring = self.Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
            self.ImageDraw.Draw(ring).rounded_rectangle(
                [bx[0] - 3, bx[1] - 3, bx[2] + 3, bx[3] + 3], 14, outline=ACCENT + (int(255 * box_alpha),), width=4
            )
            crop = self.Image.alpha_composite(crop.convert("RGBA"), ring).convert("RGB")
        out = self.app_bg.copy()
        out.paste(crop, (x0, y0), self.app_mask)
        return out

    def terminal(self, lines_shown, typing=None, cursor=True):
        img = self.app_bg.copy()
        d = self.ImageDraw.Draw(img)
        x0, y0, x1, y1 = APP_BOX
        d.rounded_rectangle((x0, y0, x1, y1), 14, fill=(12, 12, 16))
        d.rounded_rectangle((x0, y0, x1, y0 + 46), 14, fill=(32, 34, 40))
        d.rectangle((x0, y0 + 30, x1, y0 + 46), fill=(32, 34, 40))
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((x0 + 20 + i * 26, y0 + 15, x0 + 36 + i * 26, y0 + 31), fill=c)
        d.text((x0 + 110, y0 + 10), "Terminal  ·  a fresh clone on this PC", font=self.f_chap, fill=MUTED)
        rows = list(lines_shown)
        if typing is not None:
            rows.append(typing)
        line_h, top = 35, y0 + 66
        visible = (y1 - top - 20) // line_h
        rows = rows[-visible:]
        colours = {"out": (204, 204, 204), "dim": (120, 128, 140), "ok": (134, 239, 172), "pass": (74, 222, 128)}
        for i, (kind, text, venv) in enumerate(rows):
            y = top + i * line_h
            x = x0 + 28
            if kind in ("cmd", "typing"):
                if venv:
                    d.text((x, y), "(.venv) ", font=self.f_mono, fill=(134, 239, 172))
                    x += d.textlength("(.venv) ", font=self.f_mono)
                d.text((x, y), "> ", font=self.f_mono, fill=ACCENT)
                x += d.textlength("> ", font=self.f_mono)
                d.text((x, y), text, font=self.f_mono_b, fill=(250, 250, 250))
                if kind == "typing" and cursor:
                    cx = x + d.textlength(text, font=self.f_mono_b) + 2
                    d.rectangle((cx, y + 4, cx + 13, y + 30), fill=(250, 250, 250))
            else:
                d.text((x, y), text, font=self.f_mono, fill=colours.get(kind, (204, 204, 204)))
        return img

    def chapter(self, img, label):
        if not label:
            return img
        if label not in self._chap_cache:
            tw = int(self.ImageDraw.Draw(img).textlength(label, font=self.f_chap))
            chip = self.Image.new("RGBA", (tw + 44, 44), (0, 0, 0, 0))
            cd = self.ImageDraw.Draw(chip)
            cd.rounded_rectangle((0, 0, tw + 43, 43), 22, fill=(15, 23, 42, 230), outline=(51, 65, 85, 255))
            cd.ellipse((16, 17, 26, 27), fill=ACCENT + (255,))
            cd.text((34, 8), label, font=self.f_chap, fill=INK)
            self._chap_cache[label] = chip
        chip = self._chap_cache[label]
        img = img.convert("RGBA")
        img.alpha_composite(chip, (APP_BOX[0], 20))
        return img.convert("RGB")

    def subtitle(self, text):
        if not text:
            return None
        if text not in self._sub_cache:
            d = self.ImageDraw.Draw(self.Image.new("RGB", (8, 8)))
            words, lines, cur = text.split(), [], ""
            for word in words:
                trial = f"{cur} {word}".strip()
                if d.textlength(trial, font=self.f_sub) > 1500 and cur:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            lines.append(cur)
            lh = 46
            bw = int(max(d.textlength(t, font=self.f_sub) for t in lines)) + 56
            bh = lh * len(lines) + 26
            pill = self.Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            pd = self.ImageDraw.Draw(pill)
            pd.rounded_rectangle((0, 0, bw - 1, bh - 1), 16, fill=(2, 6, 14, 205))
            for i, t in enumerate(lines):
                tw = pd.textlength(t, font=self.f_sub)
                pd.text(((bw - tw) / 2, 10 + i * lh), t, font=self.f_sub, fill=(248, 250, 252))
            self._sub_cache[text] = (pill, ((W - bw) // 2, H - bh - 22))
        return self._sub_cache[text]


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _rect_for(shot: Shot) -> tuple[float, float, float, float]:
    if shot.box is None or shot.zoom <= 1.0:
        return (0.0, 0.0, float(APP_W), float(APP_H))
    w, h = APP_W / shot.zoom, APP_H / shot.zoom
    cx, cy = (shot.box[0] + shot.box[2]) / 2, (shot.box[1] + shot.box[3]) / 2
    x0 = min(max(cx - w / 2, 0), APP_W - w)
    y0 = min(max(cy - h / 2, 0), APP_H - h)
    return (x0, y0, x0 + w, y0 + h)


def _on_slide(tm: Timed, u: float) -> bool:
    s = tm.scene
    if not s.slide:
        return False
    if not s.shots:
        return True
    a, f = s.shots[0].at
    return u < tm.line_starts[a] + tm.line_lengths[a] * f + 0.2


def render_scene_frame(cv: Canvas, tm: Timed, u: float):
    """The picture of scene ``tm`` at ``u`` seconds into it (no subtitle)."""
    s = tm.scene
    if s.slide and not s.shots:
        return cv.slide(s.slide)
    times = [tm.line_starts[a] + tm.line_lengths[a] * f for a, f in ((sh.at[0], sh.at[1]) for sh in s.shots)]
    if s.terminal and (not s.shots or u < times[0]):
        return _terminal_at(cv, tm, u)
    if s.slide and u < times[0]:
        return cv.slide(s.slide)
    k = max(i for i, t in enumerate(times) if t <= max(u, times[0]))
    shot = s.shots[k]
    since = u - times[k]
    prev = s.shots[k - 1] if k > 0 else None
    rect_to = _rect_for(shot)
    rect_from = _rect_for(prev) if prev is not None else rect_to
    p = _ease(since / 0.8)
    rect = tuple(a + (b - a) * p for a, b in zip(rect_from, rect_to))
    box_alpha = _ease((since - 0.5) / 0.4) if shot.box else 0.0
    img = cv.app_view(cv.frame(shot.frame), rect, shot.box, box_alpha)
    if prev is not None and prev.frame != shot.frame and since < 0.3:
        old = cv.app_view(cv.frame(prev.frame), rect, None, 0.0)
        img = cv.Image.blend(old, img, _ease(since / 0.3))
    elif k == 0 and s.terminal and since < 0.35:
        img = cv.Image.blend(_terminal_at(cv, tm, u), img, _ease(since / 0.35))
    elif k == 0 and s.slide and since < 0.45:
        img = cv.Image.blend(cv.slide(s.slide), img, _ease(since / 0.45))
    return img


def _terminal_at(cv: Canvas, tm: Timed, u: float):
    shown, typing, venv = [], None, False
    for i, (t, kind, text) in enumerate(tm.term):
        if t > u:
            break
        if kind == "venv":
            venv = True
            continue
        if kind == "cmd":
            nxt = tm.term[i + 1][0] if i + 1 < len(tm.term) else t + 1.5
            typing_end = t + min(len(text) / 26.0, (nxt - t) * 0.7)
            if u < typing_end:
                n = int(len(text) * (u - t) / (typing_end - t))
                typing = ("typing", text[:n], venv)
                break
        shown.append((kind, text, venv))
    if typing is None:
        # while a command still has output to come there is no new prompt yet
        upcoming = [kind for t, kind, _text in tm.term if t > u and kind != "venv"]
        running = bool(upcoming) and upcoming[0] != "cmd" and any(k == "cmd" for k, _t, _v in shown)
        typing = None if running else ("typing", "", venv)
    blink = typing is not None and (typing[1] != "" or int(u * 2.2) % 2 == 0)
    return cv.terminal(shown, typing, cursor=blink)


def build() -> None:
    scenes = storyboard(CUT)
    tms = timeline(scenes)
    total = tms[-1].start + tms[-1].length
    print(f"video length {total:.1f} s")

    # the soundtrack
    audio = np.zeros(int((total + 1) * RATE), dtype=np.int32)
    for tm in tms:
        for i, line in enumerate(tm.scene.lines):
            clip = _wav(VOICE / (f"{line.clip}.wav" if line.clip else f"{tm.scene.key}_{i}.wav"))
            at = int((tm.start + tm.line_starts[i]) * RATE)
            audio[at : at + len(clip)] += clip
    sound = OUT / "soundtrack.wav"
    with wave.open(str(sound), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.clip(audio, -32768, 32767).astype(np.int16).tobytes())

    cv = Canvas()
    ffmpeg = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-i", str(sound),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest",
            str(VIDEO),
        ],
        stdin=subprocess.PIPE,
    )  # fmt: skip
    fade = 0.4
    n_frames = int(total * FPS)
    started = time.time()
    for f in range(n_frames):
        t = f / FPS
        k = max(i for i, tm in enumerate(tms) if tm.start <= t)
        tm = tms[k]
        u = t - tm.start
        img = render_scene_frame(cv, tm, u)
        if k + 1 < len(tms) and u > tm.length - fade / 2:  # cross-fade into the next scene
            nxt = tms[k + 1]
            a = _ease((u - (tm.length - fade / 2)) / fade)
            img = cv.Image.blend(img, render_scene_frame(cv, nxt, 0.0), a)
        elif k > 0 and u < fade / 2:
            prev = tms[k - 1]
            a = _ease((u + fade / 2) / fade)
            img = cv.Image.blend(render_scene_frame(cv, prev, prev.length), img, a)
        if not _on_slide(tm, u):
            img = cv.chapter(img, tm.scene.chapter)
        sub = None
        for i, start in enumerate(tm.line_starts):
            end = tm.line_starts[i + 1] if i + 1 < len(tm.line_starts) else tm.length - 0.2
            if start - 0.1 <= u < end:
                sub = cv.subtitle(tm.scene.lines[i].show)
        if sub is not None:
            img = img.convert("RGBA")
            img.alpha_composite(sub[0], sub[1])
            img = img.convert("RGB")
        ffmpeg.stdin.write(img.tobytes())
        if f % (FPS * 10) == 0:
            print(f"  {t:5.1f}/{total:.1f} s  ({time.time() - started:.0f} s)", flush=True)
    ffmpeg.stdin.close()
    ffmpeg.wait()
    print("wrote", VIDEO, f"{VIDEO.stat().st_size / 1e6:.1f} MB")


def preview() -> None:
    """One still per shot, as it looks once its highlight is on, for checking before a build."""
    tms = timeline(storyboard(CUT))
    cv = Canvas()
    shots_dir = OUT / ("preview" if CUT == "tour" else f"preview-{CUT}")
    shots_dir.mkdir(parents=True, exist_ok=True)
    stills = []
    for tm in tms:
        s = tm.scene
        moments = [tm.line_starts[a] + tm.line_lengths[a] * f + 1.3 for a, f in (sh.at for sh in s.shots)]
        if not s.shots:
            moments = [tm.length * 0.6]
        elif s.slide:
            moments = [0.8] + moments
        for i, u in enumerate(moments):
            u = min(u, tm.length - 0.3)
            img = render_scene_frame(cv, tm, u)
            img = img if _on_slide(tm, u) else cv.chapter(img, s.chapter)
            path = shots_dir / f"{s.key}_{i}.jpg"
            img.save(path, quality=85)
            stills.append(path)
    print(len(stills), "stills in", shots_dir, f"- video about {tms[-1].start + tms[-1].length:.0f} s")


# ----------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    cut = "tour"
    if "--cut" in argv:
        i = argv.index("--cut")
        cut = argv[i + 1]
        argv = argv[:i] + argv[i + 2 :]
    if cut not in CUTS:
        print("unknown cut", cut, "- one of", ", ".join(CUTS))
        return 2
    use_cut(cut)
    steps = argv or ["capture", "slides", "voice", "build"]
    team = json.loads((HERE / "team.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for step in steps:
        print("==", step)
        if step == "capture":
            # Tk and DPI settings stay out of this process
            subprocess.run([sys.executable, __file__, "_capture"], check=True)
        elif step == "_capture":
            capture()
        elif step == "slides":
            slides(team)
        elif step == "voice":
            voices(storyboard(CUT))
        elif step == "build":
            build()
        elif step == "preview":
            preview()
        else:
            print("unknown step", step)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
