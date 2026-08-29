"""Declarative role -> permission matrix.  Add a role or permission here, nowhere else."""

from __future__ import annotations

from enum import Enum

from hth.domain.models import User


class Permission(str, Enum):
    VIEW_DASHBOARD = "view_dashboard"
    RECORD_SALE = "record_sale"
    ADD_CUSTOMER = "add_customer"
    ADD_ITEM = "add_item"
    MANAGE_KRAR = "manage_krar"
    VIEW_REPORTS = "view_reports"
    EXPORT = "export"
    EDIT_RECORDS = "edit_records"
    DELETE_RECORDS = "delete_records"
    VIEW_AUDIT = "view_audit"
    MANAGE_USERS = "manage_users"
    MANAGE_SETTINGS = "manage_settings"
    BACKUP = "backup"


ROLES: dict[str, str] = {"admin": "Administrator", "employee": "Employee"}

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "admin": frozenset(Permission),
    "employee": frozenset(
        {
            Permission.VIEW_DASHBOARD,
            Permission.RECORD_SALE,
            Permission.ADD_CUSTOMER,
            Permission.ADD_ITEM,
            Permission.MANAGE_KRAR,
            Permission.VIEW_REPORTS,
            Permission.EXPORT,
        }
    ),
}


def permissions_for(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(user: User | None, permission: Permission) -> bool:
    if user is None or not user.is_active:
        return False
    return permission in permissions_for(user.role)
