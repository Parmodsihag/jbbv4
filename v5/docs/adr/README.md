# Architecture decision records

Each record states one significant decision: the situation that forced it, what was
decided, what follows from it, and what else was considered. The format is Michael
Nygard's. Records are numbered in order and never deleted; a decision that changes gets a
new record that *supersedes* the old one.

Records 0002 – 0013 were written on 2026-10-23 from the code, the CHANGELOG, the design
documents and the git history. Their *Date* is when the decision took effect (the release
that shipped it).

| # | decision | status | date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-10-23 |
| [0002](0002-one-sqlite-file-transactional-units.md) | One SQLite file; every unit of work one transaction | Accepted | 2026-08-29 (4.0) |
| [0003](0003-layered-architecture.md) | Layers: ui → services → db / domain | Accepted | 2026-08-29 (4.0) |
| [0004](0004-business-rules-pinned-to-v3.md) | Business rules pinned to v3 by tests; "today" at call time | Accepted | 2026-08-29 (4.0) |
| [0005](0005-forward-only-migrations.md) | Forward-only versioned migrations, backed up first | Accepted, amended 5.0 | 2026-08-29 (4.0) |
| [0006](0006-feature-modules.md) | Feature modules discovered through `ModuleSpec` | Accepted | 2026-08-29 (4.1) |
| [0007](0007-v5-own-data-folder.md) | v5 keeps its own data folder and copies v4 read-only | Accepted | 2026-10-19 (5.0) |
| [0008](0008-english-record-hindi-display.md) | English is the record; Hindi is a display layer | Accepted | 2026-10-20 (5.1) |
| [0009](0009-assistant-two-systems-read-only.md) | Assistant: System 1 always, System 2 optional, read-only | Accepted | 2026-10-20 (5.2) |
| [0010](0010-offline-voice-restricted-vocabulary.md) | Offline voice with a vocabulary limited to the shop's words | Accepted | 2026-10-21 (5.3) |
| [0011](0011-in-app-updates.md) | In-app updates from GitHub, staged and undoable | Accepted | 2026-10-21 (5.4) |
| [0012](0012-two-layouts-one-core.md) | Two layouts over one core | Accepted | 2026-10-20 (5.5) |
| [0013](0013-kept-connections-and-freshness.md) | Kept connections and version-based screen freshness | Accepted | 2026-10-20 (5.6) |

## Writing a new one

Copy the shape below to `NNNN-short-title.md`, add it to the table, and link it from
[ARCHITECTURE.md §10](../ARCHITECTURE.md#10-decisions) when it changes the structure.

```markdown
# NNNN. Title in the imperative

* Status: Proposed | Accepted | Superseded by NNNN
* Date: YYYY-MM-DD

## Context
What forces the decision: the problem, the constraints, the facts.

## Decision
What we will do, stated plainly.

## Consequences
What becomes easier, what becomes harder, what we must now keep doing.

## Alternatives considered
Each option not taken, and why.
```
