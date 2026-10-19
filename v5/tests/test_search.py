from hth.modules.bills.service import BillsService
from hth.services.search import SearchService


def test_search_across_entities(db, accounts, inventory, tmp_path):
    from hth.config import Settings

    ram = accounts.add_customer("ram kumar", "dhansu 98123", 0)
    accounts.add_customer("shyam", "other", 0)
    urea = inventory.add_item("urea 45kg", 1, 1, batch="RAM1")
    bills = BillsService(db, Settings(data_dir=tmp_path))
    b = bills.create_bill(
        "2026-08-01",
        "RAM KUMAR",
        "x",
        [dict(name="A", unit="", batch="", expiry_date="", rate=10, item_type="O", quantity=1)],
        "admin",
    )
    s = SearchService(db)
    hits = s.search("ram")
    assert [(h.kind, h.id) for h in hits] == [("customer", ram.id), ("item", urea.id), ("bill", b.bill_number)]
    assert hits[0].label.startswith("👤") and "cat C" in hits[0].subtitle
    assert [h.kind for h in s.search("ram", kinds={"item"})] == ["item"]
    assert s.search(str(ram.id))[0].kind == "customer"
    assert s.search(str(b.bill_number))[-1].kind == "bill"
    assert s.search("dhansu")[0].id == ram.id
    assert s.search("") == [] and s.search("zzz") == []
