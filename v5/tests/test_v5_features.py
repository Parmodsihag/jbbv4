"""Tests for features added in v5."""

from __future__ import annotations

import datetime as dt

import pytest

from hth.domain import numbers
from hth.domain.interest import calculate_interest, fy_label, interest_schedule
from hth.services import auth as auth_module
from hth.services.auth import AuthError
from hth.services.insights import InsightsService
from hth.services.preferences import Preferences

TODAY = dt.date(2026, 8, 29)


@pytest.fixture(autouse=True)
def _indian_numbers():
    numbers.set_style("indian")
    yield
    numbers.set_style("indian")


def test_indian_and_international_grouping():
    assert numbers.amount(1234567.5) == "12,34,567.50"
    assert numbers.amount(-14409317.9) == "-1,44,09,317.90"
    assert numbers.amount(999) == "999.00"
    assert numbers.amount(123456) == "1,23,456.00"
    assert numbers.amount(-0.001) == "0.00"  # no negative zero
    assert numbers.amount(1234567.5, style="international") == "1,234,567.50"
    assert numbers.quantity(1234.5) == "1,234.5" and numbers.quantity(2) == "2"
    assert numbers.amount(None) == "" and numbers.amount("") == ""


def test_number_style_preference_applies_globally(db):
    from hth.ui.format import compact_money, money

    prefs = Preferences(db)
    assert prefs.number_style() == "indian"
    assert money(1234567) == "12,34,567.00" and compact_money(14409317.9) == "1.44 Cr"
    prefs.set_number_style("international")
    assert money(1234567) == "1,234,567.00" and compact_money(14409317.9) == "14.41 M"
    with pytest.raises(ValueError):
        prefs.set_number_style("roman")
    assert prefs.theme() == "dark"
    prefs.set_theme("light")
    assert Preferences(db).theme() == "light"
    prefs.set_lock_minutes(5)
    assert prefs.lock_minutes() == 5
    with pytest.raises(ValueError):
        prefs.set_lock_minutes(-1)


def test_interest_schedule_adds_up_to_calculate_interest():
    pieces = interest_schedule(10000, "2024-11-15", "2026-08-29")
    assert [fy_label(end) for end, _ in pieces] == ["FY 2024-25", "FY 2025-26", "FY 2026-27"]
    total = 0.0
    for _end, v in pieces:
        total += v
    assert round(total, 2) == calculate_interest(10000, "2024-11-15", "2026-08-29")
    assert interest_schedule(100, "2026-08-29", "2026-08-29") == []
    assert fy_label(dt.date(2026, 3, 31)) == "FY 2025-26" and fy_label(dt.date(2026, 4, 1)) == "FY 2026-27"


