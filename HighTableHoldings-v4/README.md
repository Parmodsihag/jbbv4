# High Table Holdings v4

Accounting and inventory management for **Jaat Beaj Bhander** — customer ledgers with
interest, stock, *krar* (promised payments), reports and dashboards.

v4 is a ground-up rewrite of v3.7.1: **same business rules, same numbers**, new UI, one
database, users with access levels, tests, and a clean layered codebase.

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python run.py
```

Requirements: Python 3.10+, Windows/macOS/Linux.

### First sign-in

Two users are created on first launch. **Change both passwords immediately**
(Settings → *Change my password*; admins can reset anyone in *Users*).

| username | password | role          |
|----------|----------|---------------|
| `admin`  | `admin`  | Administrator |
| `emp1`   | `emp1`   | Employee      |

### Bringing your v3 data across

Either **Settings → Import v3 data…** (admin; a backup is taken first), or from a terminal:

```bash
python tools/migrate_v3.py C:/JBB/data
```

Customer, item and krar IDs are preserved. Every v3 daily note becomes an audit-log entry.
Balances after import match v3 for the same date (see `tests/test_migration.py`).

The importer never guesses silently: every value it had to skip or normalise (blank or odd
tag, type not P/M, blank amount, date not `YYYY-MM-DD`, krar for a deleted customer) is
listed with its v3 table and row id in `<data folder>/migration_report.txt`. Work through
that list with **Reports → Audit log** (the v3 daily notes, searchable by customer name or
date) and correct entries from the ledger screens. Then run **Reports → Data check**, or
`python tools/check_data.py`, which flags invalid dates, negative stock, duplicate
customers, zero-amount or future-dated entries, lone settlement rows, open krar with
nothing owed, and long-inactive debtors.

### Where the data lives

One SQLite file, `hth.db`, plus `exports/`, `backups/` and `logs/` next to it:

| platform | default folder                                      |
|----------|-----------------------------------------------------|
| Windows  | `C:\JBB\v4`                                          |
| macOS    | `~/Library/Application Support/HighTableHoldings`   |
| Linux    | `~/.local/share/HighTableHoldings`                  |

Set the environment variable `HTH_DATA_DIR` to use a different folder (e.g. a synced drive).
**Settings → Backup now** writes a consistent copy to `backups/`.

---

## Roles and permissions

| capability                                   | admin | employee |
|----------------------------------------------|:-----:|:--------:|
| Dashboard                                    |  ✓    |   ✓      |
| Record sales / receipts                      |  ✓    |   ✓      |
| Add accounts and items                       |  ✓    |   ✓      |
| Add / settle krar                            |  ✓    |   ✓      |
| Reports and Excel export                     |  ✓    |   ✓      |
| Edit ledger entries, stock movements, items, customers |  ✓ |  –   |
| Delete anything                              |  ✓    |   –      |
| Audit log                                    |  ✓    |   –      |
| Manage users                                 |  ✓    |   –      |
| Backup, import v3 data                       |  ✓    |   –      |

The matrix is one table in `hth/services/permissions.py`; every screen and destructive
button checks it, and every write records the acting user in the audit log.

---

## Screens

* **Dashboard** – receivable / payable / stock-value / krar KPIs, activity (14 days),
  monthly debits vs credits, receivables by age, top 10 debtors, and the krar list.
* **Sales** – sale or receive against an account; item search auto-fills the last price;
  live amount preview; today's entries on the right. `Ctrl+Enter` = sale,
  `Ctrl+Shift+Enter` = receive. **Loose sales:** quantities are fractional and can be
  entered in any unit compatible with the item's stock unit — 100 G of a KG item, 2.5 QTL of
  a crop kept in KG, 500 ML of a LTR bottle. Price is always per stock unit. Set seed / crop
  / liquid items to `KG` / `LTR` when you add them so they can be split.
* **Bills** – GST tax invoices (see *Bills module* below).
* **Accounts** – create customers; searchable list with balance, days since activity and
  score; double-click for the full ledger (interest, debit, credit, running balance).
  Admins add / edit / delete entries from the ledger.
* **Items** – create items with opening stock; searchable stock list; double-click for the
  movement history. Admins edit items and movements.
* **Karar** – add or reschedule a promise date, settle it; Overdue / Today / Upcoming tabs.
* **Reports** – see below. Double-click a row to jump to the ledger or item.
* **Users** (admin) – add, reset password, change role, activate / deactivate.
* **Settings** – light/dark theme, backup, v3 import, change password.

`Alt+D/S/A/I/K/R/B/C/U/T` switch screens.

---

## Business rules (unchanged from v3)

| rule | detail |
|------|--------|
| Interest | 24 % p.a. as a daily rate (`0.24/365`), **compounded on 31 March** (financial year end). Implemented once, in `hth/domain/interest.py`, and pinned against the v3 code in `tests/test_interest.py`. |
| Entry type | `P` = debit (customer owes more), `M` = credit (customer paid / we owe). |
| Tags | `1` normal (earns interest), `2` no interest, `0` settlement marker. |
| Balance | Sum over entries **after the last tag-0 row** (ordered by date, then id): `P` adds, `M` subtracts, tag-1 amounts include interest to today. |
| Settlement | A sale/receipt with tag 0 writes three tag-0 rows: the entry, *Settled Amount* (balance before) and *Discount* (difference). The period restarts at zero. |
| Stock | `in stock = Σ received − Σ sold`, in the item's own unit. A sale/receipt against a stock item writes a movement and sets the item's *last price*. Quantities are fractional (v3 truncated to whole numbers). |
| Units | Mass: `G` `KG` `QTL` (1 QTL = 100 KG). Volume: `ML` `LTR`. Count: `PCS` `BAG` `BOX` `PKT` `BTL` (not convertible). `hth/domain/units.py`. |
| Days / score | *Days* = days since the newest non-settlement entry. *Score* = `0.6·norm(log amount) + 0.4·norm(log days)`. |
| Audit codes | `01` account added, `02` item added, `03` sale, `04` receive, `05` modify, `06` delete, plus new `07` krar, `08` login, `09` user/admin. |

One deliberate fix: v3 froze "today" at program start, so an app left running overnight
computed interest with yesterday's date. v4 always uses the current date.

---

## Reports

Built in (all exportable to Excel, all sortable by clicking a column):

| group     | report                        | parameters            |
|-----------|-------------------------------|-----------------------|
| Accounts  | Account summary               | –                     |
|           | Customer ledger               | customer              |
|           | Receivables aging             | –                     |
|           | Top debtors                   | how many              |
|           | Interest summary              | –                     |
|           | Customer activity             | date range            |
| Trends    | Monthly debits vs credits     | months                |
|           | Day book                      | date                  |
| Inventory | Stock on hand                 | –                     |
|           | Item movement                 | date range            |
|           | Low stock                     | threshold             |
|           | Expiring items                | days                  |
|           | Dead stock                    | days without a sale   |
| Krar      | Krar list                     | bucket                |
| Admin     | Audit log                     | date range, action, search |
|           | Data check                    | – (double-click a finding to open the record) |

Adding a report is one `ReportSpec` entry in `hth/ui/views/reports.py`; the query goes in
`hth/services/reports.py`.

### Suggested next reports and dashboard widgets

Ideas that fit the data you already have, roughly in order of value to the shop:

1. **Customer statement (PDF / print)** – ledger for a date range with the interest
   breakdown, to hand to the customer. The ledger rows already exist; add a print layout.
2. **Collections planner** – krar due this week merged with balance and phone number, sorted
   by amount; one-tap "call list".
3. **Interest earned per financial year** – how much of the receivable is interest vs
   principal, by year, for tax planning.
4. **Cash-flow forecast** – expected receipts from krar dates for the next 30/60/90 days.
5. **GST summary** – items carry a GST rate; group sales by rate for the monthly return
   (wire this up when the bills module returns).
6. **Item profitability** – `last price − stock value` × quantity sold, by item and month.
7. **Season comparison** – kharif vs rabi sales by item type (F/P/S/O), year on year.
8. **Customer risk flags on the dashboard** – balance growing three months in a row with no
   receipt; no activity for 180+ days with a balance.
9. **Expiry calendar** – items expiring in the next quarter as a month grid.
10. **Employee activity** – entries per user per day (from the audit log) for supervision.
11. **Reorder suggestions** – items whose 30-day sales exceed stock on hand.
12. **WhatsApp reminders** – template message for overdue krar (needs an outbound integration).

---

## Project layout

```
run.py                      launcher
tools/migrate_v3.py         v3 → v4 import (writes migration_report.txt)
tools/check_data.py         data-quality findings for the live database
hth/
  config.py                 data folder resolution, Settings
  logging_setup.py          rotating file log in <data>/logs
  db/connection.py          Database: one file, transaction-scoped, re-entrant connections
  db/schema.py              versioned migrations (PRAGMA user_version)
  domain/                   constants, interest formula, dataclasses (no I/O)
  services/                 business logic: accounts, inventory, sales, krar, reports,
                            audit, auth, permissions, export, integrity (data checks)
  migration/from_v3.py      legacy importer
  ui/                       customtkinter app: theme, widgets, views, app shell
  modules/                  optional feature modules (bills, crop trading) – see README there
