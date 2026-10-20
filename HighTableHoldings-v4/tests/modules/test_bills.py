import datetime as dt
import random
import re
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from hth.config import Settings
from hth.modules.bills.numwords import integer_words, to_currency
from hth.modules.bills.service import MAX_RENDER_TOTAL, BillsService, _n, compute_line, normalize_month, totals
from hth.services.accounts import ValidationError

LINE = dict(name="X", unit="PCS", batch="NA", expiry_date="NA", rate=10, item_type="O", quantity=1)


def _docx_text(path):
    with zipfile.ZipFile(path) as zf:
        return re.sub(r"<[^>]+>", "", zf.read("word/document.xml").decode("utf-8"))


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
    assert bills.next_bill_number(dt.date(2026, 8, 29)) == 2627002
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


JULY = dt.date(2026, 7, 1)


@pytest.mark.parametrize(
    "items, n_bills",
    [
        ([(1, 1000.0, JULY)], 80),  # one big item: crashed on ~78% of seeds
        ([(1, 300.0, JULY)], 40),
        ([(1, 120.0, JULY), (2, 40.0, dt.date(2026, 7, 15))], 40),  # the batch test above: ~20% of seeds
        ([(1, 10.5, JULY)], 80),  # fractional total
    ],
)
def test_batch_quantities_never_crash(items, n_bills):
    # randint(low, high) got low > high once an item had less than a usual bill's worth left
    for seed in range(300):
        rng = random.Random(seed)
        dates = BillsService.distribute_dates(n_bills, JULY, dt.date(2026, 7, 31), rng)
        plan, leftovers = BillsService.distribute_quantities(items, dates, rng)
        assert leftovers == {}
        for item_id, total, start_date in items:
            assert sum(lines.get(item_id, 0) for _, lines in plan) == pytest.approx(total)
            assert all(day >= start_date for day, lines in plan if item_id in lines)
        assert all(q > 0 for _, lines in plan for q in lines.values())


def test_invoice_prints_exact_amounts(bills):
    # ':g' kept 6 significant digits: 19999.99 printed as 20000, 1234567 as 1.23457e+06
    values = (1542.0, 12345.67, 19999.99, 10620.45, 1234567.0, 2.5, 0.125, 0.0, -0.0)
    assert [_n(v) for v in values] == [
        "1542",
        "12345.67",
        "19999.99",
        "10620.45",
        "1234567",
        "2.5",
        "0.125",
        "0",
        "0",
    ]
    mono = dict(LINE, name="MONO", rate=1694.5, item_type="P", quantity=7)
    b = bills.create_bill("2026-08-29", "RAM", "", [mono], "admin")
    ctx = bills.template_context(b)
    assert (ctx["taxable_amount_total"], ctx["ctotal"], ctx["stotal"], ctx["grand_total"]) == (
        "11861.5",
        "1067.54",
        "1067.54",
        "13996.58",
    )
    assert "13996.58" in _docx_text(bills.render_docx(b))


def test_batch_is_all_or_nothing(bills, monkeypatch):
    bills.add_month_item("2026-07", "UREA", "BAG", 300, "F", "2026-07-01", "NA", "NA", 120)
    bills.add_month_item("2026-07", "DAP", "BAG", 1350, "F", "2026-07-01", "NA", "NA", 60)
    with pytest.raises(ValidationError, match="negative"):  # used to fail later, half-way through the batch
        bills.add_month_item("2026-07", "TYPO", "PCS", -45, "O", "2026-07-20", "NA", "NA", 5)
    with pytest.raises(ValidationError):
        bills.add_month_item("2026-07", "NAN", "PCS", "nan", "O", "2026-07-20", "NA", "NA", 5)

    # a start number that runs into an existing bill is refused before anything is written
    bills.create_bill("2026-08-05", "A", "", [LINE], "admin", bill_number=2627002)
    with pytest.raises(ValidationError, match="2627002"):
        bills.generate_month("2026-07", 60, 2627001, "admin", render=False, rng=random.Random(0))
    assert bills.list_bills("2026-07") == []

    # any failure part-way rolls the whole month back, so a retry is not blocked
    real, calls = bills.create_bill, []

    def failing(*args, **kwargs):
        calls.append(1)
        if len(calls) == 5:
            raise RuntimeError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(bills, "create_bill", failing)
    with pytest.raises(RuntimeError):
        bills.generate_month("2026-07", 60, 2627100, "admin", render=False, rng=random.Random(0))
    assert len(calls) == 5 and bills.list_bills("2026-07") == []
    monkeypatch.undo()
    res = bills.generate_month("2026-07", 60, 2627100, "admin", render=False, rng=random.Random(0))
    assert len(bills.list_bills("2026-07")) == res.created > 0


