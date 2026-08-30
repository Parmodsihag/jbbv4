import datetime as dt

import pytest

from hth.services.accounts import ValidationError
from hth.services.categories import CategoryService
from hth.services.reports import ReportsService

AS_OF = dt.date(2026, 8, 30)


@pytest.fixture
def cats(db):
    return CategoryService(db)


def _seed(accounts):
    # balances: big & old -> high score, small & recent -> low score
    big = accounts.add_customer("big old", "", 100000, "2023-01-01")
    mid = accounts.add_customer("mid", "", 5000, "2026-03-01")
    small = accounts.add_customer("small new", "", 200, "2026-08-25")
    clean = accounts.add_customer("clean", "", 0)
    default = accounts.add_customer("defaulter", "", 80000, "2019-01-01")
    return big, mid, small, clean, default


def test_defaults_and_settings(cats):
    assert cats.customer_report_categories() == {"A", "B", "C", "D"}
    assert cats.thresholds() == (0.25, 0.5, 0.75) and cats.exclude_defaulters_from_score()
    assert cats.default_customer_category() == "C" and cats.velocity_days() == (30, 90, 180)
    cats.set_customer_report_categories(["a", "B", "e"])
    assert cats.customer_report_categories() == {"A", "B", "E"}
    with pytest.raises(ValidationError):
        cats.set_customer_report_categories(["Z"])
    with pytest.raises(ValidationError):
        cats.set_thresholds(0.5, 0.4, 0.9)
    cats.set_thresholds(0.2, 0.4, 0.6)
    assert cats.thresholds() == (0.2, 0.4, 0.6)
    with pytest.raises(ValidationError):
        cats.set_default_customer_category("E")
    cats.set_default_customer_category("b")
    assert cats.default_customer_category() == "B"
    with pytest.raises(ValidationError):
        cats.set_velocity_days(90, 30, 180)


def test_new_customer_gets_default_category(cats, accounts):
    assert accounts.add_customer("x", "", 0).category == "C"
    cats.set_default_customer_category("A")
    assert accounts.add_customer("y", "", 0).category == "A"
    assert accounts.get_customer(accounts.add_customer("z", "", 0).id).category == "A"


def test_manual_category_locks_and_e_is_manual_only(cats, accounts):
    big, mid, small, clean, default = _seed(accounts)
    cats.set_customer_category(default.id, "e", "admin")
    c = accounts.get_customer(default.id)
    assert c.category == "E" and c.category_locked
    with pytest.raises(ValidationError):
        cats.set_customer_category(mid.id, "F", "admin")
    cats.set_customer_category(mid.id, "B", "admin")

    report = cats.rescore_customers("admin", AS_OF)
    by_id = {x.id: x.category for x in accounts.list_customers()}
    assert by_id[default.id] == "E"  # untouched
    assert by_id[mid.id] == "B"  # locked, untouched
    assert by_id[clean.id] == "A"  # nothing outstanding
    assert by_id[big.id] == "D" and by_id[small.id] in ("A", "B")
    assert report.defaulters == 1 and report.locked == 1 and report.changed >= 2
    assert sum(report.counts.values()) == 5

    with pytest.raises(ValidationError):
        cats.unlock_customer(default.id, "admin")
    cats.unlock_customer(mid.id, "admin")
    assert not accounts.get_customer(mid.id).category_locked
    report2 = cats.rescore_customers("admin", AS_OF)
    assert report2.locked == 0 and accounts.get_customer(mid.id).category != "E"


def test_defaulters_kept_out_of_score_population(cats, accounts):
    big, mid, small, clean, default = _seed(accounts)
    cats.set_customer_category(default.id, "E", "admin")
    with_e = {s.id: s for s in accounts.summaries(AS_OF)}
    without_e = {s.id: s for s in cats.customer_summaries(AS_OF, scope="all")}
    assert without_e[default.id].scored is False and without_e[default.id].score == 0
    assert with_e[default.id].scored is True and with_e[default.id].score > 0
    # with the (older, larger) defaulter out of the normalisation, the big customer is the max
    assert without_e[big.id].score == 1.0 and with_e[big.id].score < 1.0
    cats.set_exclude_defaulters_from_score(False)
    again = {s.id: s for s in cats.customer_summaries(AS_OF, scope="all")}
    assert again[default.id].scored and again[big.id].score < 1.0


def test_report_scope(cats, accounts, inventory, db):
    big, mid, small, clean, default = _seed(accounts)
    cats.set_customer_category(default.id, "E", "admin")
    reports = ReportsService(db)
    scoped = cats.customer_summaries(AS_OF)
    assert default.id not in {s.id for s in scoped} and len(scoped) == 4
    assert len(cats.customer_summaries(AS_OF, scope="all")) == 5
    k = reports.kpis(scoped)
    k_all = reports.kpis(cats.customer_summaries(AS_OF, scope="all"))
    assert k.customers == 4 and k_all.customers == 5 and k.receivable < k_all.receivable
    assert default.id not in {r[0] for r in reports.interest_summary(AS_OF)}
    assert default.id in {r[0] for r in reports.interest_summary(AS_OF, categories=None)}
    accounts.add_transaction(default.id, AS_OF.strftime("%Y-%m-%d"), "x", 10, "P", "2")
    assert default.id not in {r[0] for r in reports.customer_activity("2026-08-01", "2026-08-31")}
    assert default.id in {r[0] for r in reports.customer_activity("2026-08-01", "2026-08-31", categories=None)}
    flow_all = sum(m.debit for m in reports.monthly_flow(1, categories=None))
    flow_scoped = sum(m.debit for m in reports.monthly_flow(1))
    assert flow_all - flow_scoped == 10
    # explicit empty scope = nothing
    assert reports.interest_summary(AS_OF, categories=set()) == []
    assert cats.customer_scope("all") is None and cats.customer_scope() == {"A", "B", "C", "D"}


def test_item_categories(cats, inventory, db):
    fast = inventory.add_item("fast", 10, 12, opening_quantity=100)
    slow = inventory.add_item("slow", 10, 12, opening_quantity=100)
    dead = inventory.add_item("dead", 10, 12, opening_quantity=100)
    gone = inventory.add_item("gone", 10, 12, opening_quantity=5)
    inventory.add_item_transaction(fast.id, "2026-08-20", 0, 1, "s")
    inventory.add_item_transaction(slow.id, "2026-06-01", 0, 1, "s")
    inventory.add_item_transaction(dead.id, "2025-01-01", 0, 1, "s")
    cats.set_item_category(gone.id, "E", "admin")
    report = cats.auto_categorize_items("admin", AS_OF)
    by_id = {i.id: i.category for i in inventory.list_items()}
    assert by_id == {fast.id: "A", slow.id: "B", dead.id: "D", gone.id: "E"}
    assert report.defaulters == 1 and report.changed == 3
    assert {s.item.id for s in inventory.summaries(categories=cats.item_report_categories())} == {
        fast.id,
        slow.id,
        dead.id,
    }
    reports = ReportsService(db)
    assert gone.id not in {r[0] for r in reports.item_movement("2026-01-01", "2026-12-31")}
    assert gone.id in {r[0] for r in reports.item_movement("2026-01-01", "2026-12-31", categories=None)}
    assert dead.id in {r[0] for r in reports.dead_stock(90, AS_OF)}
    k = reports.kpis(cats.customer_summaries(AS_OF))
    assert k.items == 3 and k.stock_value == 99 * 10 * 3
    cats.set_item_category(dead.id, "C", "admin")
    report2 = cats.auto_categorize_items("admin", AS_OF)
    assert report2.locked == 1 and inventory.get_item(dead.id).category == "C"
