"""What the new layout shows: its areas, the screens inside each, and where every classic
screen key now lives.

A *tab* is one screen inside an area.  Its key is the classic screen key (``customers``,
``karar``, ``bills`` …), so ``navigate("karar")`` from any old code path lands on
Khata › Collections, and every classic Alt-letter shortcut keeps working.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace

from hth.services.permissions import Permission


@dataclass(frozen=True)
class Tab:
    key: str  # the classic screen key
    label: str
    factory: Callable  # (master, ctx) -> BaseView
    permission: Permission | None = None
    shortcut: str = ""  # Alt+<letter>, as in the classic layout


@dataclass(frozen=True)
class Area:
    key: str
    label: str
    tabs: tuple[Tab, ...] = field(default_factory=tuple)
    in_bar: bool = True  # False: reached from the gear / the Ask bar, not a top tab
    factory: Callable | None = None  # a rebuilt area's own screen; None = host the tabs


def build_areas(modules: Iterable = ()) -> list[Area]:
    """Every area with all its tabs (before permissions).  ``modules`` are the discovered
    ``ModuleSpec``s; each one lands in the area its spec names, or gets an area of its own."""
    from hth.ui.modern.areas.counter import CounterView
    from hth.ui.modern.areas.khata import KhataView
    from hth.ui.modern.areas.today import TodayView
    from hth.ui.views.assistant import AssistantView
    from hth.ui.views.customers import CustomersView
    from hth.ui.views.dashboard import DashboardView
    from hth.ui.views.items import ItemsView
    from hth.ui.views.karar import KararView
    from hth.ui.views.reports import ReportsView
    from hth.ui.views.sales import SalesView
    from hth.ui.views.settings import SettingsView
    from hth.ui.views.users import UsersView

    areas = {
        "today": Area(
            "today",
            "Today",
            (Tab("dashboard", "Today", DashboardView, Permission.VIEW_DASHBOARD, "d"),),
            factory=TodayView,  # rebuilt (v5.5): the agenda; the classic dashboard stays in Classic
        ),
        "counter": Area(
            "counter",
            "Counter",
            (Tab("sales", "Counter", SalesView, Permission.RECORD_SALE, "s"),),
            factory=CounterView,  # rebuilt (v5.5); the tab keeps "sales" and Alt+S pointing here
        ),
        "khata": Area(
            "khata",
            "Khata",
            (
                Tab("customers", "Customers", CustomersView, Permission.ADD_CUSTOMER, "a"),
                Tab("karar", "Collections", KararView, Permission.MANAGE_KRAR, "k"),
            ),
            factory=KhataView,  # rebuilt (v5.5): Customers + Collections
        ),
        "stock": Area("stock", "Stock", (Tab("items", "Items", ItemsView, Permission.ADD_ITEM, "i"),)),
        "money": Area("money", "Money", ()),
        "reports": Area("reports", "Reports", (Tab("reports", "Reports", ReportsView, Permission.VIEW_REPORTS, "r"),)),
    }
    extra: list[Area] = []
    for spec in sorted(modules, key=lambda s: (getattr(s, "order", 100), s.label)):
        tab = Tab(spec.key, spec.tab or spec.label, spec.view_factory, spec.permission, spec.shortcut or "")
        area = areas.get(getattr(spec, "area", None) or "")
        if area is not None:
            areas[area.key] = replace(area, tabs=_ordered(area.key, (*area.tabs, tab)))
        else:
            extra.append(Area(spec.key, spec.label, (tab,)))
    hidden = [
        Area(
            "settings",
            "Settings",
            (
                Tab("settings", "Settings", SettingsView, None, "t"),
                Tab("users", "Users", UsersView, Permission.MANAGE_USERS, "u"),
            ),
            in_bar=False,
        ),
        Area("ask", "Ask", (Tab("assistant", "Assistant", AssistantView, None, "h"),), in_bar=False),
    ]
    return [*areas.values(), *extra, *hidden]


# Inside Money the cash book comes first, whatever order the modules load in.
_TAB_ORDER = {"money": ("finance", "bills"), "stock": ("items", "crops")}


def _ordered(area_key: str, tabs: tuple[Tab, ...]) -> tuple[Tab, ...]:
    order = _TAB_ORDER.get(area_key, ())
    return tuple(sorted(tabs, key=lambda t: order.index(t.key) if t.key in order else len(order)))


def allowed(areas: Iterable[Area], can: Callable[[Permission | None], bool]) -> list[Area]:
    """The areas this user may open, each holding only the tabs they may open."""
    out = []
    for area in areas:
        tabs = tuple(t for t in area.tabs if can(t.permission))
        if tabs or (area.factory is not None and not area.tabs):
            out.append(replace(area, tabs=tabs))
    return out


def resolve(areas: Iterable[Area], key: str, kwargs: dict) -> tuple[str | None, dict]:
    """``navigate`` key -> (area key, kwargs).  A classic screen key becomes its area with
    ``tab=<key>`` added; an unknown or forbidden key gives ``None``."""
    areas = list(areas)
    for area in areas:
        if area.key == key:
            # "settings" / "reports" name both an area and its own screen: open that screen
            same = any(t.key == key for t in area.tabs) and "tab" not in kwargs
            return key, {**kwargs, "tab": key} if same else kwargs
    for area in areas:
        if any(t.key == key for t in area.tabs):
            return area.key, {**kwargs, "tab": key}
    return None, kwargs


def home(areas: Iterable[Area], is_admin: bool) -> str:
    """Where a sign-in lands: admins on Today, everyone else at the Counter."""
    keys = [a.key for a in areas]
    for key in ("today", "counter") if is_admin else ("counter", "today"):
        if key in keys:
            return key
    return keys[0] if keys else "settings"
