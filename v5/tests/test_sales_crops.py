"""Crop trades entered through the main sales service."""

import pytest

from hth.modules.crop_trading.service import CropService
from hth.services.accounts import ValidationError


@pytest.fixture
def crop_setup(db, accounts, inventory):
    crops = CropService(db)
    farmer = accounts.add_customer("farmer", "village", 0)
    buyer = accounts.add_customer("trader", "mandi", 0)
    wheat = crops.add_crop("wheat", "KG")
    return crops, farmer, buyer, wheat


def test_credit_on_crop_item_creates_a_lot(crop_setup, sales, accounts, inventory):
    crops, farmer, _buyer, wheat = crop_setup
    res = sales.record(
        "M",
        "2026-08-01",
        farmer.id,
        wheat.display,
        5,
        2200,
        "2",
        "emp1",
        item_id=wheat.id,
        unit="QTL",
        deduction=0.2,
        quality="b",
        notes="wet",
    )
    assert res.is_crop and res.crop_lot_id and res.stock_quantity == 480 and res.amount == 480 * 2200
    lot = crops.get_lot(res.crop_lot_id)
    assert (lot.gross_qty, lot.deduction_qty, lot.qty, lot.quality, lot.notes) == (500, 20, 480, "B", "wet")
    assert inventory.quantity(wheat.id) == 480
    assert accounts.get_balance(farmer.id) == -(480 * 2200)
    assert inventory.get_last_value(wheat.id) == 2200
    tx = accounts.get_transaction(res.transaction_ids[0])
    assert tx.type == "M" and tx.tag == "2"


def test_debit_on_crop_item_is_fifo_costed(crop_setup, sales, accounts, inventory):
    crops, farmer, buyer, wheat = crop_setup
    sales.record("M", "2026-08-01", farmer.id, wheat.display, 100, 20, "2", "emp1", item_id=wheat.id, unit="KG")
    sales.record("M", "2026-08-02", farmer.id, wheat.display, 100, 24, "2", "emp1", item_id=wheat.id, unit="KG")
    res = sales.record("P", "2026-08-05", buyer.id, wheat.display, 1.5, 30, "1", "emp1", item_id=wheat.id, unit="QTL")
    assert res.crop_sale_id and res.amount == 4500 and res.cost == 3200 and res.margin == 1300 and res.short_qty == 0
    assert inventory.quantity(wheat.id) == 50
    assert accounts.get_transaction(res.transaction_ids[0]).tag == "1"
    assert crops.get_sale(res.crop_sale_id).buyer_name == "TRADER"

    with pytest.raises(ValidationError):
        sales.record("P", "2026-08-06", buyer.id, wheat.display, 80, 30, "2", "emp1", item_id=wheat.id, unit="KG")
    short = sales.record(
        "P", "2026-08-06", buyer.id, wheat.display, 80, 30, "2", "emp1", item_id=wheat.id, unit="KG", allow_short=True
    )
    assert short.short_qty == 30


def test_crop_trade_rejects_settlement_tag(crop_setup, sales):
    _crops, farmer, _buyer, wheat = crop_setup
    with pytest.raises(ValidationError):
        sales.record("M", "2026-08-01", farmer.id, wheat.display, 10, 20, "0", "emp1", item_id=wheat.id)


def test_plain_items_unaffected(crop_setup, sales, inventory, accounts):
    _crops, farmer, _buyer, _wheat = crop_setup
    urea = inventory.add_item("urea", 260, 300, unit="BAG", opening_quantity=10)
    res = sales.record("M", "2026-08-01", farmer.id, urea.display, 2, 250, "2", "emp1", item_id=urea.id, unit="BAG")
    assert not res.is_crop and inventory.quantity(urea.id) == 12
    assert accounts.get_transactions(farmer.id)[0].description == f"2 BAG = {urea.display}"


def test_crop_trade_is_atomic(crop_setup, sales, inventory, accounts, monkeypatch):
    crops, farmer, _buyer, wheat = crop_setup
    import hth.services.sales as sales_mod

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(sales_mod.InventoryService, "set_last_value", boom)
    with pytest.raises(RuntimeError):
        sales.record("M", "2026-08-01", farmer.id, wheat.display, 10, 20, "2", "emp1", item_id=wheat.id)
    assert crops.lots() == [] and inventory.quantity(wheat.id) == 0 and accounts.get_transactions(farmer.id) == []
