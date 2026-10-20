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
        assert _area(app, area).current == tab, old

    app.navigate("customers", customer_id=c.id)
    _pump(app)
    assert app.find_view("customers").ledger_panel.customer.id == c.id
    # Alt-letters of the classic layout are bound for the new one
    assert {"<Alt-s>", "<Alt-k>", "<Alt-b>", "<Alt-u>", "<Alt-h>"} <= set(app._shell_keys)
    assert ("Alt+K", "Khata › Collections") in app._modern.shortcut_list()


def test_a_sale_through_the_counter_area(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 0, "2026-01-01")
    item = ctx.inventory.add_item("UREA", 260, 300, opening_quantity=10)
    _login(app, "admin", "admin")
    app.navigate("sales")
    _pump(app)
    sales = app.find_view("sales")
    sales.account.set(c.id)
    sales.item.set(item.id)
    sales.quantity.set("2")
    sales.price.set("300")
    sales.submit("P")
    _pump(app)
    assert ctx.inventory.quantity(item.id) == 8


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
