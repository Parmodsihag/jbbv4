# Screencast script (2–3 minutes)

Guideline §7: show the **entire process of compiling and deploying** the application and
**explain the important features**, with voice-over. Record at 1920×1080, 30 fps; use OBS
or the Windows screen recorder (Win+Alt+R); keep the terminal font large. Target length:
**2:50**.

Prepare beforehand: a fresh clone in an empty folder; a **demo data folder** (set
`HTH_DATA_DIR` to an empty folder and enter a dozen made-up customers, items, sales and
promises, two of them named Ramesh in different villages) so no real customer appears; a headset microphone for the voice question; Windows' Hindi
voice installed; the browser closed. Never record the shop's real data.

| Time | On screen | Voice-over |
|------|-----------|------------|
| 0:00–0:12 | Title slide: project name, course, Team No., four names, Git URL. | "This is High Table Holdings, our Software Engineering and Management project: the shop computer of an agri-input shop that sells on credit with interest, buys crops back from farmers and issues GST bills." |
| 0:12–0:40 | Terminal: `git clone https://github.com/Parmodsihag/jbbv4.git`, `cd jbbv4\v5`, `python -m venv .venv`, activate, `pip install -r requirements.txt` (speed up 4×), `pytest -rs` ending in *282 passed, 34 skipped*. | "Building it is a clone, a virtual environment and one install. Before running it, three hundred automated tests check the business rules: interest, balances, settlement, stock, FIFO costing, the migrations, the assistant and the updater. The skipped ones drive the real window; we run them separately before each release." |
| 0:40–0:52 | `pyinstaller … run.py` (cut to result); then show the shop-PC launcher `Start High Table Holdings v5.bat` starting the app. | "For a PC without Python we package a single folder with PyInstaller. On the shop PC a launcher starts it with no console, and from then on it updates itself from this repository." |
| 0:52–1:05 | Sign in as admin → **Today**: promises due, stock running out, housekeeping, owed-to-us by age. | "The owner starts on Today: every promise that is late or due, stock that will run out at the current selling rate, a missing backup, the money owed by age." |
| 1:05–1:30 | **Counter** › Sale: pick a customer (snapshot appears), three lines incl. 500 G of a KG item, *Paid now* 2000 cash, Ctrl+Enter, slip. Then Ctrl+Z. | "The Counter speaks shop language: Sale, Purchase, Payment in, Payment out. Several items, part paid in cash, the rest on the khata — saved as one transaction across ledger, stock and cash book, or not at all. Loose quantities are converted to the stock unit. A mistake can be undone for fifteen minutes." |
| 1:30–1:45 | **Khata**: the customer's page, *Owes us* split into entered + interest; Statement opens in the browser. **Collections** › Late › WhatsApp. | "Interest is 24 percent a year, compounded every 31 March, exactly as the old program — and that is pinned by tests against its code. Late promises come with a ready WhatsApp reminder." |
| 1:45–2:05 | Ask box: type *sabse bade 5 bakayedar* → Hindi answer. Press F2, say *Ramesh ka balance batao* → "कौन से रमेश?" → say *rohtak wala* → answer spoken. | "Ask the shop a question in Hindi, Hinglish or English, typed or spoken. It runs offline on the shop's Celeron, asks back when a name is ambiguous, and only ever reads — it cannot change the books." |
| 2:05–2:18 | Settings › Appearance & language: switch to हिन्दी (Counter in Hindi), back to English; Colours: Forest dark, High contrast. | "One switch puts the whole program in Hindi, names included, without changing the records. Seven colour themes, each checked for readable contrast." |
| 2:18–2:32 | Settings › Updates › Check for updates; Backup & data; Reports catalogue (search "gst", pin). | "Updates install from GitHub with every file hash-checked and can be undone. Backups are daily, restores are checked, and thirty-four reports export to Excel." |
| 2:32–2:45 | Architecture slide (layers, modules, assistant) + `v5/docs/` folder listing. | "Under the hood: strict layers from screens to services to the database, feature modules that plug in, versioned atomic migrations, and decision records, a test plan and a test report in the repository." |
| 2:45–2:50 | Closing slide with the Git URL. | "Code, documentation and tests are in the public repository. Thank you." |

Tips: keep the cursor still while talking; cut dead time; for the voice part keep the room
quiet; export MP4 (H.264) under 200 MB so it fits in `TeamNo.zip`.
