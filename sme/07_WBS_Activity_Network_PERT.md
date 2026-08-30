# Chapter 5 — Project planning: WBS, Activity Network, PERT, Gantt

Planning window: **Mon 24 Aug 2026 → Wed 11 Nov 2026** (final submission). Working days
are Mon–Fri; the plan uses **57 working days**, leaving Nov 11 as the submission day.
Team of four; effort figures are calendar working days for the team, not person-days.

## 5.1 Work Breakdown Structure

```mermaid
flowchart TB
  R[High Table Holdings v4]
  R --> W1[1. Project management]
  R --> W2[2. Requirements]
  R --> W3[3. Design]
  R --> W4[4. Implementation]
  R --> W5[5. Testing]
  R --> W6[6. Deployment]
  R --> W7[7. Documentation & deliverables]

  W1 --> W11[1.1 Team setup, Git repo, conventions]
  W1 --> W12[1.2 Planning: WBS, network, PERT]
  W1 --> W13[1.3 Weekly reviews, risk log]

  W2 --> W21[2.1 Study legacy v3 & interview owner]
  W2 --> W22[2.2 Abstract]
  W2 --> W23[2.3 User stories & glossary]
  W2 --> W24[2.4 SRS: FR / NFR]
  W2 --> W25[2.5 Formal: decision tables, algebraic specs]

  W3 --> W31[3.1 Architecture & layering]
  W3 --> W32[3.2 DB schema & migrations]
  W3 --> W33[3.3 DFD / ER / UML models]
  W3 --> W34[3.4 UI/UX: theme, widgets, screens]
  W3 --> W35[3.5 Module extension contract]

  W4 --> W41[4.1 Domain: interest, units, constants]
  W4 --> W42[4.2 Core services: accounts, inventory, sales, krar]
  W4 --> W43[4.3 Auth, permissions, audit]
  W4 --> W44[4.4 UI screens & dashboard]
  W4 --> W45[4.5 Reports & Excel export]
  W4 --> W46[4.6 v3 migration tool & data check]
  W4 --> W47[4.7 Modules: bills, crop trading, finance]
  W4 --> W48[4.8 Ops: backup, wizard, search, statements, reminders]

  W5 --> W51[5.1 Unit tests: business rules]
  W5 --> W52[5.2 Integration tests: sales flow, migration]
  W5 --> W53[5.3 UI walkthrough tests]
  W5 --> W54[5.4 System / acceptance testing with shop data]
  W5 --> W55[5.5 Test-case document & traceability]

  W6 --> W61[6.1 PyInstaller build]
  W6 --> W62[6.2 Install on shop PC, import v3]
  W6 --> W63[6.3 User hand-over]

  W7 --> W71[7.1 README, CHANGELOG]
  W7 --> W72[7.2 Final documentation PDF]
  W7 --> W73[7.3 Screencast video]
  W7 --> W74[7.4 Presentation & Q&A prep]
```

### WBS dictionary (leaf work packages)

| WBS | Work package | Deliverable | Owner |
|-----|--------------|-------------|-------|
| 1.1 | Team setup, Git repo, conventions | Public repo, branch rules, `ruff` config | M4 |
| 1.2 | Planning | This chapter | M4 |
| 2.1 | Study v3, interview owner | Notes on business rules, v3 quirks | M1 |
| 2.2 | Abstract | `TeamNo.pdf` | M1 |
| 2.3–2.4 | User stories, SRS | Chapter 1 | M1 |
| 2.5 | Decision tables, algebraic specs | Chapters 3–4 | M4 |
| 3.1 | Architecture | `hth/` package layout, layering rule | M1 |
| 3.2 | DB schema & migrations | `hth/db/schema.py` | M1 |
| 3.3 | DFD / ER / UML | Chapter 2 | M4 |
| 3.4 | UI/UX | Theme, widgets, wireframes | M2 |
| 3.5 | Module contract | `hth/modules/README.md`, `ModuleSpec` | M3 |
| 4.1 | Domain | `hth/domain/*` | M1 |
| 4.2 | Core services | `hth/services/{accounts,inventory,sales,krar}.py` | M1 |
| 4.3 | Auth, permissions, audit | `hth/services/{auth,permissions,audit}.py` | M1 |
| 4.4 | UI screens | `hth/ui/views/*` | M2 |
| 4.5 | Reports & export | `hth/services/{reports,export}.py`, reports view | M2 |
| 4.6 | Migration & data check | `tools/*.py`, `hth/migration/from_v3.py`, `integrity.py` | M3 |
| 4.7 | Modules | `hth/modules/{bills,crop_trading,finance}` | M3 |
| 4.8 | Ops features | backup, setup wizard, search, statements, reminders | M2/M3 |
| 5.1–5.3 | Automated tests | `tests/` (96 tests) | M4 |
| 5.4 | Acceptance with shop data | Signed-off checklist | M4 + owner |
| 5.5 | Test-case document | Chapter 6 | M4 |
| 6.1–6.3 | Build, install, hand-over | `HighTableHoldings/` folder on shop PC | M3 |
| 7.1–7.4 | Docs, video, PPT | `Documentation.pdf`, video, slides | all |

