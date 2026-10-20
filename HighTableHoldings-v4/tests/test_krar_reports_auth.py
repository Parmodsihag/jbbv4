import datetime as dt

import pytest

from hth.domain.models import User
from hth.services.auth import AuthError
from hth.services.permissions import Permission, has_permission

TODAY = dt.date(2026, 8, 29)


def test_krar_lifecycle(accounts, krar):
    c = accounts.add_customer("a", "", 0)
    k1 = krar.add_or_update(c.id, "2026-08-29")
    k2 = krar.add_or_update(c.id, "2026-09-05")  # reschedule -> same krar
    assert k1 == k2
    assert krar.unsettled_dates(c.id) == ["2026-08-29", "2026-09-05"]
    assert [e.customer_id for e in krar.entries("future", TODAY)] == [c.id]
    assert krar.entries("today", TODAY) == [] and krar.entries("past", TODAY) == []
    krar.settle(c.id)
    assert krar.unsettled_customer_ids() == []
    assert krar.settled_history(c.id)[0][1] == 2
    k3 = krar.add_or_update(c.id, "2026-08-01")
    assert k3 != k1
    assert [e.krar_id for e in krar.entries("past", TODAY)] == [k3]


def test_reports(accounts, inventory, sales, krar, reports):
    a = accounts.add_customer("a", "", 1000, "2026-01-01")
    b = accounts.add_customer("b", "", 0)
    accounts.add_transaction(b.id, "2026-08-25", "paid", 200, "M", "2")
    item = inventory.add_item("w", 10, 10, opening_quantity=10)
    sales.record("P", "2026-08-10", a.id, item.display, 2, 10, "2", "u", item_id=item.id)
    krar.add_or_update(a.id, "2026-01-01")

    summaries = accounts.summaries(TODAY)
    k = reports.kpis(summaries)
    assert k.customers == 2 and k.debtors == 1 and k.payable == 200 and k.receivable > 1000
    assert k.stock_value == 80 and k.krar_overdue == 1

    aging = dict((label, (n, amt)) for label, n, amt in reports.aging(summaries))
    assert aging["0-30 days"][0] == 1 and aging["180+ days"][0] == 0
    assert reports.top_debtors(5, summaries)[0].id == a.id

    flow = {m.month: m for m in reports.monthly_flow(12, today=TODAY)}
    assert flow["2026-08"].debit == 20 and flow["2026-08"].credit == 200
    # calendar months, not 31-day steps: 7 months back from August stops at February
    assert [m.month for m in reports.monthly_flow(7, today=TODAY)] == ["2026-08"]
    assert [m.month for m in reports.monthly_flow(8, today=TODAY)] == ["2026-01", "2026-08"]
    inter = {row[0]: row for row in reports.interest_summary(TODAY)}
    assert inter[a.id][2] == 1020 and inter[a.id][3] > 0 and inter[b.id][2] == -200
    assert reports.item_movement("2026-08-01", "2026-08-31")[0][3] == 2
    assert reports.dead_stock(90, TODAY) == []
    assert reports.day_book("2026-08-10")[0][1] == "A"
    assert reports.customer_activity("2026-08-01", "2026-08-31")[0][0] == a.id


def test_default_users_and_login(auth):
    assert auth.authenticate("admin", "admin").is_admin
    assert auth.authenticate("emp1", "emp1").role == "employee"
    assert auth.authenticate("admin", "wrong") is None
    assert auth.authenticate("nobody", "x") is None
    assert auth.authenticate("ADMIN", "admin") is not None  # case-insensitive username


def test_user_management(auth):
    u = auth.create_user("emp2", "pass2", "Employee 2", "employee", actor="admin")
    with pytest.raises(AuthError):
        auth.create_user("emp2", "pass2", "", "employee")
    with pytest.raises(AuthError):
        auth.create_user("x", "1", "", "employee")
    with pytest.raises(AuthError):
        auth.create_user("x", "1234", "", "boss")
    auth.set_password(u.id, "newpass", actor="admin")
    assert auth.authenticate("emp2", "pass2") is None
    assert auth.authenticate("emp2", "newpass") is not None
    auth.set_active(u.id, False, actor="admin")
    assert auth.authenticate("emp2", "newpass") is None
    admin = auth.authenticate("admin", "admin")
    with pytest.raises(AuthError):
        auth.set_active(admin.id, False, actor="admin")
    with pytest.raises(AuthError):
        auth.set_role(admin.id, "employee", actor="admin")
    auth.change_own_password(admin, "admin", "admin2")
    with pytest.raises(AuthError):
        auth.change_own_password(admin, "admin", "x1234")


def test_permissions():
    admin = User(1, "admin", "", "admin", True)
    emp = User(2, "emp1", "", "employee", True)
    inactive = User(3, "old", "", "admin", False)
    assert has_permission(admin, Permission.MANAGE_USERS)
    assert has_permission(admin, Permission.DELETE_RECORDS)
    assert has_permission(emp, Permission.RECORD_SALE)
    assert has_permission(emp, Permission.VIEW_REPORTS)
    assert not has_permission(emp, Permission.EDIT_RECORDS)
    assert not has_permission(emp, Permission.MANAGE_USERS)
    assert not has_permission(inactive, Permission.VIEW_DASHBOARD)
    assert not has_permission(None, Permission.VIEW_DASHBOARD)