def test_pdf_conversion_works_from_worker_thread(bills, monkeypatch):
    # "PDF + merge range" converts on a worker thread; Word is driven over COM, which must be
    # initialised per thread and docx2pdf never does it ("CoInitialize has not been called").
    docx2pdf = pytest.importorskip("docx2pdf")
    com = pytest.importorskip("win32com.client") if sys.platform.startswith("win") else None

    def fake_convert(src, dst):
        if com:
            com.Dispatch("Scripting.Dictionary")  # any COM call fails on an uninitialised thread
        Path(dst).write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(docx2pdf, "convert", fake_convert)
    b = bills.create_bill("2026-08-29", "RAM", "", [LINE], "admin")
    result = {}

    def work():
        try:
            result["path"] = bills.render_pdf(b)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    worker = threading.Thread(target=work)
    worker.start()
    worker.join()
    assert "error" not in result, result.get("error")
    assert result["path"].exists()


def test_bill_numbers_restart_each_financial_year(bills):
    assert bills.create_bill("2027-03-30", "A", "", [LINE], "admin").bill_number == 2627001
    assert bills.next_bill_number(dt.date(2027, 3, 31)) == 2627002
    assert bills.next_bill_number(dt.date(2027, 4, 2)) == 2728001  # used to continue at 2627002
    assert bills.create_bill("2027-04-02", "B", "", [LINE], "admin").bill_number == 2728001
    assert bills.create_bill("2027-03-31", "C", "", [LINE], "admin").bill_number == 2627002  # back-dated
    bills.create_bill("2027-03-31", "D", "", [LINE], "admin", bill_number=2627999)
    assert bills.next_bill_number(dt.date(2027, 3, 31)) == 26271000  # not 2628000, which reads as another FY
    bills.create_bill("2027-04-03", "E", "", [LINE], "admin", bill_number=7)  # typed by hand, outside the scheme
    assert bills.next_bill_number(dt.date(2027, 4, 3)) == 2728002


def test_stale_invoice_files_are_rendered_again(bills):
    old = bills.create_bill("2026-08-01", "RAM", "", [dict(LINE, name="OLD ITEM")], "admin")
    path = bills.render_docx(old)
    # the bill is gone but its file is not (restored backup, or the DOCX was open in Word on delete)
    bills.db.execute("DELETE FROM bills WHERE id = ?", (old.id,))
    new = bills.create_bill("2026-08-02", "SHYAM", "", [dict(LINE, name="NEW ITEM")], "admin")
    assert new.bill_number == old.bill_number
    text = _docx_text(bills.render_docx(new))
    assert "NEW ITEM" in text and "OLD ITEM" not in text
    # an up-to-date file is reused untouched (so "Open DOCX" still works while Word has it open)
    stamp = path.stat().st_mtime_ns
    assert bills.render_docx(new) == path and path.stat().st_mtime_ns == stamp


def test_stale_pdfs_are_converted_again_and_not_merged(bills, monkeypatch):
    docx2pdf = pytest.importorskip("docx2pdf")
    pypdf = pytest.importorskip("pypdf")
    converted = []

    def blank_pdf(dst):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(100, 100)
        with open(dst, "wb") as fh:
            writer.write(fh)

    monkeypatch.setattr(docx2pdf, "convert", lambda src, dst: (converted.append(src), blank_pdf(dst)))
    old = bills.create_bill("2026-08-01", "RAM", "", [dict(LINE, name="OLD ITEM")], "admin")
    bills.render_pdf(old)
    bills.db.execute("DELETE FROM bills WHERE id = ?", (old.id,))  # its DOCX and PDF stay behind
    new = bills.create_bill("2026-08-02", "SHYAM", "", [dict(LINE, name="NEW ITEM")], "admin")
    bills.render_docx(new)  # "Open DOCX": the DOCX is re-rendered for the new bill...
    bills.render_pdf(new)
    assert len(converted) == 2  # ...so the old bill's PDF is out of date and is converted again
    bills.render_pdf(new)
    assert len(converted) == 2  # but not again while it is current

    # merging takes only PDFs of bills that exist, not a leftover file in the number range
    other = bills.create_bill("2026-08-03", "MOHAN", "", [LINE], "admin")
    bills.render_pdf(other)
    blank_pdf(bills.pdf_dir / f"{other.bill_number + 1}.pdf")
    merged = bills.merge_pdfs(new.bill_number, other.bill_number + 1)
    assert len(pypdf.PdfReader(str(merged)).pages) == 2