def test_login_lockout_after_repeated_failures(auth, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(auth_module.time, "monotonic", lambda: clock[0])
    for _ in range(auth_module.MAX_FAILED_ATTEMPTS):
        assert auth.authenticate("admin", "wrong") is None
    with pytest.raises(AuthError, match="Too many failed attempts"):
        auth.authenticate("admin", "admin")  # even the right password waits
    clock[0] += auth_module.LOCKOUT_SECONDS + 1
    assert auth.authenticate("ADMIN", "admin") is not None  # unlocked, counter reset
    assert auth.lockout_remaining("admin") == 0
    # failures are audited; verify() never writes to the audit log
    msgs = [m["message"] for m in auth.db.fetchall("SELECT message FROM audit_log WHERE code = '08'")]
    assert sum("failed login" in m for m in msgs) == auth_module.MAX_FAILED_ATTEMPTS
    n = len(msgs)
    assert auth.verify("admin", "admin") is not None
    assert len(auth.db.fetchall("SELECT 1 FROM audit_log WHERE code = '08'")) == n


def test_change_own_password_does_not_log_a_login(auth):
    admin = auth.verify("admin", "admin")
    before = auth.db.fetchone("SELECT COUNT(*) AS n FROM audit_log WHERE message LIKE 'login %'")["n"]
    auth.change_own_password(admin, "admin", "s3cret")
    after = auth.db.fetchone("SELECT COUNT(*) AS n FROM audit_log WHERE message LIKE 'login %'")["n"]
    assert before == after


def test_day_totals_counts_a_settlement_once(accounts, reports):
    c = accounts.add_customer("a", "", 1000, "2026-08-01")
    accounts.add_transaction(c.id, "2026-08-29", "seed", 250, "P", "1")
    accounts.record_settlement(c.id, "2026-08-29", "cash", 1200, "M", "admin")
    t = reports.day_totals("2026-08-29")
    assert (t.entries, t.debit, t.credit) == (2, 250, 1200)


def test_collections_list(accounts, krar, reports):
    big = accounts.add_customer("big", "rohtak 9812345678", 5000, "2026-01-01")
    small = accounts.add_customer("small", "", 100, "2026-06-01")
    accounts.add_transaction(small.id, "2026-07-01", "cash", 50, "M", "1")
    accounts.add_customer("paid", "", 0)
    krar.add_or_update(big.id, "2026-08-01")
    rows = reports.collections(TODAY)
    assert [r.id for r in rows] == [big.id, small.id]  # only debtors, biggest first
    assert rows[0].phone == "9812345678" and rows[0].status == "Promise overdue"
    assert rows[0].last_payment == "never" and rows[0].days_since_payment is None
    assert rows[1].last_payment == "2026-07-01" and rows[1].days_since_payment == 59
    assert rows[1].status == "No promise"


def test_interest_by_fy_matches_interest_summary(accounts, reports):
    a = accounts.add_customer("a", "", 10000, "2024-06-01")
    accounts.add_transaction(a.id, "2025-05-01", "sale", 2000, "P", "1")
    accounts.add_transaction(a.id, "2025-09-01", "cash", 3000, "M", "2")
    rows = reports.interest_by_fy(TODAY)
    assert [r[0] for r in rows] == ["FY 2024-25", "FY 2025-26", "FY 2026-27"]
    summary = {r[0]: r for r in reports.interest_summary(TODAY)}[a.id]
    assert round(sum(r[1] for r in rows), 2) == summary[2]  # principal
    assert round(sum(r[2] for r in rows), 2) == summary[3]  # interest
    assert rows[0][1] == 10000 and rows[1][1] == -1000


def test_krar_forecast_buckets(accounts, krar, reports):
    a = accounts.add_customer("a", "", 1000, "2026-01-01")
    b = accounts.add_customer("b", "", 500, "2026-01-01")
    c = accounts.add_customer("c", "", 0, "2026-01-01")
    krar.add_or_update(a.id, "2026-08-20")  # overdue
    krar.add_or_update(b.id, "2026-09-02")  # week of Mon 31 Aug
    krar.add_or_update(c.id, "2027-01-01")  # beyond 90 days; owes nothing
    rows = reports.krar_forecast(90, TODAY)
    assert [r[0] for r in rows] == ["Overdue", "Week of 31 Aug 2026", "After 27 Nov 2026"]
    assert rows[0][2] == accounts.get_balance(a.id, TODAY) and rows[2][2] == 0
    assert rows[-1][3] == round(rows[0][2] + rows[1][2], 2)


def test_item_profit_and_reorder(accounts, inventory, sales, reports, db):
    c = accounts.add_customer("c", "", 0)
    urea = inventory.add_item("UREA", stock_value=250, opening_quantity=10, unit="BAG")
    dap = inventory.add_item("DAP", stock_value=1200, opening_quantity=100, unit="BAG")
    today = dt.date.today().isoformat()
    sales.record("P", today, c.id, "UREA", 8, 300, "1", "admin", item_id=urea.id)
    sales.record("P", today, c.id, "DAP", 1, 1100, "1", "admin", item_id=dap.id)
    rows = {r[1]: r for r in reports.item_profit(today, today)}
    assert rows["UREA"][3:] == (8, 2400, 2000, 400, 16.7)
    assert rows["DAP"][6] == -100  # sold below cost
    cash = inventory.add_item("CASH", unit="INR", opening_quantity=0)  # v3 kept money as an item
    sales.record("P", today, c.id, "CASH", 500, 1, "1", "admin", item_id=cash.id)
    suggestions = InsightsService(db).reorder_suggestions()
    assert [s.name for s in suggestions] == ["UREA"]  # 8 sold in 30 days, 2 left; CASH is not stock
    assert suggestions[0].in_stock == 2 and suggestions[0].days_left == 7.5


def test_insights_flag_default_passwords_and_overdue(auth, accounts, krar, db, tmp_path):
    from hth.config import Settings

    a = accounts.add_customer("a", "", 1000, "2026-01-01")
    krar.add_or_update(a.id, "2026-01-05")
    insights = InsightsService(db, Settings(tmp_path)).collect(accounts.summaries(TODAY), TODAY)
    titles = [i.title for i in insights]
    assert "Default password still in use" in titles
    assert any("overdue" in t for t in titles)
    assert "No backup yet" in titles
    assert insights[0].severity == "danger"
    admin = auth.verify("admin", "admin")
    auth.set_password(admin.id, "better-one", "admin")
    emp = auth.verify("emp1", "emp1")
    auth.set_password(emp.id, "better-two", "admin")
    assert InsightsService(db).default_password_users() == []


def test_gst_summary_and_staff_activity(db, reports, auth):
    db.execute(
        "INSERT INTO bills (bill_number, date, customer_name, taxable, cgst, sgst, grand_total) "
        "VALUES (2627001, '2026-08-10', 'X', 1000, 90, 90, 1180)"
    )
    bill_id = db.fetchone("SELECT id FROM bills")["id"]
    db.execute(
        "INSERT INTO bill_lines (bill_id, name, rate, quantity, amount, gst_rate, cgst, sgst) "
        "VALUES (?, 'UREA', 100, 10, 1000, 18, 90, 90)",
        (bill_id,),
    )
    assert reports.gst_summary("2026-08-01", "2026-08-31") == [("2026-08", 18.0, 1, 1000.0, 90.0, 90.0, 1180.0)]
    auth.authenticate("admin", "admin")
    today = dt.date.today().isoformat()
    staff = {r[0]: r for r in reports.staff_activity(today, today)}
    assert staff["admin"][1] == 1 and staff["admin"][6] >= 1


def test_record_lines_is_atomic_and_undo_reverses_everything(accounts, inventory, sales, db):
    from hth.services.accounts import ValidationError
    from hth.services.sales import SaleLine

    c = accounts.add_customer("ram", "", 0)
    urea = inventory.add_item("UREA", stock_value=250, last_value=280, opening_quantity=10, unit="BAG")
    dap = inventory.add_item("DAP", stock_value=1200, last_value=1300, opening_quantity=5, unit="BAG")
    lines = [SaleLine("UREA", 2, 300, urea.id, "BAG"), SaleLine("DAP", 1, 1350, dap.id, "BAG")]
    results = sales.record_lines("P", "2026-08-29", c.id, lines, "1", "admin")
    assert [r.amount for r in results] == [600, 1350]
    assert inventory.quantity(urea.id) == 8 and inventory.quantity(dap.id) == 4
    assert accounts.get_balance(c.id, TODAY) == 1950
    assert inventory.get_item(urea.id).last_value == 300

    # a bad line rolls back the good ones
    bad = [SaleLine("UREA", 1, 300, urea.id, "BAG"), SaleLine("DAP", 1, 100, dap.id, "LTR")]
    with pytest.raises(ValidationError, match="Line 2"):
        sales.record_lines("P", "2026-08-29", c.id, bad, "1", "admin")
    assert inventory.quantity(urea.id) == 8 and accounts.get_balance(c.id, TODAY) == 1950

    assert sales.undo(results, "admin") == 2
    assert accounts.get_transactions(c.id) == []
    assert inventory.quantity(urea.id) == 10 and inventory.quantity(dap.id) == 5
    assert inventory.get_item(urea.id).last_value == 280  # restored
    assert "undo sale" in db.fetchone("SELECT message FROM audit_log ORDER BY id DESC LIMIT 1")["message"]


def test_undo_money_entry_removes_cash_book_line(accounts, sales, db):
    from hth.modules.finance.service import FinanceService

    fin = FinanceService(db)
    fin.ensure_defaults()
    cash = fin.default_account_id()
    c = accounts.add_customer("ram", "", 1000, "2026-08-01")
    r = sales.record("M", "2026-08-29", c.id, "CASH", 1, 400, "1", "admin", money_account_id=cash)
    assert r.finance_entry_id is not None and fin.balance(cash) == 400
    sales.undo([r], "admin")
    assert fin.balance(cash) == 0
    assert [t.description for t in accounts.get_transactions(c.id)] == ["NEW ACCOUNT"]


def test_undo_settlement_and_crop_purchase(accounts, inventory, sales):
    c = accounts.add_customer("a", "", 1000, "2026-01-01")
    r = sales.record("M", "2026-08-29", c.id, "CASH", 1, 900, "0", "admin")
    assert len(r.transaction_ids) == 3  # entry, Settled Amount, Discount
    sales.undo([r], "admin")
    assert len(accounts.get_transactions(c.id)) == 1

    farmer = accounts.add_customer("farmer", "", 0)
    wheat = inventory.add_item("WHEAT", unit="KG", item_type="C")
    lot = sales.record("M", "2026-08-29", farmer.id, "WHEAT", 100, 25, "2", "admin", item_id=wheat.id)
    assert inventory.quantity(wheat.id) == 100
    sales.undo([lot], "admin")
    assert inventory.quantity(wheat.id) == 0 and accounts.get_transactions(farmer.id) == []


def test_restore_backup_round_trip_with_safety_copy(tmp_path):
    from hth.config import Settings
    from hth.db import schema
    from hth.db.connection import Database
    from hth.services.accounts import AccountsService
    from hth.services.backup import BackupService

    settings = Settings(tmp_path)
    settings.ensure_dirs()
    db = Database(settings.db_path)
    schema.initialize(db)
    acc = AccountsService(db)
    acc.add_customer("before", "", 100, "2026-01-01")
    svc = BackupService(db, settings)
    snapshot = svc.manual()
    acc.add_customer("after", "", 200, "2026-01-02")

    info = svc.inspect(snapshot)
    assert info.customers == 1 and info.schema_version == schema.MIGRATIONS[-1][0]
    safety = svc.restore(snapshot, "admin")
    assert [c.name for c in acc.list_customers()] == ["BEFORE"]
    assert BackupService.inspect(safety).customers == 2  # what was there before the restore
    assert "restored backup" in db.fetchone("SELECT message FROM audit_log ORDER BY id DESC LIMIT 1")["message"]

    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database at all" * 100)
    with pytest.raises(ValueError):
        svc.inspect(junk)
    other = Database(tmp_path / "other.db")
    other.execute("CREATE TABLE t (x)")
    with pytest.raises(ValueError, match="not a High Table Holdings"):
        svc.inspect(tmp_path / "other.db")
    newer = Database(tmp_path / "newer.db")
    schema.initialize(newer)
    newer.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="newer version"):
        svc.inspect(tmp_path / "newer.db")


