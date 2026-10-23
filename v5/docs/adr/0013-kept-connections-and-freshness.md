# 0013. Kept connections and version-based screen freshness

* Status: Accepted
* Date: 2026-10-20 (5.6.0)

## Context

Profiling on a shop-sized copy (663 accounts, 6,200 entries, 76 items) showed that opening
a SQLite connection on Windows cost about 300 times a small query (it creates the WAL side
files, and closing the last one checkpoints and deletes them, under the virus scanner's
eyes), and a screen makes dozens of small queries. Screens also re-read everything each time
they were shown, even when nothing had changed.

## Decision

* **Each thread keeps its connection open** between units of work. The unit of work is
  unchanged: commit or roll back at the outermost block ([ADR 0002](0002-one-sqlite-file-transactional-units.md)).
  `Database.close()` closes every kept connection; it is called at exit and before the file
  is copied over or replaced (restore). Finished threads give their connection back.
* `Database.version` goes up with every committed change. A screen remembers the version and
  the date it was filled at (`Freshness`); when neither changed, coming back to it reads
  nothing. After a change, Today redraws only the cards whose figures moved.
* Small caches (parsed dates, financial-year periods of each date) are allowed only where a
  test shows they give **bit-for-bit** the same interest and balances.
* Heavy libraries (openpyxl, matplotlib, NumPy) load the first time they are needed.

## Consequences

* Start-up takes about a quarter of the time; the Counter reacts two to three times faster;
  returning to an unchanged screen is instant.
* Correctness is guarded by `tests/test_speed.py` (version moves only on committed changes,
  each thread keeps and returns its connection, caches give identical figures).
* Anything that replaces `hth.db` on disk must call `Database.close()` first.

## Alternatives considered

* **A connection pool library.** More than needed; one connection per thread is enough.
* **Caching query results with time-outs.** Risk of showing stale balances; the version
  counter is exact.
