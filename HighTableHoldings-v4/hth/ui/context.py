"""Everything a view needs, in one object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from hth.config import Settings
from hth.db.connection import Database
from hth.domain.models import User
from hth.services.accounts import AccountsService
from hth.services.audit import AuditService
from hth.services.auth import AuthService
from hth.services.inventory import InventoryService
from hth.services.krar import KrarService
from hth.services.permissions import Permission, has_permission
from hth.services.reports import ReportsService
from hth.services.sales import SalesService

if TYPE_CHECKING:
    from hth.ui.app import App


@dataclass
class AppContext:
    db: Database
    settings: Settings
    app: Any = None  # App; typed loosely to avoid an import cycle
    user: User | None = None
    accounts: AccountsService = field(init=False)
    inventory: InventoryService = field(init=False)
    sales: SalesService = field(init=False)
    krar: KrarService = field(init=False)
    reports: ReportsService = field(init=False)
    audit: AuditService = field(init=False)
    auth: AuthService = field(init=False)

    def __post_init__(self) -> None:
        self.accounts = AccountsService(self.db)
        self.inventory = InventoryService(self.db)
        self.sales = SalesService(self.db)
        self.krar = KrarService(self.db)
        self.reports = ReportsService(self.db)
        self.audit = AuditService(self.db)
        self.auth = AuthService(self.db)

    @property
    def username(self) -> str:
        return self.user.username if self.user else "system"

    def can(self, permission: Permission | None) -> bool:
        return True if permission is None else has_permission(self.user, permission)

    # Thin proxies so views don't need to know about the App class ------------------
    def toast(self, message: str, kind: str = "info") -> None:
        if self.app is not None:
            self.app.toast(message, kind)

    def status(self, message: str) -> None:
        if self.app is not None:
            self.app.set_status(message)

    def navigate(self, key: str, **kwargs) -> None:
        if self.app is not None:
            self.app.navigate(key, **kwargs)

    def app_window(self) -> App:
        return self.app
