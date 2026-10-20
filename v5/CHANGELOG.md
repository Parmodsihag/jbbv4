# Changelog

## 5.6.0 — 2026-10-20

### Faster - same books, same numbers
Measured on a copy-sized shop (663 accounts, 6,200 entries, 76 items): every interest and
balance figure is identical, checked bit for bit.
- **Start-up**: Excel (openpyxl), charts (matplotlib) and the Assistant's numpy now load the
  first time they are needed, not when the program opens - loading the program takes a
  quarter of the time it did.
- **Counter**: picking a customer and switching Sale / Purchase / Payment in / Payment out is
  two to three times faster. The two side columns keep their width, so a long name no longer
  re-lays-out the whole screen; the screen no longer pushes the status line off the bottom.
- **Coming back to a screen** reads nothing when nothing has been written since and it is the
  same day: Khata, Collections, Stock, Money, Today and the Counter only reload when something
  changed. After a change Today redraws only the cards whose figures moved.
- **Collections**: Late / Today / Next 7 days … switch instantly (the lists come from the last
  load instead of recomputing every balance).
- **Reports**: typing in the search box is about five times faster - the catalogue is built
  once and searching shows and hides its rows.
- **Balances and interest** for the whole shop are computed about twice as fast (dates are read
  once, the financial-year periods of each date once).
- **Database**: each part of the program keeps its connection open instead of opening one for
  every small question - opening one cost 300 times the question itself on Windows.
- **Today**: "default password still in use" no longer re-hashes admin/admin and emp1/emp1 on
  every visit (only after a password changes). **Settings** lists the microphones in the
  background instead of making the screen wait for the sound system.

## 5.5.0 — 2026-10-20

### A new layout - and the classic one is still there
- **New** (the default): six areas across the top - **Today · Counter · Khata · Stock · Money ·
  Reports** - with Settings behind the gear and an **Ask** box on every screen. **Classic** is the
  sidebar layout of v5.4, unchanged. **Settings → Appearance & language → Layout** switches the
  whole shop (admin), and back; the user menu (top right) has "Switch to the classic layout".
  A shop that chose Classic keeps it after updating.
- Every Alt-letter still works (Alt+S Counter, Alt+A Khata, Alt+K Collections, Alt+I Stock,
  Alt+C Crops & rates, Alt+F Money, Alt+B GST bills, Alt+R Reports, Alt+T Settings, Alt+U
  Users, Alt+H Ask). Admins start on Today, everyone else at the Counter.
- **Counter**: four tabs in shop words - Sale, Purchase, Payment in, Payment out (Alt+1-4) -
  instead of Debit / Credit; the small print under Save still says what is booked (P/M, tag).
  The customer's balance, promise, last payment and last entries beside the form; "+ New
  customer" without leaving the entry; **Paid now** inside a sale (cash / UPI / bank) saved
  together with it; Payment in can mark the open promise kept and settle the account;
  Ctrl+Shift+Enter never saves a sale.
- **Khata**: customer list and one page per customer (balance split into entered + interest,
  promise, Sale / Payment in / Promise / WhatsApp / Statement, entries by period, promises,
  crop trades, details); admin corrections on an entry's right-click. Deleting an entry says
  the new balance and that stock does not change. **Collections** replaces Karar: late / today /
  next 7 days / later / owe-but-no-promise, with the reminder (editable) and what happened.
- **Today**: what needs doing - promises due with WhatsApp / Got payment / New date, stock
  running out, housekeeping (Back up now, monthly expenses to post, data problems) - today's
  figures, who owes by age, latest entries.
- **Stock**: item list with Running low / Out / Expiring / Not selling and an item page (lasts
  about N days, movements); Crops & rates inside. **Money**: account tiles, due expenses, the
  cash book with + Expense / Income / Transfer, this month so far; GST bills and Reports &
  setup inside. **Reports**: one searchable catalogue of all 34 reports with pinned favourites.
  **Settings**: sections instead of one long scroll; Users is a section.

### Under the hood
- Business rules, numbers and the database are unchanged. One service method was added:
  `SalesService.record_sale_with_payment` (the sale's lines and the payment in one
  transaction, undone together).
