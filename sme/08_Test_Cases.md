# Chapter 6 — Test cases for the working prototype

## 6.1 Test strategy

The full test plan (risks, techniques, entry / exit criteria, defect management) is
`v5/docs/TEST_PLAN.md`; the latest results are in `v5/docs/TEST_REPORT_5.7.0.md`.

| Level | What | How | Where (`v5/tests/`) |
|-------|------|-----|-------|
| Unit | Domain rules: interest, units, numbers, Hindi words, GST, transliteration, question normalisation | `pytest`, pure functions, pinned against v3 | `test_interest.py`, `test_units.py`, `test_hindi.py`, `modules/test_bills.py`, parts of `test_assistant.py` |
| Integration | Services on an in-memory SQLite: accounts, sales, inventory, krar, auth, categories, statements, modules, assistant tools, updates | `pytest` fixtures build a fresh DB per test; fakes for GitHub and the microphone | `test_*.py`, `modules/*` |
| Migration / data | v3 → v4 equivalence; v4 → v5 first-start copy; atomic migrations; restore | synthetic legacy data, injected failures | `test_migration.py`, `test_v5_fixes.py`, `test_v5_features.py` |
| Regression | one test per fixed defect | reproduce, then fix | `test_v5_fixes.py` and named tests |
| Non-functional | speed without changing figures; WCAG contrast; assistant and voice accuracy | metamorphic (cached = uncached), contrast formula, held-out evaluation | `test_speed.py`, `test_themes.py`, `test_assistant.py`, `test_voice.py` |
| System (UI) | Classic and New layouts, both roles, first-run wizard, Hindi, assistant, voice, updates, on the real window | `HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py tests/test_ui_modern.py` | `test_ui_smoke.py`, `test_ui_modern.py` |
| Acceptance | Manual checklist with the shop's real data on the shop PC | Owner + tester | §6.4 |

Current automated status (5.7.0, 23 Oct 2026; Windows 11, Python 3.10.4, customtkinter
6.0.0): **316 tests, 316 passed** — 282 in the plain run (34 skipped) and the 34 skipped
ones in a second run with `HTH_UI_TESTS=1` and `HTH_VOICE_MODEL` set. Lint and formatting
(`ruff`) clean. v4 had 96 tests; v5 added 220.

Test-case fields: **Id**, requirement traced, precondition, steps / input, expected
result, and the automated test that implements it (or *manual*). TC-01 – TC-82 were
designed for v4 and still run unchanged in v5; TC-83 – TC-166 cover the v5 requirements.

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

