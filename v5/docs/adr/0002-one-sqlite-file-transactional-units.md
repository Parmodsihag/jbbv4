# 0002. One SQLite file; every unit of work one transaction

* Status: Accepted
* Date: 2026-08-29 (4.0.0)

## Context

v3 kept its data in five SQLite files with one table per customer, per item and per day,
opened one global connection per file at import time and shared a cursor across the whole
program. A sale touched the customer's table, the item's table and the day's notes
separately: a crash between them left the books inconsistent, and nothing could be rolled
back. The shop has one PC, one user at a time, no server and no administrator.

## Decision

* All data lives in **one SQLite database**, `hth.db`, with a normalised schema: one
  ledger table for every customer, one movements table for every item, foreign keys on.
* `Database.connect()` is a context manager that hands out a connection for one **unit of
  work**. The outermost block commits or rolls back. Nested blocks on the same thread reuse
  the outer connection, so a service that calls other services (a sale touches accounts,
  inventory, the cash book and the audit log) commits once, atomically.
* WAL journal mode; a 10-second busy timeout so a background read does not fail a write.
* Derived figures (balances, interest, stock, cash-book balances) are computed from rows,
  never stored.

## Consequences

* A sale is all or nothing; tests inject a failure and check nothing was written
  (`test_sale_is_atomic`, `test_crop_trade_is_atomic`,
  `test_record_lines_is_atomic_and_undo_reverses_everything`).
* Backup and restore are a consistent copy of one file through SQLite's backup API.
* No stored balance can disagree with its rows; the cost is computing them, which is why
  the balance query was rewritten as one ordered pass in 5.0 (4.8 s → 0.1 s).
* SQLite allows one writer at a time. That fits one shop PC; several PCs writing at once
  would need a server database.

## Alternatives considered

* **Keep v3's files.** No atomicity, no foreign keys, one table per customer.
* **A server database (PostgreSQL, MySQL).** Needs installing and administering on the
  shop PC, for no gain with one user.
* **Store balances.** Faster to read, but every edit, delete, settlement and day of
  interest would have to keep them right; v3's numbers would be at risk.
