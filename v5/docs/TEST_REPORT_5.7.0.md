# Test report: 5.7.0

Test summary report for High Table Holdings **5.7.0** (commit `61d0b5b`, "v5.7.0: colour
themes"), following the [test plan](TEST_PLAN.md).

| | |
|---|---|
| Run on | 2026-10-23 |
| Run by | release tester, on the developer PC |
| Verdict | **Pass.** All 316 automated tests pass; lint and formatting are clean. Shop-PC acceptance is still to be done. |

## 1. Environment

| | |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| Python | 3.10.4 |
| customtkinter | 6.0.0 |
| pytest / ruff | 9.1.1 / 0.17.1 |
| Other packages | matplotlib 3.7.1, numpy 1.26.4, openpyxl 3.0.10, docxtpl 0.16.8, pypdf 6.16.2, vosk 0.3.45, sounddevice 0.4.6, pywin32 304, setuptools 80.10.2 |
| Voice model | `vosk-model-small-hi-0.22`; Windows Hindi voice installed |
| Data | in-memory SQLite and temporary folders; no shop data was read |

**Deviation:** openpyxl 3.0.10 is installed, below the `openpyxl>=3.1` that `requirements.txt`
declares. The Excel exports were exercised by the suites and worked, but the developer PC
should be brought up to the declared minimum (`pip install -r requirements.txt`) so it tests
what the shop installs.

## 2. Results

| run | command | passed | failed | skipped | time |
|---|---|---:|---:|---:|---:|
| Non-UI suite | `pytest -rs` | 282 | 0 | 34 | 42.9 s |
| UI suites and real voice | `HTH_UI_TESTS=1 HTH_VOICE_MODEL=… pytest tests/test_ui_smoke.py tests/test_ui_modern.py tests/test_voice.py::test_real_voice_round_trip` | 34 | 0 | 0 | 300.7 s |
| **Total** | | **316** | **0** | **0** | |
| Lint | `ruff check hth tests tools` | all checks passed | | | |
| Format | `ruff format --check hth tests tools` | 149 files already formatted | | | |

The 34 skips in the first run are exactly the 33 UI tests (skipped without `HTH_UI_TESTS`)
and the real-voice test (skipped without `HTH_VOICE_MODEL`); the second run executed all of
them. The flaky Tk start described in the test plan did not occur.

### By area

| area | files | tests | result |
|---|---|---:|---|
| Books: interest, ledger, settlement, categories, statements | interest, accounts, categories, statements | 37 | pass |
| Counter, stock, units, crops from the counter | inventory_sales, units, unit_change, sales_crops | 28 | pass |
| Promises, reports, sign-in, permissions, search, data check, reminders, backup | krar_reports_auth, search, integrity, reminders_backup | 11 | pass |
| Migration from v3 | migration | 3 | pass |
| Modules: bills, crops, finance | modules/* | 27 | pass |
| v5 features and fixes | v5_features, v5_fixes | 32 | pass |
| Speed (identical figures) | speed | 8 | pass |
| Themes and contrast | themes | 11 | pass |
| Hindi | hindi | 25 | pass |
| Assistant | assistant | 44 | pass |
| Voice | voice | 41 | pass |
| Updates | updates | 16 | pass |
| UI: Classic and New layouts | ui_smoke, ui_modern | 33 | pass |

## 3. Requirements coverage

Every functional requirement of the SRS ([sme/03_SRS.md](../../sme/03_SRS.md)) has at least
one automated test case; the traceability matrix is in
[sme/08_Test_Cases.md §6.3](../../sme/08_Test_Cases.md#63-traceability-matrix-requirement--test-cases).
Requirements checked only by hand are listed under *Not tested* below.

Code coverage was **not measured** (`pytest-cov` is not installed).

## 4. Not tested in this run

| item | why | plan |
|---|---|---|
| Acceptance checklist on the shop PC (AT-1 … AT-20) | needs the shop PC and the owner | after the update is installed at the shop |
| UI on customtkinter 5.2.2 | the shop's version is not installed here | covered by acceptance |
| PDF bills through Microsoft Word | needs Word and `docx2pdf` | acceptance step AT-9 |
| System 2 language model | optional; no model installed | the Kaggle cell's own verdict |
| Real recorded questions in the owner's voice | none recorded yet | `eval_voice.py --recordings` when available |
| Same-figures check on a copy of the shop's database | 5.7.0 changes colours only, no books code | required again for the next release that touches the books |

## 5. Defects

No defects were found in this run. The defects fixed in 5.7.0 (the CHANGELOG's *Fixed*
section) are covered by `test_v5_light_dark_switch_on_the_dashboard_charts` (classic
dashboard light / dark switch) and `test_colour_themes_recolour_every_screen_in_place`.

## 6. Residual risks

* The real accuracy of voice questions in the shop is unknown until the owner's own speech
  is measured.
* Without coverage figures, untested branches cannot be listed.
* Without CI, the exit criteria depend on the tester running both commands.

## 7. Recommendation

Release 5.7.0 to the shop (already on the `v5` update branch) and complete the acceptance
checklist there. Before the next release: install `pytest-cov` and report coverage, bring
openpyxl to the declared version, and add a CI workflow for the non-UI suite and ruff.