### v5: counter, safety and data (FR-9.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-83 | Customer, two items | Save three lines where the third is invalid; then three valid lines; then undo | First save writes nothing; second writes all lines; undo removes every row and restores last prices | `test_record_lines_is_atomic_and_undo_reverses_everything` |
| TC-84 | New layout, customer | Counter › Sale with three lines and *Paid now* 2000 CASH; Ctrl+Enter | Three debits, one credit 2000 with a cash-book receipt; balance after = before + items − 2000 | `test_counter_sale_with_lines_and_paid_now` (UI) |
| TC-85 | CASH receipt saved at the counter | Undo | Ledger row and its cash-book line both removed | `test_undo_money_entry_removes_cash_book_line` |
| TC-86 | A settlement; a crop purchase | Undo each | All three tag-0 rows removed; the lot, ledger credit and stock movement removed | `test_undo_settlement_and_crop_purchase` |
| TC-87 | User `admin` | 5 wrong passwords; the right one; wait 31 s; the right one | Right password refused while waiting; accepted after (username case-insensitive), counter reset; 5 failures audited 08; `verify()` writes no audit | `test_login_lockout_after_repeated_failures` |
| TC-88 | Signed in | Change own password | No *login* audit row written | `test_change_own_password_does_not_log_a_login` |
| TC-89 | Classic Sales screen | Lines, undo, Ctrl+L lock and unlock, date rolls past midnight | Undo works; typed text survives the lock; date fields move to the new day | `test_v5_sales_lines_undo_lock_and_day_change` (UI) |
| TC-90 | Data, a backup | Restore the backup | Checks pass; `hth_before_restore_*` written; data equals the backup; audit 09 | `test_restore_backup_round_trip_with_safety_copy` |
| TC-91 | Debtors with promises and payments | Collections list | Everyone who owes, biggest first, with phone, last payment, promise, status | `test_collections_list` |
| TC-92 | Balances across FYs | Interest by FY | Principal and interest per FY; total equals the interest summary | `test_interest_by_fy_matches_interest_summary` |
| TC-93 | Promises over several weeks | Promised receipts forecast | Overdue first, then by week, with a running total | `test_krar_forecast_buckets` |
| TC-94 | Sales with values; stock | Item profit; reorder suggestions | Margin = sales − cost at today's cost; items whose recent sales use up stock, with days left | `test_item_profit_and_reorder` |
| TC-95 | Bills; entries by two users | GST summary; staff activity | Taxable / CGST / SGST by month and rate; per user days active, sales, receipts, edits, deletes | `test_gst_summary_and_staff_activity` |
| TC-96 | Default passwords; overdue promise | Insights (Needs attention / Today) | Both flagged with the amount at stake | `test_insights_flag_default_passwords_and_overdue` |
| TC-97 | A saved two-bag sale | Counter slip; slip of nothing | Slip shows SALE, the customer, the line, 600.00 and the account balance; an empty slip is refused | `test_counter_slip` |
| TC-98 | v4 folder with `hth.db`, empty v5 folder | First start; second start | v4 data copied through a read-only connection; v4 file byte-for-byte unchanged; nothing copied once v5 has its own database | `test_first_start_copies_v4_database_read_only` |
| TC-99 | Copy forced to fail | First start | No `hth.db`, no temp file left; error shown | `test_failed_copy_of_v4_creates_nothing` |
| TC-100 | Database at an older version; failing migration | Initialize | Database unchanged; pre-migration backup exists; a fresh database takes no backup | `test_failed_migration_leaves_database_untouched`, `test_fresh_database_takes_no_pre_migration_backup` |
| TC-101 | Counter receipt in the cash book | Edit, then delete the ledger row | Cash-book line follows the edit, then is removed | `test_ledger_edits_keep_the_cash_book_in_step` |
| TC-102 | Ledger rows from a crop lot | Edit / delete from the ledger | Refused with a pointer to crop trading | `test_crop_ledger_rows_are_changed_in_crop_trade_only` |
| TC-103 | Farmer and crop with lots | Delete either | Clear refusal instead of a foreign-key error | `test_deleting_a_farmer_or_crop_with_lots_is_refused_cleanly` |
| TC-104 | Settlement with negative rows | Admin edits *Discount* | Accepted | `test_negative_settlement_rows_can_be_edited` |
| TC-105 | A day with a settlement | Day totals | The settlement counted once | `test_day_totals_counts_a_settlement_once` |
| TC-106 | Entries over several FYs | Interest schedule | Sum of the schedule = `calculate_interest` | `test_interest_schedule_adds_up_to_calculate_interest` |
| TC-107 | Accounts owing, in credit, settled | Balance message | Correct wording for each; no "pay Rs −1,000" | `test_balance_message_for_every_kind_of_balance` |

### v5: Hindi (FR-10.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-108 | Language English | `tr()` on any text | Returned unchanged | `test_english_is_untouched` |
| TC-109 | Language Hindi | Phrases, `{}` patterns, composite texts | Every pattern fills; composites translate piece by piece | `test_phrases_patterns_and_segments`, `test_every_pattern_fills` |
| TC-110 | — | Transliterate customer and item names | Expected Devanagari (compound names split, units and brands from the word list) | `test_transliterate_names`, `test_transliterate_items`, `test_names_and_cells` |
| TC-111 | Customer with an automatic and one with a corrected Hindi name | Rename both in English; *Fill missing* | Automatic copy follows; corrected one kept; fill touches only empty copies | `test_hindi_copies_follow_renames_unless_corrected`, `test_fill_missing_only_touches_empty_copies` |
| TC-112 | Language Hindi | Statement, slip, reminder; a date | Hindi names and template; Hindi month and day names | `test_hindi_documents_and_reminders`, `test_hindi_dates` |
| TC-113 | Signed in | Switch to हिन्दी and back | Screens rebuilt in Hindi, then English; no data changed | `test_v5_hindi_switch` (UI) |

