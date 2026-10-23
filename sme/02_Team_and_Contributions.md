# High Table Holdings — Project Documentation

**Course:** Software Engineering & Management (SEM 2026-27), BITS Pilani
**Team No.:** <<Team No.>>
**Git repository (public):** <https://github.com/Parmodsihag/jbbv4>
**Application version documented:** 5.7.0 (folder `v5/`; history in `v5/CHANGELOG.md`).
v4 (4.7.0, folder `HighTableHoldings-v4/`) is the first increment and is kept for reference.

## Team members and contributions

> **Edit this table before submitting** so it shows who actually did what. Grading is
> team-based, but the guidelines require each member's contribution on this page. The rows
> below are a starting split by area of the code and documents.

| # | Name | BITS ID | Contribution |
|---|------|---------|--------------|
| 1 | <<Member 1>> | <<ID>> | Requirements elicitation with the shop owner and study of legacy v3; SRS (informal, semi-formal, formal) for v4 and the v5 increment; domain layer: interest formula, constants, units, Indian number grouping; `accounts` and `sales` services incl. multi-line entries, paid-now and undo; SQLite schema and migrations. |
| 2 | <<Member 2>> | <<ID>> | UI/UX: customtkinter shell, themes and the seven colour themes, reusable widgets; Classic screens and the New layout (Today, Counter, Khata, Stock, Money, Reports, Settings); keyboard shortcuts; Hindi interface (phrase table, widget hook, transliteration); user guide. |
| 3 | <<Member 3>> | <<ID>> | Feature modules (bills, crop trading, finance); v3 importer and data check; v5 safety (own data folder, restore, atomic migrations, lock, lockout); in-app updates; the assistant (System 1, tools, System 2 training cell) and voice; admin guide. |
| 4 | <<Member 4>> | <<ID>> | Quality & management: test plan, `pytest` suite (96 tests in v4, 316 in v5.7), test cases and traceability, test report; decision tables, algebraic specifications, DFDs; WBS / activity network / PERT and tracking; project management plan; architecture and decision records; video and presentation. |

## Document map

| Chapter | Content |
|---------|---------|
| 1 | Software Requirements Specification: informal, semi-formal and formal (v4 FR-1 – FR-8, v5 FR-9 – FR-14) |
| 2 | DFD modelling (levels 0, 1, 2), ER diagram, architecture, deployment |
| 3 | Decision tables DT-1 – DT-22 |
| 4 | Algebraic specifications (interest, ledger, stock, FIFO, krar, permissions, audit, cash book, entry and undo, lockout, update) |
| 5 | Work Breakdown Structure, activity network, CPM, PERT, Gantt; plan vs actual; re-baselined plan to submission; risk register |
| 6 | Test cases TC-1 – TC-166, traceability matrix, acceptance checklist |
| 7 | Project management plan: process, roles, communication, configuration and change management, quality, metrics, lessons learned |

Engineering documents kept with the code (`v5/docs/`): user guide, admin and operations
guide, architecture (arc42), 13 architecture decision records, data dictionary, test plan,
test report 5.7.0, release process; `CONTRIBUTING.md` and `SECURITY.md` at the repository
root.

## How to build and run (summary)

```bash
git clone https://github.com/Parmodsihag/jbbv4.git
cd jbbv4/v5
python -m venv .venv && .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py                                          # first start: admin/admin, emp1/emp1 (change them)

pip install -r requirements-dev.txt
pytest -rs                                             # 282 passed, 34 skipped (UI and real-voice tests)
HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py tests/test_ui_modern.py   # the 33 UI tests

pyinstaller --noconfirm --windowed --name HighTableHoldings --add-data "bundled;bundled" --collect-all vosk run.py
```

On the shop PC the program is started with `Start High Table Holdings v5.bat` and updates
itself from the repository's `v5` branch (Settings › Updates).
