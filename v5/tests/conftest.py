import pytest

from hth.db.connection import Database
from hth.db.schema import initialize
from hth.services.accounts import AccountsService
from hth.services.auth import AuthService
from hth.services.inventory import InventoryService
from hth.services.krar import KrarService
from hth.services.reports import ReportsService
from hth.services.sales import SalesService


@pytest.fixture(autouse=True)
def _reset_login_lockout():
    from hth.services import auth as auth_module

    auth_module._failures.clear()
    yield
    auth_module._failures.clear()


@pytest.fixture
def db():
    database = Database(":memory:")
    initialize(database)
    return database


@pytest.fixture
def accounts(db):
    return AccountsService(db)


@pytest.fixture
def inventory(db):
    return InventoryService(db)


@pytest.fixture
def sales(db):
    return SalesService(db)


@pytest.fixture
def krar(db):
    return KrarService(db)


@pytest.fixture
def reports(db):
    return ReportsService(db)


@pytest.fixture
def auth(db):
    service = AuthService(db)
    service.ensure_default_users()
    return service
