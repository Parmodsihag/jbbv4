# High Table Holdings v5

Accounting and inventory management for **Jaat Beaj Bhander** — customer ledgers with
interest, stock, *krar* (promised payments), reports and dashboards.

v4 was a ground-up rewrite of v3.7.1 (**same business rules, same numbers**). v5 builds on
v4 with the same rules and numbers again — every balance and interest figure is
byte-for-byte identical to v4 on the shop's data — and makes it faster (the dashboard and
account list load ~40× faster), safer (screen lock, login lockout, backup restore, atomic
migrations, undo) and more useful at the counter (multi-item entries, account snapshot,
printable slip, Indian number format, seven new reports, a *Needs attention* panel).
See [CHANGELOG.md](CHANGELOG.md) for the full list.

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python run.py
```

Requirements: Python 3.10+, Windows/macOS/Linux. On the shop PC, double-click
`Start High Table Holdings v5.bat` (no console window).

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
| Windows  | `C:\JBB\v5`                                          |
| macOS    | `~/Library/Application Support/HighTableHoldings`   |
| Linux    | `~/.local/share/HighTableHoldings`                  |

Set the environment variable `HTH_DATA_DIR` to use a different folder (e.g. a synced drive).
**Settings → Backup now** writes a consistent copy to `backups/`; **Restore a backup…**
brings one back (the current data is saved first as `hth_before_restore_<time>.db`).

### Moving from v4

v5 keeps its own folder so v4's data is never changed. On the **first start** in the default
Windows folder, v5 copies `C:\JBB\v4\hth.db` into `C:\JBB\v5` (opened read-only, copied
with SQLite's backup API, so it is consistent even if v4 is open) and says so once after
sign-in. From then on the two are separate: entries made in v5 are not seen by v4. To copy
again, close v5, delete or rename `C:\JBB\v5\hth.db`, and start v5. With `HTH_DATA_DIR`
set nothing is copied. Before any schema upgrade of an existing database v5 also writes
`backups/hth_pre_migration_v<N>_<time>.db`.

---

## Roles and permissions

| capability                                   | admin | employee |
|----------------------------------------------|:-----:|:--------:|
| Dashboard                                    |  ✓    |   ✓      |
| Record sales / receipts                      |  ✓    |   ✓      |
| Undo your own last entry (15 minutes)        |  ✓    |   ✓      |
| Add accounts and items                       |  ✓    |   ✓      |
| Add / settle krar                            |  ✓    |   ✓      |
| Reports and Excel export                     |  ✓    |   ✓      |
| Edit ledger entries, stock movements, items, customers |  ✓ |  –   |
| Delete anything                              |  ✓    |   –      |
| Audit log                                    |  ✓    |   –      |
| Manage users                                 |  ✓    |   –      |
| Backup, restore a backup, import v3 data     |  ✓    |   –      |
| Shop-wide settings (number style, auto-lock) |  ✓    |   –      |

The matrix is one table in `hth/services/permissions.py`; every screen and destructive
button checks it, and every write records the acting user in the audit log.

---

## Screens

* **Dashboard** – clickable tiles (receivable, payable, today's debits / credits, overdue
  krar, stock value, cash & bank, accounts) in lakh / crore with the exact figure beneath;
  debits vs credits per month, receivables by age, top 10 debtors, entries per day; the
  krar list; and **Needs attention**: overdue promises with the amount at stake, debtors
  silent for 180+ days, items that will run out within a month at the current selling rate,
  stock that is expired or expiring, data errors, future-dated entries, a stale or missing
  backup, and default passwords still in use. Click a finding to go and fix it.
* **Sales** – sale or receive against an account; item search auto-fills the last price;
  live amount preview; today's entries on the right. `Ctrl+Enter` = sale,
  `Ctrl+Shift+Enter` = receive. The buttons read **Debit · sale / pay out** and
  **Credit · receive / purchase** because each has two everyday meanings in a ledger: a debit
  is a sale *or* cash paid out to an account in credit; a credit is a payment received *or*
  goods bought from that account (a farmer). **Crops:** pick a crop item and the form grows
  crop fields — Credit records a purchase lot (gross, deduction/kaat, quality), Debit a
  FIFO-costed sale with the margin previewed before you save.
  **Loose sales:** quantities are fractional and can be
  entered in any unit compatible with the item's stock unit — 100 G of a KG item, 2.5 QTL of
  a crop kept in KG, 500 ML of a LTR bottle. Price is always per stock unit. Set seed / crop
  / liquid items to `KG` / `LTR` when you add them so they can be split.
  **Several items, one account:** *+ Add line* (or Enter in the price box) collects lines;
  Debit / Credit then posts them all — the line still in the form included — as one unit:
  if any line is wrong nothing is written. **Undo last entry** (`Ctrl+Z`, 15 minutes)
  reverses everything the entry wrote: ledger rows (all three for a settlement), stock
  movement, cash-book entry or crop lot / sale, and the item's last price.
  **Print slip** opens an 80 mm receipt of that entry. **Quick CASH / UPI / BANK** fills a
  money entry and puts the cursor on the amount. The right side shows the picked account:
  balance, open promise, last payment and newest entries, with *Open ledger*.
* **Bills** – GST tax invoices (see *Bills module* below).
* **Accounts** – create customers; searchable list with balance, days since activity and
  score; double-click for the full ledger (interest, debit, credit, running balance).
  Admins add / edit / delete entries from the ledger. The ledger shows *All*, the *Current
  period* (since the last settlement), *This FY* or *Last 90 days*, has a find box, *New
  entry ▸* (opens Sales for the account) and *WhatsApp balance* (a balance message — also
  for accounts in credit or settled). Editing a receipt that went into the cash book updates
  that cash-book line; deleting it removes it. Ledger rows that belong to a crop lot or sale
  are changed from Crop Trade, so stock and FIFO costs stay right.
  **Statement** (ledger header) writes a print-ready HTML statement for a date range —
  opening balance, every entry with its interest, totals, closing balance, shop header and
  signature lines — and opens it in the browser (print or *Save as PDF*). Shop name, address,
  phone, GSTIN and footer note come from Settings → *Shop details*.
* **Items** – create items with opening stock; searchable stock list; double-click for the
  movement history. Admins edit items and movements. **Changing an item's unit converts its
  whole history**: same-family changes (KG ↔ QTL ↔ G, LTR ↔ ML) convert automatically;
  unrelated units (PKT → KG) ask "how many KG is 1 PKT?" — or leave it blank to relabel
  only. Quantities are multiplied, per-unit prices divided, money amounts untouched, across
  stock movements, crop lots/sales and market rates.
* **Karar** – add or reschedule a promise date, settle it; Overdue / Today / Upcoming tabs
  (opens on Overdue when anything is overdue), find box.
  **Reminders**: *Copy reminder* puts a ready message (name, amount, promised date) on the
  clipboard; *WhatsApp* opens a chat when the account details contain a 10-digit mobile
  number; *Copy all shown* copies one message per row. Template in Settings. Accounts that
  owe nothing get a balance message instead and are left out of *Copy all shown*.
* **Reports** – see below. Double-click a row to jump to the ledger or item.
* **Users** (admin) – add, reset password, change role, activate / deactivate.
* **Settings** – theme (light / dark / system, remembered), **number style** (Indian
  12,34,567.00 or international 1,234,567.00, used everywhere including statements and
  reminders), **text size** (90–130 %), **auto-lock** after N idle minutes, backup (plus **automatic daily backup** on
  the first start each day, keeping the last N), **restore a backup**, v3 import, shop
  details, reminder template, categories, run the setup wizard again, change password.
* **Lock** – `Ctrl+L`, the sidebar *Lock* button or the idle timer hides the work behind a
  password prompt; whatever was half-typed is still there after unlocking. *Sign in as
  someone else* signs out. After five wrong passwords a username waits 30 s (doubling).
* **Sidebar** – icons, shortcut hints, and ☰ to collapse it to icons on small screens
  (remembered). The header shows today's date (it rolls over at midnight, and so do date
  fields still showing the old day) and the status bar the time of the last backup.
* **First run** – a wizard asks for shop details, new admin / employee passwords and an
  optional v3 folder; *Skip* to do it later.
* **Search** – `Ctrl+K` (or the header button) finds accounts, items and bills; Enter jumps
  to the ledger, item history or bill. Every search box matches all the words you type in
  any order (`ram rohtak`), exact id and name-starts-with first.
* **Tables** – click a title to sort; Enter or double-click opens the row; `Ctrl+C` copies
  the row and right-click copies all rows (tab-separated: paste into Excel or WhatsApp).

`Alt+D/S/A/I/K/R/B/C/U/T` switch screens; **`F1` lists every shortcut.**

---

## Hindi (हिन्दी)

**Settings → Appearance → Language** switches the whole program between English and
Hindi at once. It is shop-wide and remembered.

* **Interface** - every label, button, tab, menu, message, report title and column comes
  from one phrase table, `hth/i18n/hi.py` (English key → Hindi). Phrases with numbers use
  `{}` holes: `"{} entries": "{} एंट्री"`. To change a word, edit that file - nothing else
  in the code needs touching. `HTH_I18N_MISSES=<file>` records any text shown in Hindi mode
  that has no entry yet.
* **Names** - each customer and item keeps a Hindi copy of its name (and the customer's
  details) next to the English one, generated offline from the English spelling
  (`hth/i18n/translit.py` with the word list in `hindi_words.py`). Correct a name in
  *Edit customer* / *Edit item* or in **Settings → Hindi names → Review / correct names…**;
  corrected names are marked ✓ and never regenerated. *Fill missing* and *Regenerate
  automatic ones* redo the automatic copies.
* English stays the original: ledger entries, bills, v3 import and the database itself
  keep English, so switching back loses nothing. Search boxes match English and Hindi.
* Statements, counter slips and Excel exports come out in Hindi with Hindi names;
  reminders use a separate Hindi template (Settings → Payment reminders, while in Hindi).
* Chart text stays Latin - matplotlib cannot draw Devanagari correctly.

## Assistant (सहायक)

**Alt+H** opens a chat where you ask about the shop the way you would ask a person - in
Hindi, Hinglish or English - and the answer comes back in the same language:

| ask | get |
|---|---|
| *Ramesh ka last month ka hisab btao* | "कौन से रमेश?" with every Ramesh (village / phone), then that ledger for September |
| *यूरिया कितना बचा है* / *dap ka bhav* | stock / selling price of the item |
| *kiske karar ki tarikh nikal gayi* | overdue promises with balances |
| *pichle mahine kitni bikri hui*, then *aur is mahine?* | sales of each period |
| *sabse bade 10 bakayedar*, *collection list*, *kya mangwana hai* | the lists, with a button to the full report |

It only **looks things up** - nothing is ever changed. Unclear questions are asked back
(reply with the number, *rohtak wala*, *dusra*, or phone digits; *chhodo* cancels); an
answered question is forgotten, except that a follow-up within two minutes (*aur …*,
*uska …*) reuses it. Answers respect the user's role.

How it works (details in `docs/AI_CHAT_DESIGN.md`):

* **System 1** (always on, nothing to install): names are matched against the shop's own
  customers and items and replaced by `<C1>` / `<I1>`; a small NumPy classifier trained on
  generated questions picks what is being asked; rules read periods, days and numbers.
  It trains itself the first time the screen opens (seconds; cached in `<data>/assistant/`).
* **System 2** (optional): a fine-tuned small language model for questions System 1 is not
  sure about. Train it free on Kaggle: open a GPU notebook with Internet on, paste
  `tools/assistant/kaggle_train_cell.py` into one cell, run it (~40 min), download
  `hth_assistant_model.zip`, then **Settings → Assistant → Install model…**. Running it needs
  `pip install llama-cpp-python` on the shop PC. No shop data is used for training. The cell
  ends with a verdict: it compares System 1 alone with System 1 + the model and says whether
  the model is worth installing. In the app the model runs in its own process (if this PC
  cannot run it, only the model switches off) and is trusted only when it agrees with one of
  System 1's three best guesses.
* **Voice** (optional, details in `docs/VOICE_DESIGN.md`): press **🎤** or **F2** and speak -
  Hinglish, Hindi or English. The words appear in the box as they are heard; the question goes
  1.2 s after you stop (tap the text to correct it). The answer is spoken back in Hindi.
  Setup on the shop PC:
  1. `pip install -U pip setuptools` then `pip install vosk sounddevice pywin32`;
  2. download `vosk-model-small-hi-0.22.zip` (42 MB) from alphacephei.com/vosk/models and
     install it with **Settings → Assistant → Install voice model…**;
  3. for spoken answers, Windows needs its Hindi voice: Settings → Time & language → Speech →
     Add voices → Hindi (often already there). **Speak answers**: when I speak / always / never.

  The recogniser is limited to the shop's words (questions, numbers, the Hindi copies of
  names and villages) - fast and accurate on a Celeron; when that hearing makes no sense the
  full dictionary is tried. A USB or headset microphone helps more than anything else.
* Check quality with `python tools/assistant/eval.py` (questions it never saw),
  `python tools/assistant/eval_names.py` (finds your real customers; read-only, prints only
  totals) and `python tools/assistant/eval_voice.py` (spoken questions; `--recordings <folder>`
  for real recordings, which stay on the PC). After changing `hth/assistant/data.py` or
  `spoken.py`, run `python tools/assistant/build_kaggle_cell.py`.

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

## Finance module

`hth/modules/finance/` — sidebar **Finance** (`Alt+F`). Employees see the cash book and can
add entries; administrators also get *Reports* and *Setup*.

* **Money accounts** — as many as you keep: cash box, bank accounts, UPI. Each has an
  opening balance; balances are always derived from entries. One account is the *default
  for Sales*.
* **Cash book** — per account, per period, with a running balance; balance tiles for every
  account plus the total. Add **expense** (to a head), **other income**, **transfer**
  between accounts, **capital in** and **drawings**.
* **Customer receipts and payments come from the Sales screen**: when the entry moves money
  rather than stock (item `CASH`, or any typed text), a *Money account* picker appears,
  defaulting to the default account; the receipt (Credit) or payment (Debit) is written to
  that account's cash book, linked to the ledger entry. Stock entries never touch the cash
  book.
* **Expense heads** (rent, salaries, electricity, transport, EMI, interest paid, repairs,
  office, bank charges, taxes, other; income: commission, interest received, other) — add,
  rename, deactivate.
* **Recurring expenses** — head, account, amount, day of month; *Post due now* creates the
  entries for every month not yet posted (idempotent).
* **Reports** — Cash flow (money in by source, money out by kind and head, net, and each
  account's opening → in → out → closing), **Profit & loss** (item sales margin at current
  item cost + crop FIFO margin + other income − expenses; interest on customer balances is
  *not* included since it is accrued, not received), Expenses by head, Monthly expenses,
  Account balances. All exportable.
* Dashboard gains a **Cash & bank** tile.

From this version every stock movement made from the Sales screen also records its value
(`item_transactions.value`), which is what the P&L uses; movements imported from v3 have no
value and are excluded from item revenue.

## Categories (A–E)

Every customer and item carries a stored category. **A** best … **D** worst; **E** is the
defaulter (customers) / discontinued (items) category, **assigned by hand only** — re-scoring
never gives or removes it.

* **Settings → Categories** chooses which categories feed the dashboard and reports
  (default A–D, so multi-year defaulters stop distorting receivables, aging and top-debtor
  lists). Every customer/item report has a *Scope* switch: *Per settings* or *All categories*.
* **Re-score customers now** maps the v3 account score (0 = small & recent … 1 = large & long
  outstanding) to A–D by three thresholds; nothing outstanding = A. Customers whose category
  was set by hand are **locked** and skipped (the ledger shows a 🔒). *Keep E out of the score
  maths* (on by default) removes defaulters from the score's min/max normalisation so they do
  not push everyone else's score down; they get no score.
* **Auto-categorise items** uses days since the last sale (A ≤ 30, B ≤ 90, C ≤ 180, else D —
  configurable). Manual item categories lock the same way.
* Set a category from the ledger / item history header (*Category* button); the Accounts and
  Items lists show a *Cat* column and a category filter.

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
|           | **Collections list** (v5)     | – everyone who owes, biggest first, with phone, last payment, promise and status: the call list |
|           | **Interest by financial year** (v5) | – open balances split into principal entered and interest accrued per FY |
| Trends    | Monthly debits vs credits     | months                |
|           | Day book                      | date                  |
|           | **Promised receipts forecast** (v5) | next N days – open krar by week, overdue first, with a running total |
| Inventory | Stock on hand                 | –                     |
|           | Item movement                 | date range            |
|           | Low stock                     | threshold             |
|           | Expiring items                | days                  |
|           | Dead stock                    | days without a sale   |
|           | **Item profit** (v5)          | date range – sales value, cost at today's cost, margin and margin % per item (same rule as Finance → P&L) |
|           | **Reorder suggestions** (v5)  | sales window – items whose recent sales use up the stock, with days left |
| Krar      | Krar list                     | bucket                |
| Tax       | **GST summary** (v5)          | date range – invoice lines by month and GST rate: taxable, CGST, SGST, total |
| Admin     | **Staff activity** (v5)       | date range – per user: days active, sales, receipts, edits, deletes, last seen |
|           | Audit log                     | date range, action, search |
|           | Data check                    | – (double-click a finding to open the record) |

Every report has a **Filter rows** box (any words), and date defaults are worked out when
the report is opened, so they are right after midnight too.

Adding a report is one `ReportSpec` entry in `hth/ui/views/reports.py`; the query goes in
`hth/services/reports.py`.

### Suggested next reports and dashboard widgets

Done in v4.6–v5: customer statement, collections list, interest by FY, receipts forecast,
GST summary, item profit, risk flags (*Needs attention*), staff activity, reorder
suggestions, WhatsApp reminders. Still open, roughly in order of value:

1. **Season comparison** – kharif vs rabi sales by item type (F/P/S/O), year on year.
2. **Expiry calendar** – items expiring in the next quarter as a month grid.
3. **Balance trend flags** – balance growing three months in a row with no receipt.
4. **Customer phone field** – today the mobile number is read out of *Other details*.

---

## Project layout

```
run.py                      launcher
tools/migrate_v3.py         v3 → v4 import (writes migration_report.txt)
tools/check_data.py         data-quality findings for the live database
tools/assistant/            eval.py, eval_names.py, eval_voice.py, the Kaggle cell and its builder
hth/
  config.py                 data folder resolution, Settings
  logging_setup.py          rotating file log in <data>/logs
  db/connection.py          Database: one file, transaction-scoped, re-entrant connections
  db/schema.py              versioned migrations (PRAGMA user_version)
  i18n/                     English -> Hindi: tr(), widget hook, phrase table (hi.py),
                            transliteration of names (translit.py, hindi_words.py)
  domain/                   constants, interest formula, numbers (Indian grouping),
                            units, dataclasses (no I/O)
  services/                 business logic: accounts, inventory, sales, krar, reports,
                            audit, auth, permissions, export, integrity (data checks),
                            insights (Needs attention), preferences, backup/restore,
                            slips (counter receipts), statements, reminders, search
  assistant/                chat assistant: normalize (language, periods), entities (names,
                            ask-back), voice (Vosk, microphone), speech (spoken answers),
                            spoken (Hinglish as heard),
                            ask-back), system1 (classifier), system2 (optional GGUF model),
                            tools (read-only answers), core (dialog), data (training corpus)
  migration/from_v3.py      legacy importer
  ui/                       customtkinter app: theme, icons, widgets, views, app shell
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
ruff format hth tests tools # formatting
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
deleting lots/sales needs admin. **Trades are entered on the Sales screen** (pick a crop
item); Crop Trade is where you review lots and sales, value stock, keep market rates and run
the reports.

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
  sale, and each lot's remaining quantity goes down. The Sales screen previews the FIFO cost
  and margin before you save. Selling more than is in stock is refused unless *Allow selling
  short* is ticked (the uncovered part is costed at the last purchase rate and flagged).
  Crop trades cannot carry tag 0 — settle a farmer or buyer with a separate CASH entry.
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
