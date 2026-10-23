# Chapter 7 — Project management plan

How the project is organised, controlled and measured. Planning (WBS, activity network,
PERT, Gantt) and the risk register are in Chapter 5; testing in Chapter 6 and
`v5/docs/TEST_PLAN.md`.

## 7.1 Project charter (summary)

| | |
|---|---|
| Purpose | Replace the shop's legacy accounting tool (v3.7.1) with a tested, layered, multi-user program that gives the same figures, then extend it with what the shop asks for. |
| Customer | The owner of Jaat Beaj Bhander, an agri-input shop (fertiliser, seed, pesticide) that also buys crops. |
| Other stakeholders | Shop staff (users), farmers and buyers (receive statements, slips, reminders), the course instructor (evaluator), the team. |
| Objectives | O1 every balance and interest figure identical to v3 (then v4); O2 no data loss: atomic writes, backups, undo, restore; O3 counter work in shop words, in English or Hindi; O4 runs offline on the shop's Celeron PC; O5 complete SE artefacts and a public repository by 11 Nov 2026. |
| Success criteria | All automated tests pass; owner's acceptance checklist passes on the shop PC; figures checked identical on the shop's data; deliverables submitted on time. |
| Constraints | One shop PC; Python + customtkinter; four-member team; course deadlines 25 Aug (abstract) and 11 Nov (final). |
| Out of scope | Cloud sync, mobile app, payment gateway, an assistant that changes data. |

## 7.2 Process model

**Iterative and incremental**, with two increments and a release at the end of every
iteration:

| increment | releases | content |
|---|---|---|
| v4 | 4.0.0 – 4.7.0 (11 releases) | re-engineering of v3 with the same rules; modules bills, crop trading, finance; categories; statements; reminders; backups; wizard |
| v5 | 5.0.0 – 5.7.0 (9 releases) | safety, counter speed, Hindi, assistant, voice, in-app updates, New layout, performance, colour themes |

Within an iteration the business rules are developed **test-first**: the expected figures
come from v3's code or by hand, the test is written, then the service. Large changes are
split into phases that each leave the program working (the New layout went in as phases
0 – 6, one area per commit, each with its UI tests). Design-heavy features (the assistant,
voice) get a written design for review before code (`v5/docs/AI_CHAT_DESIGN.md`,
`VOICE_DESIGN.md`), and the decisions are recorded (`v5/docs/adr/`).

Why this model: the customer can only judge the program by using it; every release is
installable through the in-app updater and can be undone, so feedback arrives quickly and a
bad release is cheap to reverse. The plan-driven part (WBS, PERT) is kept for the course
deliverables and the deadline (Chapter 5).

## 7.3 Organisation and responsibilities

Roles: **M1** requirements & core, **M2** UI/UX & localisation, **M3** modules, data &
operations, **M4** quality & management (see the contributions table on the first page).
The shop owner is the customer and the acceptance tester.

RACI (R responsible, A accountable, C consulted, I informed):

| Activity | M1 | M2 | M3 | M4 | Owner |
|---|---|---|---|---|---|
| Requirements, SRS | A/R | C | C | C | C |
| Formal specs (decision tables, algebraic) | C | | C | A/R | |
| Architecture and decision records | A/R | C | C | R | |
| Domain rules, core services | A/R | | C | C | I |
| Screens, layouts, Hindi | C | A/R | C | C | C |
| Modules, importer, updates | C | C | A/R | C | I |
| Assistant and voice | C | C | A/R | C | C |
| Test plan, test cases, test report | C | C | C | A/R | |
| Acceptance testing | I | I | C | A/R | R |
| Release to the shop | C | C | R | A | I |
| Planning, tracking, risks | C | C | C | A/R | |
| Video, presentation | R | R | R | A/R | |

## 7.4 Communication plan

| What | Who | When | Channel | Output |
|---|---|---|---|---|
| Stand-up: done, next, blocked | team | twice a week | team chat / call | updated task list |
| Design review | team + reviewer | before a design-heavy feature | design document in `v5/docs/` | decisions, then an ADR |
| Code review | author + one reviewer | every pull request | GitHub pull request | approved PR |
| Demo to the owner | M3 / M1 + owner | after each minor release | at the shop | feedback, change requests |
| Release note | maintainer → shop | every release | `CHANGELOG.md`, shown by the updater | — |
| Progress against plan | M4 → team | weekly | Chapter 5 §5.8 | variance, risks |
| Defects | anyone | when found | GitHub issue with severity | fix + regression test |

## 7.5 Configuration and change management

**Configuration items** under version control in one public Git repository
(`github.com/Parmodsihag/jbbv4`): source (`v5/hth`), tests (`v5/tests`), tools
(`v5/tools`), the bill template (`invoice.docx`), the bundled voice model (with its SHA-256
in `bundled/voice/README.md`), requirements files, the CHANGELOG, all documentation
(`v5/docs`, `sme/`). The shop's data is **not** a configuration item: it lives outside the
repository in `C:\JBB\v5`.

**Identification.** Semantic version in `hth/__init__.py` and `pyproject.toml`; database
schema version in `PRAGMA user_version`; release tags `v<version>`; snapshot tag
`v4-snapshot-2026-10-19` taken before the v5 work.

**Baselines.** `main` is the integration baseline; `v5` is the released baseline the shop
installs from. A release is promoted by a pull request `main → v5`
(`v5/docs/RELEASING.md`).

**Change control.** A change request (from the owner, a defect or the team) is recorded as
an issue, assessed for its effect on the numbers, the data and the plan, and accepted or
deferred by M1 (scope) and M4 (schedule). Rules that cannot be changed by a request alone:
interest rate, year end, settlement rows (a decision record and a test change are needed).

