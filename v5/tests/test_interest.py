"""The v4 interest function must match v3 bit-for-bit.  v3's implementation is ported
below verbatim (only the frozen default argument removed) as the oracle."""

import datetime

import pytest

from hth.domain.interest import calculate_interest, financial_year_end


def v3_calculate_interest(principle_amount, from_date_str, to_date):
    daily_interest_rate = 0.0006575342465753425
    from_date = datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date()
    total_interest = 0
    while from_date < to_date:
        year_end = datetime.date(from_date.year, 3, 31)
        if from_date.month > 3:
            year_end = datetime.date(from_date.year + 1, 3, 31)
        end_date = min(year_end, to_date)
        days = (end_date - from_date).days
        interest = principle_amount * days * daily_interest_rate
        total_interest += interest
        principle_amount += interest
        from_date = end_date + datetime.timedelta(days=1)
    return round(total_interest, 2)


@pytest.mark.parametrize(
    "amount,start,end",
    [
        (1000, "2024-01-01", datetime.date(2024, 1, 1)),
        (1000, "2024-01-01", datetime.date(2024, 1, 31)),
        (1000, "2024-01-01", datetime.date(2024, 3, 31)),
        (1000, "2024-01-01", datetime.date(2024, 4, 1)),
        (1000, "2024-01-01", datetime.date(2026, 8, 29)),
        (12345.67, "2022-11-15", datetime.date(2026, 8, 29)),
        (500, "2025-03-31", datetime.date(2025, 4, 30)),
        (500, "2025-04-01", datetime.date(2026, 3, 31)),
        (0, "2020-01-01", datetime.date(2026, 1, 1)),
        (100, "2027-01-01", datetime.date(2026, 1, 1)),  # future-dated: no interest
    ],
)
def test_matches_v3(amount, start, end):
    assert calculate_interest(amount, start, end) == v3_calculate_interest(amount, start, end)


def test_one_year_is_24_percent_before_compounding():
    # 365 days inside one financial year: 1000 * 365 * (0.24/365) = 240
    assert calculate_interest(1000, "2024-04-01", datetime.date(2025, 3, 31)) == pytest.approx(239.34, abs=0.01)


def test_compounds_at_financial_year_end():
    one_year = calculate_interest(1000, "2024-04-01", datetime.date(2025, 3, 31))
    two_years = calculate_interest(1000, "2024-04-01", datetime.date(2026, 3, 31))
    assert two_years > 2 * one_year  # second year earns interest on interest


def test_default_to_date_is_today(monkeypatch):
    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return cls(2030, 1, 1)

    monkeypatch.setattr("hth.domain.interest.dt.date", FakeDate)
    assert calculate_interest(1000, "2029-12-01") == v3_calculate_interest(
        1000, "2029-12-01", datetime.date(2030, 1, 1)
    )


def test_financial_year_end():
    assert financial_year_end(datetime.date(2024, 1, 10)) == datetime.date(2024, 3, 31)
    assert financial_year_end(datetime.date(2024, 3, 31)) == datetime.date(2024, 3, 31)
    assert financial_year_end(datetime.date(2024, 4, 1)) == datetime.date(2025, 3, 31)


def test_accepts_date_objects_and_strings():
    d = datetime.date(2024, 1, 1)
    assert calculate_interest(100, d, "2024-02-01") == calculate_interest(100, "2024-01-01", datetime.date(2024, 2, 1))
