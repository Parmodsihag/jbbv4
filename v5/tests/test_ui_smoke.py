"""Drives the real window through every screen.  Needs a display, so it is skipped unless
``HTH_UI_TESTS=1`` is set:  ``HTH_UI_TESTS=1 pytest tests/test_ui_smoke.py``."""

from __future__ import annotations

import os

import pytest

from hth.ui.format import today_str

pytestmark = pytest.mark.skipif(not os.environ.get("HTH_UI_TESTS"), reason="set HTH_UI_TESTS=1 to run UI tests")

CORE_KEYS = ["dashboard", "sales", "customers", "items", "karar", "reports", "users", "settings"]


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
    if not os.environ.get("HTH_UI_FRESH"):
        from hth.ui.views.setup import mark_setup

        mark_setup(db, True)
    application = App(db, settings)
    application.update()
    yield application
    application.destroy()


def _pump(app, n=30):
    for _ in range(n):
        app.update()


def _wait(app, cond, timeout=8.0):
    """Pump the event loop until ``cond()`` is true (background loads finish asynchronously)."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        app.update()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _buttons(widget):
    import customtkinter as ctk

    out = []
    for ch in widget.winfo_children():
        if isinstance(ch, ctk.CTkButton):
            out.append(ch)
        out.extend(_buttons(ch))
    return out


def _login(app, username, password):
    app._login.username.set(username)
    app._login.password.set(password)
    app._login.submit()
    _pump(app)


def test_admin_and_employee_walkthrough(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 1000, "2026-01-01")
    item = ctx.inventory.add_item("UREA", 260, 300, opening_quantity=10)
    # open krar -> the dashboard and karar tables get rows with hidden trailing ids
    ctx.krar.add_or_update(c.id, "2026-01-05")
    ctx.krar.add_or_update(ctx.accounts.add_customer("SHYAM", "Y", 0).id, "2099-01-01")

    _login(app, "admin", "admin")
    assert ctx.user.is_admin
    assert set(app._nav_buttons) >= set(CORE_KEYS) | {"bills", "crops", "finance"}
    for key in CORE_KEYS + ["bills", "crops", "finance"]:
        app.navigate(key)
        _pump(app, 40)
        assert app._active == key
    assert len(app._views["dashboard"].krar_table.rows) == 2
    app._views["karar"].bucket.set("All")
    app._views["karar"].reload()
    assert len(app._views["karar"].table.rows) == 2
    app.navigate("reports", report="datacheck")
    _pump(app, 40)

    app.navigate("customers", customer_id=c.id)
    _pump(app)
    assert app._views["customers"].ledger_panel.customer.id == c.id

    # plain stock sale through the Sales screen
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
    assert not sales.is_crop

    # bills module: manual invoice through the real panel
    app.navigate("bills")
    _pump(app, 40)
    bills_view = app._views["bills"]
    new = bills_view.new
    new.name.set("RAM")
    new.item.set(item.id)
    new._on_item(item.id, "")
    new.qty.set("2")
    new.add_line()
    assert len(new._lines) == 1
    saved = bills_view.svc.create_bill(new.date.get(), new.name.get(), new.address.get(), new._lines, "admin")
    assert saved.grand_total > 0
    bills_view.browse.reload()
    _pump(app)
    assert bills_view.browse.table.rows[0][0] == saved.bill_number

    # crop trading through the main Sales screen
    cv = app._views["crops"]
    wheat = cv.svc.add_crop("WHEAT", "KG")
    app.navigate("sales")
    _pump(app)
    sales.account.set(c.id)
    sales.item.set(wheat.id)
    sales._on_item(wheat.id)
    _pump(app, 5)
    assert sales.is_crop and sales.crop_box.winfo_ismapped()
    sales.quantity.set("2")
    sales.unit.set("QTL")
    sales.deduction.set("0.1")
    sales.price.set("22")
    sales.submit("M")
    _pump(app, 5)
    assert not sales.crop_box.winfo_ismapped()
    sales.item.set(wheat.id)
    sales._on_item(wheat.id)
    sales.quantity.set("100")
    sales.price.set("26")
    sales.submit("P")
    _pump(app)
    assert sales.recent.rows[0][1] == "Crop sale"
    app.navigate("crops")
    _pump(app, 30)
    assert cv.lots.lots_table.rows[0][6] == 190  # net 1.9 QTL = 190 KG
    assert cv.lots.sales_table.rows[0][8] == 400  # margin (26-22)*100
    cv.tabs.set("Stock & rates")
    cv.stock.reload()
    _pump(app)
    assert cv.stock.table.rows[0][2] == 90
    cv.tabs.set("Reports")
    cv.reports.which.set("Margin by crop")
    cv.reports.run()
    _pump(app)
    assert cv.reports.table.rows[0][7] == 400

    # categories: mark a defaulter, re-score from Settings, filter the accounts list
    bad = ctx.accounts.add_customer("BAD DEBT", "Z", 50000, "2019-01-01")
    ctx.categories.set_customer_category(bad.id, "E", "admin")
    app.navigate("settings")
    _pump(app, 30)
    sv = app._views["settings"]
    sv.cust_cat_vars["E"].set(False)
    sv.save_categories()
    report = ctx.categories.rescore_customers("admin")
    assert report.defaulters == 1 and ctx.accounts.get_customer(bad.id).category == "E"
    app.navigate("customers")
    lst = app._views["customers"].list_panel
    assert _wait(app, lambda: any(r[6] == "E" for r in lst.table.rows))
    lst.cat_filter.set("E")
    lst._filter()
    assert [r[1] for r in lst.table.rows] == ["BAD DEBT"]
    lst.cat_filter.set("All")
    lst._filter()
    app.navigate("customers", customer_id=bad.id)
    _pump(app)
    assert "category E" in app._views["customers"].ledger_panel.name_label.cget("text")
    dash = app._views["dashboard"]
    dash._data = None
    app.navigate("dashboard")
    total = len(ctx.accounts.list_customers())
    assert _wait(app, lambda: dash._data is not None and dash._data["kpis"].customers == total - 1)  # E excluded
    app.navigate("reports", report="summary")
    rv = app._views["reports"]
    assert _wait(app, lambda: rv.table.rows and all(r[6] != "E" for r in rv.table.rows))
    rv._param_widgets["scope"].set("All categories")
    rv.run()
    assert _wait(app, lambda: any(r[6] == "E" for r in rv.table.rows))

    # finance: receipt from the Sales screen lands in the cash book; expense via the panel
    app.navigate("finance")
    _pump(app, 40)
    fv = app._views["finance"]
    cash_id = fv.svc.money_accounts()[0].id
    app.navigate("sales")
    _pump(app)
    sales.account.set(c.id)
    sales.item.set(None, "CASH")
    _pump(app, 5)
    assert sales.money.winfo_ismapped() and sales.money.get() == "CASH"
    sales.quantity.set("1")
    sales.price.set("250")
    sales.tag.set("2 No interest")
    sales.submit("M")
    _pump(app)
    assert fv.svc.balance(cash_id) == 250
    fv.svc.add_expense(today_str(), cash_id, fv.head_id("RENT"), 100, "rent", "admin")
    app.navigate("finance")
    _pump(app, 40)
    assert fv.book.table.rows and fv.book.table.rows[-1][6] == 150
    fv.tabs.set("Reports")
    fv.reports.which.set("Profit & loss")
    fv.reports.run()
    _pump(app)
    assert any(r[0] == "NET PROFIT" for r in fv.reports.table.rows)

    # statement from the ledger (service path used by the dialog)
    st = ctx.statements.build(c.id, "2026-01-01", today_str())
    path = ctx.statements.write(st, ctx.settings.export_dir)
    assert path.exists() and "RAM" in path.read_text(encoding="utf-8")
    app.navigate("customers", customer_id=c.id)
    _pump(app)
    assert any(b.cget("text") == "Statement" for b in _buttons(app._views["customers"].ledger_panel))

    # global search (Ctrl+K)
    app.open_search()
    _pump(app, 10)
    pal = app._palette
    pal.var.set("RAM")
    _pump(app, 5)
    assert pal.hits and pal.hits[0].kind == "customer"
    pal.pick()
    _pump(app, 10)
    assert app._active == "customers" and app._views["customers"].ledger_panel.customer.id == c.id
    app.open_search()
    app._palette.var.set(str(saved.bill_number))
    _pump(app, 5)
    assert any(h.kind == "bill" for h in app._palette.hits)
    app._palette.listbox.selection_clear(0, "end")
    app._palette.listbox.selection_set([i for i, h in enumerate(app._palette.hits) if h.kind == "bill"][0])
    app._palette.pick()
    _pump(app, 20)
    assert app._active == "bills" and app._views["bills"].browse.table.rows[0][0] == saved.bill_number

    app.toggle_theme()
    app.navigate("dashboard")
    _pump(app, 40)

    app.logout()
    _pump(app)
    _login(app, "emp1", "emp1")
    assert "users" not in app._nav_buttons
    assert "bills" in app._nav_buttons  # employees may create invoices
    assert "crops" in app._nav_buttons and "finance" in app._nav_buttons
    app.navigate("finance")
    _pump(app, 30)
    assert app._views["finance"].setup is None  # employees: cash book only
    app.navigate("bills")
    _pump(app, 30)
    assert not hasattr(app._views["bills"], "batch")  # ...but not run the month batch
    app.navigate("users")  # silently refused
    assert app._active != "users"
    app.navigate("reports")
    _pump(app, 40)
    assert "audit" not in app._views["reports"]._buttons


def test_first_run_wizard(tmp_path, monkeypatch):
    monkeypatch.setenv("HTH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HTH_UI_FRESH", "1")
    from hth.config import get_settings
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.services.auth import AuthService
    from hth.ui.app import App

    settings = get_settings()
    db = Database(settings.db_path)
    initialize(db)
    AuthService(db).ensure_default_users()
    app = App(db, settings)
    try:
        _pump(app, 10)
        assert app._setup is not None and app._login is None
        w = app._setup
        w.name.set("MY SHOP")
        w.admin_pw.set("admin")  # same as default -> refused
        w.admin_pw2.set("admin")
        w.emp_pw.set("emp-pass")
        w.emp_pw2.set("emp-pass")
        w.finish()
        _pump(app, 5)
        assert "different" in w.error.cget("text") and app._setup is not None
        w.admin_pw.set("secret1")
        w.admin_pw2.set("secret1")
        w.finish()
        _pump(app, 10)
        assert app._setup is None and app._login is not None
        assert app.ctx.auth.authenticate("admin", "secret1") is not None
        assert app.ctx.auth.authenticate("admin", "admin") is None
        assert app.ctx.auth.authenticate("emp1", "emp-pass") is not None
        assert app.ctx.company.profile().name == "MY SHOP"
        # a second launch goes straight to login
        app.show_login()
        _pump(app, 5)
        assert app._login is not None and app._setup is None
    finally:
        app.destroy()


def test_v5_sales_lines_undo_lock_and_day_change(app, monkeypatch):
    import datetime as dt

    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 0)
    urea = ctx.inventory.add_item("UREA", 260, 300, unit="BAG", opening_quantity=10)
    dap = ctx.inventory.add_item("DAP", 1200, 1350, unit="BAG", opening_quantity=5)
    _login(app, "admin", "admin")
    app.navigate("sales")
    _pump(app)
    sales = app._views["sales"]

    # two lines, posted together as one debit
    sales.account.set(c.id)
    sales.item.set(urea.id)
    sales._on_item(urea.id)
    sales.quantity.set("2")
    sales.add_line()
    assert len(sales._lines) == 1 and sales.lines_box.winfo_manager()
    sales.item.set(dap.id)
    sales._on_item(dap.id)
    sales.quantity.set("1")
    sales.submit("P")  # the line still in the form is included
    _pump(app)
    assert ctx.inventory.quantity(urea.id) == 8 and ctx.inventory.quantity(dap.id) == 4
    assert ctx.accounts.get_balance(c.id) == 600 + 1350
    assert not sales._lines and not sales.lines_box.winfo_manager()
    assert sales.undo_button.cget("state") == "normal"

    # undo puts everything back
    monkeypatch.setattr("hth.ui.views.sales.confirm", lambda *a, **k: True)
    sales.undo_last()
    _pump(app)
    assert ctx.accounts.get_transactions(c.id) == []
    assert ctx.inventory.quantity(urea.id) == 10 and ctx.inventory.quantity(dap.id) == 5
    assert sales.undo_button.cget("state") == "disabled"

    # lock hides the work, wrong password keeps it locked, right one restores it
    sales.quantity.set("7")
    app.lock()
    _pump(app)
    assert app.is_locked and not sales.winfo_ismapped()
    app.navigate("reports")  # ignored while locked
    assert app._active == "sales"
    app._lock.password.set("nope")
    app._lock.submit()
    assert app.is_locked
    app._lock.password.set("admin")
    app._lock.submit()
    _pump(app)
    assert not app.is_locked and sales.winfo_ismapped() and sales.quantity.get() == "7"

    # a new day rolls the untouched date field forward
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    sales.date._auto_value = yesterday
    sales.date.set(yesterday)
    app._today = dt.date.today() - dt.timedelta(days=1)
    app._tick()
    assert sales.date.get() == dt.date.today().isoformat()
    assert app.date_label.cget("text") == dt.date.today().strftime("%A, %d %B %Y")

    # collapsed sidebar is remembered
    app.toggle_sidebar()
    _pump(app)
    assert app.prefs.sidebar_compact()
    app.toggle_sidebar()
    assert not app.prefs.sidebar_compact()

    # every report in the catalogue runs without error
    from hth.ui.views.reports import REPORTS

    app.navigate("reports")
    rv = app._views["reports"]
    for spec in REPORTS:
        if any(p.kind == "customer" for p in spec.params):
            continue
        rv.select(spec)
        assert _wait(app, lambda: not rv.table.footer.cget("text").startswith("Running")), spec.key


def test_v5_ledger_views_and_snapshot(app):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "ROHTAK 9812345678", 1000, "2024-01-01")
    ctx.accounts.add_transaction(c.id, "2025-02-01", "UREA", 500, "P", "1")
    ctx.accounts.record_settlement(c.id, "2025-03-01", "CASH", 1500, "M", "admin")
    ctx.accounts.add_transaction(c.id, today_str(), "DAP", 300, "P", "1")
    _login(app, "admin", "admin")
    app.navigate("customers", customer_id=c.id)
    _pump(app)
    ledger = app._views["customers"].ledger_panel
    assert len(ledger.table.rows) == 6
    ledger.period.set("Current period")
    ledger._apply_view()
    assert [r[2] for r in ledger.table.rows] == ["DAP"]
    ledger.period.set("All")
    ledger._apply_view()
    ledger.table.filter("urea")
    assert [r[2] for r in ledger.table.rows] == ["UREA"]
    ledger.table.filter("")
    ledger.new_entry()
    _pump(app)
    sales = app._views["sales"]
    assert app._active == "sales" and sales.account.get_key() == c.id
    assert sales.snapshot.customer_id == c.id and sales.snapshot.table.rows[0][1] == "DAP"


def test_v5_quick_money_slip_and_shortcuts(app, monkeypatch):
    ctx = app.ctx
    c = ctx.accounts.add_customer("RAM", "X", 1000, "2026-01-01")
    _login(app, "admin", "admin")
    app.navigate("sales")
    _pump(app)
    sales = app._views["sales"]
    sales.account.set(c.id)
    sales.quick_money("CASH")
    assert sales.item.get_text() == "CASH" and sales.quantity.get() == "1"
    _pump(app, 5)
    assert sales.money.winfo_manager() and sales.money.get() == "CASH"
    sales.price.set("400")
    sales.submit("M")
    _pump(app)
    assert ctx.accounts.get_balance(c.id) < 1000
    opened = []
    monkeypatch.setattr("hth.ui.format.open_path", lambda p: opened.append(p))
    sales.print_slip()
    assert opened and opened[0].exists() and "RECEIPT" in opened[0].read_text(encoding="utf-8")

    app.show_shortcuts()
    _pump(app, 5)
    from hth.ui.widgets.dialogs import ShortcutSheet

    sheets = [w for w in app.winfo_children() if isinstance(w, ShortcutSheet)]
    assert sheets
    sheets[0].destroy()
