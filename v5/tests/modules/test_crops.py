import datetime as dt

import pytest

from hth.modules.crop_trading.rates import CsvRateProvider, RatesService
from hth.modules.crop_trading.service import CropService
from hth.services.accounts import ValidationError


@pytest.fixture
def crops(db):
    return CropService(db)


def test_add_crop_is_item_type_c(crops, inventory):
    wheat = crops.add_crop("wheat", "kg")
    assert wheat.item_type == "C" and wheat.unit == "KG" and inventory.quantity(wheat.id) == 0
    with pytest.raises(ValidationError):
        crops.add_crop("WHEAT")
    urea = inventory.add_item("urea", 1, 1, unit="BAG")
    with pytest.raises(ValidationError):
        crops.get_crop(urea.id)
    assert [c.id for c in crops.crops()] == [wheat.id]


def test_purchase_credits_farmer_adds_stock_and_lot(crops, accounts, inventory):
    farmer = crops.add_party("ramesh", "dhansu")
    wheat = crops.add_crop("wheat")
    lot = crops.record_purchase(
        "2026-08-01", farmer.id, wheat.id, 10, 0.5, 2200, "QTL", "admin", quality="a", notes="moist"
    )
    assert (lot.gross_qty, lot.deduction_qty, lot.qty, lot.remaining_qty) == (1000, 50, 950, 950)
    assert lot.rate == 2200 and lot.amount == 950 * 2200 and lot.quality == "A"
    assert inventory.quantity(wheat.id) == 950
    assert accounts.get_balance(farmer.id) == -(950 * 2200)  # we owe the farmer
    tx = accounts.get_transaction(lot.tx_id)
    assert tx.type == "M" and tx.tag == "2" and "CROP PURCHASE 950 KG WHEAT @ 2200 [A]" == tx.description
    with pytest.raises(ValidationError):
        crops.record_purchase("2026-08-01", farmer.id, wheat.id, 10, 12, 2200, "KG", "admin")
    with pytest.raises(ValidationError):
        crops.record_purchase("2026-08-01", farmer.id, wheat.id, 10, 0, 2200, "LTR", "admin")


def test_sale_fifo_margin_and_ledger(crops, accounts, inventory):
    f1, f2 = crops.add_party("f1"), crops.add_party("f2")
    buyer = crops.add_party("mandi trader")
    wheat = crops.add_crop("wheat")
    lot1 = crops.record_purchase("2026-08-01", f1.id, wheat.id, 100, 0, 20, "KG", "admin", quality="B")
    lot2 = crops.record_purchase("2026-08-02", f2.id, wheat.id, 100, 0, 24, "KG", "admin", quality="A")
    preview = crops.preview_cost(wheat.id, 150)
    assert (
        preview.cost == 100 * 20 + 50 * 24
        and preview.short_qty == 0
        and [a.lot_id for a in preview.allocations] == [lot1.id, lot2.id]
    )

    sale = crops.record_sale("2026-08-05", wheat.id, 1.5, 30, "QTL", "admin", buyer_id=buyer.id)
    assert sale.qty == 150 and sale.amount == 4500 and sale.cost == 3200 and sale.margin == 1300
    assert sale.margin_pct == pytest.approx(40.62, abs=0.01)
    assert [(a.lot_id, a.qty) for a in sale.allocations] == [(lot1.id, 100), (lot2.id, 50)]
    assert crops.get_lot(lot1.id).remaining_qty == 0 and crops.get_lot(lot2.id).remaining_qty == 50
    assert inventory.quantity(wheat.id) == 50
    assert accounts.get_balance(buyer.id) == 4500

    with pytest.raises(ValidationError):
        crops.record_sale("2026-08-06", wheat.id, 80, 30, "KG", "admin")  # only 50 left
    short = crops.record_sale("2026-08-06", wheat.id, 80, 30, "KG", "admin", allow_short=True)
    assert short.short_qty == 30 and short.buyer_name == "CASH" and short.tx_id is None
    assert short.cost == 50 * 24 + 30 * 24  # uncovered part costed at the last purchase rate
    assert inventory.quantity(wheat.id) == -30

    stock = crops.stock()
    assert stock[0].qty == 0 and stock[0].inventory_qty == -30

    crops.delete_sale(short.id, "admin")
    assert crops.get_lot(lot2.id).remaining_qty == 50 and inventory.quantity(wheat.id) == 50
    with pytest.raises(ValidationError):
        crops.delete_lot(lot1.id, "admin")  # already sold
    crops.delete_sale(sale.id, "admin")
    assert accounts.get_balance(buyer.id) == 0
    crops.delete_lot(lot1.id, "admin")
    assert accounts.get_balance(f1.id) == 0 and inventory.quantity(wheat.id) == 100