tests/                      pytest suite (business rules, migration, opt-in UI walkthrough)
```

Layering rule: `ui` → `services` → `db`/`domain`. Views never write SQL; services never
import Tk.

## Development

```bash
pip install -r requirements-dev.txt
pytest                      # business-rule tests (fast, in-memory SQLite)
HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py   # drives the real window (needs a display)
ruff check hth tests tools  # lint
```

Packaging for the shop PC (single folder, no Python needed):

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name HighTableHoldings run.py
```

## Bills module

`hth/modules/bills/` — the first feature module, rebuilt from v3's `bills/` package.
Sidebar entry **Bills** (`Alt+B`); employees can create and print invoices, only admins run
the month batch or delete a month.

* **New invoice** – pick a customer (or type a name), add lines from stock or free text,
  see taxable / CGST / SGST / total live, *Save & create DOCX* (or *Save & make PDF* when
  Microsoft Word is available).
* **Browse** – bills by month, search by number or name, lines of the selected bill, open
  DOCX, make PDF, *PDF + merge range* (`from`–`to` numbers → one PDF), delete.
* **Month batch** (admin) – enter each item's total sold in the month with its sell-from
  date, choose the number of bills and the start number, and generate: the totals are split
  at random over the month's dates with random customer names (address *Dhansu*), exactly as
  v3 did, and every bill is rendered. Bills of ₹20,000 or more are created but flagged, not
  rendered.