## 5.2 Activity list with PERT estimates

Three-point estimates in working days: optimistic `o`, most likely `m`, pessimistic `p`;
expected `te = (o + 4m + p) / 6`; variance `σ² = ((p − o) / 6)²`.

| Id | Activity (WBS) | Predecessors | o | m | p | te | σ² |
|----|----------------|--------------|---|---|---|----|----|
| A | Requirements elicitation, study v3 (2.1, 1.1) | — | 3 | 5 | 7 | 5.0 | 0.44 |
| B | Abstract & scope (2.2) | A | 1 | 2 | 3 | 2.0 | 0.11 |
| C | SRS: user stories, FR/NFR, use cases (2.3, 2.4) | B | 4 | 6 | 8 | 6.0 | 0.44 |
| D | Formal specs: decision tables, algebraic (2.5) | C | 3 | 4 | 5 | 4.0 | 0.11 |
| E | Architecture, DB schema, migrations (3.1, 3.2, 3.5) | C | 3 | 4 | 5 | 4.0 | 0.11 |
| F | UI/UX design: theme, widgets, wireframes (3.4) | C | 3 | 5 | 7 | 5.0 | 0.44 |
| G | Domain + core services (4.1, 4.2) | E | 8 | 12 | 16 | 12.0 | 1.78 |
| H | Auth, permissions, audit (4.3) | E | 2 | 3 | 4 | 3.0 | 0.11 |
| I | UI screens, dashboard, reports, export (4.4, 4.5) | F, G, H | 8 | 12 | 16 | 12.0 | 1.78 |
| J | v3 migration tool & data check (4.6) | G | 3 | 4 | 5 | 4.0 | 0.11 |
| K | Modules: bills, crop trading, finance (4.7) | G | 8 | 10 | 15 | 10.5 | 1.36 |
| L | Unit & integration tests (5.1, 5.2) | G, H, J | 4 | 6 | 8 | 6.0 | 0.44 |
| M | UI walkthrough tests, ops features, bug fixing (5.3, 4.8) | I, K | 3 | 5 | 7 | 5.0 | 0.44 |
| N | System / acceptance testing, test-case document (5.4, 5.5) | L, M | 3 | 4 | 5 | 4.0 | 0.11 |
| O | Documentation: DFD, WBS/PERT, compile PDF (3.3, 7.1, 7.2) | D, N | 4 | 6 | 8 | 6.0 | 0.44 |
| P | Video & presentation (7.3, 7.4) | N | 2 | 3 | 4 | 3.0 | 0.11 |
| Q | Build, install on shop PC, final review & submission (6.x) | O, P | 1 | 1 | 1 | 1.0 | 0.00 |

## 5.3 Activity network (activity-on-node)

