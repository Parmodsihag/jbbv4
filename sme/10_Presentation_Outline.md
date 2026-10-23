# Presentation outline (PPT + Q&A)

Aim for 13 slides / 10 minutes, one speaker per section so every member presents.

| # | Slide | Content | Speaker |
|---|-------|---------|---------|
| 1 | Title | Project, course, Team No., members, Git URL | M1 |
| 2 | Problem | Credit-based agri-input shop: interest periods, promises (karar), crop buy-back, GST; legacy v3 pain points (one table per customer, no users, no tests, frozen "today" bug) | M1 |
| 3 | Objectives & scope | Same numbers as v3; multi-user; one DB; tests; modules; then the v5 increment (safety, Hindi, assistant, voice, updates, shop-word screens). Out of scope | M1 |
| 4 | Process | Iterative & incremental (v4: 11 releases, v5: 9), test-first business rules, phased delivery, design reviews and decision records; change control (CR log) | M4 |
| 5 | Requirements | Use cases (v4 + v5), top FRs (FR-2 ledger, FR-9 counter & safety, FR-11 assistant), NFRs (correctness, atomicity, privacy, accessibility) | M1 |
| 6 | Formal specs | DT-17 (which answer the assistant gives) or DT-2 (sales validation) + the LEDGER spec with the settlement invariant and ENTRY's undo axiom | M4 |
| 7 | Design | Architecture (layers, modules, assistant), ER diagram, ADRs: one SQLite file, English-as-record, in-app updates | M2 |
| 8 | Data flow | DFD level 1 and the level-2 DFDs for *Record transaction* and *Answer question* | M2 |
| 9 | Planning & tracking | Baseline WBS / critical path (57 days), plan vs actual, the re-baselined PERT to submission (8.3 days, σ 0.9, 97 % by 5 Nov), risk register | M4 |
| 10 | Implementation | New layout screens (Today, Counter, Khata), Hindi, assistant and voice; stats: 31 k lines, 20 tables, 34 reports, 316 tests | M2/M3 |
| 11 | Testing | Strategy and levels, oracle against v3, fault injection, traceability excerpt, 316/316 passing, acceptance checklist | M3 |
| 12 | Demo | 60-second live demo (or the video): a sale with paid-now, undo, a spoken question | M3 |
| 13 | Conclusion | Lessons learned, deferred CRs (assistant that records entries, mandi rate feed), future work (CI, coverage, phone field) | M4 |

## Likely Q&A and prepared answers

| Question | Answer |
|----------|--------|
| Why not a web app? | One shop PC, unreliable internet, data must stay offline; a desktop app with SQLite keeps deployment to a folder copy. The services have no UI dependency, so a web or bot front-end could be added. |
| How do you know the numbers match v3? | The interest function is pinned against v3's code (`test_matches_v3`); the migration test imports a synthetic v3 folder and asserts identical balances; v5 was checked byte-for-byte against v4 on the shop's data; every speed-up has a "same figures" test. |
| What is compounded on 31 March? | Accrued simple interest is added to the principal at the financial-year end; the next year's interest is on the larger amount (INTEREST axiom I5). |
| Why three rows on settlement? | To keep v3's ledger format: the entry, the balance being settled and the discount (negative on overpayment). The invariant `bal(settle(L)) = 0` is tested. |
| How is atomicity guaranteed? | `Database.connect()` is a transaction-scoped, re-entrant context; a multi-line sale and its payment are one block. Tests inject a failure and check nothing was written (ENTRY axiom E2). |
| How does undo work? | The save returns what it wrote; undo deletes exactly those rows and restores last prices, in one transaction, within 15 minutes (E6). Balances are derived, so nothing else needs fixing. |
| Isn't an AI assistant risky for accounts? | It never writes numbers: it only picks one of 25 read-only queries that the reports already use. Names are matched against the shop's own records and asked back when ambiguous; the optional model is trusted only if it agrees with one of the classifier's top three (DT-17). |
| Does any data leave the PC? | No. Recognition, classification and speech are offline; the only network use is the update check. The audit log keeps the tool used, not the question. |
| How are updates safe? | Only changed files, each checked against GitHub's hash; applied before the program loads, with the old files zipped and put back on any error; undo available; the data folder is never touched (UPDATE spec). |
| How did the plan compare with reality? | Implementation finished well ahead of the baseline because the rules were built test-first against v3; the slack went to an accepted scope change (v5). The remaining work was re-baselined with PERT: 8.3 days expected, target 5 Nov against an 11 Nov deadline. |
| What was hardest? | Reproducing v3's quirks while deciding which to keep (negative discount rows) and which to fix (frozen date, truncated quantities); making Hindi work without touching the values the code compares; voice on a weak PC. |
| How would you extend it? | A `ReportSpec` for a report, a `ModuleSpec` package for a feature, a `Tool` plus templates for a new question, a `RateProvider` for a market-rate API; each has a how-to in `CONTRIBUTING.md`. |
| Individual contributions? | Refer to the first page of the documentation. |