- The new layout lives in `hth/ui/modern/`; modules name their place in it (`ModuleSpec.area`,
  `tab`, `reports`) and core still never imports them.

## 5.4.0 — 2026-10-21

### Updates from inside the app
- **Settings → Updates → Check for updates**: looks at the app's GitHub branch
  (github.com/Parmodsihag/jbbv4, branch `v5`, folder `v5` - changeable there), says which
  version is there and what is new (from the CHANGELOG), and **Install update** downloads it.
  Admins also get a message after signing in when a new version appears (checked once a day).
- Only the files that changed are downloaded, each checked against GitHub's own hash; a
  broken download changes nothing. New Python packages in `requirements.txt` are installed
  while downloading. The app itself changes only at the next start (**Restart now**): before
  it loads, every file about to be replaced is saved to `<data>/updates/before-….zip`, the new
  files go in, and if anything fails the old files are put back. **Undo last update** restores
  that backup the same way. The data folder is never touched (a new version's database
  changes are made by its migrations, which back the database up first). Every step is in
  the audit log (code 14) and `<data>/logs/updates.log`.
- A developer copy (a git checkout) is updated with `git pull --ff-only`, and only when it has
  no uncommitted changes. A packaged build cannot update itself.

### The voice model ships with the app
- `bundled/voice/vosk-model-small-hi-0.22.zip` (42 MB, Apache 2.0) is part of the app; it is
  unpacked into `<data>/voice` the first time the Assistant opens - nothing to download or
  install. An update that brings a different model zip installs it on the next start; a model
  installed by hand in Settings is kept.
- `vosk`, `sounddevice` and `pywin32` are now regular requirements; `setuptools` stays below 81
  (the DOCX bills need its `pkg_resources`).

## 5.3.1 — 2026-10-21

### Fixed
- Asking by voice always said "कुछ सुनाई नहीं दिया" on PCs where Windows' default recording
  device is **Stereo Mix** (it records what the speakers play, not the microphone). The
  assistant now picks the real microphone itself and never a loopback device; the choice can
  be changed in **Settings → Assistant → Microphone**, with **Test microphone** (records three
  seconds, shows how loud it was and what was heard).
- Speech is noticed by loudness as well as by words: a question in words outside the shop's
  vocabulary is heard again with the full dictionary instead of being dropped as silence.
- Clear messages: "no sound is coming from <microphone>" (wrong device or muted) versus "I
  heard a voice but could not make out the words". A microphone that refuses 16 kHz is
  recorded at its own rate.

## 5.3.0 — 2026-10-21

### Voice - ask by speaking, hear the answer
- **🎤 on the Assistant screen (or F2)**: speak the question - mostly Hinglish, *"Ramesh ka
  last month ka balance batao"* - the words appear in the box as they are heard and the
  question goes by itself 1.2 s after you stop (tap the text to correct it first). Answers to
  spoken questions are **spoken back in Hindi** with Windows' own Hindi voice (Hemant /
  Kalpana): amounts in whole rupees in Hindi words, dates as "दस अक्टूबर", the ask-back
  choices as "रमेश सैनी, भिवानी वाले या रमेश कुमार, रोहतक वाले" - answer "रोहतक वाले" by voice.
- **System 1 voice**: Vosk's small Hindi model (`vosk-model-small-hi-0.22`, 42 MB, offline, no
  AVX needed), limited to the shop's own words - the question words of the corpus, numbers,
  and the Hindi copies of every customer, village and item name. When that hearing does not
  make sense, the same audio is heard again with the model's full 179,000-word dictionary.
  Names the dictionary lacks get a *voice spelling* once (spoken by the Windows voice, heard
  by the model). Install it from **Settings → Assistant → Install voice model…** (the zip from
  alphacephei.com/vosk/models); needs `pip install vosk sounddevice pywin32`.
- Measured on 150 held-out spoken questions (Windows voices, made-up names): answered right
  **99.3 %** clean and **95.3 %** with shop-like noise (15 dB), ~0.1-0.2 s per question on a
  laptop; the open vocabulary alone gets 96.7 % / 84.0 % at ~1 s. Real recordings will be
  lower - `tools/assistant/eval_voice.py --recordings <folder>` measures them on the PC.
