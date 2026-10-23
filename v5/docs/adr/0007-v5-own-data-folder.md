# 0007. v5 keeps its own data folder and copies v4 read-only

* Status: Accepted
* Date: 2026-10-19 (5.0.0)

## Context

v4 was in daily use at the shop with its data in `C:\JBB\v4`. v5 adds schema migrations
and many new screens. Running v5 on v4's database would upgrade it in place: if v5 had a
problem the shop could not simply go back to v4, and the two versions could not be
compared side by side.

## Decision

* v5's default data folder is `C:\JBB\v5`.
* On the **first start** in that default folder, if `C:\JBB\v4\hth.db` exists, v5 copies it:
  opened with a read-only URI and copied with SQLite's backup API into a temporary file,
  which becomes `hth.db` only when complete. v4's files are never written.
* After that the two are separate. A one-time notice after sign-in says where the data
  came from.
* With `HTH_DATA_DIR` set, nothing is copied: that folder was chosen on purpose.
* A failed copy creates nothing and says so; the next start tries again.

## Consequences

* The shop could keep v4 as a fallback and compare figures (every balance, day count,
  score and the interest summary were checked identical on the shop's data).
* Entries made in v5 are not seen by v4. To start v5 again from v4's latest data: close v5,
  rename `C:\JBB\v5\hth.db`, start v5.
* Tested by `test_first_start_copies_v4_database_read_only` and
  `test_failed_copy_of_v4_creates_nothing`.

## Alternatives considered

* **Upgrade v4's database in place.** No way back without a restore; v4 could no longer
  open the file once migrated.
* **Ask the user to copy the file.** Error-prone (copying a database that is open can give
  a broken copy).
