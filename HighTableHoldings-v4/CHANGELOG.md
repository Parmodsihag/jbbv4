# Changelog

## 4.7.0 — 2026-08-30

- **Payment reminders** on the Karar screen: copy a message, open WhatsApp (when a mobile
  number is in the account details), copy all shown; editable template in Settings.
- **Automatic daily backup** on the first start of each day (`hth_auto_YYYYMMDD.db`),
  pruned to the last N; toggle and count in Settings.
- **First-run wizard**: shop details, new passwords (defaults refused), optional v3 import;
  rerun from Settings.
- **Global search** (`Ctrl+K` / header button) across accounts, items and bills.

## 4.6.0 — 2026-08-30

- **Customer statement**: ledger → *Statement* → date range → print-ready HTML in the
  exports folder, opened in the browser (print / save as PDF). Same rows and running
  balance as the screen; opening/closing balances, period totals, interest column.
- **Shop details** (name, tagline, address, phone, GSTIN, licences, footer) in Settings,
  stored in the database; used by statements now and by invoices next.

## 4.5.1 — 2026-08-30

- **Unit change converts history.** Edit item → Unit now converts every stock movement,
  crop lot / sale / allocation and market rate to the new unit (automatic factor for related
  units, asked for unrelated ones, or relabel-only on request). Per-unit prices are divided
  by the same factor so money values are unchanged. Useful for imported items that were
  stored as packets but are sold loose.

## 4.5.0 — 2026-08-30

- **Finance module** (`hth/modules/finance`, sidebar *Finance*, `Alt+F`): multiple money
  accounts (cash / bank / UPI) with opening balances; cash book with running balance;
  expenses by head, other income, transfers, capital in / drawings; expense & income heads;
  recurring expenses with one-click posting; reports: cash flow, profit & loss, expenses by
  head, monthly expenses, account balances. Permissions `finance` (all) and
  `finance_reports` (admin: reports, setup, delete). Migration 5; audit code `12`.
- **Sales screen**: a *Money account* picker appears for money entries (item CASH / free
  text); customer receipts and payments are written to the cash book automatically, linked
  to the ledger entry. Stock movements now store their value for the P&L.
- Dashboard: *Cash & bank* tile.

## 4.4.0 — 2026-08-30

- **Customer & item categories A–E** stored on each record (migration 4). E = defaulter /
  discontinued, manual only, locked; manual assignment of any category locks it.
- **Re-score customers** (Settings) maps the account score to A–D by configurable thresholds,
  skipping locked and E; **Auto-categorise items** by days since last sale.
- Setting *Keep E out of the score maths* (default on) excludes defaulters from score
  normalisation.
- **Report / dashboard scope**: Settings choose the categories included (default A–D); each
  customer/item report gets a *Scope: Per settings / All categories* switch. Dashboard KPIs,
  aging, top debtors, monthly flow, interest summary, customer activity, stock value, item
  movement, low/expiring/dead stock all honour it.
- Accounts and Items lists: *Cat* column, category filter; ledger and item headers show the
  category with a *Category* button. New customers start in the configurable default (C).
- `settings` table now backs a `SettingsService` for shared application settings.

## 4.3.0 — 2026-08-30

- **Crop trades on the main Sales screen.** Picking a crop item (type C) reveals the crop
  fields: Credit = purchase lot from the farmer (gross, deduction/kaat, quality, notes),
  Debit = FIFO-costed sale to the buyer with a live cost/margin preview and *Allow selling
  short*. One entry point for all money and stock movements; the crop module registers a
  handler with the sales service, so tools and the UI behave identically.
- Crop Trade screen now has *Lots & sales* (review, delete, new crop), *Stock & rates* and
  *Reports*; its separate purchase/sale forms are gone.
- Sales buttons renamed **Debit · sale / pay out** and **Credit · receive / purchase**, with
  an explanation of both meanings; today's list shows crop purchases and sales.

## 4.2.0 — 2026-08-30

- **Crop trading module** (`hth/modules/crop_trading`, sidebar *Crop Trade*, `Alt+C`):
  crops are items of type `C`; farmers and buyers are customer accounts; purchases are lots
  (gross / deduction / net, rate, quality) that credit the farmer and add stock; sales are
  FIFO-costed against lots with stored cost, margin and margin %, debit the buyer (or cash)
  and reduce stock; pay-farmer / receive-from-buyer entries; stock valuation at cost and at
  the latest market rate with unrealized gain; manual / CSV market rates with a
  `RateProvider` interface for a future API feed and a naive trend estimate as the predictor
  seam; reports (summary, margin by crop / buyer, purchases by farmer / quality, open lots).
  Schema migration 3; new permission `crop_trading` (both roles); item type `C`; audit
  codes `10` crop, `11` rate.
- Fix: `CTkTabview(segmented_button_font=...)` is not accepted by customtkinter 5.2.x
  (the version on the shop PC); the font is now set on the internal segmented button when
  supported. The full UI walkthrough now runs on both 5.2.2 and 6.0.

## 4.1.1 — 2026-08-30

- Fix: on laptop screens (≈1366×768) the Bills "Save & create DOCX" button and the
  bill-lines table were squeezed to zero height — tables requested 20 rows and were packed
  before the buttons. Tables now request 6 rows and grow to fit; action rows and hint labels
  are anchored to the bottom so they always keep their space (Bills, Accounts, Items, Karar).
- Bills screen shows a banner with the exact `pip install` command when `docxtpl` / `pypdf`
  are missing, and rendering fails with a clear message instead of a stack trace.

## 4.1.0 — 2026-08-29

- **Bills module** (`hth/modules/bills`): manual GST invoices, browse / open / PDF / merge,
  admin month-end batch generation — rebuilt from v3 with the same tax rules, Hindi amount
  in words and the same DOCX template. New permissions `billing` (all users) and
  `billing_batch` (admin). Schema migration 2 adds `bills`, `bill_lines`,
  `bill_month_items`.
- **Fractional quantities and units**: sell 100 G of a KG item or 2.5 QTL of a KG crop;
  the quantity is converted to the item's stock unit, stock and last price are no longer
  truncated to whole numbers. Unit picker on the Sales screen; new units G, QTL, ML, BTL.
- **Layout**: dashboard, Sales / Accounts / Items / Karar forms and the Bills panels are
  scrollable with fixed-height cards, so buttons are never pushed off-screen and charts no
  longer overlap on small displays.
- Typing an exact item label on the Sales screen adopts its unit and price like a click.

## 4.0.1 — 2026-08-29

- Fix: tables with hidden trailing values (dashboard krar list, Karar screen) crashed with
  `zip() argument 2 is shorter than argument 1` after the first import of real data.
- Migration now reports every skipped or normalised value with its v3 table and row id, and
  writes the list to `<data>/migration_report.txt` (also shown after Settings → Import).
- New admin report **Data check** and `tools/check_data.py`: invalid / future dates,
  negative stock, duplicate customers, zero-amount entries, lone settlement rows, open krar
  with nothing owed, long-inactive debtors. Double-click a finding to open the record.
- UI walkthrough test now seeds krar so hidden-column tables are exercised.

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
