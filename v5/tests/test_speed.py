"""v5.6 speed work: the shortcuts must never change an answer."""

from __future__ import annotations

import datetime as dt
import random
import threading

import pytest

from hth.db.connection import Database
from hth.db.schema import initialize
from hth.domain.constants import DAILY_INTEREST_RATE
from hth.domain.interest import calculate_interest, financial_year_end, interest_schedule, parse_date
from hth.services.accounts import AccountsService
from hth.services.insights import InsightsService


@pytest.fixture
def file_db(tmp_path):
    db = Database(tmp_path / "hth.db")
    initialize(db)
    yield db
    db.close()


def test_version_moves_on_committed_changes_only(db, accounts):
    v = db.version
    accounts.list_customers()
    db.fetchone("SELECT COUNT(*) FROM customers")
    assert db.version == v  # reading changes nothing
    accounts.add_customer("ramesh", "", 500, "2026-01-01")  # nested blocks: one unit, one step
    assert db.version == v + 1
    with pytest.raises(RuntimeError):
        with db.connect() as conn:
            conn.execute("INSERT INTO customers (name, other_details) VALUES ('X', '')")
            raise RuntimeError("rolled back")
    assert db.version == v + 1
    assert [c.name for c in accounts.list_customers()] == ["RAMESH"]


def test_each_thread_keeps_its_connection_and_sees_the_others_writes(file_db):
    with file_db.connect() as a:
        pass
    with file_db.connect() as b:
        assert b is a  # kept between units of work
    seen = {}

    def other():
        with file_db.connect() as c:
            seen["conn"] = c
            c.execute("INSERT INTO customers (name, other_details) VALUES ('FROM THREAD', '')")

    t = threading.Thread(target=other)
    t.start()
    t.join()
    assert seen["conn"] is not a
    # the main thread's kept connection is not stuck on an old snapshot
    assert file_db.fetchone("SELECT COUNT(*) AS n FROM customers")["n"] == 1
    # a failed unit on a kept connection leaves nothing behind
    with pytest.raises(ValueError):
        with file_db.connect() as conn:
            conn.execute("INSERT INTO customers (name, other_details) VALUES ('HALF', '')")
            raise ValueError
    assert file_db.fetchone("SELECT COUNT(*) AS n FROM customers")["n"] == 1
    file_db.close()
    with file_db.connect() as fresh:
        assert fresh is not a
    assert file_db.fetchone("SELECT COUNT(*) AS n FROM customers")["n"] == 1


def test_finished_threads_give_their_connection_back(file_db):
    def work():
        file_db.fetchone("SELECT 1")

    for _ in range(5):
        t = threading.Thread(target=work)
        t.start()
        t.join()
    file_db.fetchone("SELECT 1")  # a new connection on this thread tidies up after the others
    assert len(file_db._kept) <= 2


def test_parse_date_is_cached_but_still_strict():
    assert parse_date("2026-04-01") == dt.date(2026, 4, 1) == parse_date(" 2026-04-01 ")
    assert parse_date("2026-04-01") is parse_date("2026-04-01")  # parsed once
    for bad in ("2026-13-01", "01-04-2026", ""):
        with pytest.raises(ValueError):
            parse_date(bad)
        with pytest.raises(ValueError):
            parse_date(bad)  # errors are not cached as answers


def _old_schedule(principal, start: dt.date, end: dt.date):
    """interest_schedule exactly as it was before the period cache."""
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


def test_cached_periods_give_bit_for_bit_the_same_interest():
    rnd = random.Random(5)
    base = dt.date(2019, 1, 1)
    for _ in range(3000):
        start = base + dt.timedelta(days=rnd.randint(0, 2900))
        end = start + dt.timedelta(days=rnd.randint(-5, 1500))
        amount = rnd.choice([1, 266.5, 1350, 12345.67, rnd.uniform(0, 250000)])
        assert interest_schedule(amount, start.isoformat(), end.isoformat()) == _old_schedule(amount, start, end)
        old_total = 0.0
        for _end, interest in _old_schedule(amount, start, end):
            old_total += interest
        assert calculate_interest(amount, start.isoformat(), end.isoformat()) == round(old_total, 2)


def test_balances_unchanged_by_the_caches(db, accounts, sales):
    c = accounts.add_customer("a", "", 0, "2024-01-01")
    for days, amount, kind in [(700, 1000, "P"), (400, 250.5, "M"), (380, 999.99, "P"), (10, 100, "M")]:
        date = (dt.date(2026, 8, 29) - dt.timedelta(days=days)).isoformat()
        sales.record(kind, date, c.id, "CASH", 1, amount, "1", "admin")
    as_of = dt.date(2026, 8, 29)
    assert accounts.balances(as_of)[c.id] == accounts.get_balance(c.id, as_of)
    assert accounts.ledger(c.id, as_of)[-1].balance == accounts.get_balance(c.id, as_of)


def test_default_password_check_hashes_once_per_stored_password(auth, db, monkeypatch):
    from hth.services import insights as insights_module

    insights_module._still_default.clear()
    calls = []
    real = insights_module.AuthService.verify
    monkeypatch.setattr(insights_module.AuthService, "verify", lambda self, u, p: calls.append(u) or real(self, u, p))
    assert InsightsService(db).default_password_users() == ["admin", "emp1"]
    assert InsightsService(db).default_password_users() == ["admin", "emp1"]
    assert calls == ["admin", "emp1"]  # the second look hashed nothing
    admin = next(u for u in auth.list_users() if u.username == "admin")
    auth.set_password(admin.id, "a-better-one", "admin")
    assert InsightsService(db).default_password_users() == ["emp1"]
    assert calls == ["admin", "emp1", "admin"]


def test_freshness_follows_writes_and_the_date(db):
    from hth.ui.modern.widgets import Freshness

    fresh = Freshness(db)
    assert fresh.stale()
    fresh.filling()
    assert not fresh.stale()
    AccountsService(db).add_customer("b", "", 0, "2026-01-01")
    assert fresh.stale()
    fresh.filling()
    assert not fresh.stale()
    fresh._filled_at = (db.version, dt.date.today() - dt.timedelta(days=1))  # filled yesterday
    assert fresh.stale()  # interest and "days late" move at midnight
    fresh.filling()
    fresh.forget()
    assert fresh.stale()