def test_balance_message_for_every_kind_of_balance(accounts, db):
    from hth.services.reminders import ReminderService

    r = ReminderService(db)
    owes = accounts.add_customer("ram", "village 9812345678", 1500, "2026-08-29")
    owed = accounts.add_customer("shyam", "", 700, "2026-08-29", tx_type="M")
    settled = accounts.add_customer("mohan", "", 0)
    m = r.balance_message(owes.id, TODAY)
    assert "Rs 1,500.00" in m.text and m.whatsapp_url and "9812345678" in m.whatsapp_url
    assert "owes you Rs 700.00" in r.balance_message(owed.id, TODAY).text
    assert "fully settled" in r.balance_message(settled.id, TODAY).text


def test_rank_matches_any_word_order():
    from hth.ui.widgets.searchbox import rank_matches

    data = [(12, "12 RAM KUMAR ROHTAK"), (3, "3 SHRI RAM HISAR"), (120, "120 RAMESH X"), (7, "7 MOHAN ROHTAK")]
    assert [k for k, _ in rank_matches("ram", data)] == [12, 120, 3]
    assert [k for k, _ in rank_matches("rohtak ram", data)] == [12]
    assert [k for k, _ in rank_matches("12", data)][0] == 12
    assert rank_matches("  ", data) == []


