# Administration and operations guide

For whoever installs, looks after and repairs High Table Holdings on the shop PC: the shop
owner (the program's **admin**) and the developer. Everyday screens are in the
[user guide](USER_GUIDE.md); how the program is built is in [ARCHITECTURE.md](ARCHITECTURE.md).

Version described: **5.7.0**.

**Contents:** [1 Install](#1-install) · [2 First start](#2-first-start) ·
[3 The data folder](#3-the-data-folder) · [4 Backups and restore](#4-backups-and-restore) ·
[5 Updates](#5-updates) · [6 Users and security](#6-users-and-security) ·
[7 Troubleshooting](#7-troubleshooting) · [8 Routine checklist](#8-routine-checklist) ·
[9 Optional parts](#9-optional-parts) · [10 Reference](#10-reference)

---

## 1. Install

### What the PC needs

| | minimum | notes |
|---|---|---|
| Windows | 10 or 11 | also runs on macOS and Linux (no spoken answers there) |
| Processor, memory | the shop's Celeron with 4 GB is enough | the optional language model (System 2) needs a CPU with AVX |
| Screen | 1366 × 768 | text size 90–130 % in Settings |
| Python | 3.10 or newer, from python.org, with *Add to PATH* ticked | not needed for a packaged build |
| Disk | a few hundred MB for Python and its packages, 80 MB for the unpacked voice model, plus the data | |
| Optional | Microsoft Word (PDF bills), a USB or headset microphone (voice), Windows' Hindi voice (spoken answers) | see [§9](#9-optional-parts) |

No internet connection is needed to use the program. It is only used to check for and
download updates, and to install Python packages.

### From the repository (the shop PC today)

```bash
git clone https://github.com/Parmodsihag/jbbv4.git
cd jbbv4/v5
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Upgrade pip first: an old pip cannot build the `srt` helper that `vosk` needs. Keep
`setuptools` below 81 (it is pinned in `requirements.txt`): the DOCX bills still need its
`pkg_resources`.

To start it without a console window, double-click **`Start High Table Holdings v5.bat`**
(it uses `pythonw`, falling back to `python`). Put a shortcut to it on the desktop.

A copy made without git (a zip of the `v5` folder) works the same way and can update
itself from inside the program ([§5](#5-updates)).

### As a packaged folder (no Python on the PC)

On a build PC with Python:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name HighTableHoldings --add-data "bundled;bundled" --collect-all vosk run.py
```

Copy `dist/HighTableHoldings/` to the shop PC and run `HighTableHoldings.exe`. The
`bundled` folder (the voice model) must be included. A packaged build **cannot update
itself**; install a new build over it instead.

## 2. First start

On the first start the program:

1. **Copies v4's data** if this is the default Windows folder and `C:\JBB\v4\hth.db` exists:
   it is opened read-only and copied with SQLite's backup API into `C:\JBB\v5\hth.db`, so v4's
   files are never changed. A notice after sign-in says where the data came from. From then
   on v4 and v5 are separate. If the copy fails (for example v4 is open), nothing is
   created and the next start tries again.
2. **Creates the database** (or upgrades a copied one; see [§4](#before-a-database-upgrade)).
3. **Creates two users**, `admin` / `admin` (Administrator) and `emp1` / `emp1` (Employee).
4. **Runs the setup wizard** for the admin: shop details, new passwords for both users (the
   defaults are refused), and an optional v3 data folder to import. *Skip* does it later;
   **Settings › Backup & data › Run setup wizard** runs it again.

**Change both default passwords straight away.** Until you do, *Today* lists "Default
password still in use".

### Bringing v3 data across

Settings › Backup & data › **Import v3 data…** (a backup is taken first), or:

```bash
python tools/migrate_v3.py C:/JBB/data
```

Customer, item and promise numbers are kept. Every v3 daily note becomes an audit-log entry.
Balances after import equal v3's for the same date. Every value the importer had to skip or
normalise (an odd tag, a type that is not P/M, a blank amount, a date not in `YYYY-MM-DD`, a
promise for a deleted customer) is listed with its v3 table and row in
`<data>\migration_report.txt`. Work through that list, then run **Reports › Data check**
(or `python tools/check_data.py`).

## 3. The data folder

Everything the shop owns is in one folder. Back up this folder and you have everything.

| platform | default folder |
|---|---|
| Windows | `C:\JBB\v5` |
| macOS | `~/Library/Application Support/HighTableHoldings` |
| Linux | `~/.local/share/HighTableHoldings` (or `$XDG_DATA_HOME/HighTableHoldings`) |

Set the environment variable **`HTH_DATA_DIR`** to use another folder. Then nothing is
copied from v4.

| inside | what it is |
|---|---|
| `hth.db` | **the books**: one SQLite database ([data dictionary](DATA_DICTIONARY.md)). While the program runs you may also see `hth.db-wal` and `hth.db-shm`; they belong to it. Never copy `hth.db` alone while the program is open: use *Backup now*. |
| `backups\` | `hth_auto_YYYYMMDD.db` (daily), `hth_YYYYMMDD_HHMMSS.db` (Backup now), `hth_pre_migration_v<N>_<time>.db` (before an upgrade), `hth_before_restore_<time>.db` (before a restore) |
| `logs\` | `hth.log` (rotates at 2 MB, five old files kept), `updates.log` |
| `exports\` | Excel exports and HTML statements |
| `bills\`, `pdfs\`, `merged_pdfs\` | GST invoices as DOCX, PDF, and merged PDFs |
| `updates\` | downloaded updates waiting for a restart (`staged\`), the backup of the files each update replaced (`before-<version>-from-<version>-<time>.zip`), `last.json` |
| `assistant\` | the Assistant's trained classifier (rebuilt by itself when missing), voice spellings, an installed language model |
| `voice\` | the unpacked Hindi voice model |
| `migration_report.txt` | the list from the last v3 import |

## 4. Backups and restore

### What happens by itself

* **Daily backup.** On the first start of each day the program writes
  `backups\hth_auto_YYYYMMDD.db` and deletes the oldest automatic backups beyond the number
  to keep (default **14**). Turn it off or change the number in Settings › Backup & data.
  A failed automatic backup never stops the program from starting; it is written to the log
  and *Today* shows the backup as missing or old.
* <a id="before-a-database-upgrade"></a>**Before a database upgrade.** When a new version
  changes the database, the existing file is first copied to
  `backups\hth_pre_migration_v<N>_<time>.db`. Each change runs in one transaction with its
  version number, so a failure leaves the database as it was.
* **Before a restore** the current data is saved as `hth_before_restore_<time>.db`.

### What you should do

The backups folder is on the same disk as the books. A dead disk or a stolen PC takes both.
**Once a week, copy the newest file from `backups\` to a USB stick or a cloud folder**, and
keep at least one copy away from the shop. With the daily backup and a weekly copy, the
most a disk failure can lose is one week; a mistake in the books can be undone to any of the
last 14 days.

*Backup now* (Settings › Backup & data, or **Back up now** on Today) takes a consistent copy
at any moment. Take one before anything unusual: a restore, a big correction, an import.

### Restore

Settings › Backup & data › **Restore a backup…** and pick a `.db` file. The program:

1. checks the file: that it opens, passes SQLite's `quick_check`, is a High Table Holdings
   database, and is not from a newer version than this program;
2. shows how many accounts and entries it holds and its last activity, and asks you to
   confirm;
3. saves the current data as `hth_before_restore_<time>.db` (so a restore can itself be
   undone by restoring that file);
4. copies the backup in, upgrades it if it is from an older version, writes an audit entry
   and signs everyone out.

Everything entered after the backup was taken is replaced.

**If the program will not start at all**, restore by hand: close it, rename `hth.db` to
`hth_broken.db`, delete any `hth.db-wal` / `hth.db-shm`, copy the chosen backup to
`hth.db`, and start the program.

## 5. Updates

### Checking and installing

Settings › **Updates** › *Check for updates* compares this copy with the app on GitHub
(repository `Parmodsihag/jbbv4`, branch `v5`, folder `v5`; all three can be changed there)
and shows the new version and what is new, taken from the CHANGELOG. Admins also see a
message after signing in when a new version is there; the program checks at most once a
day.

**Install update**:

1. downloads only the files that changed, each checked against GitHub's own hash (a broken
   download changes nothing);
2. installs any new Python packages named in `requirements.txt`;
3. waits for **Restart now**.

At the next start, before anything else loads, every file about to be replaced is saved to
`<data>\updates\before-….zip`, the new files are put in, and if anything goes wrong the old
files are put back. Files dropped upstream are removed. Paths outside the app folder are
never written. The **data folder is never changed** by an update; a new version's database
changes are made by its own upgrade step, which backs the database up first.

**Undo last update** puts the previous files back the same way, at the next start.

Every step is written to `logs\updates.log` and the audit log (code 14).

A **git checkout** (a developer's copy) is updated with `git pull --ff-only` instead, and
only when it has no uncommitted changes. A packaged build cannot update itself.

Set `HTH_NO_UPDATE_CHECK=1` to stop the automatic check (the tests do this).

### Publishing an update (developer)

See [RELEASING.md](RELEASING.md). In short: raise `__version__` in `hth/__init__.py` and the
version in `pyproject.toml`, add a `## <version>` section to `CHANGELOG.md`, and push to the
`v5` branch. Shop PCs see it at their next check.

## 6. Users and security

| task | where |
|---|---|
| Add a user, reset a password, change a role, deactivate | Settings › Users (`Alt+U`) |
| Change your own password | Settings › My password |
| Lock the screen after idle minutes | Settings › Appearance & language › Auto-lock |
| See who did what | Reports › Audit log; Reports › Staff activity |

* Two roles: **Administrator** and **Employee** ([user guide §14](USER_GUIDE.md#14-who-can-do-what)).
  The full list of permissions is in `hth/services/permissions.py`.
* A user cannot deactivate themselves, and the last active administrator cannot be
  deactivated. A deactivated user cannot sign in and has no permissions.
* Passwords must be at least 4 characters (the program enforces no more than that, so ask
  for longer ones). They are stored as salted PBKDF2-SHA256 hashes (200,000 rounds), never
  as text.
* After 5 wrong passwords a username waits 30 seconds, doubling with each further failure.
  Restarting the program clears the wait.
* Give each person their own user, so the audit log and Staff activity mean something.
* The data folder is not encrypted. Protect the PC itself: a Windows password, and the
  backups copied off the PC kept somewhere safe. See [SECURITY.md](../../SECURITY.md).

## 7. Troubleshooting

Start with the log: `<data>\logs\hth.log`. Every error the program catches is written there
with the details, including the ones the screen shows only as "Something went wrong".

| symptom | cause and fix |
|---|---|
| "Could not copy the v4 data from …" at first start | v4 is open or the file is locked. Close v4 and start v5 again; nothing was created. |
| The program does not open after an update | Start it from a console (`python run.py`) to see the error; `logs\updates.log` says what the update did. A failed update has already put the old files back by itself. If the update succeeded but the new version will not start, Settings is unreachable, so undo by hand: unzip the newest `<data>\updates\before-….zip` over the `v5` folder (leave out its `_update.json`) and delete any file that zip's `_update.json` lists under `created`. |
| "… was made by a newer version" on restore | The backup comes from a newer program. Update this copy first. |
| Bills: *Save & make PDF* is missing | PDF needs Microsoft Word **and** `pip install docx2pdf`. DOCX works without either. |
| Bills screen shows a `pip install` banner | `docxtpl` / `pypdf` are missing: run the command shown. |
| `pip install` fails building `srt` | `python -m pip install --upgrade pip`, then install again. |
| Bills fail with an error about `pkg_resources` | `setuptools` 81 or newer was installed. `pip install "setuptools<81"`. |
| The Assistant says it heard nothing | Settings › Assistant & voice › Microphone: choose the real microphone, never "Stereo Mix" (it records the speakers). *Test microphone* shows the loudness and what it heard. "No sound is coming from …" means a muted or wrong device; "I heard a voice but could not make out the words" means the microphone works. |
| Answers are not spoken | Windows needs its Hindi voice: Windows Settings › Time & language › Speech › Add voices › Hindi. Also check Settings › Assistant & voice › Speak answers. |
| Assistant's language model (System 2) switched itself off | This PC cannot run it (often no AVX). Nothing else is affected; System 1 keeps answering. |
| Charts show English text in Hindi mode | Expected: the chart library cannot draw Devanagari correctly. |
| Interest looks wrong after the PC was off for months | Check the PC's date and time. Interest runs to *today* by the PC's clock. |
| Text or buttons are cut off on a small screen | Settings › Appearance & language › Text size 90 %; in Classic, ☰ collapses the sidebar. |
| A balance does not match the paper | Open the khata, *All* entries; check tags (0 / 1 / 2) and dates. Reports › Data check finds lone settlement rows, future dates and the like. |

### Checking the books

**Reports › Data check** (admin) and `python tools/check_data.py` list: invalid or future
dates, negative stock, duplicate customers, zero-amount entries, lone settlement rows,
open promises with nothing owed, and long-inactive debtors. Double-click a finding to open
the record.

## 8. Routine checklist

| when | what |
|---|---|
| Every day | Glance at the status line: the last backup should be today. Clear *Today*'s housekeeping. |
| Every week | Copy the newest backup off the PC. Run Reports › Data check. Work through Collections. |
| Every month | Post recurring expenses (Money). Look at Staff activity and the Audit log. Check for updates. |
| 31 March (year end) | Nothing to do for interest: it is added to the amount by itself. Take a *Backup now* and keep that file permanently. Print statements if the shop sends them. GST bill numbers start again in the new financial year (2627001, 2627002 … for 2026-27). |
| Before a big change | *Backup now*. |

## 9. Optional parts

| part | needs | how |
|---|---|---|
| PDF bills | Microsoft Word, `pip install docx2pdf` | Money › GST bills shows *Save & make PDF* |
| Voice questions | the bundled Vosk Hindi model (unpacked by itself), `vosk`, `sounddevice` (in `requirements.txt`), a microphone | see [VOICE_DESIGN.md](VOICE_DESIGN.md); another Vosk model: Settings › Assistant & voice › Install voice model… |
| Spoken answers | Windows' Hindi voice, `pywin32` | Windows only |
| Assistant System 2 | `pip install llama-cpp-python`, a trained model zip, a CPU with AVX | train it on Kaggle with `tools/assistant/kaggle_train_cell.py`, then Settings › Assistant & voice › Install model…; see [AI_CHAT_DESIGN.md](AI_CHAT_DESIGN.md) |

## 10. Reference

### Environment variables

| variable | effect |
|---|---|
| `HTH_DATA_DIR` | use this data folder (nothing is copied from v4) |
| `HTH_NO_UPDATE_CHECK` | no automatic update check |
| `HTH_I18N_MISSES=<file>` | record every text shown in Hindi mode that has no translation yet |
| `HTH_UI_TESTS`, `HTH_UI_FRESH`, `HTH_VOICE_MODEL` | tests only ([TEST_PLAN.md](TEST_PLAN.md)) |

### Tools

| command | does |
|---|---|
| `python tools/migrate_v3.py <v3 folder>` | import v3 data |
| `python tools/check_data.py` | data-quality findings for the live database |
| `python tools/assistant/eval.py` | Assistant accuracy on questions it never saw |
| `python tools/assistant/eval_names.py` | how well the Assistant finds the shop's real customers (read-only, prints totals only) |
| `python tools/assistant/eval_voice.py [--recordings <folder>]` | voice accuracy |
| `python tools/readme_shots.py` | retake the README screenshots from a made-up demo shop |

### Start-up order

1. Apply a staged update (or its undo), then restart.
2. Set up logging.
3. First start only: copy v4's database.
4. Upgrade the database (with a backup first).
5. Make missing Hindi copies of names.
6. Create the default users if there are none.
7. Daily backup.
8. Default money account and expense heads.
9. Open the window.