- **Spoken Hinglish understood**: a fourth corpus style (`sp`) - the Hinglish templates as a
  Hindi recogniser writes them ("लास्ट मंथ का बैलेंस", English words in Devanagari, numbers as
  words) - from a hand-made table of 300 words (`hth/assistant/spoken.py`). System 1 on unseen
  phrasings: 96.0 % overall (spoken 96.5 %, Hindi 99.2 %, Hinglish 95.9 %, English 94.5 %).
- Settings → Assistant → **Speak answers**: when I speak (default) / always / never.

### Fixed
- Periods in Devanagari loanwords were not read: "लास्ट मंथ", "इस मंथ", "इस वीक", "टुडे",
  "लास्ट ईयर" fell back to a default period. Number words now count in periods too:
  "पिछले तीस दिन", "pichle do din", "लास्ट थर्टी डेज़", "पंद्रह तारीख".
- "sabse bade bakayedar **bata do**" showed the top 2: "do" (tell me) was read as the number
  2. It is a number only before what it counts ("do bakayedar", "do hazaar").

## 5.2.0 — 2026-10-20

### Assistant (सहायक) - ask about the shop in plain words
- New screen **Assistant** (Alt+H, second in the sidebar): type a question in Hindi,
  Hinglish or English - *"Ramesh ka last month ka hisab btao"*, *"यूरिया कितना बचा है"*,
  *"whose promises are overdue?"* - and get the answer as a short card with a table and a
  button to open the matching screen or report. Answers come in the language of the
  question. Big text, tap-able choices, suggestion chips; read-only - it never changes data.
- **Asks back** when a question is unclear: three customers called Ramesh → *"कौन से
  रमेश?"* with the three (village / phone shown); reply with the number, *"rohtak wala"*,
  *"dusra"* or the last digits of the phone. A missing name is asked for. Once answered the
  question leaves the conversation; only a quick follow-up within two minutes reuses it
  (*"aur pichle mahine?"*, *"and Suresh?"*, *"uska phone number"*). *"chhodo"* cancels.
- 25 read-only answers: balance, ledger for a period, phone, interest, a customer's karar;
  overdue / today's / coming karar; biggest debtors, collection list, total receivable /
  payable; a day's or a period's sales, day book; stock, price and sales of an item; low
  stock, reorder, expiring; profit, expenses, cash and bank (finance module); what needs
  attention. Each checks the user's role (an employee is not shown profit).
- **System 1** (built in, no download): names are found in the question against the shop's
  own customers and items (English and Hindi spellings, typos, villages, phone digits) and
  replaced by placeholders; a NumPy classifier trained on a synthetic corpus of ~560
  question templates in three styles picks the intent in under a millisecond; periods
  (*pichle mahine*, *इस हफ्ते*, *15 tarikh*, *last 30 days*), numbers and categories are
  parsed by rules. Trained once on first use (seconds) and cached in `<data>/assistant/`.
  Held-out accuracy on phrasings it never saw: 95 % (Hindi 99 %, Hinglish 96 %,
  English 93 %); on the real shop data, full customer names are found 99.7 % of the time.
- **System 2** (optional): a small language model (FunctionGemma 270M or Qwen2.5 0.5B,
  LoRA fine-tuned) consulted only when System 1 is unsure. Train it with the single Kaggle
  cell `tools/assistant/kaggle_train_cell.py` (paste, run, download the zip) and install it
  in **Settings → Assistant → Install model…**; it needs `pip install llama-cpp-python`.
  It runs in its own process (a crash there - e.g. a Celeron without AVX - only switches it
  off), started on first use and stopped after 10 idle minutes, and its answer is taken only
  when it is one of System 1's three best guesses. First Kaggle run (FunctionGemma 270M,
  15 min on a T4): System 1 alone 95.3 % → with the model 96.9 % on unseen phrasings; Q4_K_M
  file 253 MB, ~0.7 s per question on Kaggle's CPU. Without it the assistant asks
  *"did you mean …"* instead.
