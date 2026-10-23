# Test plan

The master test plan for High Table Holdings v5, laid out after ISO/IEC/IEEE 29119-3. It
says what is tested, how, where, and when a release is good enough to reach the shop. The
results of each release go in a test report ([TEST_REPORT_5.7.0.md](TEST_REPORT_5.7.0.md) is
the latest). The test *cases* traced to requirements are in the course pack,
[sme/08_Test_Cases.md](../../sme/08_Test_Cases.md).

**Contents:** [1 Scope](#1-scope) · [2 Risks](#2-risks-that-drive-the-testing) ·
[3 Approach](#3-approach) · [4 Suites](#4-the-automated-suites) ·
[5 Environment](#5-environment) · [6 Criteria](#6-entry-exit-and-suspension-criteria) ·
[7 Defects](#7-defect-management) · [8 Regression and flaky tests](#8-regression-and-flaky-tests) ·
[9 Roles and schedule](#9-roles-and-schedule) · [10 Running the tests](#10-running-the-tests) ·
[11 Gaps](#11-known-gaps)

---

## 1. Scope

**Test item:** the `v5/` application (package `hth`, the tools in `tools/`), version 5.7.0
and every later 5.x release.

**In scope**

| area | features |
|---|---|
| Books | interest, balances, settlement, ledger, statements, categories and scores |
| Counter | sales, purchases, payments, several lines, paid-now, undo, slips, unit conversion |
| Stock | items, movements, unit changes, alerts, reorder |
| Promises | promise lifecycle, buckets, reminders |
| Modules | GST bills, crop trading (lots, FIFO), finance (cash book, recurring, P&L) |
| Reports | all 34 reports, scope, Excel export |
| Security | sign-in, lockout, permissions, audit |
| Data safety | migrations, backup, restore, v3 import, first-start copy of v4, data check |
| Updates | check, stage, apply, roll back, undo, git mode |
| Hindi | phrase table, widget hook, transliteration, Hindi documents |
| Assistant and voice | language, periods, names, ask-back, tools, System 2 fallback, recogniser vocabulary, spoken answers |
| Interface | both layouts, layout switch, themes and contrast, text size, shortcuts |
| Speed | caches and kept connections give identical figures; freshness |

**Out of scope**

* customtkinter, SQLite, Vosk, matplotlib themselves.
* PDF conversion through Microsoft Word (needs Word; checked by hand, [§11](#11-known-gaps)).
* Training System 2 on Kaggle (it reports its own verdict; `test_kaggle_cell_is_up_to_date`
  checks the cell matches the app's corpus).
* macOS and Linux beyond start-up; the shop runs Windows.

## 2. Risks that drive the testing

Testing effort follows product risk. The highest risks get the strongest oracles.

| # | risk | likelihood | impact | how the tests answer it |
|---|---|---|---|---|
| PR-1 | A balance or interest figure differs from v3 / v4 | low | **critical** (trust) | oracle = v3's own code (`test_matches_v3`); hand-checked figures; migration equivalence; bit-for-bit checks on every speed-up (`test_speed.py`) |
| PR-2 | A partial write leaves ledger, stock and cash book out of step | low | critical | fault injection inside the transaction (`test_sale_is_atomic`, `test_crop_trade_is_atomic`, `test_record_lines_is_atomic_and_undo_reverses_everything`) |
| PR-3 | An upgrade, restore or update loses data or leaves an unusable program | medium | critical | failed-migration test; restore round trip; update tests against a fake GitHub incl. failure while applying |
| PR-4 | An employee reaches an admin action | medium | high | permission matrix for every permission; UI walkthrough as employee; report-link check |
| PR-5 | The assistant gives a confident wrong answer | medium | high | accuracy on held-out phrasings; ambiguity asks back; System 2 only within System 1's top three; read-only check |
| PR-6 | Hindi mode changes what the code compares | medium | medium | English untouched; values read back stay English; every phrase pattern fills |
| PR-7 | Text unreadable in a theme | low | medium | WCAG contrast for every token pair in every theme |
| PR-8 | A screen breaks on the shop's customtkinter version or screen size | medium | medium | UI walkthroughs; acceptance at 1366 × 768 on the shop PC |

## 3. Approach

### Test levels

| level | what | technique | where |
|---|---|---|---|
| Unit | pure rules: interest, units, numbers, GST, Hindi words, transliteration, normalisation | equivalence classes, boundary values (31 March, FY edges, zero / negative amounts), oracle comparison with v3 | `test_interest.py`, `test_units.py`, `test_hindi.py`, parts of `test_assistant.py` |
| Integration | services on a fresh in-memory SQLite per test | decision-table testing (the decision tables in [sme/05](../../sme/05_Decision_Tables.md)), state transitions (promise, account period, crop lot, update), fault injection | `test_accounts.py` … `test_v5_features.py`, `tests/modules/` |
| Migration / data | v3 import, v4 first-start copy, schema migration, restore | synthetic legacy data, planted anomalies, failure injection | `test_migration.py`, `test_integrity.py`, `test_v5_fixes.py`, `test_v5_features.py` |
| Regression | one test per fixed defect | reproduce, then fix | `test_v5_fixes.py`, named tests elsewhere |
| System (UI) | the real window, both layouts, both roles, as a user would | scripted walkthroughs, pumping the Tk loop | `test_ui_smoke.py`, `test_ui_modern.py` (opt-in) |
| Non-functional | speed without changing answers; contrast; assistant and voice accuracy | metamorphic checks (cached = uncached), WCAG formula, held-out evaluation | `test_speed.py`, `test_themes.py`, `test_assistant.py`, `test_voice.py`, `tools/assistant/eval*.py` |
| Acceptance | the shop's own data on the shop PC, by the owner | checklist | [sme/08 §6.4](../../sme/08_Test_Cases.md) |

### Test doubles

* **Database:** a fresh `Database(":memory:")` per test (`tests/conftest.py`).
* **Time:** functions take an optional `today` / `on_date`.
* **GitHub:** the updater takes a `fetch` function; tests pass a fake repository.
* **Speech:** recogniser and microphone are faked except in `test_real_voice_round_trip`.
* **Data folder:** UI tests set `HTH_DATA_DIR` to a temporary folder and
  `HTH_NO_UPDATE_CHECK=1`, so the shop's data and GitHub are never touched.

### Test design rules

* A test checks one behaviour and says so in its name
  (`test_settlement_overpayment_writes_negative_discount`).
* Expected figures are worked out independently (by hand or by v3's code), never copied
  from the program's output.
* Business-rule tests never need a display.
* No test reads the shop's real data. Tools that measure on real data
  (`eval_names.py`) open it read-only and print totals only.

## 4. The automated suites

316 tests in 26 files at 5.7.0.

| file | tests | level | covers |
|---|---:|---|---|
| `test_interest.py` | 15 | unit | interest, FY compounding, v3 equality, "today" at call time |
| `test_units.py` | 9 | unit | unit names, families, conversion, formatting |
| `test_accounts.py` | 14 | integration | customers, ledger, balance, settlement, running balance, scores, cascade |
| `test_inventory_sales.py` | 11 | integration | items, stock, sales, receipts, atomicity, loose sales, validation |
| `test_unit_change.py` | 3 | integration | unit change converts history |
| `test_sales_crops.py` | 5 | integration | crop trades from the counter, FIFO, atomicity |
| `test_categories.py` | 6 | integration | categories A–E, locking, scope, re-scoring |
| `test_krar_reports_auth.py` | 5 | integration | promises, reports, sign-in, users, permissions |
| `test_statements.py` | 2 | integration | statements, shop details |
| `test_reminders_backup.py` | 3 | integration | phone extraction, reminders, daily backup |
| `test_search.py` | 1 | integration | search across accounts, items, bills |
| `test_integrity.py` | 2 | integration | data check |
| `test_migration.py` | 3 | migration | v3 import: ids, balances, report |
| `modules/test_bills.py` | 15 | integration | GST, Hindi words, numbering, rendering, batch |
| `modules/test_crops.py` | 6 | integration | lots, FIFO, short sales, rates, valuation |
| `modules/test_finance.py` | 6 | integration | accounts, cash book, recurring, cash flow, P&L |
| `test_v5_features.py` | 24 | integration | number style, lockout, new reports, insights, multi-line, undo, restore, slips, preferences, layouts |
| `test_v5_fixes.py` | 8 | regression | v5 fixes: cash book follows ledger edits, crop rows, failed migration, v4 copy |
| `test_speed.py` | 8 | non-functional | kept connections, version counter, caches identical, freshness |
| `test_themes.py` | 11 | non-functional | every theme complete, WCAG contrast, switching in place |
| `test_hindi.py` | 25 | unit / integration | phrase table, patterns, transliteration, Hindi copies, documents |
| `test_assistant.py` | 44 | unit / integration | language, periods, names, ask-back, tools, accuracy, System 2 |
| `test_voice.py` | 41 | unit / integration | spoken forms, grammar, spellings, microphone choice, spoken answers; one real-model test |
| `test_updates.py` | 16 | integration | update check, staging, apply, rollback, undo, unsafe paths, git mode, voice model |
| `test_ui_smoke.py` | 11 | system | Classic: admin and employee walkthrough, wizard, v5 screens, Hindi, assistant, voice, updates |
| `test_ui_modern.py` | 22 | system | New: every area, both roles, layout switch, themes, Ask bar, freshness |

`pytest --collect-only -q` prints the current list.

## 5. Environment

| | developer PC (reference) | shop PC (acceptance) |
|---|---|---|
| OS | Windows 11 | Windows 10/11 |
| Python | 3.10 | 3.10+ |
| customtkinter | 6.0.0 | 5.2.2 |
| Display | needed for UI suites | the shop's 1366 × 768 screen |
| Voice | Vosk small Hindi model; Windows Hindi voice for the real-voice test | USB / headset microphone |
| Data | in-memory or temporary | a **copy** of the shop's data |

Variables: `HTH_UI_TESTS=1` runs the UI suites; `HTH_UI_FRESH=1` starts them on the first-run
wizard; `HTH_VOICE_MODEL=<folder>` runs the real recogniser test.

## 6. Entry, exit and suspension criteria

**Entry** (before a release is tested): the version is raised in `hth/__init__.py` and
`pyproject.toml`; the CHANGELOG section exists; `ruff check` and `ruff format --check` are clean.

**Exit** (before it is pushed to the `v5` branch):

1. The non-UI suite passes: 0 failures.
2. The UI suites pass with `HTH_UI_TESTS=1` on Windows.
3. Every defect fixed in the release has a regression test.
4. No open defect of severity S1 or S2 ([§7](#7-defect-management)).
5. For a release that touches the books (interest, balances, settlement, migrations,
   import): every balance, day count, score and the interest summary on a copy of the
   shop's database are identical to the previous release.
6. The test report for the release is written.

**Suspend** testing when the build does not start or the in-memory database cannot be
created; **resume** when a fix is in. A failing business-rule test stops the release
outright.

## 7. Defect management

Defects are tracked as GitHub issues on `Parmodsihag/jbbv4` with a severity label; a fix
references the issue in its commit and adds a regression test.

| severity | meaning | example | must be fixed |
|---|---|---|---|
| **S1 critical** | wrong figures, lost or corrupted data, cannot start | a balance differs from v3; a migration leaves a half-written database | before any release; hotfix if already shipped |
| **S2 major** | a main task cannot be done, or a permission leak | a sale cannot be saved; an employee opens an admin report | before the release |
| **S3 minor** | a task is awkward, a workaround exists | a button cut off at 1366 × 768 | next release |
| **S4 cosmetic** | wording, colour, alignment | a Hindi phrase missing | when convenient |

Lifecycle: *new → confirmed (reproduced) → in progress → fixed (test added) → verified in the
release test run → closed.*

## 8. Regression and flaky tests

* **Every defect fix adds a test** that fails before the fix. v5's fixes are collected in
  `test_v5_fixes.py`; others sit with their feature and name the bug in a docstring
  (for example `test_v5_light_dark_switch_on_the_dashboard_charts`).
* The full non-UI suite runs before every commit that touches `hth/` (about 45 s).
* **Known flaky start:** on some Windows set-ups a UI test can fail while Tk starts, with
  `init.tcl: No error` or a `tcl_findLibrary` error, before any of the program runs. Re-run
  the UI suite once; if it fails the same way twice, record it in the test report as an
  environment failure, not a product defect. A failure *after* the window opens is always a
  real failure.
* A test is never deleted to make a run green. A test that is wrong is fixed in its own
  commit with the reason.

## 9. Roles and schedule

| role | who | does |
|---|---|---|
| Developer | the author of a change | writes the tests with the change; runs the non-UI suite |
| Release tester | the team's QA member | runs the full plan before a release; writes the test report |
| Acceptance | the shop owner, with the release tester | the acceptance checklist on the shop PC with real data |

Per release: unit and integration tests during development → full run including UI →
comparison on a copy of the shop's data when the books are touched → push to `v5` → the
owner's acceptance after the update is installed.

## 10. Running the tests

```bash
cd v5
pip install -r requirements-dev.txt

pytest                                                    # everything that needs no display (~45 s)
HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py tests/test_ui_modern.py   # the real window (~5 min)
HTH_VOICE_MODEL=C:/JBB/v5/voice/vosk-model-small-hi-0.22 pytest tests/test_voice.py::test_real_voice_round_trip
pytest -rs                                                # also list what was skipped and why
pytest tests/test_interest.py -k v3                       # one area
ruff check hth tests tools && ruff format --check hth tests tools

python tools/assistant/eval.py                            # assistant accuracy on unseen phrasings
python tools/assistant/eval_voice.py --recordings <folder>   # real spoken questions, if recorded
```

In PowerShell set the variables first: `$env:HTH_UI_TESTS = "1"`.

## 11. Known gaps

| gap | risk | mitigation |
|---|---|---|
| Code coverage is not measured | untested code goes unnoticed | add `pytest-cov` to `requirements-dev.txt` and report line and branch coverage per release |
| No continuous integration | a test can be forgotten | the exit criteria above; a CI workflow is proposed in [RELEASING.md](RELEASING.md#7-continuous-integration) |
| The UI suites run on customtkinter 6.0, the shop has 5.2.2 | a screen that works here breaks there | acceptance on the shop PC; 4.2.0 showed this class of bug |
| PDF through Word is not automated | a Word or docx2pdf change breaks PDF bills | manual check AT-9 on the shop PC |
| Assistant accuracy is measured on generated and synthesised questions | real accuracy is lower | record the owner's own questions and run `eval_voice.py --recordings` |
| Performance figures are measured by hand | a slowdown is noticed late | `test_speed.py` guards the mechanisms; timing on a shop-sized copy before releases that touch queries |
