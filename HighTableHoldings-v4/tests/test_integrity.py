import datetime as dt

from hth.services.integrity import IntegrityService

TODAY = dt.date(2026, 8, 29)


def test_findings(db, accounts, inventory, krar):
    a = accounts.add_customer("a", "x", 100, "2026-01-01")
    accounts.add_transaction(a.id, "2027-01-01", "future", 10, "P", "2")
    accounts.add_transaction(a.id, "2026-02-01", "", 0, "P", "1")
    accounts.add_transaction(a.id, "2026-03-01", "settle", 0, "M", "0")  # lone settlement row
    b = accounts.add_customer("b", "y", 500, "2024-01-01")  # stale debtor
    accounts.add_customer("b", "y", 0)  # duplicate
    zero = accounts.add_customer("z", "", 0)
    krar.add_or_update(zero.id, "2026-09-01")
    item = inventory.add_item("neg", 10, 10, opening_quantity=1)
    inventory.add_item_transaction(item.id, "2026-05-01", 0, 5, "oversold")
    db.execute("UPDATE transactions SET date = 'bad' WHERE description = 'NEW ACCOUNT' AND customer_id = ?", (b.id,))

    issues = {(f.severity, f.issue, f.ref_id) for f in IntegrityService(db).run(TODAY)}
    assert ("ERROR", "Entry has an invalid date", b.id) in issues
    assert ("ERROR", "Negative stock", item.id) in issues
    assert ("WARN", "Entry dated in the future", a.id) in issues
    assert ("WARN", "Entry with zero amount", a.id) in issues
    assert ("WARN", "Duplicate customer (same name and details)", b.id) in issues
    assert ("INFO", "Settlement rows not in a group of 3", a.id) in issues
    assert ("INFO", "Entry without description", a.id) in issues
    assert ("INFO", "Open krar but nothing owed", zero.id) in issues
    first = IntegrityService(db).run(TODAY)[0]
    assert first.severity == "ERROR"


def test_clean_database_has_no_errors(db, accounts, inventory):
    c = accounts.add_customer("ok", "", 100, "2026-01-01")
    accounts.add_transaction(c.id, "2026-02-01", "paid", 50, "M", "1")
    inventory.add_item("fine", 10, 10, opening_quantity=3)
    assert [f for f in IntegrityService(db).run(TODAY) if f.severity != "INFO"] == []
