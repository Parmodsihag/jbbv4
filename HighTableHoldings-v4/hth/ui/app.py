"""Main window: login, sidebar navigation, header, content area, status bar."""

from __future__ import annotations

import datetime as dt
import logging
import sys

import customtkinter as ctk

from hth import __app_name__, __company__, __version__
from hth.config import Settings
from hth.db.connection import Database
from hth.domain.models import User
from hth.modules import discover
from hth.services.permissions import ROLES, Permission
from hth.ui import theme
from hth.ui.context import AppContext
from hth.ui.views.base import BaseView
from hth.ui.views.customers import CustomersView
from hth.ui.views.dashboard import DashboardView
from hth.ui.views.items import ItemsView
from hth.ui.views.karar import KararView
from hth.ui.views.login import LoginView
from hth.ui.views.reports import ReportsView
from hth.ui.views.sales import SalesView
from hth.ui.views.settings import SettingsView
from hth.ui.views.users import UsersView
from hth.ui.widgets.toast import ToastHost

log = logging.getLogger(__name__)

# (key, label, shortcut, permission, class)
CORE_VIEWS: list[tuple[str, str, str, Permission | None, type[BaseView]]] = [
    ("dashboard", "Dashboard", "d", Permission.VIEW_DASHBOARD, DashboardView),
    ("sales", "Sales", "s", Permission.RECORD_SALE, SalesView),
    ("customers", "Accounts", "a", Permission.ADD_CUSTOMER, CustomersView),
    ("items", "Items", "i", Permission.ADD_ITEM, ItemsView),
    ("karar", "Karar", "k", Permission.MANAGE_KRAR, KararView),
    ("reports", "Reports", "r", Permission.VIEW_REPORTS, ReportsView),
    ("users", "Users", "u", Permission.MANAGE_USERS, UsersView),
    ("settings", "Settings", "t", None, SettingsView),
]