### v5: assistant (FR-11.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-114 | — | Questions in Devanagari, Roman Hindi, English | Answer language hi, hi, en | `test_language_follows_the_question` |
| TC-115 | Fixed today | *pichle mahine*, *इस हफ्ते*, *15 tarikh*, *last 30 days*; "may I know" | Correct date ranges; "may" is not a month there | `test_periods`, `test_last_month_dates`, `test_may_is_not_a_month_in_may_i_know` |
| TC-116 | Three customers named Ramesh | *Ramesh ka balance*; answer *rohtak wala* / *2* | Asks back with village / phone; answers for the chosen one; question then forgotten | `test_three_rameshes_are_ambiguous_and_a_village_settles_it`, `test_ask_back_with_names_then_answer_and_forget`, `test_pick_by_number_and_english_answer` |
| TC-117 | — | *chhodo* during an ask-back; question with no name | Cancelled; the missing name is asked for | `test_cancel_clears_the_open_question`, `test_missing_customer_is_asked_for` |
| TC-118 | An answer given | *aur pichle mahine?* within 2 minutes | Same question for the new period | `test_follow_ups_reuse_the_last_question` |
| TC-119 | Employee | Ask for profit | Refused (needs finance reports) | `test_employee_sees_only_what_their_role_allows` |
| TC-120 | — | Ask every kind of question | No row of the books changed; audit 13 has the tool and arguments, not the question text | `test_answers_are_read_only_and_audited_without_the_question` |
| TC-121 | Held-out phrasings (generated, never trained on); typos | Classify; route | Intent accuracy ≥ 88 %, routed answer ≥ 90 %; typos still name the concept | `test_system1_accuracy_on_unseen_phrasings`, `test_typos_still_name_the_concept` |
| TC-122 | Fake System 2 | System 1 unsure; System 2 inside / outside top three | Inside: System 2's intent used; outside: "did you mean" | `test_system2_is_used_only_when_system1_is_unsure`, `test_system2_outside_system1s_top_three_is_asked_back` |
| TC-123 | Model process crashes / model broken | Ask | Only System 2 switched off; System 1 answers | `test_model_runs_in_its_own_process`, `test_a_crashing_model_process_only_switches_system2_off`, `test_broken_model_falls_back_quietly` |
| TC-124 | Model zips with extra files / for another prompt | Install | Only model files taken; wrong-prompt model refused | `test_install_zip_takes_only_model_files`, `test_install_zip_refuses_a_model_for_another_prompt` |
| TC-125 | — | Every tool, both languages | Each answers in English and Hindi | `test_every_tool_answers_in_both_languages` |
| TC-126 | Signed in | Assistant screen: ambiguous question, then a choice | Ask-back card, then the answer card | `test_v5_assistant_chat_asks_back_and_answers` (UI) |

### v5: voice (FR-12.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-127 | Corpus | Spoken forms of Hinglish templates | Every template word has a spoken form; spoken questions classified right | `test_every_hinglish_template_word_has_a_spoken_form`, `test_to_spoken_writes_hinglish_as_a_recogniser_does`, `test_spoken_hinglish_intents` |
| TC-128 | Fake recogniser | Restricted hearing makes no sense | Same audio decoded with the open dictionary | `test_grammar_keeps_known_words_and_unk`, `test_restricted_hearing_falls_back_to_the_open_one` |
| TC-129 | Device list with Stereo Mix; a silent device | Pick automatically; record | Never a loopback device; silence reported with its level | `test_the_microphone_is_never_a_loopback_like_stereo_mix`, `test_a_silent_device_is_reported_with_its_level` |
| TC-130 | Answer cards | Speak | Amounts in Hindi words; ask-back with villages, not phone numbers | `test_answers_are_spoken_in_hindi_words`, `test_ask_back_is_spoken_with_villages_not_phone_numbers` |
| TC-131 | A zip with `../` paths | Install voice model | Nothing written outside the voice folder | `test_install_voice_zip_is_confined_to_the_voice_folder` |
| TC-132 | Real Vosk model, Windows Hindi voice | Synthesise "रमेश का लास्ट मंथ का बैलेंस बताओ", recognise | Heard exactly | `test_real_voice_round_trip` |
| TC-133 | Signed in, fake microphone | F2, speak | Text appears, question sent, answer spoken | `test_v5_assistant_voice_question_is_sent_and_spoken_back` (UI) |

