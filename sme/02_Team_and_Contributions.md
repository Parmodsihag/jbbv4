# High Table Holdings v4 — Project Documentation

**Course:** Software Engineering & Management (SEM 2026-27), BITS Pilani
**Team No.:** <<Team No.>>
**Git repository (public):** <https://github.com/Parmodsihag/jbbv4>
**Application version documented:** 4.7.0 (see `HighTableHoldings-v4/CHANGELOG.md`)

## Team members and contributions

> Edit the table so it reflects the actual split. Grading is team-based, but the
> guidelines require each member's contribution to be listed on this page.

| # | Name | BITS ID | Contribution |
|---|------|---------|--------------|
| 1 | <<Member 1>> | <<ID>> | Requirements elicitation from the shop owner and study of legacy v3; SRS (informal, semi-formal, formal); domain layer — interest formula, constants, unit conversion; `accounts` and `sales` services; SQLite schema and migrations. |
| 2 | <<Member 2>> | <<ID>> | UI/UX — customtkinter app shell, theme, reusable widgets (data table, search box, dialogs, KPI tiles, charts); Dashboard, Sales, Accounts, Items, Karar, Reports and Settings screens; keyboard shortcuts; global search; first-run wizard. |
| 3 | <<Member 3>> | <<ID>> | Feature modules — Bills (GST invoice, DOCX/PDF, month batch), Crop trading (lots, FIFO costing, rates), Finance (cash book, P&L, cash flow); module extension contract; v3 → v4 migration tool and migration report; data-quality check. |
| 4 | <<Member 4>> | <<ID>> | Quality & management — `pytest` suite (96 tests: business rules, migration equivalence, modules, UI walkthrough), decision tables, algebraic specifications, DFDs, WBS / activity network / PERT, test-case design and traceability, packaging with PyInstaller, video and presentation. |

## Document map

| Chapter | Content |
|---------|---------|
| 1 | Software Requirements Specification — informal, semi-formal and formal |
| 2 | DFD modelling, ER diagram, architecture |
| 3 | Decision tables |
| 4 | Algebraic specifications |
| 5 | Work Breakdown Structure, Activity Network, PERT chart, Gantt |
| 6 | Test cases and traceability matrix |

## How to build and run (summary)

```bash
git clone https://github.com/Parmodsihag/jbbv4.git
cd jbbv4/HighTableHoldings-v4
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                                         # default users admin/admin, emp1/emp1
pip install -r requirements-dev.txt && pytest         # 94 passed, 2 skipped (UI tests need a display)
pyinstaller --noconfirm --windowed --name HighTableHoldings run.py   # shop-PC build
```
