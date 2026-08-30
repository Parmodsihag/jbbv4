# Chapter 6 — Test cases for the working prototype

## 6.1 Test strategy

| Level | What | How | Where |
|-------|------|-----|-------|
| Unit | Domain rules: interest, units, scores, Hindi words, GST | `pytest`, pure functions, pinned against v3 | `tests/test_interest.py`, `test_units.py`, `modules/test_bills.py` |
| Integration | Services on an in-memory SQLite: accounts, sales, inventory, krar, auth, categories, statements, modules | `pytest` fixtures build a fresh DB per test | `tests/test_*.py`, `tests/modules/*` |
| Migration | v3 → v4 equivalence: ids preserved, balances identical, report of normalised values | `pytest` with a synthetic v3 folder | `tests/test_migration.py` |
| UI | Full admin + employee walkthrough and first-run wizard on the real window | `HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py` | `tests/test_ui_smoke.py` |
| Acceptance | Manual checklist with the shop's real data on the shop PC | Owner + tester | §6.4 |

Current automated status (`pytest -q`, Python 3.10, customtkinter 6.0):
**94 passed, 2 skipped** (the two UI tests skip unless a display is available and
`HTH_UI_TESTS=1` is set). Lint: `ruff check hth tests tools` clean.

Test-case fields: **Id**, requirement traced, precondition, steps / input, expected
result, and the automated test that implements it (or *manual*).

## 6.2 Automated test cases

### Interest (FR-2.4)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-01 | — | `calculate_interest(1000, 2024-04-01, 2025-03-31)` | 240.00 (one FY, simple) | `test_one_year_is_24_percent_before_compounding` |
| TC-02 | — | 1000 from 2024-04-01 to 2026-03-31 | 240 for FY1, then 24 % on 1240 for FY2 = 537.60 total (compound at 31 Mar) | `test_compounds_at_financial_year_end` |
| TC-03 | — | Random (amount, from, to) triples vs v3's function | Results identical to 2 dp | `test_matches_v3` |
| TC-04 | Clock moved past midnight | `calculate_interest(p, d)` with no `to_date` | Uses *today at call time*, not import time | `test_default_to_date_is_today` |
| TC-05 | — | `financial_year_end(2024-02-10)`, `(2024-06-10)` | 2024-03-31, 2025-03-31 | `test_financial_year_end` |
| TC-06 | — | Dates as `str` and `date` objects | Same result | `test_accepts_date_objects_and_strings` |

### Accounts and ledger (FR-2.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-07 | Empty DB | Add customer with opening balance 500 | One `P`/tag-1 row dated today; balance 500 | `test_add_customer_creates_opening_transaction` |
| TC-08 | Empty DB | Add customer without opening balance | No transaction rows | `test_add_customer_without_opening_balance_has_no_transaction` |
| TC-09 | Customer exists | Amount −5, date `31/12/2024`, type `X`, tag `7` | `ValidationError`, nothing written | `test_validation` |
| TC-10 | Customer with P 1000 (tag 1, 100 days ago) and M 300 (tag 2) | `get_balance()` | 1000 + I(1000,100d) − 300, rounded 2 dp | `test_balance_debit_minus_credit_with_interest` |
| TC-11 | Customer with balance B | Settlement receipt of amount B (tag 0) | Balance 0; next tag-1 entry starts a new period from 0 | `test_settlement_resets_period` |
| TC-12 | Balance 1200 | Settlement receipt 1000 (M, tag 0) | Three tag-0 rows: entry 1000, *Settled Amount* 1200, *Discount* 200 | `test_record_settlement_writes_three_tag0_rows` |
| TC-13 | Balance 1000 | Settlement receipt 1100 | *Discount* = −100 (negative allowed, as v3) | `test_settlement_overpayment_writes_negative_discount` |
| TC-14 | Customer in credit (−400) | Settlement | Rows written with negative Settled Amount; balance 0 | `test_settlement_on_credit_balance` |
| TC-15 | Ledger with a settlement in the middle | `ledger()` | Running balance resets to 0 after the tag-0 group; per-row interest shown | `test_ledger_running_balance_and_reset` |
| TC-16 | Ledger never settled | `ledger()` | Running balance accumulates across all rows | `test_ledger_no_settlement_running_balance` |
| TC-17 | Several customers with entries | `summaries()`, `days_since_last_activity()` | Days = days since newest non-settlement row; summary balances match `get_balance` | `test_days_and_summaries` |
| TC-18 | Pairs (amount, days) | `account_scores(pairs)` | `0.6·norm(log amount)+0.4·norm(log days)`; single element → 0 | `test_account_scores_formula` |
| TC-19 | Customer with rows, krar | Update name; delete customer | Name changed; rows and krar cascade-deleted; audit 05/06 written | `test_update_and_delete_cascade` |

