import datetime as dt

import pytest

from hth.modules.crop_trading.service import CropService
from hth.modules.finance.service import FinanceService
from hth.services.accounts import ValidationError


@pytest.fixture
def fin(db):
    f = FinanceService(db)
    f.ensure_defaults()
    return f


def _head(fin, name):
    return next(h.id for h in fin.heads(active_only=False) if h.name == name)


def test_defaults(fin):
    accounts = fin.money_accounts()
    assert [a.name for a in accounts] == ["CASH"] and accounts[0].kind == "cash"
    assert len(fin.heads("expense")) == 11 and len(fin.heads("income")) == 3
    fin.ensure_defaults()  # idempotent
    assert len(fin.money_accounts()) == 1 and fin.default_account_id() == accounts[0].id


def test_accounts_balances_and_cash_book(fin):
    cash = fin.money_accounts()[0]
    bank = fin.add_account("sbi current", "bank", 10000, "2026-08-01")
    upi = fin.add_account("phonepe", "upi")
    with pytest.raises(ValidationError):
        fin.add_account("SBI CURRENT", "bank")
    with pytest.raises(ValidationError):
        fin.add_account("x", "crypto")
    fin.owner("2026-08-02", cash.id, 5000, "in", "opening float")
    fin.add_expense("2026-08-03", cash.id, _head(fin, "RENT"), 1200, "august rent")
    fin.add_income("2026-08-04", bank.id, _head(fin, "COMMISSION"), 300, "seed co")
    fin.transfer("2026-08-05", bank.id, cash.id, 2000, "withdrawal")
    fin.transfer("2026-08-06", cash.id, upi.id, 500)
    with pytest.raises(ValidationError):
        fin.transfer("2026-08-06", cash.id, cash.id, 1)
    with pytest.raises(ValidationError):
        fin.add_expense("2026-08-03", cash.id, _head(fin, "COMMISSION"), 10)  # income head on an expense
    with pytest.raises(ValidationError):
        fin.add_expense("2026-08-03", cash.id, _head(fin, "RENT"), 0)

    assert fin.balance(cash.id) == 5000 - 1200 + 2000 - 500
    assert fin.balance(bank.id) == 10000 + 300 - 2000
    assert fin.balance(upi.id) == 500
    assert fin.balance(cash.id, "2026-08-03") == 3800
    opening, rows, closing = fin.cash_book(cash.id, "2026-08-03", "2026-08-06")
    assert opening == 5000 and closing == 5300
    assert [r[2] for r in rows] == ["Expense", "Transfer", "Transfer"]
    assert rows[1][4] == 2000 and rows[2][5] == 500 and rows[2][6] == 5300
    assert "← SBI CURRENT" in rows[1][3] and "→ PHONEPE" in rows[2][3]

    fin.update_account(bank.id, "admin", is_active=False)
    assert [a.name for a in fin.money_accounts()] == ["CASH", "PHONEPE"]
    fin.set_default_account(upi.id)
    assert fin.default_account_id() == upi.id
    fin.delete_entry(rows[0][0], "admin")
    assert fin.balance(cash.id) == 6500