def test_customer_search_matches_all_words(accounts, db):
    from hth.services.search import SearchService

    a = accounts.add_customer("ram kumar", "rohtak", 0)
    accounts.add_customer("ram singh", "hisar", 0)
    hits = SearchService(db).search("rohtak ram", kinds={"customer"})
    assert [h.id for h in hits] == [a.id]
    assert SearchService(db).search(str(a.id), kinds={"customer"})[0].id == a.id


def test_counter_slip(accounts, inventory, sales, db):
    from hth.services.sales import SaleLine
    from hth.services.slips import SlipService

    c = accounts.add_customer("ram kumar", "rohtak", 100, "2026-08-01")
    urea = inventory.add_item("UREA", stock_value=250, opening_quantity=10, unit="BAG")
    results = sales.record_lines("P", "2026-08-29", c.id, [SaleLine("UREA", 2, 300, urea.id, "BAG")], "2", "admin")
    html = SlipService(db).html(results, c.id, "admin")
    assert "SALE" in html and "RAM KUMAR" in html and "600.00" in html and "UREA" in html
    assert "Account balance" in html
    from hth.services.accounts import ValidationError

    with pytest.raises(ValidationError, match="Nothing to print"):
        SlipService(db).html([], c.id)


def test_text_scale_preference(db):
    prefs = Preferences(db)
    assert prefs.text_scale() == 1.0
    prefs.set_text_scale(1.3)
    assert Preferences(db).text_scale() == 1.3
    with pytest.raises(ValueError):
        prefs.set_text_scale(2.0)
