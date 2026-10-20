import datetime as dt

import pytest

from hth.domain.interest import calculate_interest
from hth.services.accounts import ValidationError, account_scores

AS_OF = dt.date(2026, 8, 29)


def test_add_customer_creates_opening_transaction(accounts):
    c = accounts.add_customer("ram kumar", "village x", 1500, "2026-01-01", username="admin")
    assert c.name == "RAM KUMAR" and c.other_details == "VILLAGE X"
    txs = accounts.get_transactions(c.id)
    assert len(txs) == 1 and txs[0].amount == 1500 and txs[0].type == "P" and txs[0].tag == "1"
    assert txs[0].description == "NEW ACCOUNT"


def test_add_customer_without_opening_balance_has_no_transaction(accounts):
    c = accounts.add_customer("shyam", "", "", username="admin")
    assert accounts.get_transactions(c.id) == []
    assert accounts.get_balance(c.id) == 0


def test_validation(accounts):
    with pytest.raises(ValidationError):
        accounts.add_customer("", "", 0)
    c = accounts.add_customer("a", "", 0)
    with pytest.raises(ValidationError):
        accounts.add_transaction(c.id, "31-12-2025", "x", 10, "P", "1")
    with pytest.raises(ValidationError):
        accounts.add_transaction(c.id, "2025-12-31", "x", "abc", "P", "1")
    with pytest.raises(ValidationError):
        accounts.add_transaction(c.id, "2025-12-31", "x", 10, "X", "1")
    with pytest.raises(ValidationError):
        accounts.add_transaction(c.id, "2025-12-31", "x", 10, "P", "7")


