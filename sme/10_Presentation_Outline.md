# Presentation outline (PPT + Q&A)

Aim for 12 slides / 8–10 minutes, one speaker per section so every member presents.

| # | Slide | Content | Speaker |
|---|-------|---------|---------|
| 1 | Title | Project, course, Team No., members, Git URL | M1 |
| 2 | Problem | Credit-based agri-input shop; interest periods, krar, crop buy-back, GST; legacy v3 pain points (one table per customer, no users, no tests, frozen "today" bug) | M1 |
| 3 | Objectives & scope | Same numbers as v3; multi-user; one DB; tests; modules. Out of scope | M1 |
| 4 | Process | Iterative + TDD on Git; artefacts: SRS → decision tables / algebraic specs → DFD → WBS/PERT → tests; changelog & semver | M4 |
| 5 | Requirements | Use-case diagram; top FRs; NFRs (correctness, atomicity, portability) | M1 |
| 6 | Formal specs | One decision table (Sales entry) + the LEDGER algebraic spec with the settlement invariant | M4 |
| 7 | Design | Architecture diagram (layering rule), ER diagram, module contract | M2 |
| 8 | Data flow | DFD level 1 and level 2 for *Record transaction* | M2 |
| 9 | Planning | WBS, activity network with critical path (57 days), PERT probability, Gantt | M4 |
| 10 | Implementation | Screens (dashboard, sales, ledger, karar, reports), modules (bills, crops, finance); stats: ~13 k lines Python, 20 tables, 16 reports, 96 tests | M2/M3 |
| 11 | Testing | Strategy pyramid, traceability matrix excerpt, `pytest` output, acceptance checklist with real shop data | M3 |
| 12 | Demo & conclusion | 60-second live demo (or the video), lessons learned, future work (rate feed API, cash-flow forecast, GST summary) | M3 |

## Likely Q&A and prepared answers

| Question | Answer |
|----------|--------|
| Why not a web app? | The shop has one PC, intermittent internet and needs the old data offline; a desktop app with SQLite keeps deployment to a folder copy. The services layer has no UI dependency, so a web front-end could be added later. |
| How do you know the numbers match v3? | The interest function is pinned against v3's code by `test_matches_v3`; the migration test imports a synthetic v3 folder and asserts identical balances per customer; acceptance step AT-3 compares real customers on the shop PC. |
| What is compounded on 31 March? | Accrued simple interest is added to the principal at the financial-year end and the next year's interest is computed on the larger amount (spec INTEREST axiom I5). |
| Why three rows on settlement? | To preserve the v3 ledger format: the entry, the balance being settled and the discount (which may be negative on overpayment). The invariant `bal(settle(L)) = 0` is tested. |
| How is atomicity guaranteed? | `Database.connect()` is a transaction-scoped, re-entrant context; a sale's ledger, stock, cash-book and audit rows are written in one `with db.connect()` block. `test_sale_is_atomic` injects a failure and checks nothing was written. |
| How are permissions enforced? | A single declarative matrix (`ROLE_PERMISSIONS`); views hide controls and services refuse calls; tested for both roles and for inactive users. |
| What did the PERT analysis tell you? | Expected 57 working days against 56 available — about a one-in-three chance of finishing on the expected path alone, so we kept a working prototype on `main` from mid-project and treated modules as scope that can shrink. |
| What was hardest? | Reproducing v3's quirks (frozen "today", negative discount rows, whole-number truncation) while deciding which to keep (rows) and which to fix (date, truncation), and documenting each decision. |
| How would you extend it? | Add a `ReportSpec` for a report, a `ModuleSpec` package for a feature, a `RateProvider` for a market-rate API; each has a test template. |
| Individual contributions? | Refer to the first page of the documentation. |