def test_sales_screen_money_flow(fin, accounts, inventory, sales):
    cash = fin.money_accounts()[0]
    bank = fin.add_account("bank", "bank")
    c = accounts.add_customer("ram", "", 1000, "2026-01-01")
    res = sales.record("M", "2026-08-10", c.id, "CASH", 1, 600, "2", "emp1", money_account_id=bank.id)
    assert res.money_account_id == bank.id
    e = fin.entries(bank.id)[0]
    assert (e.kind, e.amount, e.customer_id, e.tx_id) == ("receipt", 600, c.id, res.transaction_ids[0])
    assert fin.balance(bank.id) == 600
    sales.record("P", "2026-08-11", c.id, "CASH", 1, 200, "2", "emp1", money_account_id=cash.id)
    assert fin.balance(cash.id) == -200 and fin.entries(cash.id)[0].kind == "payment"
    # settlement (tag 0) still records the money that actually moved
    sales.record("M", "2026-08-12", c.id, "CASH", 1, 300, "0", "emp1", money_account_id=cash.id)
    assert fin.balance(cash.id) == 100
    # a stock item never touches the cash book
    urea = inventory.add_item("urea", 260, 300, unit="BAG", opening_quantity=5)
    r2 = sales.record(
        "P", "2026-08-13", c.id, urea.display, 2, 300, "2", "emp1", item_id=urea.id, money_account_id=cash.id
    )
    assert r2.money_account_id is None and fin.balance(cash.id) == 100
    # ... but its value is recorded on the movement for the P&L
    tx = next(t for t in inventory.get_item_transactions(urea.id) if t.sale > 0)
    assert (
        tx.sale == 2 and fin.db.fetchone("SELECT value FROM item_transactions WHERE id = ?", (tx.id,))["value"] == 600
    )
    # no money account -> no cash-book entry
    sales.record("M", "2026-08-14", c.id, "DISCOUNT", 1, 50, "2", "emp1")
    assert len(fin.entries()) == 3


def test_recurring(fin):
    cash = fin.money_accounts()[0]
    rent = fin.add_recurring(_head(fin, "RENT"), cash.id, 5000, 5, "shop rent", "2026-06")
    with pytest.raises(ValidationError):
        fin.add_recurring(_head(fin, "COMMISSION"), cash.id, 10, 1)
    with pytest.raises(ValidationError):
        fin.add_recurring(_head(fin, "RENT"), cash.id, 10, 31)
    due = fin.due_recurring(dt.date(2026, 8, 4))
    assert [(r.id, m) for r, m in due] == [(rent.id, ["2026-06", "2026-07"])]  # August not yet due (day 5)
    assert fin.post_due("admin", dt.date(2026, 8, 4)) == 2
    assert fin.get_recurring(rent.id).last_posted == "2026-07"
    assert fin.due_recurring(dt.date(2026, 8, 4)) == []
    assert fin.post_due("admin", dt.date(2026, 8, 5)) == 1
    assert fin.post_due("admin", dt.date(2026, 8, 5)) == 0  # idempotent
    assert [e.date for e in fin.entries(kind="expense")] == ["2026-06-05", "2026-07-05", "2026-08-05"]
    # last 4 calendar months as of October = Jul..Oct (June is out)
    assert [m for m, *_ in fin.monthly_expenses(4, today=dt.date(2026, 10, 15))] == ["2026-07", "2026-08"]
    assert fin.balance(cash.id) == -15000
    fin.set_recurring_active(rent.id, False)
    assert fin.due_recurring(dt.date(2026, 12, 31)) == []
    fin.delete_recurring(rent.id)
    assert fin.recurring() == []


