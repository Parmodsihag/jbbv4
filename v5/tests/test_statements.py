import datetime as dt

import pytest

from hth.domain.interest import calculate_interest
from hth.services.accounts import ValidationError
from hth.services.company import CompanyService
from hth.services.statements import StatementService, financial_year_start

AS_OF = dt.date(2026, 8, 30)


def test_statement_rows_and_balances(db, accounts, tmp_path):
    c = accounts.add_customer("ram <kumar>", "dhansu", 1000, "2026-01-01")
    accounts.add_transaction(c.id, "2026-03-01", "paid", 400, "M", "2")
    accounts.add_transaction(c.id, "2026-05-10", "5 BAG = UREA", 1500, "P", "1")
    accounts.add_transaction(c.id, "2026-06-15", "paid", 500, "M", "2")
    svc = StatementService(db)
    st = svc.build(c.id, "2026-05-01", "2026-06-30", AS_OF)
    full = accounts.ledger(c.id, AS_OF)
    assert [r.particulars for r in st.rows] == ["5 BAG = UREA", "paid"]
    assert st.opening_balance == full[1].balance  # balance after the last row before May
    assert st.closing_balance == full[3].balance
    assert st.total_debit == 1500 and st.total_credit == 500
    assert st.total_interest == calculate_interest(1500, "2026-05-10", AS_OF)
    html = svc.html(st)
    assert "RAM &lt;KUMAR&gt;" in html and "JAAT BEEJ BHANDAR" in html and "5 BAG = UREA" in html
    assert "due from you" in html and "Opening balance" in html and "2026-05-01 to 2026-06-30" in html
    path = svc.write(st, tmp_path)
    assert path.exists() and path.name.startswith("statement_RAM") and "<!doctype html>" in path.read_text()

    empty = svc.build(c.id, "2025-01-01", "2025-12-31", AS_OF)
    assert empty.rows == [] and empty.opening_balance == 0 and empty.closing_balance == 0
    assert "No entries" in svc.html(empty)
    with pytest.raises(ValidationError):
        svc.build(c.id, "2026-06-30", "2026-05-01")
    with pytest.raises(ValidationError):
        svc.build(999, "2026-01-01", "2026-12-31")


def test_company_profile_and_fy(db):
    cs = CompanyService(db)
    assert cs.profile().name == "JAAT BEEJ BHANDAR"
    cs.update(name="New Name", phone=" 99 ")
    p = cs.profile()
    assert p.name == "New Name" and p.phone == "99" and p.gstin == "06AOIPR2828B1Z3"
    with pytest.raises(ValueError):
        cs.update(colour="red")
    assert financial_year_start(dt.date(2026, 8, 30)) == "2026-04-01"
    assert financial_year_start(dt.date(2026, 2, 1)) == "2025-04-01"
