# Contributing

How to work on High Table Holdings: set up, branch, write code that fits, test it, and get
it to the shop. The program keeps a real shop's books, so the rules below are about not
breaking the numbers and not losing data before they are about style.

**Contents:** [Where things are](#where-things-are) · [Set up](#set-up) ·
[Workflow](#workflow) · [Code standards](#code-standards) · [Tests](#tests) ·
[How-tos](#how-tos) · [Definition of done](#definition-of-done) · [Docs](#documentation)

## Where things are

| folder | what |
|---|---|
| `v5/` | **the app.** All new work goes here. |
| `v5/docs/` | user, admin, architecture, data, test and release documents; decision records in `v5/docs/adr/` |
| `HighTableHoldings-v4/` | v4, kept for reference. Do not change it. |
| `sme/` | the Software Engineering & Management course pack (SRS, DFDs, decision tables, PERT, test cases) |
| `docs/screenshots/` | images for the front-page README (retake with `python v5/tools/readme_shots.py`) |

Start with [v5/docs/ARCHITECTURE.md](v5/docs/ARCHITECTURE.md).

## Set up

```bash
git clone https://github.com/Parmodsihag/jbbv4.git
cd jbbv4/v5
python -m venv .venv
.venv\Scripts\activate             # macOS / Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pytest                             # should pass before you change anything
```

Work with your own data folder so you never touch the shop's books:

```bash
set HTH_DATA_DIR=C:\hth-dev        # PowerShell: $env:HTH_DATA_DIR = "C:\hth-dev"
python run.py
```

To try a change on real figures, restore a **copy** of a backup into that folder (Settings ›
Backup & data › Restore a backup…). Never point a development copy at `C:\JBB\v5`.

## Workflow

### Branches

| branch | purpose |
|---|---|
| `main` | integration: everything that is finished and tested |
| `v5` | **the update channel**: shop PCs install whatever is here ([RELEASING.md](v5/docs/RELEASING.md)) |
| `feature/<name>`, `fix/<name>`, `docs/<name>` | one piece of work each, from `main` |

1. Branch from an up-to-date `main`.
2. Commit in small steps that each pass the tests.
3. Open a pull request into `main`. Describe what changed for the shop and how it was
   tested; link the issue.
4. Review: at least one other person reads it against the [definition of done](#definition-of-done).
5. Merge with a merge commit (the history keeps each phase of larger work).
6. Releasing to the shop is a separate step: a pull request from `main` into `v5`.

Never push straight to `v5`.

### Commit messages

`<area>: <what changed, in plain words>`, present tense, the why in the body when it is
not obvious. Release commits are `v<version>: <headline>`.

```
counter: Ctrl+Shift+Enter never saves a sale
fix billing: batch crash, printed amounts, atomic batch
docs: AI chat assistant design for review
v5.7.0: colour themes
```

## Code standards

### Layers (enforced in review)

* `hth/domain`: pure rules, no I/O, no imports from the rest of `hth`.
* `hth/db`: SQLite only.
* `hth/services` and module `service.py`: business logic. **Never import `tkinter` or
  `customtkinter`.**
* `hth/ui` and module `views.py`: screens. **Never run SQL**; call a service.
* Core never imports from `hth/modules/`. Modules register handlers instead.
* `hth/services/updates.py` stays standard-library only.

The reasons are in [the decision records](v5/docs/adr/README.md).

### The books

* **Never change how a balance or interest is computed** without a decision record, a test
  change, and a same-figures check on a copy of the shop's data.
* Every write that touches more than one table runs inside one `with db.connect():` block.
* Dates are `YYYY-MM-DD` text (`DATE_FMT`). Anything that depends on today takes an
  optional `today` argument.
* Every write records the user and an audit-log line (`ctx.audit.log(code, message, user)`).
* Every screen and destructive action checks a `Permission`; the service checks too where it
  matters.
* Bad input raises `ValidationError` with a message the shop staff understand. Never
  `print`; log with `logging`.

### Python

* Python 3.10. `from __future__ import annotations` at the top of modules.
* `ruff check` and `ruff format` must be clean (line length 120; rules E, F, I, B, UP;
  see `pyproject.toml`).
* Type hints on public functions. Dataclasses for records.
* Names say what a thing is in the shop's terms (`balance`, `promise`, `paid_now`).
* Comments and docstrings explain **why**, not what. Keep the existing density: a module
  docstring that says what the module is for, short docstrings on non-obvious functions.
* Import heavy libraries (openpyxl, matplotlib, numpy) inside the function that needs them.

### Text the user sees

* Shop words, not accounting words: *Sale, Purchase, Payment in, Payment out, owes us*.
* Every English string shown on screen needs an entry in `hth/i18n/hi.py`. Use `{}` holes for
  numbers. Run the program in Hindi with `HTH_I18N_MISSES=misses.txt` to find missing ones.
* Values the code compares stay English; only display text is translated.

## Tests

* **Every change comes with tests**; every bug fix with a test that fails before the fix.
* Business-rule tests use the `db` fixture (in-memory SQLite) and need no display.
* Work out expected figures by hand or from v3; never copy them from the program's output.
* Before pushing:

```bash
pytest
ruff check hth tests tools && ruff format --check hth tests tools
```

* Before a pull request that touches screens, also run
  `HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py tests/test_ui_modern.py`.

Details: [v5/docs/TEST_PLAN.md](v5/docs/TEST_PLAN.md).

## How-tos

**Add a report.** Add the query to `hth/services/reports.py` (with a test), then one
`ReportSpec` to `REPORTS` in `hth/ui/views/reports.py`. Add it to `SCOPED_REPORTS` if it lists
customers or items. Both layouts' catalogues pick it up. Give it a permission if it is for
admins.

**Change the database.** Append a new `(version, SQL)` entry to `MIGRATIONS` in
`hth/db/schema.py`. Never edit an entry that has shipped. Update
[DATA_DICTIONARY.md](v5/docs/DATA_DICTIONARY.md) and add a test that opens a database at the
previous version.

**Add a feature module.** See [v5/hth/modules/README.md](v5/hth/modules/README.md): a package
with `service.py`, `views.py`, `MODULE = ModuleSpec(...)` (including `area` and `tab` for the
New layout), tests in `tests/modules/`.

**Add a permission or a role.** Edit the one matrix in `hth/services/permissions.py` and
`test_permissions`. Nowhere else.

**Add a shop-wide setting.** A default in `DEFAULTS` of `hth/services/preferences.py` (or the
service that owns it), a getter and a setter that validates, a test, and a row in the data
dictionary's settings table.

**Add a question the Assistant understands.** Templates in all styles in
`INTENTS` (`hth/assistant/data.py`), a read-only `Tool` in `TOOLS` (`hth/assistant/tools.py`)
that calls an existing service and checks a permission, tests in `tests/test_assistant.py`,
then `python tools/assistant/build_kaggle_cell.py` so the System 2 training cell matches.

**Add a colour theme.** A `Theme` in `THEMES` (`hth/ui/theme.py`) defining every token, light
and dark. `tests/test_themes.py` checks completeness and contrast.

**Record a decision.** A new file in `v5/docs/adr/` ([how](v5/docs/adr/README.md)).

## Definition of done

A change is done when:

- [ ] it does what the issue asked, in both layouts where it shows on screen;
- [ ] tests cover it, and a bug fix has its regression test;
- [ ] `pytest` passes, and the UI suites pass if screens changed;
- [ ] `ruff check` and `ruff format --check` are clean;
- [ ] every new on-screen string has its Hindi entry;
- [ ] permissions and the audit log are respected;
- [ ] no balance, interest or stock figure changed (or the change is intended, recorded in a
      decision record, and checked on a copy of the shop's data);
- [ ] a database change has its migration and data-dictionary update;
- [ ] the CHANGELOG's next section says what changed, in the shop's words;
- [ ] the user or admin guide is updated if the shop will see the difference;
- [ ] someone else reviewed it.

## Documentation

| when you change … | update |
|---|---|
| what the shop sees | `CHANGELOG.md`, [USER_GUIDE.md](v5/docs/USER_GUIDE.md), screenshots if a screen changed a lot |
| installing, backups, updates | [ADMIN_GUIDE.md](v5/docs/ADMIN_GUIDE.md) |
| structure or a major choice | [ARCHITECTURE.md](v5/docs/ARCHITECTURE.md), a decision record |
| the database | [DATA_DICTIONARY.md](v5/docs/DATA_DICTIONARY.md) |
| requirements or rules | the course pack in `sme/` (SRS, decision tables, test cases) |

The documentation index is [v5/docs/README.md](v5/docs/README.md).