```mermaid
flowchart LR
  S((Start)) --> A
  A["A  Requirements<br/>5d"] --> B["B  Abstract<br/>2d"]
  B --> C["C  SRS<br/>6d"]
  C --> D["D  Formal specs<br/>4d"]
  C --> E["E  Architecture & schema<br/>4d"]
  C --> F["F  UI/UX design<br/>5d"]
  E --> G["G  Core services<br/>12d"]
  E --> H["H  Auth & permissions<br/>3d"]
  F --> I
  G --> I["I  UI screens & reports<br/>12d"]
  H --> I
  G --> J["J  Migration tool<br/>4d"]
  G --> K["K  Modules<br/>10.5d"]
  G --> L
  H --> L["L  Unit/integration tests<br/>6d"]
  J --> L
  I --> M["M  UI tests, ops, bug fix<br/>5d"]
  K --> M
  L --> N["N  Acceptance & test doc<br/>4d"]
  M --> N
  D --> O["O  Documentation<br/>6d"]
  N --> O
  N --> P["P  Video & PPT<br/>3d"]
  O --> Q["Q  Build & submit<br/>1d"]
  P --> Q
  Q --> X((End<br/>57d))

  classDef crit fill:#f8d7da,stroke:#c0392b,stroke-width:2px,color:#000;
  class A,B,C,E,G,I,M,N,O,Q crit;
```

Red nodes form the **critical path**.

## 5.4 CPM schedule: forward / backward pass

| Id | te | ES | EF | LS | LF | Float | Critical |
|----|----|----|----|----|----|-------|----------|
| A | 5.0 | 0 | 5 | 0 | 5 | 0 | ✓ |
| B | 2.0 | 5 | 7 | 5 | 7 | 0 | ✓ |
| C | 6.0 | 7 | 13 | 7 | 13 | 0 | ✓ |
| D | 4.0 | 13 | 17 | 46 | 50 | 33 | |
| E | 4.0 | 13 | 17 | 13 | 17 | 0 | ✓ |
| F | 5.0 | 13 | 18 | 24 | 29 | 11 | |
| G | 12.0 | 17 | 29 | 17 | 29 | 0 | ✓ |
| H | 3.0 | 17 | 20 | 26 | 29 | 9 | |
| J | 4.0 | 29 | 33 | 36 | 40 | 7 | |
| K | 10.5 | 29 | 39.5 | 30.5 | 41 | 1.5 | |
| I | 12.0 | 29 | 41 | 29 | 41 | 0 | ✓ |
| L | 6.0 | 33 | 39 | 40 | 46 | 7 | |
| M | 5.0 | 41 | 46 | 41 | 46 | 0 | ✓ |
| N | 4.0 | 46 | 50 | 46 | 50 | 0 | ✓ |
| O | 6.0 | 50 | 56 | 50 | 56 | 0 | ✓ |
| P | 3.0 | 50 | 53 | 53 | 56 | 3 | |
| Q | 1.0 | 56 | 57 | 56 | 57 | 0 | ✓ |

**Critical path:** A → B → C → E → G → I → M → N → O → Q, length **57 working days**.

## 5.5 PERT analysis

Variance along the critical path:
`σ² = 0.44 + 0.11 + 0.44 + 0.11 + 1.78 + 1.78 + 0.44 + 0.11 + 0.44 + 0 = 5.67`,
so `σ = 2.38 days`.

| Question | Computation | Result |
|----------|-------------|--------|
| Expected duration | Σ te on critical path | 57 days |
| Probability of finishing within 57 days | z = 0 | 50 % |
| Probability of finishing within 60 days (≈ Nov 13 if we slip past the deadline) | z = (60 − 57)/2.38 = 1.26 | ≈ 90 % |
| Duration with 95 % confidence | 57 + 1.645 × 2.38 | ≈ 61 days |
| Probability of finishing by Nov 10 (56 working days) | z = (56 − 57)/2.38 = −0.42 | ≈ 34 % |

Interpretation and mitigation: the deadline gives 56 working days for a 57-day expected
path, so the plan is tight. Mitigation adopted: (1) G and I, the two largest-variance
activities, are split across two members and started with the domain layer that has the
most tests; (2) D (formal specs) has 33 days of float and P (video) 3 days — they absorb
slack; (3) the acceptance test N is time-boxed; (4) a working prototype is kept on `main`
from the end of G so a partial slip in K (modules, float 1.5) reduces scope, not the
deliverable.

### PERT chart (event-on-arrow view)