### Inventory, units and sales (FR-3.x, FR-4.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-20 | Empty DB | Add item, opening stock 50 KG | One *received* movement 50; `quantity()` = 50 | `test_add_item_writes_opening_stock` |
| TC-21 | Items with movements, expiry dates | `summaries()`, `low_stock(5)`, `expiring(60)` | Correct stock, value, alert lists | `test_summaries_and_alerts` |
| TC-22 | Customer + item (last price 10) | Sale: 3 units @ 12, tag 1 | Ledger P 36; movement sale 3; last price 12; audit 03 | `test_sale_updates_ledger_stock_price_and_audit` |
| TC-23 | As above | Receive: 5 units @ 9 | Ledger M 45; movement received 5; audit 04 | `test_receive_adds_stock_and_credits` |
| TC-24 | Customer | Sale with free-text item `CASH` | Ledger row only; no stock movement | `test_sale_without_item_only_touches_ledger` |
| TC-25 | Customer with balance | Sale with tag 0 | Three tag-0 rows + stock movement, balance 0 | `test_settlement_sale_flow` |
| TC-26 | Stock movement forced to fail | `record()` | Ledger row rolled back — no partial write | `test_sale_is_atomic` |
| TC-27 | — | qty 0 / bad date / unknown customer / tag 9 | `ValidationError` each time | `test_sale_validation` |
| TC-28 | Item unit KG | Sell 100 G @ ₹50/KG | Stock −0.1 KG; amount ₹5; detail "100 G (0.1 KG) = item" | `test_loose_sale_in_grams_converts_to_stock_unit` |
| TC-29 | Crop kept in KG | Sell 2.5 QTL @ ₹22.5/KG | Stock −250; amount 5625; fractional price accepted | `test_sale_in_quintals_and_fractional_price` |
| TC-30 | Item unit PKT | Sell 1 KG | Rejected: incompatible unit | `test_incompatible_unit_rejected` |
| TC-31 | — | `normalize("kg")`, `("Kgs")`, `("quintal")` | KG, KG, QTL | `test_normalize_aliases` |
| TC-32 | — | families / `compatible(KG, G)`, `(KG, LTR)` | True / False | `test_families_and_compatibility` |
| TC-33 | — | `convert(1, QTL, KG)`, `(500, G, KG)`, `(1, LTR, ML)` | 100, 0.5, 1000 | `test_convert` |
| TC-34 | — | `convert(1, PKT, KG)` | `UnitError` | `test_convert_incompatible` |
| TC-35 | — | `format_qty(2.5)`, `(3.0)` | "2.5", "3" | `test_format_qty` |
| TC-36 | Item KG with movements, prices | Change unit to QTL | Quantities ÷100, prices ×100, values unchanged | `test_same_family_conversion` |
| TC-37 | Item PKT | Change unit to KG without factor | Needs factor (`None` returned / asks); with factor 25 → qty ×25, price ÷25 | `test_unrelated_units_need_a_factor` |
| TC-38 | Crop with lots, sales, rates | Change unit | Lots, allocations, sales and rates converted consistently | `test_crop_history_converted` |

### Crop trades from the Sales screen (FR-4.1, FR-4.4, FR-8.2)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-39 | Crop item (type C), farmer account | Credit 1000 KG gross, kaat 20, @ ₹20 | Lot net 980; farmer credited 19 600 (tag 2); stock +980 | `test_credit_on_crop_item_creates_a_lot` |
| TC-40 | Two lots @ 20 (500) and @ 22 (500) | Debit sale 700 KG @ 25 to buyer | Cost = 500·20 + 200·22 = 14 400; margin 3 100; buyer debited 17 500; lots 0 / 300 left | `test_debit_on_crop_item_is_fifo_costed` |
| TC-41 | Crop item | Any crop trade with tag 0 | Rejected | `test_crop_trade_rejects_settlement_tag` |
| TC-42 | Non-crop item | Sale | Behaves as TC-22 (no crop handler involved) | `test_plain_items_unaffected` |
| TC-43 | Crop trade with induced failure | `record()` | Nothing written (lot, ledger, stock all rolled back) | `test_crop_trade_is_atomic` |
| TC-44 | Open stock 300 | Sale 400 without *allow short* / with it | Rejected / accepted, uncovered 100 at last rate, flagged | `test_sale_fifo_margin_and_ledger` |
| TC-45 | Lots, sales, payments | Pay farmer, receive from buyer; Summary, margin by crop/buyer, purchases by farmer/quality, open lots | Ledger balances and report totals reconcile | `test_payments_and_reports` |
| TC-46 | Rates on several dates | Valuation at cost & market; `estimate_rate()` | Unrealised gain = (market − avg cost) × qty; naive linear trend | `test_rates_valuation_and_estimate` |
| TC-47 | CSV `crop,date,rate` | `CsvRateProvider.fetch()` | Quotes parsed, bad rows skipped | `test_csv_rate_provider` |
| TC-48 | — | `add_crop()` | Item type C, unit KG | `test_add_crop_is_item_type_c` |

