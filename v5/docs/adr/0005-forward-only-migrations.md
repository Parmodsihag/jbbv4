# 0005. Forward-only versioned migrations, backed up first

* Status: Accepted; amended in 5.0.0 (atomic migrations, pre-migration backup)
* Date: 2026-08-29 (4.0.0)

## Context

The schema grows with each feature (bills, crops, categories, finance, Hindi names), and
the shop's one database must be upgraded in place on a PC with no developer present. In
4.x a migration ran through `executescript`, which committed statement by statement: a
failure halfway left a half-migrated database.

## Decision

* `MIGRATIONS` in `hth/db/schema.py` is an ordered list of `(version, SQL)`. The database's
  version is `PRAGMA user_version`. At start-up every migration newer than that version
  runs, in order.
* **A shipped migration is never edited.** A change is a new entry at the end.
* Since 5.0, each migration runs inside one explicit transaction **together with its
  version bump**: it either fully applies or not at all.
* Since 5.0, before migrating an existing database the program writes
  `backups/hth_pre_migration_v<N>_<time>.db`. A fresh database takes no backup.
* A restored backup from an older version is migrated forward the same way; one from a
  newer version is refused.

## Consequences

* Upgrading is automatic and safe to interrupt (`test_failed_migration_leaves_database_untouched`,
  `test_fresh_database_takes_no_pre_migration_backup`).
* There are no down-migrations. Going back means restoring the pre-migration backup.
* Modules add their tables through this same list, so there is still one database.

## Alternatives considered

* **A migration library (Alembic).** Needs SQLAlchemy and a migrations folder for six
  small scripts.
* **Down-migrations.** Rarely correct for data changes, and the backup already gives a
  tested way back.