### v5: updates (FR-13.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-134 | — | Compare 5.10.0 with 5.9.3; read a version; hash a blob | 5.10.0 is newer (numeric, not text); version parsed; git blob hash as git computes it | `test_versions_compare_as_numbers` |
| TC-135 | Fake GitHub with two changed files | Check | Only the two listed with the CHANGELOG notes; CRLF copies not re-downloaded; nothing newer → nothing to do | `test_check_lists_only_changed_files_and_the_notes`, `test_crlf_copies_are_not_downloaded_again`, `test_nothing_newer_means_nothing_to_do` |
| TC-136 | Staged update | Start-up | Files replaced, backup zip written, `last.json` ok | `test_stage_then_apply_at_the_next_start` |
| TC-137 | A file with a wrong hash | Install | Nothing staged | `test_a_bad_download_stages_nothing` |
| TC-138 | Copy fails half-way | Apply | Every file back as before | `test_a_failure_while_applying_rolls_everything_back` |
| TC-139 | Applied update | Undo last update, restart | Previous files back | `test_undo_puts_the_old_files_back` |
| TC-140 | Paths `../evil.py`, `/abs.py`, `C:/x.py`, `a/../../b.py`, `.git/config`; a file dropped upstream | Apply | Unsafe paths never written; dropped file removed | `test_unsafe_paths_are_never_written`, `test_files_dropped_upstream_are_removed_on_the_next_update` |
| TC-141 | A git checkout | Update | `git pull --ff-only` | `test_a_git_checkout_is_updated_with_git` |
| TC-142 | No network | Check | Clear error, nothing changed | `test_github_unreachable_is_a_clear_error` |
| TC-143 | Bundled voice zip | First Assistant open; zip changes; manual model present | Unpacked once; refreshed when changed; manual model left alone; repository ships the zip | `test_the_bundled_voice_model_is_set_up_once_and_refreshed_when_it_changes`, `test_a_model_installed_in_settings_is_left_alone`, `test_the_repository_ships_the_voice_model` |
| TC-144 | Signed in as admin, fake GitHub | Settings › Updates › Check, Install | Version and notes shown; files staged | `test_v5_settings_updates_check_and_download` (UI) |

### v5: interface (FR-14.x)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-145 | Fresh database | Read layout; list areas | Default *new*, shop-wide; New holds every classic screen; module reports named as their screens | `test_layout_preference_is_shop_wide_and_defaults_to_new`, `test_new_layout_areas_hold_every_classic_screen`, `test_module_report_names_match_their_screens` |
| TC-146 | New layout | Sign in as admin / employee; old Alt keys | Admin on Today, employee on Counter; no admin screens for the employee; every key finds its area | `test_admin_lands_on_today_and_old_keys_find_their_area`, `test_employee_lands_on_counter_and_sees_no_admin_screens` |
| TC-147 | Signed in | Switch New → Classic → New; sign out and in | Works both ways; layout kept | `test_switch_both_ways_while_signed_in`, `test_signing_out_and_in_keeps_the_shop_layout` |
| TC-148 | Customer owing 1000 with an open promise | Counter › Payment in 400 (promise *kept* ticked); then 500 with *Settle*; then Ctrl+Shift+Enter on Sale | Balance 600 and promise kept; then balance 0 (three tag-0 rows); the sale shortcut saves nothing | `test_counter_payment_in_keeps_the_promise_and_settles` |
| TC-149 | Crop item | Counter › Purchase with gross / kaat / quality | Lot created; farmer credited | `test_counter_crop_purchase_makes_a_lot` |
| TC-150 | Customers, promises | Khata page; delete an entry; Collections chips; as employee | New balance stated before delete; buckets right; no admin actions for the employee | `test_khata_customer_page_and_a_careful_delete`, `test_khata_collections_buckets_and_side_panel`, `test_khata_for_an_employee` |
| TC-151 | Overdue promise, low stock, no backup | Today | Each listed with its button | `test_today_lists_what_needs_doing` |
| TC-152 | Data | Stock, Money, Reports, Settings areas, both roles | Items page, crops hosted; cash book, bills; catalogue with pins; sections per role | `test_stock_items_page_and_crops_hosted`, `test_money_cash_book_bills_and_reports`, `test_money_for_an_employee`, `test_reports_catalogue_pins_and_opening`, `test_reports_for_an_employee`, `test_settings_sections` |
| TC-153 | Seven themes | Check every token and contrast, light and dark | Complete; body text ≥ 7:1, other text ≥ 4.5:1 | `test_every_theme_defines_every_token`, `test_theme_is_readable_in_both_modes` |
| TC-154 | Screens open | Change colour theme | Recoloured in place, nothing rebuilt; customtkinter defaults follow; preference saved | `test_switching_rewrites_the_shared_lists_in_place`, `test_colour_themes_recolour_every_screen_in_place`, `test_ctk_defaults_follow_the_palette`, `test_colour_theme_preference` |
| TC-155 | — | Format 1234567 in each style; change the setting | 12,34,567.00 / 1,234,567.00 everywhere | `test_indian_and_international_grouping`, `test_number_style_preference_applies_globally` |
| TC-156 | — | Text size 1.3; then 2.0 | 1.3 saved and read back; 2.0 refused | `test_text_scale_preference` |
| TC-157 | "ram rohtak" | Search | Matches all words in any order, exact id first | `test_rank_matches_any_word_order`, `test_customer_search_matches_all_words` |
| TC-158 | Employee | Open Data check through a link | Refused | `test_v5_employee_cannot_open_admin_reports_by_link` (UI) |
| TC-159 | Classic dashboard | Switch light / dark | Charts redrawn, no "Something went wrong" (5.7.0 fix) | `test_v5_light_dark_switch_on_the_dashboard_charts` (UI) |
| TC-160 | New layout | Type a question in the Ask bar | Handed to the assistant | `test_ask_bar_hands_questions_to_the_assistant` (UI) |
| TC-161 | Classic | Quick CASH / UPI / BANK, slip, F1; ledger periods, snapshot | Behave as specified | `test_v5_quick_money_slip_and_shortcuts`, `test_v5_ledger_views_and_snapshot` (UI) |

