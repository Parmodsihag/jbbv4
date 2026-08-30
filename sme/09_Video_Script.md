# Screencast script (2–3 minutes)

Guideline §7: show the **entire process of compiling and deploying** the application and
**explain the important features**, with voice-over. Record at 1920×1080, 30 fps; use OBS
or the OS screen recorder; keep the terminal font large. Target length: **2:45**.

Prepare beforehand: a fresh clone in an empty folder, a v3 sample data folder, the app
already run once elsewhere so you know the wizard fields, and the browser closed.

| Time | On screen | Voice-over |
|------|-----------|------------|
| 0:00–0:15 | Title slide: project name, course, Team No., four names. | "This is High Table Holdings version 4, our Software Engineering and Management project — an accounting and inventory system for an agri-input shop, built as a tested, layered re-engineering of a legacy tool." |
| 0:15–0:45 | Terminal: `git clone https://github.com/Parmodsihag/jbbv4.git`, `cd jbbv4/HighTableHoldings-v4`, `python -m venv .venv`, activate, `pip install -r requirements.txt` (speed up 4×), `pytest -q` showing *94 passed*. | "Compiling and deploying is three commands: clone the public repo, create a virtual environment and install five dependencies — customtkinter, matplotlib, openpyxl, docxtpl and pypdf. Before we run it, the test suite confirms the business rules: interest, balances, settlement, stock, FIFO costing and the v3 migration all pass." |
| 0:45–1:00 | `pyinstaller --noconfirm --windowed --name HighTableHoldings run.py` (cut to result), then open the `dist/HighTableHoldings` folder and double-click the exe. | "For the shop PC we package a single folder with PyInstaller — no Python installation needed. Launching it…" |
| 1:00–1:20 | First-run wizard: shop details, new admin/employee passwords, select v3 folder, Import. Show `migration_report.txt` briefly. | "The first-run wizard collects shop details, refuses the default passwords, and imports the legacy data — preserving every id and reporting every value it had to normalise, so nothing is guessed silently." |
| 1:20–1:35 | Login as `emp1`. Dashboard: KPI tiles, activity, aging, top debtors. | "Two roles: employee and administrator. The dashboard shows receivables, payables, stock value, cash and bank, and open promises." |
| 1:35–2:05 | Sales screen: pick a customer, type an item (price auto-fills), enter 250 G of a KG item, Ctrl+Enter. Show today's list, then open the customer's ledger (running balance, interest column). Then a crop item: credit a lot with deduction, debit a sale — margin preview. | "One Sales form records everything: a loose sale in grams is converted to the stock unit; ledger, stock, cash book and audit log are updated in a single transaction. Interest runs at 24 percent a year and compounds on 31 March — exactly as the shop's paper ledger. For crops, a purchase becomes a lot and a sale is costed FIFO with the margin shown before saving." |
| 2:05–2:25 | Karar screen: Overdue / Today / Upcoming, click *WhatsApp*. Then Reports → Receivables aging → sort → Export to Excel; Reports → Statement → HTML opens. | "Promises to pay are tracked and reminders go out on WhatsApp. Fifteen reports export to Excel, and a print-ready customer statement is one click away." |
| 2:25–2:40 | Log in as `admin`: Users screen, Audit log, Settings → Backup now, Bills → new invoice DOCX. | "Administrators manage users, see who did what in the audit log, take backups — one is also taken automatically every day — and issue GST invoices." |
| 2:40–2:50 | Architecture slide (Chapter 2 diagram) + repo tree. | "Under the hood: a strict `ui → services → domain/db` layering, declarative permissions and reports, versioned migrations, and optional feature modules — bills, crop trading and finance — that plug into the core." |
| 2:50–2:55 | Closing slide with Git URL. | "Code, documentation and tests are in the public repository. Thank you." |

Tips: keep the cursor still while talking; cut dead time; export as MP4 (H.264), under
200 MB so it fits in `TeamNo.zip`.