def test_balance_debit_minus_credit_with_interest(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2026-01-01", "sale", 1000, "P", "1")
    accounts.add_transaction(c.id, "2026-02-01", "paid", 400, "M", "1")
    accounts.add_transaction(c.id, "2026-03-01", "no int", 100, "P", "2")
    expected = (
        1000
        + calculate_interest(1000, "2026-01-01", AS_OF)
        - (400 + calculate_interest(400, "2026-02-01", AS_OF))
        + 100
    )
    assert accounts.get_balance(c.id, AS_OF) == round(expected, 2)


def test_settlement_resets_period(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2025-01-01", "old", 5000, "P", "1")
    accounts.add_transaction(c.id, "2025-06-01", "settle", 0, "M", "0")
    accounts.add_transaction(c.id, "2025-06-01", "new", 300, "P", "1")  # same date, later id
    assert accounts.last_settlement(c.id)[0] == "2025-06-01"
    expected = 300 + calculate_interest(300, "2025-06-01", AS_OF)
    assert accounts.get_balance(c.id, AS_OF) == round(expected, 2)


def test_record_settlement_writes_three_tag0_rows(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2026-01-01", "sale", 1000, "P", "1")
    before = accounts.get_balance(c.id)
    accounts.record_settlement(c.id, "2026-08-01", "5 = WHEAT", 900, "M", "admin")
    txs = accounts.get_transactions(c.id)
    assert [t.tag for t in txs[-3:]] == ["0", "0", "0"]
    assert txs[-3].description == "5 = WHEAT" and txs[-3].amount == 900 and txs[-3].type == "M"
    assert txs[-2].description == "Settled Amount" and txs[-2].amount == before
    assert txs[-1].description == "Discount" and txs[-1].amount == round(before - 900, 2)
    assert accounts.get_balance(c.id) == 0


def test_ledger_running_balance_and_reset(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2026-01-01", "sale", 1000, "P", "1")
    accounts.add_transaction(c.id, "2026-02-01", "paid", 400, "M", "2")
    accounts.add_transaction(c.id, "2026-03-01", "settle", 0, "M", "0")
    accounts.add_transaction(c.id, "2026-04-01", "sale2", 200, "P", "2")
    rows = accounts.ledger(c.id, AS_OF)
    assert [r.particulars for r in rows] == ["sale", "paid", "settle", "sale2"]
    i1 = calculate_interest(1000, "2026-01-01", AS_OF)
    # rows before the settlement are not in the current period: no interest, principal only
    assert rows[0].interest == 0 and rows[0].debit == 1000 and rows[0].balance == 0
    assert rows[1].credit == 400 and rows[1].balance == 0
    assert rows[2].interest is None and rows[2].balance == 0
    assert rows[3].balance == 200
    assert i1 > 0  # sanity: the oracle produced interest for the pre-settlement row


def test_ledger_no_settlement_running_balance(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2026-01-01", "sale", 1000, "P", "2")
    accounts.add_transaction(c.id, "2026-02-01", "paid", 400, "M", "2")
    rows = accounts.ledger(c.id, AS_OF)
    assert [r.balance for r in rows] == [1000, 600]


def test_days_and_summaries(accounts):
    a = accounts.add_customer("a", "", 0)
    b = accounts.add_customer("b", "", 0)
    accounts.add_transaction(a.id, "2026-08-01", "x", 100, "P", "2")
    accounts.add_transaction(a.id, "2026-08-20", "y", 50, "P", "2")
    assert accounts.days_since_last_activity(a.id, AS_OF) == 9
    assert accounts.days_since_last_activity(b.id, AS_OF) == 0
    s = {x.id: x for x in accounts.summaries(AS_OF)}
    assert s[a.id].balance == 150 and s[a.id].days == 9
    assert s[b.id].balance == 0 and s[b.id].score == 0
    assert s[a.id].score == 1.0  # max on both axes


def test_account_scores_formula():
    assert account_scores([]) == []
    assert account_scores([(100, 10)]) == [0.0]
    scores = account_scores([(100, 10), (10, 100), (0, 0)])
    assert scores[2] == 0.0 and 0 < scores[1] < 1 and 0 < scores[0] < 1
    assert scores[0] > scores[1]  # amount weighted 0.6 vs days 0.4


def test_update_and_delete_cascade(accounts, db):
    c = accounts.add_customer("a", "d", 10)
    accounts.update_customer(c.id, "new name", "new d", "admin")
    assert accounts.get_customer(c.id).name == "NEW NAME"
    tx = accounts.get_transactions(c.id)[0]
    accounts.update_transaction(tx.id, "2026-01-02", "edited", 20, "M", "2", "admin")
    assert accounts.get_transaction(tx.id).amount == 20
    accounts.delete_customer(c.id, "admin")
    assert accounts.get_customer(c.id) is None
    assert db.fetchall("SELECT * FROM transactions") == []
    codes = [r["code"] for r in db.fetchall("SELECT code FROM audit_log ORDER BY id")]
    assert codes == ["01", "05", "05", "06"]


def test_settlement_overpayment_writes_negative_discount(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2026-08-01", "sale", 100, "P", "2")
    accounts.record_settlement(c.id, "2026-08-02", "CASH", 150, "M", "admin")
    txs = accounts.get_transactions(c.id)
    assert txs[-1].description == "Discount" and txs[-1].amount == -50
    assert accounts.get_balance(c.id) == 0


def test_settlement_on_credit_balance(accounts):
    c = accounts.add_customer("a", "", 0)
    accounts.add_transaction(c.id, "2026-08-01", "paid", 100, "M", "2")  # we owe them 100
    accounts.record_settlement(c.id, "2026-08-02", "GOODS", 40, "P", "admin")
    txs = accounts.get_transactions(c.id)
    assert txs[-2].amount == -100 and txs[-1].amount == -60
    assert accounts.get_balance(c.id) == 0


def test_bulk_period_totals_match_per_customer_rules(accounts):
    """period_totals() is the one-query version of get_balance / days / interest summary."""
    import random

    rng = random.Random(7)
    ids = []
    for n in range(25):
        c = accounts.add_customer(f"c{n}", "", 0)
        ids.append(c.id)
        for _ in range(rng.randint(0, 12)):
            day = dt.date(2023, 1, 1) + dt.timedelta(days=rng.randint(0, 1300))
            amount = round(rng.uniform(1, 50000), 2)
            kind = rng.choice("PM")
            if rng.random() < 0.15:
                accounts.record_settlement(c.id, day.isoformat(), "settle", amount, kind, "t")
            else:
                accounts.add_transaction(c.id, day.isoformat(), "x", amount, kind, rng.choice("1112"))
    empty = accounts.add_customer("nobody", "", 0)
    for as_of in (None, AS_OF, dt.date(2027, 4, 1)):
        totals = accounts.period_totals(as_of)
        for cid in ids + [empty.id]:
            t = totals[cid]
            assert t.balance == accounts.get_balance(cid, as_of)
            assert t.days_since(as_of) == accounts.days_since_last_activity(cid, as_of)
            principal = sum((1 if tx.is_debit else -1) * tx.amount for tx in accounts.current_period_transactions(cid))
            assert t.principal == round(principal, 2)
    assert accounts.balances(AS_OF, [ids[0]]) == {ids[0]: accounts.get_balance(ids[0], AS_OF)}
    assert accounts.balances(AS_OF, []) == {}
