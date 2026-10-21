"""Crop trading module - buy small lots from farmers, sell combined to buyers, track margin.

Trades are entered on the main Sales screen (a receipt of a crop item is a purchase lot,
a sale is FIFO-costed); this module supplies the rules, the stock/valuation screen and
the reports.  Importing the package registers the crop handler with the sales service.
"""

from __future__ import annotations

from hth.modules import ModuleSpec
from hth.services.permissions import Permission
from hth.services.sales import register_crop_handler


def _view_factory(master, ctx):
    from hth.modules.crop_trading.views import CropTradingView

    return CropTradingView(master, ctx)


def _crop_service(db):
    from hth.modules.crop_trading.service import CropService

    return CropService(db)


register_crop_handler(_crop_service)

MODULE = ModuleSpec(
    key="crops",
    label="Crop Trade",
    view_factory=_view_factory,
    permission=Permission.CROP_TRADING,
    shortcut="c",
    order=20,
    area="stock",
    tab="Crops & rates",
    reports=(
        "Summary",
        "Margin by crop",
        "Margin by buyer",
        "Purchases by farmer",
        "Purchases by quality",
        "Open lots",
    ),
)
