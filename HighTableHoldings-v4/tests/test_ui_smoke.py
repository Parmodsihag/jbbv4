"""Drives the real window through every screen.  Needs a display, so it is skipped unless
``HTH_UI_TESTS=1`` is set:  ``HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py``."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("HTH_UI_TESTS"), reason="set HTH_UI_TESTS=1 to run UI tests")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("HTH_DATA_DIR", str(tmp_path))
    from hth.config import get_settings
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.services.auth import AuthService
    from hth.ui.app import App

    settings = get_settings()
    db = Database(settings.db_path)
    initialize(db)
    AuthService(db).ensure_default_users()
    application = App(db, settings)
    application.update()
    yield application
    application.destroy()


def _pump(app, n=30):
    for _ in range(n):
        app.update()


def test_admin_and_employee_walkthrough(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 1000, "2026-01-01")
    item = ctx.inventory.add_item("UREA", 260, 300, opening_quantity=10)
    # open krar -> the dashboard and karar tables get rows with hidden trailing ids
    ctx.krar.add_or_update(c.id, "2026-01-05")
    ctx.krar.add_or_update(ctx.accounts.add_customer("SHYAM", "Y", 0).id, "2099-01-01")

    app._login.username.set("admin")
    app._login.password.set("admin")
    app._login.submit()
    _pump(app)
    assert ctx.user.is_admin
    assert set(app._nav_buttons) >= {
        "dashboard",
        "sales",
        "customers",
        "items",
        "karar",
        "reports",
        "users",
        "settings",
    }
    for key in [
        "dashboard",
        "sales",
        "customers",
        "items",
        "karar",
        "reports",
        "users",
        "settings",
    ]:
        app.navigate(key)
        _pump(app, 40)
        assert app._active == key

    app.navigate("customers", customer_id=c.id)
    _pump(app)
    assert app._views["customers"].ledger_panel.customer.id == c.id

    sales = app._views["sales"]
    app.navigate("sales")
    sales.account.set(c.id)
    sales.item.set(item.id)
    sales.quantity.set("2")
    sales.price.set("300")
    sales.submit("P")
    _pump(app)
    assert ctx.inventory.quantity(item.id) == 8
    assert sales.recent.rows[0][1] == "Sale"

    app.toggle_theme()
    app.navigate("dashboard")
    _pump(app, 40)

    app.logout()
    _pump(app)
    app._login.username.set("emp1")
    app._login.password.set("emp1")
    app._login.submit()
    _pump(app)
    assert "users" not in app._nav_buttons
    assert "bills" in app._nav_buttons  # employees may create invoices
    app.navigate("bills")
    _pump(app, 30)
    assert not hasattr(app._views["bills"], "batch")  # ...but not run the month batch
    app.navigate("users")  # silently refused
    assert app._active != "users"
    app.navigate("reports")
    _pump(app, 40)
    assert "audit" not in app._views["reports"]._buttons
