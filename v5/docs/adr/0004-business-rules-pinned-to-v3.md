# 0004. Business rules pinned to v3 by tests; "today" at call time

* Status: Accepted
* Date: 2026-08-29 (4.0.0)

## Context

The shop trusts the numbers its old program (v3.7.1) produced: 24 % a year as a daily
rate, compounded on 31 March; P/M types; tags 0/1/2; a settlement that writes three rows.
A rewrite that changed a balance by one paisa would lose that trust. v3 also had quirks:
"today" was frozen when the program started (an app left open overnight used yesterday's
date), quantities were truncated to whole numbers, a settlement discount could be negative.

## Decision

* The interest formula exists in exactly one function, `hth/domain/interest.py`. The
  constants are in `hth/domain/constants.py`.
* Tests pin the rules against v3's own implementation (`test_matches_v3`) and against
  hand-checked figures; the importer is tested to give every customer the same balance as
  v3 for the same date.
* Each v3 quirk is decided explicitly and written down:
  * **kept**: negative discount rows, the three-row settlement, P/M and tag meanings, audit
    codes 01–06;
  * **fixed**: "today" is evaluated at every call; quantities are fractional.
* Every later speed-up must give bit-for-bit the same figures (checked on a copy of the
  shop's database for 5.0 and 5.6, and by `tests/test_speed.py`).

## Consequences

* Changing the interest rate or the year end is a code change plus a test change, never a
  setting someone can flip by mistake.
* The REAL-number arithmetic of v3 is kept, so money is stored as `REAL` and rounded to
  2 dp ([ARCHITECTURE §12](../ARCHITECTURE.md#12-risks-and-technical-debt)).
* Functions that depend on the date take an optional `today`, which also makes them
  testable.

## Alternatives considered

* **Re-derive the rules from the shop's description.** Too easy to differ in rounding and
  in where compounding happens.
* **Integer paise.** Cleaner, but it would change some v3 figures in the last digit.