### v5: performance without changing figures (NFR-1, NFR-15)
| Id | Precondition | Input / steps | Expected | Automated by |
|----|--------------|---------------|----------|--------------|
| TC-162 | Database | Commit, roll back, read | `version` moves only on a commit | `test_version_moves_on_committed_changes_only` |
| TC-163 | Two threads | Write in one, read in the other; finish a thread | Each keeps its connection and sees the other's writes; finished threads give it back | `test_each_thread_keeps_its_connection_and_sees_the_others_writes`, `test_finished_threads_give_their_connection_back` |
| TC-164 | Shop-like data | Balances and interest with and without caches | Bit-for-bit identical; bad dates still rejected | `test_parse_date_is_cached_but_still_strict`, `test_cached_periods_give_bit_for_bit_the_same_interest`, `test_balances_unchanged_by_the_caches` |
| TC-165 | Screen filled | Return with no write, same day; after a write; next day | No query; reload; reload | `test_freshness_follows_writes_and_the_date`, `test_coming_back_to_an_unchanged_screen_reads_nothing`, `test_collections_chips_switch_without_reading_again`, `test_reports_search_shows_and_hides_the_rows_it_built` |
| TC-166 | Default users | Today visited repeatedly | Default-password check hashes once per stored password | `test_default_password_check_hashes_once_per_stored_password` |

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
| FR-9.1–9.3 Lines, paid-now, undo | TC-83–86, 89 |
| FR-9.4–9.5 Lockout, screen lock | TC-87, 88, 89 |
| FR-9.6 Restore | TC-90 |
| FR-9.7 New reports | TC-91–95 |
| FR-9.8 Today / Needs attention | TC-96, 151, 166 |
| FR-9.9 Slip | TC-97, 161 |
| FR-9.10 First-start copy of v4 | TC-98, 99 |
| FR-9.11 Atomic migrations | TC-100 |
| FR-9.12 Cash book follows ledger; crop rows | TC-101–104 |
| FR-10.1–10.4 Hindi | TC-108–113 |
| FR-11.1–11.7 Assistant | TC-114–126 |
| FR-12.1–12.4 Voice | TC-127–133 |
| FR-13.1–13.5 Updates | TC-134–144 |
| FR-14.1–14.2 Layouts, Counter | TC-145–152, 160 |
| FR-14.3 Themes | TC-153, 154, 159 |
| FR-14.4 Number style, text size | TC-155, 156 |
| FR-14.5 Shortcuts, search | TC-157, 161 |
| NFR-1 Correctness vs v3 / v4 | TC-03, 68, 106, 164 |
| NFR-3 Atomic writes | TC-26, 43, 83, 100 |
| NFR-5 Security | TC-51–53, 87, 119, 140, 158 |
| NFR-12 Accessibility | TC-153 |
| NFR-13 Privacy | TC-120 |
| NFR-14 Assistant quality | TC-121, 132 |
| NFR-15 Performance | TC-162–166 |

