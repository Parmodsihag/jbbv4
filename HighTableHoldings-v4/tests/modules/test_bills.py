import random

import pytest

from hth.config import Settings
from hth.modules.bills.numwords import integer_words, to_currency
from hth.modules.bills.service import MAX_RENDER_TOTAL, BillsService, compute_line, normalize_month, totals
from hth.services.accounts import ValidationError


@pytest.fixture
def bills(db, tmp_path):
    settings = Settings(data_dir=tmp_path)
    settings.ensure_dirs()
    return BillsService(db, settings)


def test_tax_rates_by_type():
    p = compute_line("MONO", "LTR", "B1", "2027-01-01", 450, "P", 2)
    f = compute_line("UREA", "BAG", "NA", "NA", 300, "F", 3)
    s = compute_line("WHEAT", "KG", "NA", "NA", 48, "S", 10)
    assert (p.amount, p.gst_rate, p.cgst, p.sgst) == (900, 9, 81, 81)
    assert (f.amount, f.gst_rate, f.cgst, f.sgst) == (900, 2.5, 22.5, 22.5)
    assert (s.amount, s.gst_rate, s.cgst, s.sgst) == (480, 0, 0, 0)
    assert totals([p, f, s]) == (2280, 103.5, 103.5, 2487.0)
    # v3.6.3: tax rounded to 2 dp
    x = compute_line("X", "PCS", "NA", "NA", 33.33, "P", 1)
    assert x.cgst == 3.0 and x.sgst == 3.0
    with pytest.raises(ValidationError):
        compute_line("X", "PCS", "NA", "NA", 10, "P", 0)


def test_hindi_words():
    assert integer_words("1250") == "एक हज़ार दौ सौ पचास"
    assert integer_words("100") == "एक सौ "
    assert integer_words("2487") == "दौ हज़ार चार सौ सत्तासी"
    assert integer_words("125000") == "एक लाख पच्चीस हज़ार "
    assert to_currency(1) == "एक रुपया"
    assert to_currency(1250) == "एक हज़ार दौ सौ पचास रूपये"
    assert to_currency(1250.5) == "एक हज़ार दौ सौ पचास रूपये, पचास पैसे"
    assert to_currency(7.01) == "सात रूपये, एक पैसा"


def test_create_bill_numbering_and_render(bills, accounts):
    c = accounts.add_customer("ram", "dhansu", 0)
    assert bills.next_bill_number(__import__("datetime").date(2026, 8, 29)) == 2627001
    b = bills.create_bill(
        "2026-08-29",
        "RAM",
        "Dhansu",
        [
            dict(name="MONO", unit="LTR", batch="B1", expiry_date="2027-01-01", rate=450, item_type="P", quantity=2),
            dict(name="WHEAT", unit="KG", batch="NA", expiry_date="NA", rate=48, item_type="S", quantity=10),
        ],
        "admin",
        customer_id=c.id,
    )
    assert b.bill_number == 2627001 and b.taxable == 1380 and b.cgst == 81 and b.grand_total == 1542
    assert len(b.lines) == 2 and b.customer_id == c.id
    assert bills.next_bill_number() == 2627002
    with pytest.raises(ValidationError):
        bills.create_bill(
            "2026-08-29",
            "X",
            "",
            [dict(name="A", unit="", batch="", expiry_date="", rate=1, item_type="O", quantity=1)],
            "admin",
            bill_number=2627001,
        )
    with pytest.raises(ValidationError):
        bills.create_bill("2026-08-29", "", "", [], "admin")

    path = bills.render_docx(b)
    assert path.exists() and path.name == "2627001.docx"
    import re
    import zipfile

    # Read the raw XML: the header block (bill number, date, customer) sits in text boxes,
    # which python-docx's paragraph/table walk does not visit.
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", "", xml)
    assert "2627001" in text and "RAM" in text and "MONO" in text and "29-08-2026" in text
    assert "एक हज़ार पाँच सौ बयालीस रूपये" in text
    assert "{{" not in text

    assert [x.bill_number for x in bills.list_bills("2026-08")] == [2627001]
    assert bills.list_bills(search="ram")[0].id == b.id
    bills.delete_bill(b.id, "admin")
    assert bills.get_bill(b.id) is None and not path.exists()


def test_month_items_and_batch(bills):
    assert normalize_month("2026-1") == "2026-01"
    with pytest.raises(ValidationError):
        normalize_month("2026/01")
    a = bills.add_month_item("2026-07", "UREA", "BAG", 300, "F", "2026-07-01", "NA", "NA", 120)
    b = bills.add_month_item("2026-07", "MONO", "LTR", 450, "P", "2026-07-15", "B1", "2027-01-01", 40)
    with pytest.raises(ValidationError):
        bills.add_month_item("2026-07", "X", "PCS", 1, "O", "2026-08-01", "NA", "NA", 1)  # start outside month
    assert [i.name for i in bills.month_items("2026-07")] == ["UREA", "MONO"]
    assert bills.month_years() == ["2026-07"]

    res = bills.generate_month("2026-07", 40, 2627101, "admin", render=False, rng=random.Random(1))
    assert res.created > 20 and res.first_number == 2627101 and res.last_number == 2627101 + res.created - 1
    assert res.unsold == {} and res.not_rendered == []
    created = [bills.get_bill(x.id) for x in bills.list_bills("2026-07", limit=10000)]
    sold = {}
    for bill in created:
        assert "2026-07-01" <= bill.date <= "2026-07-31"
        for line in bill.lines:
            sold[line.name] = sold.get(line.name, 0) + line.quantity
            if line.name == "MONO":
                assert bill.date >= "2026-07-15"
            assert line.quantity > 0
    assert sold == {"UREA": 120, "MONO": 40}  # every unit accounted for, exactly once
    n, taxable, gst, grand = bills.month_summary("2026-07")
    assert n == res.created and taxable == 120 * 300 + 40 * 450

    with pytest.raises(ValidationError):
        bills.generate_month("2026-07", 40, 2627101, "admin", render=False)
    assert bills.delete_month("2026-07", "admin") == res.created
    assert bills.list_bills("2026-07") == []
    bills.delete_month_item(a.id)
    bills.delete_month_item(b.id)
    assert bills.month_items("2026-07") == []


def test_batch_flags_large_bills(bills):
    bills.add_month_item("2026-06", "GOLD", "PCS", 50000, "O", "2026-06-01", "NA", "NA", 3)
    res = bills.generate_month("2026-06", 3, 1, "admin", render=True, rng=random.Random(3))
    assert res.rendered == 0 and len(res.not_rendered) == res.created
    assert all(bills.get_by_number(n).grand_total >= MAX_RENDER_TOTAL for n in res.not_rendered)