Rules carried over from v3: CGST = SGST = 9 % for type **P**, 2.5 % for **F**, 0 for
**S/O**; tax rounded to 2 dp; total = taxable + CGST + SGST; amount in Hindi words; the v3
DOCX template is used unchanged (`hth/modules/bills/templates/invoice.docx`).

Files go to `<data>/bills/<number>.docx`, `<data>/pdfs/`, `<data>/merged_pdfs/`.
PDF needs `pip install docx2pdf` **and** Microsoft Word on the PC; DOCX works everywhere.

## Crop trading module

`hth/modules/crop_trading/` — sidebar entry **Crop Trade** (`Alt+C`), available to both roles;
deleting lots/sales needs admin.

How it fits the rest of the system:

* A **crop is an item of type `C`** (stock unit KG; enter QTL / G and it converts), so it
  appears in Items, stock reports and the Data check like any other item.
* **Farmers and buyers are customer accounts.** A purchase credits the farmer's ledger (we
  owe them, tag 2 by default); a sale debits the buyer (or is a cash sale with no ledger
  entry). *Pay farmer* / *Receive from buyer* are plain ledger entries, so balances, krar and
  every existing report work unchanged.
* **Every purchase is a lot** — date, farmer, gross quantity, deduction (*kaat*, v3's
  k-quantity), net, rate per unit, quality grade (A/B/C/MIX), notes.
* **Sales are costed FIFO against open lots**: cost, margin and margin % are stored on the
  sale, and each lot's remaining quantity goes down. The Sale form previews the FIFO cost and
  margin before you save. Selling more than is in stock is refused unless *Allow selling
  short* is ticked (the uncovered part is costed at the last purchase rate and flagged).
* **Stock & rates** — per crop: quantity, lots, cost value, average cost, latest market rate,
  market value, unrealized gain, and a 7-day straight-line estimate. Enter rates by hand or
  import a CSV (`crop,date,rate`).
* **Reports** — Summary (bought, sold, revenue, COGS, margin, stock at cost/market), Margin by
  crop, Margin by buyer, Purchases by farmer, Purchases by quality, Open lots (with age).
  Double-click opens the ledger / item. Everything exports to Excel.

### Rate feed and predictor (planned)

`hth/modules/crop_trading/rates.py` defines `RateProvider` — anything with
`fetch(crops, on_date) -> [RateQuote]`. `CsvRateProvider` is the first one; register an API
provider (Agmarknet / eNAM / a mandi site) in `PROVIDERS` and the *Fetch today's rates*
button appears. `estimate_rate()` is a deliberately naive linear trend over the last 30
quotes — the seam where a real predictor (seasonality, market data) plugs in later; the UI
already labels it "rough".
