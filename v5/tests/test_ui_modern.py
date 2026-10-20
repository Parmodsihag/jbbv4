"""The new layout (v5.5) and the switch between it and the classic one.  Drives the real
window, so like ``test_ui_smoke.py`` it only runs with ``HTH_UI_TESTS=1``."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("HTH_UI_TESTS"), reason="set HTH_UI_TESTS=1 to run UI tests")

AREAS = ["today", "counter", "khata", "stock", "money", "reports", "settings"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("HTH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HTH_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr("hth.assistant.voice.bundled_dir", lambda: tmp_path / "no-bundled-voice")
    from hth.config import get_settings
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.services.auth import AuthService
    from hth.services.preferences import Preferences
    from hth.ui.app import App
    from hth.ui.views.setup import mark_setup

    settings = get_settings()
    db = Database(settings.db_path)
    initialize(db)
    AuthService(db).ensure_default_users()
    mark_setup(db, True)
    Preferences(db).set_layout("new")
    application = App(db, settings)
    application.update()
    yield application
    application.destroy()


def _pump(app, n=30):
    for _ in range(n):
        app.update()


def _login(app, username, password):
    app._login.username.set(username)
    app._login.password.set(password)
    app._login.submit()
    _pump(app)


def _area(app, key):
    return app._views[key]


def test_admin_lands_on_today_and_old_keys_find_their_area(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "KHARKHODA", 1000, "2026-01-01")
    ctx.inventory.add_item("UREA", 260, 300, opening_quantity=10)
    ctx.krar.add_or_update(c.id, "2026-01-05")

    _login(app, "admin", "admin")
    assert app._modern is not None and app.layout == "new"
    assert app._active == "today"
    assert not hasattr(app, "sidebar")  # nothing of the classic shell is left around
    assert set(app._modern.area_buttons) == {"today", "counter", "khata", "stock", "money", "reports"}
    for key in AREAS:
        app.navigate(key)
        _pump(app, 20)
        assert app._active == key

    # every classic screen key still works, from any old code path
    expected = {
        "dashboard": ("today", "dashboard"),
        "sales": ("counter", "sales"),
        "customers": ("khata", "customers"),
        "karar": ("khata", "karar"),
        "items": ("stock", "items"),
        "crops": ("stock", "crops"),
        "finance": ("money", "finance"),
        "bills": ("money", "bills"),
        "reports": ("reports", "reports"),
        "users": ("settings", "users"),
        "settings": ("settings", "settings"),
    }
    for old, (area, tab) in expected.items():
        app.navigate(old)
        _pump(app, 20)
        assert app._active == area, old
        if hasattr(_area(app, area), "current"):  # a rebuilt area (Counter) has no tabs
            assert _area(app, area).current == tab, old

    app.navigate("customers", customer_id=c.id)
    _pump(app)
    assert app.find_view("customers").page.customer.id == c.id
    # Alt-letters of the classic layout are bound for the new one
    assert {"<Alt-s>", "<Alt-k>", "<Alt-b>", "<Alt-u>", "<Alt-h>"} <= set(app._shell_keys)
    assert ("Alt+K", "Khata › Collections") in app._modern.shortcut_list()
    from hth.ui.widgets.dialogs import ShortcutSheet

    app.show_shortcuts()  # F1: the new layout's areas and the Counter's keys
    _pump(app)
    sheets = [w for w in app.winfo_children() if isinstance(w, ShortcutSheet)]
    assert sheets
    sheets[0].destroy()


def _counter(app):
    app.navigate("counter")
    _pump(app)
    return app._views["counter"]


def test_counter_sale_with_lines_and_paid_now(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 0, "2026-01-01")
    urea = ctx.inventory.add_item("UREA", 260, 300, unit="BAG", opening_quantity=10)
    dap = ctx.inventory.add_item("DAP", 1290, 1350, unit="BAG", opening_quantity=5)
    _login(app, "admin", "admin")
    view = _counter(app)
    assert app.find_view("sales") is view  # the old key reaches the new Counter
    assert view.intent.key == "sale"
    view.pick_customer(c.id)
    for item, qty in ((urea, "4"), (dap, "2")):
        view.item.set(item.id)
        view._on_item(item.id, focus=False)
        view.qty.set(qty)
        view.add_line()
    assert len(view._lines) == 2 and view.rate.get() == ""
    view.paid.insert(0, "1,000")
    view.recalc()
    assert view.stat_rows[0].value.cget("text") == "₹3,900.00"  # 4 x 300 + 2 x 1350
    view.save()
    _pump(app)
    assert ctx.inventory.quantity(urea.id) == 6 and ctx.inventory.quantity(dap.id) == 3
    assert ctx.accounts.get_balance(c.id) == 2900
    assert view._last is not None and len(view._last[0]) == 3  # two lines + the payment
    assert not view._lines and view.paid.get() == ""
    n = ctx.sales.undo(view._last[0], "admin")
    assert n == 3 and ctx.accounts.get_balance(c.id) == 0


def test_counter_payment_in_keeps_the_promise_and_settles(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 1000, "2026-01-01", tag="2")
    ctx.krar.add_or_update(c.id, "2026-01-05")
    _login(app, "admin", "admin")
    view = _counter(app)
    view.set_intent("in")
    view.pick_customer(c.id)
    assert view._promise == "2026-01-05" and view.keep_promise.get() == 1
    view.amount.insert(0, "400")
    view.recalc()
    view.save()
    _pump(app)
    assert ctx.accounts.get_balance(c.id) == 600
    assert ctx.krar.unsettled_dates(c.id) == []  # the promise was marked kept
    # settle the rest: tag 0 writes the payment, the settled amount and the discount
    view.amount.insert(0, "500")
    view.settle.select()
    view.save()
    _pump(app)
    assert ctx.accounts.get_balance(c.id) == 0
    # Ctrl+Shift+Enter never saves a sale
    view.set_intent("sale")
    view._save_credit()
    assert ctx.accounts.get_balance(c.id) == 0


def test_counter_crop_purchase_makes_a_lot(app):
    from hth.modules.crop_trading.service import CropService

    ctx = app.ctx
    farmer = ctx.accounts.add_customer("FARMER", "X", 0, "2026-01-01")
    wheat = CropService(ctx.db).add_crop("WHEAT", "KG")
    _login(app, "admin", "admin")
    view = _counter(app)
    view.set_intent("purchase")
    view.pick_customer(farmer.id)
    view.item.refresh()
    view.item.set(wheat.id)
    view._on_item(wheat.id, focus=False)
    assert view._is_crop() and view.interest.get() == "No interest"
    assert view.crop.winfo_manager() and str(view.add_button.cget("state")) == "disabled"
    view.qty.set("1000")
    view.kaat.set("10")
    view.rate.set("24")
    view.recalc()
    assert view.net_label.cget("text").startswith("990")
    view.save()
    _pump(app)
    assert ctx.inventory.quantity(wheat.id) == 990
    assert ctx.accounts.get_balance(farmer.id) == -990 * 24  # we owe the farmer


def test_employee_lands_on_counter_and_sees_no_admin_screens(app):
    _login(app, "emp1", "emp1")
    assert app._active == "counter"
    app.navigate("users")  # not theirs: nothing happens
    _pump(app)
    assert app._active == "counter"
    app.navigate("settings")
    _pump(app)
    assert [t.key for t in _area(app, "settings").area.tabs] == ["settings"]


def test_switch_both_ways_while_signed_in(app):
    _login(app, "admin", "admin")
    app.apply_layout("classic")
    _pump(app)
    assert app._modern is None and app.layout == "classic"
    assert app.is_signed_in and app._active == "settings"
    assert "dashboard" in app._nav_buttons and hasattr(app, "sidebar")
    assert app.find_view("settings").layout_choice.get() == "Classic"
    app.navigate("karar")  # classic keys mean classic screens again
    _pump(app)
    assert app._active == "karar"

    app.apply_layout("new")
    _pump(app)
    assert app._modern is not None and app.is_signed_in
    assert app._active == "settings" and not app._nav_buttons
    assert not hasattr(app, "sidebar")
    assert app.find_view("settings").layout_choice.get() == "New"
    # lock / unlock and a language rebuild keep the new layout
    app.lock()
    _pump(app)
    app.unlock()
    _pump(app)
    assert app._modern is not None
    app.apply_language("hi")
    _pump(app, 40)
    assert app._modern is not None and app._active == "settings"
    for key in AREAS:
        app.navigate(key)
        _pump(app, 20)
        assert app._active == key
    app.apply_language("en")
    _pump(app)


def test_signing_out_and_in_keeps_the_shop_layout(app):
    _login(app, "admin", "admin")
    app.logout()
    _pump(app)
    assert app._modern is None and app._shell is None
    _login(app, "emp1", "emp1")
    assert app._modern is not None and app._active == "counter"


def _wait(app, cond, timeout=8.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        app.update()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_khata_customer_page_and_a_careful_delete(app, monkeypatch):
    ctx = app.ctx
    ram = ctx.accounts.add_customer("RAM", "KHARKHODA 9812345678", 1000, "2026-01-01", tag="2")
    ctx.accounts.add_customer("SHYAM", "SAMPLA", 0, "2026-01-01")
    ctx.accounts.add_transaction(ram.id, "2026-02-01", "UREA", 500, "P", "2", "admin")
    _login(app, "admin", "admin")
    app.navigate("customers", customer_id=ram.id)
    khata = app._views["khata"]
    assert khata.current == "customers"
    page = khata.customers
    assert _wait(app, lambda: len(page.table.rows) == 2)
    assert page.page.customer.id == ram.id
    assert page.page.amount.cget("text") == "₹1,500.00"
    page.page.period.set("All")
    page.page._apply_period()
    assert len(page.page.ledger.rows) == 2
    assert page.page.detail_rows["Phone"].cget("text") == "9812345678"
    assert hasattr(page.page, "more_button")  # admin: edit / category / delete

    said = {}
    monkeypatch.setattr("hth.ui.widgets.dialogs.confirm", lambda parent, title, text: said.update(t=text) or True)
    urea = next(r for r in page.page.ledger.rows if r[1] == "UREA")
    page.page.delete(urea)
    _pump(app)
    assert "Stock is not changed" in said["t"] and "₹1,500.00" in said["t"] and "₹1,000.00" in said["t"]
    assert ctx.accounts.get_balance(ram.id) == 1000

    # the chips: owe us / we owe
    page.chips.set("Owe us")
    page._filter()
    assert [r[3] for r in page.table.rows] == [ram.id]


def test_khata_collections_buckets_and_side_panel(app, monkeypatch):
    import datetime as dt

    ctx = app.ctx
    late = ctx.accounts.add_customer("LATE", "X", 500, "2026-01-01", tag="2")
    due = ctx.accounts.add_customer("DUE", "X", 300, "2026-01-01", tag="2")
    never = ctx.accounts.add_customer("NEVER", "X", 200, "2026-01-01", tag="2")
    ctx.krar.add_or_update(late.id, "2026-01-05")
    ctx.krar.add_or_update(due.id, dt.date.today().isoformat())
    _login(app, "admin", "admin")
    app.navigate("karar")
    _pump(app)
    khata = app._views["khata"]
    assert khata.current == "karar"
    col = khata.collections
    assert col.bucket.get() == "Late"
    assert [r[7] for r in col.table.rows] == [late.id]
    col.table.select_first()
    _pump(app)
    assert col.selected[7] == late.id and "500" in col.reminder.get("1.0", "end")
    col.bucket.set("Today")
    col.reload()
    assert [r[7] for r in col.table.rows] == [due.id]
    col.bucket.set("Owe us, no promise")
    col.reload()
    assert never.id in [r[7] for r in col.table.rows] and late.id not in [r[7] for r in col.table.rows]

    monkeypatch.setattr("hth.ui.widgets.dialogs.confirm", lambda *a: True)
    col.bucket.set("Late")
    col.reload()
    col.table.select_first()
    _pump(app)
    col.kept()
    _pump(app)
    assert ctx.krar.unsettled_dates(late.id) == [] and col.table.rows == []


def test_khata_for_an_employee(app):
    c = app.ctx.accounts.add_customer("RAM", "X", 100, "2026-01-01")
    _login(app, "emp1", "emp1")
    app.navigate("customers", customer_id=c.id)
    _pump(app)
    page = app._views["khata"].customers.page
    assert page.customer.id == c.id
    assert not hasattr(page, "more_button")  # no corrections menu for employees
    assert page._row_actions(("x",) * 10)[0][0] == "Only an admin can change an entry"
