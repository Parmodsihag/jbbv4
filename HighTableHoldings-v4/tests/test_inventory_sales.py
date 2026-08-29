import pytest

from hth.services.accounts import ValidationError


def test_add_item_writes_opening_stock(inventory):
    item = inventory.add_item(
        "urea", 300, 320, "bag", "b1", "2027-01-01", 5, "f", "p", "2026-01-01", 40, "iffco", "admin"
    )
    assert item.name == "UREA" and item.unit == "BAG" and item.item_type == "F"
    assert inventory.quantity(item.id) == 40
    txs = inventory.get_item_transactions(item.id)
    assert txs[0].received == 40 and txs[0].description == "IFFCO"


def test_summaries_and_alerts(inventory):
    a = inventory.add_item("a", 10, 0, opening_quantity=3, expiry_date="2026-09-10")
    b = inventory.add_item("b", 5, 0, opening_quantity=100, expiry_date="NA")
    s = {x.item.id: x for x in inventory.summaries()}
    assert s[a.id].in_stock == 3 and s[a.id].total_value == 30
    assert s[b.id].total_value == 500
    assert inventory.total_stock_value() == 530
    assert [x.item.id for x in inventory.low_stock(5)] == [a.id]
    import datetime as dt

    exp = inventory.expiring(30, today=dt.date(2026, 8, 29))
    assert [(x.item.id, d) for x, d in exp] == [(a.id, 12)]


def test_sale_updates_ledger_stock_price_and_audit(accounts, inventory, sales, db):
    c = accounts.add_customer("ram", "", 0)
    item = inventory.add_item("wheat", 20, 25, opening_quantity=50)
    res = sales.record("P", "2026-08-01", c.id, item.display, "5", "30", "2", "emp1", item_id=item.id)
    assert res.amount == 150 and res.inventory_updated and len(res.transaction_ids) == 1
    tx = accounts.get_transactions(c.id)[0]
    assert tx.description == f"5 = {item.display}" and tx.type == "P" and tx.tag == "2"
    assert inventory.quantity(item.id) == 45
    assert inventory.get_last_value(item.id) == 30
    audit = db.fetchall("SELECT code, message, username FROM audit_log ORDER BY id DESC LIMIT 1")[0]
    assert audit["code"] == "03" and audit["username"] == "emp1"
    assert audit["message"] == f"2026-08-01, {item.display}, RAM, 5, 30, 2"


def test_receive_adds_stock_and_credits(accounts, inventory, sales):
    c = accounts.add_customer("ram", "", 0)
    item = inventory.add_item("wheat", 20, 25, opening_quantity=50)
    sales.record("M", "2026-08-01", c.id, item.display, 10, 20, "1", "emp1", item_id=item.id)
    assert inventory.quantity(item.id) == 60
    assert accounts.get_transactions(c.id)[0].type == "M"


def test_sale_without_item_only_touches_ledger(accounts, sales):
    c = accounts.add_customer("ram", "", 0)
    res = sales.record("P", "2026-08-01", c.id, "CASH", 1, 500, "2", "emp1")
    assert not res.inventory_updated and accounts.get_balance(c.id) == 500


def test_settlement_sale_flow(accounts, sales):
    c = accounts.add_customer("ram", "", 1000, "2026-01-01")
    before = accounts.get_balance(c.id)
    res = sales.record("M", "2026-08-01", c.id, "CASH", 1, 950, "0", "emp1")
    assert len(res.transaction_ids) == 3
    assert accounts.get_balance(c.id) == 0
    assert accounts.get_transactions(c.id)[-2].amount == before


def test_sale_is_atomic(accounts, inventory, sales, monkeypatch):
    c = accounts.add_customer("ram", "", 0)
    item = inventory.add_item("wheat", 20, 25, opening_quantity=50)

    def boom(*a, **k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(inventory.__class__, "set_last_value", boom)
    with pytest.raises(RuntimeError):
        sales.record("P", "2026-08-01", c.id, item.display, 5, 30, "2", "emp1", item_id=item.id)
    assert accounts.get_transactions(c.id) == []
    assert inventory.quantity(item.id) == 50


def test_sale_validation(accounts, sales):
    c = accounts.add_customer("ram", "", 0)
    with pytest.raises(ValidationError):
        sales.record("P", "2026-08-01", 999, "x", 1, 1, "1", "u")
    with pytest.raises(ValidationError):
        sales.record("P", "2026-08-01", c.id, "", 1, 1, "1", "u")
    with pytest.raises(ValidationError):
        sales.record("Z", "2026-08-01", c.id, "x", 1, 1, "1", "u")


def test_loose_sale_in_grams_converts_to_stock_unit(accounts, inventory, sales):
    c = accounts.add_customer("ram", "", 0)
    seed = inventory.add_item("wheat seed", 40, 48, unit="KG", opening_quantity=5)
    res = sales.record("P", "2026-08-01", c.id, seed.display, 250, 48, "2", "emp1", item_id=seed.id, unit="G")
    assert res.stock_quantity == 0.25 and res.stock_unit == "KG"
    assert res.amount == 12.0  # 48 per KG * 0.25 KG
    assert inventory.quantity(seed.id) == 4.75
    tx = accounts.get_transactions(c.id)[0]
    assert tx.description == f"250 G (0.25 KG) = {seed.display}" and tx.amount == 12.0


def test_sale_in_quintals_and_fractional_price(accounts, inventory, sales):
    c = accounts.add_customer("ram", "", 0)
    crop = inventory.add_item("mustard", 5000, 5500, unit="KG", opening_quantity=0)
    sales.record("M", "2026-08-01", c.id, crop.display, 2.5, 55.75, "2", "emp1", item_id=crop.id, unit="QTL")
    assert inventory.quantity(crop.id) == 250
    assert inventory.get_last_value(crop.id) == 55.75
    assert accounts.get_transactions(c.id)[0].amount == round(55.75 * 250, 2)


def test_incompatible_unit_rejected(accounts, inventory, sales):
    c = accounts.add_customer("ram", "", 0)
    item = inventory.add_item("urea", 260, 300, unit="BAG", opening_quantity=10)
    with pytest.raises(ValidationError):
        sales.record("P", "2026-08-01", c.id, item.display, 1, 300, "2", "emp1", item_id=item.id, unit="KG")
    with pytest.raises(ValidationError):
        sales.record("P", "2026-08-01", c.id, item.display, 0, 300, "2", "emp1", item_id=item.id)
