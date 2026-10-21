"""Bills module - GST tax invoices (rebuilt from v3 ``bills/``)."""

from __future__ import annotations

from hth.modules import ModuleSpec
from hth.services.permissions import Permission


def _view_factory(master, ctx):
    from hth.modules.bills.views import BillsView

    return BillsView(master, ctx)


MODULE = ModuleSpec(
    key="bills",
    label="Bills",
    view_factory=_view_factory,
    permission=Permission.BILLING,
    shortcut="b",
    order=10,
    area="money",
    tab="GST bills",
)