```mermaid
flowchart LR
  n0((0<br/>0)) -- "A 5" --> n1((1<br/>5))
  n1 -- "B 2" --> n2((2<br/>7))
  n2 -- "C 6" --> n3((3<br/>13))
  n3 -- "D 4" --> n4((4<br/>17 / 50))
  n3 -- "E 4" --> n5((5<br/>17))
  n3 -- "F 5" --> n6((6<br/>18 / 29))
  n5 -- "G 12" --> n7((7<br/>29))
  n5 -- "H 3" --> n8((8<br/>20 / 29))
  n7 -- "J 4" --> n9((9<br/>33 / 40))
  n7 -- "K 10.5" --> n10((10<br/>39.5 / 41))
  n6 -- dummy --> n11
  n8 -- dummy --> n11
  n7 -- "I 12" --> n11((11<br/>41))
  n8 -- dummy --> n12
  n9 -- "L 6" --> n12((12<br/>39 / 46))
  n10 -- dummy --> n13
  n11 -- "M 5" --> n13((13<br/>46))
  n12 -- dummy --> n14
  n13 -- "N 4" --> n14((14<br/>50))
  n4 -- dummy --> n15
  n14 -- "O 6" --> n15((15<br/>56))
  n14 -- "P 3" --> n16((16<br/>53 / 56))
  n15 -- "Q 1" --> n17((17<br/>57))
  n16 -- dummy --> n17
```
Node label = event number, then earliest time (and latest time when different).

## 5.6 Gantt chart

```mermaid
gantt
  title HTH v4 — SEM 2026-27 schedule (working days, Mon–Fri)
  dateFormat  YYYY-MM-DD
  excludes    weekends
  section Requirements
  A Requirements & v3 study        :crit, a, 2026-08-24, 5d
  B Abstract (due 25 Aug)          :crit, b, after a, 2d
  C SRS                            :crit, c, after b, 6d
  D Decision tables & algebraic    :d, after c, 4d
  section Design
  E Architecture & schema          :crit, e, after c, 4d
  F UI/UX design                   :f, after c, 5d
  section Implementation
  G Core services                  :crit, g, after e, 12d
  H Auth & permissions             :h, after e, 3d
  I UI screens & reports           :crit, i, after g, 12d
  J Migration tool & data check    :j, after g, 4d
  K Modules (bills, crops, finance):k, after g, 11d
  section Testing
  L Unit & integration tests       :l, after j, 6d
  M UI tests, ops, bug fixing      :crit, m, after i, 5d
  N Acceptance & test document     :crit, n, after m, 4d
  section Deliverables
  O Documentation PDF              :crit, o, after n, 6d
  P Video & PPT                    :p, after n, 3d
  Q Build, install, submit         :crit, q, after o, 1d
  Final submission 11 Nov          :milestone, 2026-11-11, 0d
```

## 5.7 Milestones and risk register

| Milestone | Date |
|-----------|------|
| M0 Abstract submitted | 25 Aug 2026 |
| M1 SRS frozen | 9 Sep 2026 |
| M2 Core services pass business-rule tests | 1 Oct 2026 |
| M3 Feature-complete prototype on `main` | 20 Oct 2026 |
| M4 Acceptance sign-off with shop data | 30 Oct 2026 |
| M5 Documentation, video, zip submitted | 11 Nov 2026 |

| # | Risk | P | I | Mitigation |
|---|------|---|---|------------|
| R1 | v4 numbers differ from v3 | M | H | Pin interest and balance against v3 code in tests; migration equivalence test |
| R2 | customtkinter version differences on shop PC (5.2 vs 6.0) | H | M | CI runs UI walkthrough on both; fallbacks for unsupported kwargs |
| R3 | Scope creep from modules | H | M | Modules are optional and behind `ModuleSpec`; core ships first |
| R4 | Team member unavailable | M | M | Owner per WBS package with a named backup; shared conventions |
| R5 | Laptop-resolution layout bugs | M | L | Scrollable panels, minimum row counts, tested at 1366×768 |
| R6 | Data loss during import | L | H | Automatic backup before import; import never guesses silently |
