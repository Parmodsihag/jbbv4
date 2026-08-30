"""Crop trading module - buy small lots from farmers, sell combined to buyers, track margin."""

from __future__ import annotations

from hth.modules import ModuleSpec
from hth.services.permissions import Permission


def _view_factory(master, ctx):
    from hth.modules.crop_trading.views import CropTradingView

    return CropTradingView(master, ctx)


MODULE = ModuleSpec(
    key="crops",
    label="Crop Trade",
    view_factory=_view_factory,
    permission=Permission.CROP_TRADING,
    shortcut="c",
    order=20,
)
