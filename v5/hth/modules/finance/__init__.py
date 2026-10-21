"""Finance module - money accounts (cash / bank / UPI), expenses, transfers, cash flow, P&L.

Importing the package registers the money-flow handler with the sales service, so
customer receipts and payments entered on the Sales screen land in the cash book.
"""

from __future__ import annotations

from hth.modules import ModuleSpec
from hth.services.permissions import Permission
from hth.services.sales import register_money_flow_handler


def _view_factory(master, ctx):
    from hth.modules.finance.views import FinanceView

    return FinanceView(master, ctx)


def _finance_service(db):
    from hth.modules.finance.service import FinanceService

    service = FinanceService(db)
    service.ensure_defaults()  # cheap, idempotent: a CASH account and the standard heads
    return service


register_money_flow_handler(_finance_service)

MODULE = ModuleSpec(
    key="finance",
    label="Finance",
    view_factory=_view_factory,
    permission=Permission.FINANCE,
    shortcut="f",
    order=30,
    area="money",
    tab="Cash book",
    reports=("Cash flow", "Profit & loss", "Expenses by head", "Monthly expenses", "Account balances"),
)
