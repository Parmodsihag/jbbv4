"""Optional feature modules (bills, crop trading, ...).

A module is a package under ``hth.modules`` that exposes ``MODULE = ModuleSpec(...)``.
The app discovers them at start-up and adds a navigation entry for each one the current
user is allowed to see.  Core code never imports a module directly, so a module can be
developed, tested and shipped independently.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

from hth.services.permissions import Permission

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModuleSpec:
    key: str  # navigation key, e.g. "bills"
    label: str  # sidebar text
    view_factory: Callable  # (master, ctx) -> BaseView
    permission: Permission | None = None
    shortcut: str | None = None  # Alt+<letter>
    order: int = 100
    # where the new layout (v5.5) shows the module: an area key and the tab's name there
    area: str | None = None
    tab: str | None = None
    # report names the module's screen can open with ``navigate(key, report=name)`` - listed
    # in the new layout's Reports catalogue
    reports: tuple[str, ...] = ()


def discover() -> list[ModuleSpec]:
    specs: list[ModuleSpec] = []
    for info in pkgutil.iter_modules(__path__):
        if not info.ispkg:
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{info.name}")
        except Exception:  # noqa: BLE001 - a broken module must not stop the app
            log.exception("failed to load module %s", info.name)
            continue
        spec = getattr(mod, "MODULE", None)
        if isinstance(spec, ModuleSpec):
            specs.append(spec)
        else:
            log.warning("module %s has no MODULE spec - ignored", info.name)
    return sorted(specs, key=lambda s: (s.order, s.label))
