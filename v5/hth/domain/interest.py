"""Interest calculation - the single source of truth (v3 had three copies).

Algorithm (unchanged from v3):
  * simple interest at DAILY_INTEREST_RATE for each day
  * on 31 March (financial year end) accrued interest is added to the principal
    and interest for the next year is computed on the larger amount
  * result rounded to 2 decimals

The one behavioural fix: ``to_date`` now defaults to *today at call time*.  v3 bound
``datetime.date.today()`` as a default argument, so it was frozen at import and an app
left running past midnight used yesterday's date.
"""

from __future__ import annotations

import datetime as dt

from hth.domain.constants import (
    DAILY_INTEREST_RATE,
    DATE_FMT,
    FINANCIAL_YEAR_END_DAY,
    FINANCIAL_YEAR_END_MONTH,
)


def parse_date(value: str | dt.date) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.datetime.strptime(value.strip(), DATE_FMT).date()


def financial_year_end(day: dt.date) -> dt.date:
    year = day.year if day.month <= FINANCIAL_YEAR_END_MONTH else day.year + 1
    return dt.date(year, FINANCIAL_YEAR_END_MONTH, FINANCIAL_YEAR_END_DAY)


def interest_schedule(
    principal: float, from_date: str | dt.date, to_date: str | dt.date | None = None
) -> list[tuple[dt.date, float]]:
    """Unrounded interest per financial-year period: [(period end, interest), ...].

    The periods are exactly the ones :func:`calculate_interest` adds up, so the sum of this
    schedule (in order) is its result before rounding.
    """
    start = parse_date(from_date)
    end = parse_date(to_date) if to_date is not None else dt.date.today()
    principal = float(principal)
    out = []
    while start < end:
        period_end = min(financial_year_end(start), end)
        days = (period_end - start).days
        interest = principal * days * DAILY_INTEREST_RATE
        out.append((period_end, interest))
        principal += interest
        start = period_end + dt.timedelta(days=1)
    return out


def fy_label(day: dt.date) -> str:
    """Financial year containing ``day``: 2026-08-01 -> 'FY 2026-27'."""
    end = financial_year_end(day)
    return f"FY {end.year - 1}-{str(end.year)[2:]}"


def calculate_interest(principal: float, from_date: str | dt.date, to_date: str | dt.date | None = None) -> float:
    """Compound-at-FY-end interest on ``principal`` from ``from_date`` to ``to_date``."""
    total = 0.0
    for _period_end, interest in interest_schedule(principal, from_date, to_date):
        total += interest
    return round(total, 2)