- Every answer is logged in the audit log (code 13) with the tool and its arguments - the
  question text and names are not.
- `tools/assistant/eval.py` (intent accuracy, 3-fold) and `tools/assistant/eval_names.py`
  (name finding on a database, opened read-only, totals only).
- The core (`hth/assistant/core.py`, `Assistant.ask(text, session) → Reply`) has no Tk in
  it, so a WhatsApp / Telegram bot or a voice loop can use it later. The 🎤 button is a
  placeholder for voice input.

## 5.1.0 — 2026-10-20

### Hindi (हिन्दी)
- **Settings → Appearance → Language: English / हिन्दी**, switched live (every screen is
  rebuilt). Shop-wide and remembered; Windows uses the Nirmala UI font for Devanagari.
- The whole interface is translated from one English → Hindi phrase table
  (`hth/i18n/hi.py`, ~1,100 entries in shop vocabulary: नामे / जमा, शेष, लेनदारी / देनदारी,
  करार, ब्याज). A hook in customtkinter translates labels, buttons, tabs, dropdowns,
  placeholders and window titles; values the code compares stay English, so logic is
  unchanged. Composite texts (`12 entries · debit 1,200.00`) translate piece by piece;
  dates show Hindi month and day names.
- **Hindi copies of names**: every customer (name, details) and item gets a stored Hindi
  copy, made offline by `hth/i18n/translit.py` - a word list of North-Indian names,
  Haryana gotras, places, agri brands, crops and units, compound-name splitting
  (AMARSINGH → अमरसिंह) and phonetic rules for the rest. Correct any name in the edit
  dialogs or **Settings → Hindi names → Review / correct**; a corrected name is never
  regenerated. English stays the record of truth for ledgers, bills, search and exports
  of the data itself.
- In Hindi, tables, pickers, ledger headers, the account snapshot, statements, counter
  slips and Excel exports show the Hindi names; search boxes still match English typing.
  Reminders and WhatsApp balance messages have their own Hindi template.
- Charts keep Latin text: matplotlib cannot shape Devanagari (matras would be misplaced).
- Schema migration 6: `name_hi`, `details_hi`, `hi_manual` on customers, `name_hi`,
  `hi_manual` on items (backed up first, as every migration).

### Fixed
- The Sales screen added another Ctrl+Z binding on every sign-in; the old ones pointed at
  destroyed screens.
- Clearing a filter box when opening a report or ledger hid its placeholder text.

## 5.0.0 — 2026-10-19

Same business rules and numbers as v4: on a copy of the shop's database every customer
balance, day count, score and the interest summary are byte-for-byte identical to v4.

### Data and safety
- **Own data folder** `C:\JBB\v5`. On the first start v4's `hth.db` is copied in through
  SQLite's backup API from a read-only connection — v4's files are never written — and a
  one-time notice says where the data came from.
- **Restore a backup** (Settings → Data, admin): checks the file (integrity, that it is an
  HTH database, not from a newer version), saves the current data as
  `hth_before_restore_<time>.db`, restores, migrates, signs everyone out.
- **Atomic schema migrations**: each runs in one transaction with its version bump (before,
  `executescript` committed statement by statement, so a failure left a half-migrated
  database), and an existing database is backed up first (`hth_pre_migration_v<N>_*.db`).
- **Screen lock**: `Ctrl+L`, a sidebar button, or after N idle minutes (Settings); work in
  progress stays behind the lock. Navigation and shortcuts are disabled while locked.
- **Login lockout**: after 5 wrong passwords a username waits 30 s, doubling each further
  failure; failed sign-ins are written to the audit log.

### Faster
- Customer balances for everyone are computed from **one** ordered query instead of two per
  customer: dashboard / Accounts list / account summary / re-score 4.8 s → 0.1 s, interest
  summary 3.0 s → 0.11 s on the shop's 663 accounts. Karar fetches its balances in one call.

### Sales screen
- **Several items, one account**: *+ Add line* (Enter in the price box) collects lines and
  Debit / Credit posts them together, atomically (`SalesService.record_lines`).
