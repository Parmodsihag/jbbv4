import pytest

from hth.modules.crop_trading.rates import RatesService
from hth.modules.crop_trading.service import CropService
from hth.services.accounts import ValidationError


def test_same_family_conversion(inventory, accounts, sales):
    seed = inventory.add_item("wheat seed", 40, 48, unit="KG", opening_quantity=500)
    c = accounts.add_customer("ram", "", 0)
    sales.record("P", "2026-08-01", c.id, seed.display, 250, 48, "2", "u", item_id=seed.id, unit="G")
    assert inventory.quantity(seed.id) == 499.75
    assert inventory.conversion_factor(seed.id, "QTL") == 0.01 and inventory.conversion_factor(seed.id, "LTR") is None
    factor = inventory.change_unit(seed.id, "qtl", "admin")
    assert factor == 0.01
    item = inventory.get_item(seed.id)
    assert item.unit == "QTL" and item.stock_value == 4000 and item.last_value == 4800
    assert inventory.quantity(seed.id) == pytest.approx(4.9975)
    sale = next(t for t in inventory.get_item_transactions(seed.id) if t.sale > 0)
    assert (
        sale.sale == 0.0025
        and inventory.db.fetchone("SELECT value FROM item_transactions WHERE id = ?", (sale.id,))["value"] == 12
    )
    # value unchanged, stock value in money unchanged
    assert round(inventory.quantity(seed.id) * item.stock_value, 2) == round(499.75 * 40, 2)
    assert inventory.change_unit(seed.id, "QTL", "admin") == 1.0  # no-op


def test_unrelated_units_need_a_factor(inventory):
    pkt = inventory.add_item("seed packet", 100, 120, unit="PKT", opening_quantity=10)
    with pytest.raises(ValidationError):
        inventory.change_unit(pkt.id, "KG", "admin")
    with pytest.raises(ValidationError):
        inventory.change_unit(pkt.id, "KG", "admin", factor=0)
    assert inventory.change_unit(pkt.id, "KG", "admin", factor=25) == 25
    item = inventory.get_item(pkt.id)
    assert item.unit == "KG" and item.stock_value == 4 and item.last_value == 4.8
    assert inventory.quantity(pkt.id) == 250
    # relabel only
    inventory.update_item(pkt.id, "admin", unit="BAG")
    assert inventory.get_item(pkt.id).unit == "BAG" and inventory.quantity(pkt.id) == 250


def test_crop_history_converted(db, inventory, accounts, sales):
    crops = CropService(db)
    farmer, buyer = accounts.add_customer("f", "", 0), accounts.add_customer("b", "", 0)
    wheat = crops.add_crop("wheat", "KG")
    sales.record("M", "2026-08-01", farmer.id, wheat.display, 200, 20, "2", "u", item_id=wheat.id, unit="KG")
    sale = sales.record("P", "2026-08-02", buyer.id, wheat.display, 50, 26, "2", "u", item_id=wheat.id, unit="KG")
    RatesService(db).set_rate(wheat.id, "2026-08-02", 24)
    inventory.change_unit(wheat.id, "QTL", "admin")
    lot = crops.lots()[0]
    assert (lot.qty, lot.remaining_qty, lot.rate, lot.amount) == (2, 1.5, 2000, 4000)
    s = crops.get_sale(sale.crop_sale_id)
    assert (s.qty, s.rate, s.amount, s.cost, s.margin) == (0.5, 2600, 1300, 1000, 300)
    assert s.allocations[0].qty == 0.5 and s.allocations[0].cost_rate == 2000
    assert RatesService(db).latest(wheat.id)[0] == 2400
    stock = crops.stock()[0]
    assert stock.qty == 1.5 and stock.cost_value == 3000 and stock.market_value == 3600
    # a further sale in KG still converts to the new stock unit
    sales.record("P", "2026-08-03", buyer.id, wheat.display, 50, 26, "2", "u", item_id=wheat.id, unit="KG")
    assert crops.stock()[0].qty == 1.0