class App(ctk.CTk):
    def __init__(self, db: Database, settings: Settings):
        theme.init_theme()
        super().__init__()
        self.appearance = "dark"
        self.ctx = AppContext(db=db, settings=settings, app=self)
        self.title(f"{__app_name__} {__version__}")
        self.geometry("1440x880")
        self.minsize(1100, 700)
        self.configure(fg_color=theme.color("bg"))
        theme.style_treeview()
        self.toasts = ToastHost(self)
        self._views: dict[str, BaseView] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._active: str | None = None
        self._shell: ctk.CTkFrame | None = None
        self._login: LoginView | None = None
        self._registry = self._build_registry()
        self._maximize()
        self.show_login()

    # Window ------------------------------------------------------------------------------
    def report_callback_exception(self, exc, val, tb) -> None:  # noqa: D401 - Tk hook
        """Every unhandled error inside a Tk callback ends up here instead of stderr."""
        if isinstance(val, AttributeError) and "winfo_exists" in str(val):
            # customtkinter 5/6: a <Configure> event can fire after a frame was destroyed.
            log.debug("ignored customtkinter redraw-after-destroy")
            return
        log.error("Unhandled UI error", exc_info=(exc, val, tb))
        try:
            self.toast(f"Something went wrong: {val}", "error")
        except Exception:  # noqa: BLE001
            pass

    def _maximize(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self.after(50, lambda: self.state("zoomed"))
        except Exception:  # noqa: BLE001
            pass

    def _build_registry(self):
        entries = list(CORE_VIEWS)
        for m in discover():
            entries.append((m.key, m.label, m.shortcut or "", m.permission, m.view_factory))
        return entries

    # Login / logout ----------------------------------------------------------------------
    def show_login(self) -> None:
        if self._shell is not None:
            self._shell.destroy()
            self._shell = None
        self._views.clear()
        self._nav_buttons.clear()
        self._active = None
        self.ctx.user = None
        self._login = LoginView(self, self.ctx)
        self._login.pack(fill="both", expand=True)
        self._login.on_show()

    def on_login(self, user: User) -> None:
        self.ctx.user = user
        if self._login is not None:
            self._login.destroy()
            self._login = None
        self._build_shell()
        self.navigate("dashboard")
        self.toast(f"Welcome, {user.full_name or user.username}", "success")

    def logout(self) -> None:
        self.ctx.audit.log("08", f"logout {self.ctx.username}", self.ctx.username)
        self.show_login()

    # Shell -------------------------------------------------------------------------------
    def _build_shell(self) -> None:
        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(1, weight=1)
        self._shell = shell

        sidebar = ctk.CTkFrame(shell, width=210, fg_color=theme.color("sidebar"), corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=3, sticky="nsw")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text=__company__, font=theme.font(11, "bold"), text_color=theme.color("accent")).pack(
            pady=(22, 0), padx=16, anchor="w"
        )
        ctk.CTkLabel(
            sidebar,
            text=__app_name__,
            font=theme.font(17, "bold"),
            text_color=theme.color("sidebar_text"),
            wraplength=180,
            justify="left",
            anchor="w",
        ).pack(padx=16, pady=(0, 18), anchor="w")
        for key, label, shortcut, perm, _cls in self._registry:
            if not self.ctx.can(perm):
                continue
            hint = f"Alt+{shortcut.upper()}" if shortcut else ""
            b = ctk.CTkButton(
                sidebar,
                text=f"{label:<14}{hint:>7}" if hint else label,
                anchor="w",
                height=40,
                corner_radius=8,
                font=theme.font(13),
                fg_color="transparent",
                hover_color=theme.color("sidebar_hover"),
                text_color=theme.color("sidebar_text"),
                command=lambda k=key: self.navigate(k),
            )
            b.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[key] = b
            if shortcut:
                self.bind(f"<Alt-{shortcut}>", lambda e, k=key: self.navigate(k))
                self.bind(f"<Alt-{shortcut.upper()}>", lambda e, k=key: self.navigate(k))
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        u = self.ctx.user
        chip = ctk.CTkFrame(sidebar, fg_color=theme.color("sidebar_hover"), corner_radius=8)
        chip.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(
            chip,
            text=u.full_name or u.username,
            font=theme.font(13, "bold"),
            text_color=theme.color("sidebar_text"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(
            chip,
            text=f"@{u.username} · {ROLES.get(u.role, u.role)}",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(
            sidebar,
            text="Sign out",
            height=32,
            font=theme.font(12),
            fg_color="transparent",
            border_width=1,
            border_color=theme.color("muted"),
            text_color=theme.color("sidebar_text"),
            hover_color=theme.color("sidebar_hover"),
            command=self.logout,
        ).pack(fill="x", padx=10, pady=(0, 16))

        header = ctk.CTkFrame(shell, height=56, fg_color="transparent")
        header.grid(row=0, column=1, sticky="ew", padx=16, pady=(10, 0))
        self.header_title = ctk.CTkLabel(header, text="", font=theme.font(22, "bold"))
        self.header_title.pack(side="left")
        self.theme_button = ctk.CTkButton(
            header,
            text="☾" if self.appearance == "dark" else "☀",
            width=36,
            height=32,
            font=theme.font(15),
            fg_color=theme.color("surface2"),
            hover_color=theme.color("surface3"),
            text_color=theme.color("text"),
            command=self.toggle_theme,
        )
        self.theme_button.pack(side="right")
        ctk.CTkLabel(
            header,
            text=dt.date.today().strftime("%A, %d %B %Y"),
            font=theme.font(13),
            text_color=theme.color("muted"),
        ).pack(side="right", padx=14)

        self.content = ctk.CTkFrame(shell, fg_color="transparent")
        self.content.grid(row=1, column=1, sticky="nsew", padx=12, pady=8)

        status = ctk.CTkFrame(shell, height=28, fg_color=theme.color("surface"), corner_radius=0)
        status.grid(row=2, column=1, sticky="ew")
        self.status_label = ctk.CTkLabel(
            status, text="Ready", font=theme.font(12), text_color=theme.color("muted"), anchor="w"
        )
        self.status_label.pack(side="left", padx=16)
        ctk.CTkLabel(
            status,
            text=f"{self.ctx.settings.db_path}",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="right", padx=16)

    # Navigation --------------------------------------------------------------------------
    def navigate(self, key: str, **kwargs) -> None:
        entry = next((e for e in self._registry if e[0] == key), None)
        if entry is None or not self.ctx.can(entry[3]) or self._shell is None:
            return
        _key, label, _s, _p, cls = entry
        view = self._views.get(key)
        if view is None:
            view = cls(self.content, self.ctx)
            self._views[key] = view
        if self._active and self._active != key:
            self._views[self._active].pack_forget()
        view.pack(fill="both", expand=True)
        self._active = key
        self.header_title.configure(text=label)
        for k, b in self._nav_buttons.items():
            b.configure(
                fg_color=theme.color("accent") if k == key else "transparent",
                text_color=theme.color("accent_text") if k == key else theme.color("sidebar_text"),
            )
        try:
            view.on_show(**kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("on_show failed for %s", key)
            self.toast(f"Could not load {label}: {exc}", "error")

    # Feedback ----------------------------------------------------------------------------
    def toast(self, message: str, kind: str = "info") -> None:
        self.toasts.show(message, kind)
        if kind in ("error", "warning"):
            log.warning("toast[%s]: %s", kind, message)

    def set_status(self, message: str) -> None:
        if hasattr(self, "status_label"):
            self.status_label.configure(text=message)

    # Theme -------------------------------------------------------------------------------
    def toggle_theme(self) -> None:
        self.apply_theme("light" if ctk.get_appearance_mode().lower() == "dark" else "dark")

    def apply_theme(self, mode: str) -> None:
        self.appearance = mode
        theme.apply_appearance(mode)
        if hasattr(self, "theme_button"):
            self.theme_button.configure(text="☾" if ctk.get_appearance_mode().lower() == "dark" else "☀")
        for view in self._views.values():
            try:
                view.on_theme_change()
            except Exception:  # noqa: BLE001
                log.exception("theme change failed for %s", view.key)


def run_app(db: Database, settings: Settings) -> None:
    app = App(db, settings)
    app.mainloop()