### Krar, reports, auth, permissions (FR-5.x, FR-6.1, FR-1.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-49 | Customer | Add date yesterday → bucket; reschedule to tomorrow; settle | past → future; settled not listed; audit 07 | `test_krar_lifecycle` |
| TC-50 | Seeded data | Every `ReportSpec` query | Each returns rows with the declared columns; aging buckets sum to receivable | `test_reports` |
| TC-51 | Fresh DB | Login `admin/admin`, `emp1/emp1`, wrong password | Success, success, `AuthError`; audit 08 | `test_default_users_and_login` |
| TC-52 | Admin | Add user, reset password, change role, deactivate; deactivated login | All succeed; deactivated user cannot log in | `test_user_management` |
| TC-53 | Users of both roles | `has_permission()` for every permission | Admin all True; employee only its set; inactive → all False | `test_permissions` |

### Categories and scope (FR-6.3, FR-6.4)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-54 | Fresh DB | Read settings | Default category C, scope A–D, thresholds present | `test_defaults_and_settings` |
| TC-55 | — | Add customer | Category = default | `test_new_customer_gets_default_category` |
| TC-56 | Customer | Set B by hand; re-score; set E | Locked, unchanged by re-score; E only manual, never removed by re-score | `test_manual_category_locks_and_e_is_manual_only` |
| TC-57 | Customers incl. one E with huge balance | Re-score with *keep E out* on | E excluded from min/max; others' scores unaffected | `test_defaulters_kept_out_of_score_population` |
| TC-58 | Customers in A–E | Reports with scope *per settings* vs *all* | E rows appear only in *all* | `test_report_scope` |
| TC-59 | Items with last-sale dates 10/60/120/400 days ago | Auto-categorise | A/B/C/D; manual category locked | `test_item_categories` |

### Statements, reminders, backup, search, integrity, migration (FR-2.9, FR-5.4, FR-7.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-60 | Ledger with rows before/in/after range | `statement(customer, from, to)` | Opening balance, rows in range with interest, totals, closing = ledger running balance | `test_statement_rows_and_balances` |
| TC-61 | Shop details saved | Company profile, FY label | Values round-trip; FY "2026-27" | `test_company_profile_and_fy` |
| TC-62 | Details "vill. X, 98765 43210" | `extract_phone()` | "9876543210"; none when absent | `test_extract_phone` |
| TC-63 | Overdue krar | `reminder_text()` | Template filled with name, amount, date; bucket label correct | `test_reminder_text_and_bucket` |
| TC-64 | Auto-backup on, N = 3 | Start app four times on different days | One `hth_auto_<date>.db` per day, oldest pruned; same day → no duplicate | `test_daily_backup` |
| TC-65 | Accounts, items, bills | `search("ram")` | Hits across the three entity types with navigation targets | `test_search_across_entities` |
| TC-66 | DB with planted anomalies | `integrity.findings()` | Each anomaly type reported once (invalid date, negative stock, duplicate, zero amount, lone tag-0, open krar with 0 owed, inactive debtor) | `test_findings` |
| TC-67 | Clean DB | `integrity.findings()` | No errors | `test_clean_database_has_no_errors` |
| TC-68 | Synthetic v3 folder | `migrate_v3` | Customer/item/krar ids preserved; every balance equals v3's for the same date; notes → audit rows | `test_migrate_preserves_ids_and_balances` |
| TC-69 | Non-existent folder | `migrate_v3` | Clear error, nothing written | `test_missing_folder` |
| TC-70 | v3 rows with blank tag, type `X`, date `1/2/24` | `migrate_v3` | Values normalised or skipped and each listed in `migration_report.txt` with table + row id | `test_migration_reports_normalised_values` |

