"""An area made of screens: a row of section buttons (when there is more than one) above
the chosen screen.  Screens are built the first time they are shown, like the classic
sidebar does, so an area costs nothing until it is opened."""

from __future__ import annotations

import logging

import customtkinter as ctk

from hth.ui.modern.registry import Area, Tab
from hth.ui.modern.widgets import segmented
from hth.ui.views.base import BaseView

log = logging.getLogger(__name__)


class TabbedArea(BaseView):
    def __init__(self, master, ctx, area: Area):
        self.area = area
        self.key = area.key
        self.title = area.label
        self.children_views: dict[str, BaseView] = {}
        self.current: str | None = None
        super().__init__(master, ctx)

    def build(self) -> None:
        tabs = self.area.tabs
        self.sections = None
        if len(tabs) > 1:
            bar = ctk.CTkFrame(self, fg_color="transparent")
            bar.pack(fill="x", pady=(0, 8))
            self._labels = {t.label: t.key for t in tabs}
            self.sections = segmented(bar, [t.label for t in tabs], lambda label: self.show_tab(self._labels[label]))
            self.sections.pack(side="left")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

    # Tabs ------------------------------------------------------------------------------
    def tab(self, key: str) -> Tab | None:
        return next((t for t in self.area.tabs if t.key == key), None)

    def child(self, key: str) -> BaseView | None:
        return self.children_views.get(key)

    def show_tab(self, key: str, **kwargs) -> BaseView | None:
        tab = self.tab(key) or (self.area.tabs[0] if self.area.tabs else None)
        if tab is None:
            return None
        view = self.children_views.get(tab.key)
        if view is None:
            view = tab.factory(self.body, self.ctx)
            self.children_views[tab.key] = view
        if self.current and self.current != tab.key and self.current in self.children_views:
            self.children_views[self.current].pack_forget()
        view.pack(fill="both", expand=True)
        self.current = tab.key
        if self.sections is not None:
            self.sections.set(tab.label)
        try:
            view.on_show(**kwargs)
        except Exception as exc:  # noqa: BLE001 - one broken screen must not take the area down
            log.exception("on_show failed for %s", tab.key)
            self.ctx.toast(f"Could not load {tab.label}: {exc}", "error")
        return view

    # BaseView hooks --------------------------------------------------------------------
    def on_show(self, tab: str | None = None, **kwargs) -> None:
        self.show_tab(tab or self.current or "", **kwargs)

    def on_theme_change(self) -> None:
        for view in self.children_views.values():
            try:
                view.on_theme_change()
            except Exception:  # noqa: BLE001
                log.exception("theme change failed for %s", view.key)

    def on_day_change(self) -> None:
        for view in self.children_views.values():
            try:
                view.on_day_change()
            except Exception:  # noqa: BLE001
                log.exception("day change failed for %s", view.key)