- **Undo last entry** (`Ctrl+Z`, 15 minutes): removes the ledger rows (all three for a
  settlement), stock movement, cash-book entry or crop lot / sale, and restores the item's
  last price (`SalesService.undo`).
- **Account snapshot** beside the form: balance, open promise, last payment, newest entries.
- **Print slip**: an 80 mm receipt for the entry just posted.
- **Quick CASH / UPI / BANK** money entries; Date and Tag share a row; Enter moves quantity →
  price → add line; `Alt+Up/Down` steps the date.

### Dashboard
- Clickable tiles in lakh / crore with the exact amount beneath; **Today** shows the day's
  debit and credit amounts (a settlement counts once) instead of audit-entry counts.
- **Needs attention** panel: overdue promises and the money at stake, promises due today,
  debtors silent 180+ days, items that will run out within a month, expired / expiring
  stock, data errors, future-dated entries, missing or stale backup, default passwords.
- Charts read in L / Cr instead of matplotlib's `1e6`; month labels `Nov 25`; aging as bars
  with customer counts; the legend no longer covers the bars.

### New reports
Collections list · Interest by financial year · Promised receipts forecast · Item profit ·
Reorder suggestions · GST summary (invoices) · Staff activity. Every report has a row filter.

### Everywhere
- **Text size** 90 / 100 / 115 / 130 % (Settings → Appearance): every widget, table font,
  row height and column width grows together.
- **Indian digit grouping** (12,34,567.00) by default, switchable to international; used by
  screens, statements, reminders, search results and chart axes.
- New shell: icon sidebar with shortcut hints, collapsible to icons; screen subtitles; the
  header date rolls over at midnight; last-backup time in the status bar; theme remembered.
- Ledger: *All / Current period / This FY / Last 90 days*, find box, *New entry ▸*,
  *WhatsApp balance*, *Promise…* (record or move the krar date).
- Lists: Items filter by *In stock / Out-negative / Expiring* and category; Accounts by
  *Owe us / We owe / Settled*. Dashboard *Today* opens the day book.
- `Start High Table Holdings v5.bat` starts the app without a console window.
- Tables: Enter opens a row, `Ctrl+C` copies it, right-click copies all rows for Excel /
  WhatsApp. Search boxes and `Ctrl+K` match every word in any order.
- `F1` lists every keyboard shortcut.

### Fixed
- Dashboard, Crop Trade and Finance chart cards never repainted after the window resized:
  `ChartCard` kept its matplotlib canvas in `self._canvas`, the attribute customtkinter uses
  for the frame's own background, and the resulting `AttributeError` was silently swallowed.
- Dashboard KPI tiles were ~300 px tall with their values cut off (a `CTkFrame` accent bar
  defaulted to 200 px high).
- Sales, Karar and other date fields kept **yesterday's date** when the app stayed open
  overnight; report date defaults were frozen when the program started.
- Editing or deleting a ledger receipt / payment that the Sales screen had booked into the
  cash book left the cash-book entry unchanged, so cash balances drifted. They now follow.
- Ledger rows created by a crop lot / sale could be edited or deleted from the ledger,
  leaving stock and FIFO costs inconsistent; now refused with a pointer to Crop Trade.
- Deleting a farmer or crop item that has lots failed with a raw `FOREIGN KEY constraint
  failed`; now a clear message.
- Admins could not edit negative settlement rows (*Settled Amount* / *Discount*).
- Changing your password wrote a spurious "login" entry to the audit log.
- Karar reminders said "please pay Rs -1,000" for accounts in credit; those now get a
  balance message and are left out of *Copy all shown*.
- Karar's toolbar overlapped its Overdue / Today switch at normal window sizes, and it
  opened on an empty *Today* tab while promises were overdue.
- Crop Trade's Sales table was squeezed to its header row.
- Opening Reports on a given report (e.g. from a dashboard link) skipped the report's
  permission check, so an employee could reach admin-only reports such as Data check.
- A failed first-start copy of v4's data now stops with a clear message and leaves nothing
  behind, so the next start tries again.
- Sales screen panels (crop fields, money account) could end up in the wrong state when
  toggled quickly (`winfo_ismapped` is only true after Tk's idle pass).

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