| CR | Request | Source | Impact | Decision | Release |
|----|---------|--------|--------|----------|---------|
| CR-1 | Bills and crop trading back as modules | owner | scope +; plan float on K | accepted | 4.1, 4.2 |
| CR-2 | Cash book, expenses, P&L | owner | new module, migration 5 | accepted | 4.5 |
| CR-3 | Categories A–E; keep defaulters out of reports | owner | migration 4 | accepted | 4.4 |
| CR-4 | Safety: lock, restore, undo; separate v5 folder | owner / team | migration safety, new data folder | accepted | 5.0 |
| CR-5 | Whole program in Hindi | owner | every screen; migration 6 | accepted, English stays the record | 5.1 |
| CR-6 | Ask questions in plain language, then by voice | owner | new package; optional model | accepted, read-only only | 5.2, 5.3 |
| CR-7 | Updates without a technician | owner | updater; data untouched | accepted | 5.4 |
| CR-8 | Screens in shop words | owner | second layout | accepted, Classic kept | 5.5 |
| CR-9 | Assistant that records entries | owner | writes to the books by voice | **deferred** (risk of wrong entries; needs confirmation design) | — |
| CR-10 | Market-rate feed from a mandi website | owner | network dependency | **deferred** (interface ready: `RateProvider`) | — |

## 7.6 Quality management

| Practice | How it is applied |
|---|---|
| Standards | Layering rule, coding standards and definition of done in `CONTRIBUTING.md`; `ruff` lint and format; Hindi entry for every on-screen string |
| Reviews | Pull-request review against the definition of done; design reviews for the assistant and voice; documentation checked against the code before submission |
| Testing | Risk-based test plan; oracle tests against v3; fault injection for atomicity; regression test for every fix; UI walkthroughs; owner acceptance |
| Verification of figures | Before releases that touch the books: every balance, day count, score and the interest summary compared with the previous version on a copy of the shop's data (done for 5.0 and 5.6) |
| Release discipline | Checklist in `v5/docs/RELEASING.md`; updates verified by hash; undo available |
| Records | CHANGELOG per release; test report per release; decision records; audit log in the program |

## 7.7 Metrics

| Metric | v4 (4.7.0) | v5 (5.7.0) |
|---|---:|---|
| Application code (`hth/`, lines) | 13,336 | 31,079 (112 files) |
| Test code (`tests/`, lines) | 2,065 | 5,025 (28 files) |
| Automated tests | 96 | 316 (all passing) |
| Tools (`tools/`, lines) | — | 4,173 |
| Database tables / migrations | 20 / 5 | 20 / 6 |
| Reports | 16 core (+ module reports) | 34 in one catalogue |
| Releases | 11 (4.0.0 – 4.7.0) | 9 (5.0.0 – 5.7.0) |
| Defect fixes listed in the CHANGELOG | 3 fix entries (4.0.1, 4.1.1, 4.2.0) | 22 (14 of them in 5.0.0) |
| Hindi phrase table | — | `hi.py`, 850 lines (~1,100 phrases) |
| Dashboard / account list on 663 accounts | 4.8 s | 0.1 s |
| Assistant intent accuracy, unseen phrasings | — | 95–96 % (System 1) |
| Voice questions answered right, held-out set | — | 99.3 % clean, 95.3 % with noise |

The test-to-code ratio stayed at about 0.15–0.16 lines of test per line of code while the
code more than doubled. Regression tests for the v5 fixes are collected in
`tests/test_v5_fixes.py` and in named tests beside their features.

## 7.8 Risk management

Risks are identified at planning and at every review, rated by probability and impact
(L / M / H), given an owner and a response (avoid, reduce, transfer, accept), and reviewed
weekly. The register is in Chapter 5 (§5.7 baseline, §5.11 updated 23 Oct). The two risks
that occurred: **R3 scope creep** (handled by change control and shippable increments) and
**R2 toolkit version differences** (a customtkinter 5.2 argument error in 4.2.0, fixed with
a fallback and covered by the UI walkthrough).

## 7.9 Lessons learned

| What went well | Why | Keep doing |
|---|---|---|
| Balances and interest stayed identical to v3 / v4 (checked for 4.0, 5.0 and 5.6) | interest in one function pinned to v3; same-figures checks | pin rules to an oracle before refactoring |
| Big features shipped without breaking the shop | phases, both layouts kept, undoable updates | small reversible steps |
| Fast feedback from the owner | in-app updates; release notes in the shop's words | release often |

| What was harder | Effect | Action |
|---|---|---|
| UI tests are opt-in and slow | UI regressions found late (the 4.1.1 layout bug, the 5.7.0 chart focus bug) | run them in every release checklist; add CI for the rest |
| Scope grew a lot in v5 | documentation fell behind the code until 23 Oct | doc updates are part of the definition of done |
| No coverage measurement | untested branches are unknown | add `pytest-cov`, report per release |
| The ER diagram drifted from the schema | wrong column names in the v4 pack | data dictionary generated from / checked against `schema.py` |

## 7.10 Deliverables status (23 Oct 2026)

| Deliverable (guidelines §5) | Status |
|---|---|
| Source code in a public Git repository | done: `github.com/Parmodsihag/jbbv4` (v5.7.0 on `main` and `v5`) |
| Documentation: team page, SRS, decision tables, algebraic specs, DFD, activity network, WBS, PERT, test cases | updated to v5.7 (this pack); team names and contributions to fill in; PDF build pending (activity X) |
| Video (2–3 min, compile and deploy, features) | script ready (`09_Video_Script.md`); recording pending (activity Y) |
| PPT + Q&A | outline ready (`10_Presentation_Outline.md`); slides pending (activity Z) |
| `TeamNo.zip` on Nalanda | pending (activity Q), target 5 Nov |