Every FR in Chapter 1 has at least one test case; FR-9.5's idle timer and FR-12.3's voice
on real speakers are also checked by hand (AT-15, AT-17).

## 6.4 Manual acceptance checklist (shop PC)

Run on the shop PC with a **copy** of the shop's data, by the owner with the tester, after
the release is installed through Settings › Updates. Record pass / fail and notes in the
test report.

| Id | Step | Pass criterion |
|----|------|----------------|
| AT-1 | Double-click *Start High Table Holdings v5* | Sign-in screen within 5 s, no console window |
| AT-2 | First start on a PC with v4 data (or *Run setup wizard*) | v4's data appears in v5; `C:\JBB4\hth.db` unchanged; wizard refuses default passwords |
| AT-3 | Open five customers the owner knows well; compare with v4 / paper for today | Balances identical to the paisa |
| AT-4 | As employee, Counter › Sale: three lines incl. 250 G of a KG item, *Paid now* 500 cash, print slip | Stock −0.25 KG; khata gets items − 500; cash book +500; slip prints; audit shows `emp1` |
| AT-5 | As employee, try to delete a ledger row and open Data check | No delete, no admin report |
| AT-6 | Ctrl+Z within 15 minutes of AT-4 | Every row of AT-4 gone; stock and cash back |
| AT-7 | Payment in with *Settle the account* | Three tag-0 rows; balance 0; statement prints with shop header |
| AT-8 | Collections › Late › WhatsApp | Chat opens with the reminder text; *Got payment* records it |
| AT-9 | Create a GST invoice; *Save & make PDF* (Word installed) | DOCX and PDF; amounts, Hindi words and GST match a v4 invoice |
| AT-10 | Crop purchase lot with kaat, then a part sale | Margin preview equals stored margin; open lots show the remainder |
| AT-11 | Reports › Data check; Reports catalogue search "aging", pin it | Only known legacy anomalies; pinned report stays on top |
| AT-12 | Text size 90 % and 130 % on the shop's 1366 × 768 screen | Every button reachable; nothing overlaps |
| AT-13 | Switch to हिन्दी, make a sale, print a statement; switch back | Hindi screens, names and statement; English back, nothing lost |
| AT-14 | Ask *sabse bade 5 bakayedar*, *Ramesh ka balance* (two Rameshes) | List in Hindi; asked "कौन से रमेश?"; right answer after choosing |
| AT-15 | F2 with the shop's microphone: *yuria kitna bacha hai* | Words appear; stock answer shown and spoken in Hindi |
| AT-16 | Wrong password five times | Sixth attempt told to wait 30 s; failures in the audit log |
| AT-17 | Auto-lock 1 minute; leave a half-typed sale; wait | Screen locks; after unlocking the typed text is still there |
| AT-18 | Settings › Backup now; Restore that backup | Restore shows counts; `hth_before_restore_*` written; everyone signed out |
| AT-19 | Settings › Updates › Check (with a newer version on `v5`); Install; Restart; Undo last update | New version runs; undo returns the previous one; data unchanged |
| AT-20 | Switch layout to Classic and back to New; try three colour themes, light and dark | Same data in both; every theme readable in daylight |

## 6.5 How to run

```bash
cd v5
pip install -r requirements-dev.txt
pytest -rs                                                   # 282 passed, 34 skipped (UI and real voice)
HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py tests/test_ui_modern.py   # 33 UI tests, ~5 min
HTH_VOICE_MODEL=C:/JBB/v5/voice/vosk-model-small-hi-0.22 pytest tests/test_voice.py::test_real_voice_round_trip
ruff check hth tests tools && ruff format --check hth tests tools
```

In PowerShell set variables with `$env:HTH_UI_TESTS = "1"` before `pytest`.
