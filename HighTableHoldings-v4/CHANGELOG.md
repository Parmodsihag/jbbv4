# Changelog

## 4.0.0 — 2026-08-29

Ground-up rewrite. Business rules and numbers are unchanged from 3.7.1.

### Users and access
- Sign-in screen; `admin` (administrator) and `emp1` (employee) seeded on first run.
- Declarative permission matrix (`services/permissions.py`). Employees can record,
  add and report; only administrators edit, delete, manage users, see the audit log,
  back up or import.
- Every write records the acting user; logins/logouts are audited.

### User interface
- customtkinter UI with light and dark themes, sidebar navigation, keyboard shortcuts,
  toasts and a status bar.
- Searchable pickers for accounts and items (type any part of the id / name / village).
- Sales screen: last-price auto-fill, live amount preview, current balance of the selected
  account, today's entries list.
- Accounts and Items screens combine "add" with a searchable list and a drill-in ledger /
  movement history. Admin edits happen in dialogs from the ledger — the generic "Modify by
  row id" screen is gone.
- Dashboard: KPI tiles, 14-day activity, monthly debits vs credits, receivables by age,
  top debtors, krar list.
- Reports: 15 reports in a declarative catalogue, sortable columns, Excel export,
  double-click to open the ledger / item.

### Data
- One SQLite database (`hth.db`) with a normalised schema, foreign keys and indexes,
  replacing five files and one-table-per-customer/item/day.
- Versioned schema migrations; transaction-scoped, re-entrant connections (a sale is one
  atomic transaction across ledger, stock and audit).
- Cross-platform data folder (`HTH_DATA_DIR` override); no hard-coded `C:/JBB` paths.
- `tools/migrate_v3.py` and Settings → Import v3 data (IDs preserved, tags/types normalised).
- Online backup from Settings.

### Correctness
- Interest computed in exactly one place and pinned against the v3 implementation by tests.
- "Today" is evaluated at call time (v3 froze it at import).
- Settlement discount rounded to 2 dp; derived settlement rows may be negative as in v3.
- Input validation with clear messages instead of silent failures / console prints.
- Rotating log file in `<data>/logs`.

### Removed / deferred
- `bills` and `crop_trading` are not in the core; they return as independent modules
  (`hth/modules/`).
- Dead code from v3 (`reports2.py`, `mypandasfile2.py`, `output.txt`, one-off Excel
  translation scripts) is not carried over.
