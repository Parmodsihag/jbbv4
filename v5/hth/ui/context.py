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
from hth.services.backup import BackupService
from hth.services.categories import CategoryService
from hth.services.company import CompanyService
from hth.services.integrity import IntegrityService
from hth.services.inventory import InventoryService
from hth.services.krar import KrarService
from hth.services.permissions import Permission, has_permission
from hth.services.reminders import ReminderService
from hth.services.reports import ReportsService
from hth.services.sales import SalesService
from hth.services.statements import StatementService

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
    integrity: IntegrityService = field(init=False)
    categories: CategoryService = field(init=False)
    statements: StatementService = field(init=False)
    company: CompanyService = field(init=False)
    reminders: ReminderService = field(init=False)
    backup: BackupService = field(init=False)

    def __post_init__(self) -> None:
        self.accounts = AccountsService(self.db)
        self.inventory = InventoryService(self.db)
        self.sales = SalesService(self.db)
        self.krar = KrarService(self.db)
        self.reports = ReportsService(self.db)
        self.audit = AuditService(self.db)
        self.auth = AuthService(self.db)
        self.integrity = IntegrityService(self.db)
        self.categories = CategoryService(self.db)
        self.statements = StatementService(self.db)
        self.company = CompanyService(self.db)
        self.reminders = ReminderService(self.db)
        self.backup = BackupService(self.db, self.settings)

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