def test_cash_flow_and_pnl(fin, accounts, inventory, sales, db):
    cash = fin.money_accounts()[0]
    bank = fin.add_account("bank", "bank", 1000, "2026-07-31")
    c = accounts.add_customer("ram", "", 0)
    urea = inventory.add_item("urea", 250, 300, unit="BAG", opening_quantity=10)
    sales.record("P", "2026-08-02", c.id, urea.display, 4, 300, "2", "emp1", item_id=urea.id)  # revenue 1200, cogs 1000
    sales.record("M", "2026-08-03", c.id, "CASH", 1, 1200, "2", "emp1", money_account_id=cash.id)
    fin.add_expense("2026-08-04", cash.id, _head(fin, "RENT"), 500)
    fin.add_expense("2026-08-04", bank.id, _head(fin, "SALARIES"), 300)
    fin.add_income("2026-08-05", bank.id, _head(fin, "COMMISSION"), 100)
    fin.transfer("2026-08-06", cash.id, bank.id, 400)
    fin.owner("2026-08-07", bank.id, 250, "out", "drawings")
    crops = CropService(db)
    farmer, buyer = accounts.add_customer("f", "", 0), accounts.add_customer("b", "", 0)
    wheat = crops.add_crop("wheat")
    sales.record("M", "2026-08-08", farmer.id, wheat.display, 100, 20, "2", "emp1", item_id=wheat.id)
    sales.record("P", "2026-08-09", buyer.id, wheat.display, 60, 26, "2", "emp1", item_id=wheat.id)  # margin 360

    cf = fin.cash_flow("2026-08-01", "2026-08-31")
    assert cf.inflows == {"Customer receipt": 1200, "Other income": 100}
    assert cf.outflows == {"Expense": 800, "Drawings": 250}
    assert cf.expenses_by_head == [("RENT", 500), ("SALARIES", 300)]
    assert cf.total_in == 1300 and cf.total_out == 1050 and cf.net == 250
    by_name = {a[0]: a for a in cf.accounts}
    assert by_name["CASH"] == ("CASH", 0, 1200, 900, 300)
    assert by_name["BANK"] == ("BANK", 1000, 500, 550, 950)

    pl = fin.profit_and_loss("2026-08-01", "2026-08-31")
    assert (pl.item_revenue, pl.item_cogs, pl.item_margin) == (1200, 1000, 200)
    assert (pl.crop_revenue, pl.crop_cost, pl.crop_margin) == (1560, 1200, 360)
    assert pl.gross_margin == 560 and pl.other_income == 100 and pl.total_expenses == 800
    assert pl.net_profit == 560 + 100 - 800
    assert fin.monthly_expenses(1, today=dt.date(2026, 8, 31)) == [("2026-08", 800, 100)]
    assert fin.expenses_by_head("2026-08-01", "2026-08-31") == [("RENT", 500), ("SALARIES", 300)]


def test_sale_with_payment_is_one_unit(fin, accounts, inventory, sales, db):
    """v5.5 Counter: 'Paid now' inside a sale - the lines and the payment together."""
    from hth.services.sales import SaleLine

    cash = fin.money_accounts()[0]
    c = accounts.add_customer("ram", "", 0, "2026-01-01")
    urea = inventory.add_item("urea", 260, 300, unit="BAG", opening_quantity=10)
    lines = [SaleLine(urea.display, 4, 266.5, urea.id, "BAG"), SaleLine("LABOUR", 1, 50)]
    count = lambda: db.fetchone("SELECT COUNT(*) AS n FROM transactions")["n"]  # noqa: E731
    before = count()

    results = sales.record_sale_with_payment("2026-08-10", c.id, lines, "1", "emp1", 1000, "cash", cash.id)
    assert [r.kind for r in results] == ["P", "P", "M"]
    assert count() == before + 3 and inventory.quantity(urea.id) == 6
    assert fin.balance(cash.id) == 1000 and fin.entries(cash.id)[0].kind == "receipt"
    assert accounts.get_balance(c.id, dt.date(2026, 8, 10)) == round(4 * 266.5 + 50 - 1000, 2)
    # the free-text line is a charge on the khata, not cash paid out
    assert len(fin.entries(cash.id)) == 1

    # anything invalid: nothing at all is written
    with pytest.raises(ValidationError, match="Paid now"):
        sales.record_sale_with_payment("2026-08-10", c.id, lines, "1", "emp1", "abc")
    with pytest.raises(ValidationError):
        sales.record_sale_with_payment("2026-08-10", c.id, [SaleLine("X", 0, 5)], "1", "emp1", 100)
    with pytest.raises(ValidationError, match="settle"):
        sales.record_sale_with_payment("2026-08-10", c.id, lines, "0", "emp1", 100)
    assert count() == before + 3 and inventory.quantity(urea.id) == 6 and fin.balance(cash.id) == 1000

    # nothing paid: just the sale
    assert len(sales.record_sale_with_payment("2026-08-11", c.id, lines[:1], "1", "emp1", 0)) == 1

    # undo takes back both parts of the first one
    assert sales.undo(results, "emp1") == 3
    assert fin.balance(cash.id) == 0 and inventory.quantity(urea.id) == 6  # 2 left + the 4 put back