def test_payments_and_reports(crops, accounts):
    farmer = crops.add_party("farmer")
    buyer = crops.add_party("buyer")
    wheat = crops.add_crop("wheat")
    mustard = crops.add_crop("mustard")
    crops.record_purchase("2026-08-01", farmer.id, wheat.id, 200, 0, 20, "KG", "admin", quality="A")
    crops.record_purchase("2026-08-02", farmer.id, mustard.id, 100, 10, 50, "KG", "admin", quality="B")
    crops.record_sale("2026-08-03", wheat.id, 100, 25, "KG", "admin", buyer_id=buyer.id)
    crops.record_sale("2026-08-04", mustard.id, 50, 60, "KG", "admin", buyer_id=buyer.id)
    crops.pay_farmer(farmer.id, "2026-08-05", 3000, "admin")
    crops.receive_from_buyer(buyer.id, "2026-08-05", 1000, "admin")
    assert accounts.get_balance(farmer.id) == -(200 * 20 + 90 * 50 - 3000)
    assert accounts.get_balance(buyer.id) == 2500 + 3000 - 1000

    s = crops.summary("2026-08-01", "2026-08-31")
    assert s["purchased_amount"] == 8500 and s["sold_amount"] == 5500 and s["sold_cost"] == 4500 and s["margin"] == 1000
    assert s["stock_cost"] == 100 * 20 + 40 * 50
    by_crop = {r[1]: r for r in crops.margin_by_crop("2026-08-01", "2026-08-31")}
    assert by_crop["WHEAT"][7] == 500 and by_crop["MUSTARD"][7] == 500 and by_crop["WHEAT"][8] == 25.0
    assert crops.margin_by_buyer("2026-08-01", "2026-08-31")[0][1] == "BUYER"
    farmers = crops.purchases_by_farmer("2026-08-01", "2026-08-31")
    assert farmers[0][1] == "FARMER" and farmers[0][6] == 290 and farmers[0][7] == 8500
    quality = {(r[0], r[1]): r for r in crops.purchases_by_quality("2026-08-01", "2026-08-31")}
    assert quality[("MUSTARD", "B")][5] == 50
    assert len(crops.lots(open_only=True)) == 2


def test_rates_valuation_and_estimate(crops, db):
    wheat = crops.add_crop("wheat")
    farmer = crops.add_party("f")
    crops.record_purchase("2026-08-01", farmer.id, wheat.id, 100, 0, 20, "KG", "admin")
    rates = RatesService(db)
    with pytest.raises(ValidationError):
        rates.set_rate(wheat.id, "2026-08-01", 0)
    for i, r in enumerate([21, 22, 23, 24, 25]):
        rates.set_rate(wheat.id, f"2026-08-{10 + i:02d}", r)
    rates.set_rate(wheat.id, "2026-08-14", 26)  # same day+source overwrites
    assert rates.latest(wheat.id, dt.date(2026, 8, 20)) == (26, "2026-08-14", "manual")
    assert rates.latest(wheat.id, dt.date(2026, 8, 11)) == (22, "2026-08-11", "manual")
    assert rates.latest(wheat.id, dt.date(2026, 8, 1)) is None
    st = crops.stock(dt.date(2026, 8, 20))[0]
    assert st.market_rate == 26 and st.market_value == 2600 and st.unrealized == 600 and st.avg_cost == 20
    est = rates.estimate_rate(wheat.id, days_ahead=1)
    assert est.based_on == 5 and est.trend_per_day > 1 and est.rate > 26
    assert len(rates.history(wheat.id)) == 5
    rates.delete_rate(wheat.id, "2026-08-14", "manual")
    assert len(rates.history(wheat.id)) == 4


def test_csv_rate_provider(crops, db, tmp_path):
    wheat = crops.add_crop("wheat")
    csv = tmp_path / "r.csv"
    csv.write_text(
        f"crop,date,rate\nWHEAT,2026-08-01,2210\n{wheat.id},2026-08-02,2230\nUNKNOWN,2026-08-02,1\n", encoding="utf-8"
    )
    quotes = CsvRateProvider(csv).fetch(crops.crops(), dt.date(2026, 8, 2))
    assert [(q.date, q.rate, q.source) for q in quotes] == [("2026-08-01", 2210, "csv"), ("2026-08-02", 2230, "csv")]
    assert RatesService(db).apply_quotes(quotes) == 2
    assert RatesService(db).latest(wheat.id, dt.date(2026, 8, 5))[0] == 2230
    (tmp_path / "bad.csv").write_text("crop,date,rate\nNOPE,x,y\n")
    with pytest.raises(ValidationError):
        CsvRateProvider(tmp_path / "bad.csv").fetch(crops.crops(), dt.date.today())