### Bills and Finance modules (FR-8.1, FR-8.3)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-71 | — | Tax for types P / F / S / O on 1000 | 90+90 / 25+25 / 0 / 0 | `test_tax_rates_by_type` |
| TC-72 | — | 1 234.50 in Hindi words | Correct rupees/paise string | `test_hindi_words` |
| TC-73 | Items | Create two bills | Numbers consecutive; DOCX rendered from template; totals = taxable + CGST + SGST | `test_create_bill_numbering_and_render` |
| TC-74 | Month items with totals | Month batch, n bills from start number | Σ line quantities per item = entered total; dates within month; random names, address Dhansu | `test_month_items_and_batch` |
| TC-75 | Batch producing a bill ≥ 20 000 | Month batch | Bill row flagged, not rendered | `test_batch_flags_large_bills` |
| TC-76 | Fresh DB | Finance defaults | Cash account default; standard expense/income heads | `test_defaults` |
| TC-77 | Accounts with openings | Expense, income, transfer, capital, drawings | Running balances and totals per account correct; transfers cancel | `test_accounts_balances_and_cash_book` |
| TC-78 | Customer, money account | Sales-screen receipt (CASH, M) and payment (P) | Cash-book rows linked to ledger rows; stock entries never touch the cash book | `test_sales_screen_money_flow` |
| TC-79 | Recurring rent, day 5 | *Post due now* twice | Entries created once per month, second run idempotent | `test_recurring` |
| TC-80 | Sales with values, crop margin, expenses | Cash flow, P&L | In/out by source and head; P&L = item margin + crop margin + other income − expenses, interest excluded | `test_cash_flow_and_pnl` |

### UI walkthrough (opt-in)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-81 | Display, `HTH_UI_TESTS=1` | Log in as admin; visit every screen; record sale, receipt, krar; open reports; log out; log in as employee; verify edit/delete controls absent | No exception; widgets present per permission matrix; krar table with hidden columns renders | `test_admin_and_employee_walkthrough` |
| TC-82 | Fresh data dir | First run | Wizard appears; default password refused; shop details saved; skip works | `test_first_run_wizard` |

## 6.3 Traceability matrix (requirement → test cases)

| Requirement | Test cases |
|-------------|-----------|
| FR-1.1–1.5 Auth & permissions | TC-51, 52, 53, 81, 82 |
| FR-2.1–2.2 Accounts, entries | TC-07, 08, 09, 19 |
| FR-2.3–2.4 Balance, interest | TC-01–06, 10 |
| FR-2.5–2.6 Settlement, ledger | TC-11–16, 25 |
| FR-2.8 Days / score | TC-17, 18 |
| FR-2.9 Statement | TC-60, 61 |
| FR-3.1–3.4 Items, stock, units | TC-20–35 |
| FR-3.5 Unit change | TC-36–38 |
| FR-3.6 Stock reports | TC-21, 50 |
| FR-4.1–4.5 Sales screen | TC-22–30, 39–43, 78 |
| FR-5.1–5.4 Krar, reminders | TC-49, 62, 63 |
| FR-6.1–6.2 Reports, dashboard | TC-50, 81 |
| FR-6.3–6.4 Categories, scope | TC-54–59 |
| FR-7.1 Audit | TC-19, 22, 23, 49, 51 |
| FR-7.2 Backup | TC-64 |
| FR-7.3 Migration | TC-68–70 |
| FR-7.4 Data check | TC-66, 67 |
| FR-7.5–7.6 Settings, search | TC-61, 65, 82 |
| FR-8.1 Bills | TC-71–75 |
| FR-8.2 Crop trading | TC-39–48 |
| FR-8.3 Finance | TC-76–80 |
| NFR-1 Correctness vs v3 | TC-03, 68 |
| NFR-3 Atomic writes | TC-26, 43 |

## 6.4 Manual acceptance checklist (shop PC)

| Id | Step | Pass criterion |
|----|------|----------------|
| AT-1 | Install the PyInstaller folder, double-click `HighTableHoldings.exe` | Login screen appears within 5 s |
| AT-2 | First-run wizard: shop details, new passwords, point to `C:/JBB/data` | Import completes; `migration_report.txt` opens; backup exists in `backups/` |
| AT-3 | Open five customers the owner knows well; compare balance with v3 for today | Identical to the paisa |
| AT-4 | Record a loose sale (250 G of a KG item) as employee | Stock decreases by 0.25; amount = price × 0.25; audit shows `emp1` |
| AT-5 | As employee, try to delete a ledger row | No delete button; service refuses |
| AT-6 | Settle a customer with a discount | Three tag-0 rows; balance 0; statement prints with shop header |
| AT-7 | Add krar for tomorrow, then WhatsApp reminder | Chat opens with the template text |
| AT-8 | Buy a crop lot, sell part of it | Margin preview equals stored margin; open lots report shows remainder |
| AT-9 | Create a GST invoice and open the DOCX | Amounts, Hindi words and GST match a v3 invoice |
| AT-10 | Reports → Data check | Only known legacy anomalies listed |
| AT-11 | Close, change PC date to tomorrow, reopen | New `hth_auto_<date>.db`; interest uses the new date |
| AT-12 | Resize to 1366×768 | Every button reachable; no overlap |

## 6.5 How to run

```bash
cd HighTableHoldings-v4
pip install -r requirements-dev.txt
pytest -q                                   # 94 passed, 2 skipped
HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py  # opt-in UI walkthrough (needs a display)
ruff check hth tests tools
```
