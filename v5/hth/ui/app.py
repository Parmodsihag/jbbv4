"""Main window: login, sidebar navigation, header, content area, status bar, lock screen."""

from __future__ import annotations

import datetime as dt
import logging
import sys
import time

import customtkinter as ctk

from hth import __app_name__, __company__, __version__, i18n
from hth.config import Settings
from hth.db.connection import Database
from hth.domain.models import User
from hth.i18n import widgets as i18n_widgets
from hth.modules import discover
from hth.services.hindi import HindiNamesService
from hth.services.permissions import ROLES, Permission
from hth.services.preferences import Preferences
from hth.services.search import SearchService
from hth.ui import icons, theme
from hth.ui.context import AppContext
from hth.ui.views.assistant import AssistantView
from hth.ui.views.base import BaseView
from hth.ui.views.customers import CustomersView
from hth.ui.views.dashboard import DashboardView
from hth.ui.views.items import ItemsView
from hth.ui.views.karar import KararView
from hth.ui.views.login import LockView, LoginView
from hth.ui.views.reports import ReportsView
from hth.ui.views.sales import SalesView
from hth.ui.views.settings import SettingsView
from hth.ui.views.setup import SetupView, setup_completed
from hth.ui.views.users import UsersView
from hth.ui.widgets.nav import NavItem
from hth.ui.widgets.palette import SearchPalette
from hth.ui.widgets.toast import ToastHost

log = logging.getLogger(__name__)

# (key, label, shortcut, permission, class)
CORE_VIEWS: list[tuple[str, str, str, Permission | None, type[BaseView]]] = [
    ("dashboard", "Dashboard", "d", Permission.VIEW_DASHBOARD, DashboardView),
    ("assistant", "Assistant", "h", None, AssistantView),
    ("sales", "Sales", "s", Permission.RECORD_SALE, SalesView),
    ("customers", "Accounts", "a", Permission.ADD_CUSTOMER, CustomersView),
    ("items", "Items", "i", Permission.ADD_ITEM, ItemsView),
    ("karar", "Karar", "k", Permission.MANAGE_KRAR, KararView),
    ("reports", "Reports", "r", Permission.VIEW_REPORTS, ReportsView),
    ("users", "Users", "u", Permission.MANAGE_USERS, UsersView),
    ("settings", "Settings", "t", None, SettingsView),
]

SUBTITLES = {
    "dashboard": "The shop at a glance",
    "assistant": "Ask about the shop in Hindi, Hinglish or English",
    "sales": "Sales, receipts and crop trades",
    "customers": "Customers, farmers and buyers - balances and ledgers",
    "items": "Stock, prices and movements",
    "karar": "Promised payment dates and reminders",
    "reports": "Every report, sortable and exportable",
    "users": "Who can sign in and what they may do",
    "settings": "Shop details, appearance, backups and rules",
    "bills": "GST tax invoices",
    "crops": "Crop lots, FIFO sales, stock and market rates",
    "finance": "Cash book, expenses, cash flow and profit",
}

SIDEBAR_WIDE, SIDEBAR_COMPACT = 224, 64
TICK_MS = 15_000


class App(ctk.CTk):
    def __init__(self, db: Database, settings: Settings):
        self.prefs = Preferences(db)
        self.prefs.apply_number_style()
        i18n.set_language(self.prefs.language())
        theme.set_language_font(i18n.is_hindi())
        i18n_widgets.install()  # before the first widget: labels translate themselves
        self.appearance = self.prefs.theme()
        theme.init_theme(self.appearance)
        theme.set_text_scale(self.prefs.text_scale())
        super().__init__()
        self.ctx = AppContext(db=db, settings=settings, app=self)
        self.title(f"{__app_name__} {__version__}")
        self.geometry("1440x880")
        self.minsize(1100, 700)
        self.configure(fg_color=theme.color("bg"))
        theme.style_treeview()
        self.toasts = ToastHost(self)
        self._views: dict[str, BaseView] = {}
        self._nav_buttons: dict[str, NavItem] = {}
        self._active: str | None = None
        self._shell: ctk.CTkFrame | None = None
        self._login: LoginView | None = None
        self._setup: SetupView | None = None
        self._lock: LockView | None = None
        self._palette: SearchPalette | None = None
        self._modern = None  # the new layout's ModernShell while it is the shell in use
        self._shell_keys: list[str] = []  # key sequences the current shell bound on the window
        self._registry = self._build_registry()
        self._today = dt.date.today()
        self._last_input = time.monotonic()
        for seq in ("<Key>", "<Button>", "<MouseWheel>"):
            self.bind_all(seq, self._touch, add="+")
        self._maximize()
        self.show_login()
        self.after(TICK_MS, self._tick)

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

    # Clock: day change and idle lock ---------------------------------------------------
    def _touch(self, _event=None) -> None:
        self._last_input = time.monotonic()

    def _tick(self) -> None:
        try:
            today = dt.date.today()
            if today != self._today:
                self._today = today
                self._on_day_change()
            minutes = self.prefs.lock_minutes()
            if minutes and self.is_signed_in and not self.is_locked:
                if time.monotonic() - self._last_input >= minutes * 60:
                    self.lock(reason="idle")
        except Exception:  # noqa: BLE001 - the clock must keep ticking
            log.exception("tick failed")
        self.after(TICK_MS, self._tick)

    def _on_day_change(self) -> None:
        log.info("date changed to %s", self._today)
        if self._modern is not None:
            self._modern.refresh_date()
        elif hasattr(self, "date_label"):
            self.date_label.configure(text=i18n.date_text(self._today, "%A, %d %B %Y"))
        for view in self._views.values():
            try:
                view.on_day_change()
            except Exception:  # noqa: BLE001
                log.exception("day change failed for %s", view.key)

    # Login / logout / lock ---------------------------------------------------------------
    @property
    def is_signed_in(self) -> bool:
        return self._shell is not None and self.ctx.user is not None

    @property
    def is_locked(self) -> bool:
        return self._lock is not None

    def show_login(self) -> None:
        self._close_lock()
        self._teardown_shell()
        self.ctx.user = None
        if not setup_completed(self.ctx.db):
            self.show_setup()
            return
        self._login = LoginView(self, self.ctx)
        self._login.pack(fill="both", expand=True)
        self._login.on_show()

    def show_setup(self) -> None:
        if self._login is not None:
            self._login.destroy()
            self._login = None
        self._setup = SetupView(self, self.ctx)
        self._setup.pack(fill="both", expand=True)

    def setup_done(self) -> None:
        if self._setup is not None:
            self._setup.destroy()
            self._setup = None
        self.show_login()
        self.toast("Setup complete - sign in with your new password", "success")

    def on_login(self, user: User) -> None:
        self.ctx.user = user
        if self._login is not None:
            self._login.destroy()
            self._login = None
        self.refresh_names()
        self._build_shell()
        self._last_input = time.monotonic()
        self.navigate(self._modern.home() if self._modern is not None else "dashboard")
        self.toast(f"Welcome, {user.full_name or user.username}", "success")
        self.after(600, self._upgrade_notice)
        self.after(1500, self._update_notices)

    def _upgrade_notice(self) -> None:
        """Once, after the first v5 start copied v4's data: say where it came from."""
        from hth.services.settings import SettingsService
        from hth.ui.widgets.dialogs import info

        prefs = SettingsService(self.ctx.db)
        source = prefs.get("upgrade.copied_from")
        if not source or prefs.get("upgrade.notice_shown") == "1" or not self.is_signed_in:
            return
        prefs.set("upgrade.notice_shown", "1")
        info(
            self,
            f"Welcome to {__app_name__} {__version__}",
            f"Your data was copied from\n{source}\n\n"
            f"v5 keeps its own data in\n{self.ctx.settings.data_dir}\n\n"
            "The v4 files were only read, never changed - v4 still opens its data as before. "
            "Entries made in v5 are not visible in v4.",
        )

    def _update_notices(self) -> None:
        """After sign-in (admins): say how the last update went, and once a day look for a new one."""
        import datetime as _dt
        import threading

        from hth.services import updates
        from hth.services.permissions import Permission

        if not self.is_signed_in or not self.ctx.can(Permission.MANAGE_SETTINGS):
            return
        import os

        prefs = self.ctx.prefs.settings
        last = updates.last_result(self.ctx.settings.data_dir)
        if last and last.get("when") and prefs.get("update.result_seen") != last["when"]:
            prefs.set("update.result_seen", last["when"])
            if last.get("ok"):
                self.toast(f"Updated to version {__version__}", "success")
            else:
                self.toast(
                    f"The update could not be put in - the old version was kept: {last.get('error', '')}", "error"
                )
        now = _dt.datetime.now()
        try:
            due = now - _dt.datetime.fromisoformat(prefs.get("update.last_check")) > _dt.timedelta(hours=20)
        except ValueError:
            due = True
        if not due or updates.pending(self.ctx.settings.data_dir) or os.environ.get("HTH_NO_UPDATE_CHECK"):
            return
        prefs.set("update.last_check", now.isoformat(timespec="seconds"))
        updater = updates.Updater(self.ctx.settings.data_dir, self.ctx.prefs.update_source())
        if updater.mode != "copy":
            return
        found: list = []

        def work() -> None:
            try:
                found.append(updater.check())
            except Exception:  # noqa: BLE001 - offline: try again tomorrow
                log.info("update check failed", exc_info=True)

        thread = threading.Thread(target=work, name="hth-update-check", daemon=True)
        thread.start()

        def poll() -> None:
            if thread.is_alive():
                self.after(1000, poll)
            elif found and found[0].newer and self.is_signed_in:
                self.toast(f"Version {found[0].version} is available - Settings → Updates", "info")

        self.after(1000, poll)

    def logout(self) -> None:
        self.ctx.audit.log("08", f"logout {self.ctx.username}", self.ctx.username)
        self.show_login()

    def lock(self, reason: str = "manual") -> None:
        """Hide the work (kept as it is) behind a password prompt for the signed-in user."""
        if not self.is_signed_in or self.is_locked:
            return
        if self._palette is not None and self._palette.winfo_exists():
            self._palette.close()
        self.ctx.audit.log("08", f"screen locked ({reason}) {self.ctx.username}", self.ctx.username)
        self._shell.pack_forget()
        self._lock = LockView(self, self.ctx)
        self._lock.pack(fill="both", expand=True)
        self._lock.on_show()

    def unlock(self) -> None:
        self._close_lock()
        if self._shell is not None:
            self._shell.pack(fill="both", expand=True)
        self._last_input = time.monotonic()
        self.ctx.audit.log("08", f"screen unlocked {self.ctx.username}", self.ctx.username)

    def _close_lock(self) -> None:
        if self._lock is not None:
            self._lock.destroy()
            self._lock = None

    # Global search -----------------------------------------------------------------------
    def open_search(self) -> None:
        if not self.is_signed_in or self.is_locked:
            return
        if self._palette is not None and self._palette.winfo_exists():
            self._palette.close()
        kinds = set()
        if self.ctx.can(Permission.ADD_CUSTOMER):
            kinds.add("customer")
        if self.ctx.can(Permission.ADD_ITEM):
            kinds.add("item")
        if self.ctx.can(Permission.BILLING) and any(e[0] == "bills" for e in self._registry):
            kinds.add("bill")
        self._palette = SearchPalette(self, SearchService(self.ctx.db), kinds, self._search_pick)

    def _search_pick(self, hit) -> None:
        if hit.kind == "customer":
            self.navigate("customers", customer_id=hit.id)
        elif hit.kind == "item":
            self.navigate("items", item_id=hit.id)
        elif hit.kind == "bill":
            self.navigate("bills", bill_number=hit.id)

    # Shell -------------------------------------------------------------------------------
    @property
    def layout(self) -> str:
        """'classic' (sidebar) or 'new' (six areas across the top) - one choice for the shop."""
        return self.prefs.layout()

    def _build_shell(self) -> None:
        if self.layout == "new":
            from hth.ui.modern.shell import ModernShell

            self._modern = ModernShell(self)
            self._modern.pack(fill="both", expand=True)
            self._shell = self._modern
            self.content = self._modern.content
            self.date_label = self._modern.date_label
            self.status_label = self._modern.status_label
            self.backup_label = self._modern.backup_label
            self.refresh_backup_label()
        else:
            self._build_classic_shell()
        self.bind_shell_key("<Control-k>", lambda e: self.open_search())
        self.bind_shell_key("<Control-K>", lambda e: self.open_search())
        self.bind_shell_key("<Control-l>", lambda e: self.lock())
        self.bind_shell_key("<Control-L>", lambda e: self.lock())
        self.bind_shell_key("<F1>", lambda e: self.show_shortcuts())

    def bind_shell_key(self, sequence: str, callback) -> None:
        """Bind a key on the window for the current shell; the binding goes with the shell."""
        self.bind(sequence, callback)
        self._shell_keys.append(sequence)

    # Screens bind these on the window themselves (Sales: Ctrl+Enter, Ctrl+Z); a rebuilt shell
    # has new screens, so the old screens' bindings must not outlive them.
    _VIEW_KEYS = (
        "<Control-Return>", "<Control-Shift-Return>", "<Control-z>",
        "<Alt-Key-1>", "<Alt-Key-2>", "<Alt-Key-3>", "<Alt-Key-4>",
    )  # fmt: skip
    # Widgets of the shell that App methods reach with hasattr().
    _SHELL_ATTRS = (
        "sidebar", "menu_button", "brand_text", "user_chip", "user_text", "account_buttons", "lock_button",
        "signout_button", "header_title", "header_subtitle", "theme_button", "date_label", "content",
        "status_label", "backup_label",
    )  # fmt: skip

    def _teardown_shell(self) -> None:
        """Destroy whichever shell is up, with its screens and key bindings."""
        if self._shell is not None:
            self._shell.destroy()
            self._shell = None
        self._modern = None
        for sequence in (*self._shell_keys, *self._VIEW_KEYS):
            try:
                self.unbind(sequence)
            except Exception:  # noqa: BLE001
                pass
        self._shell_keys.clear()
        for name in self._SHELL_ATTRS:
            self.__dict__.pop(name, None)
        self._views.clear()
        self._nav_buttons.clear()
        self._active = None

    def _build_classic_shell(self) -> None:
        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(1, weight=1)
        self._shell = shell
        compact = self.prefs.sidebar_compact()

        self.sidebar = sidebar = ctk.CTkFrame(
            shell, width=SIDEBAR_COMPACT if compact else SIDEBAR_WIDE, fg_color=theme.color("sidebar"), corner_radius=0
        )
        sidebar.grid(row=0, column=0, rowspan=3, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=10, pady=(14, 10))
        self.menu_button = ctk.CTkButton(
            brand,
            text=icons.icon("menu"),
            font=icons.font(15),
            width=36,
            height=32,
            fg_color="transparent",
            hover_color=theme.color("sidebar_hover"),
            text_color=theme.color("sidebar_text"),
            command=self.toggle_sidebar,
        )
        self.menu_button.pack(side="left")
        self.brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        self.brand_text.pack(side="left", padx=(6, 0), fill="x", expand=True)
        ctk.CTkLabel(
            self.brand_text, text=__company__, font=theme.font(10, "bold"), text_color=theme.color("accent"), anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(
            self.brand_text,
            text=__app_name__,
            font=theme.font(15, "bold"),
            text_color=theme.color("sidebar_text"),
            anchor="w",
        ).pack(fill="x")

        for key, label, shortcut, perm, _cls in self._registry:
            if not self.ctx.can(perm):
                continue
            item = NavItem(
                sidebar,
                key,
                label,
                f"Alt+{shortcut.upper()}" if shortcut else "",
                lambda k=key: self.navigate(k),
            )
            item.pack(fill="x", padx=8, pady=1)
            self._nav_buttons[key] = item
            if shortcut:
                self.bind_shell_key(f"<Alt-{shortcut}>", lambda e, k=key: self.navigate(k))
                self.bind_shell_key(f"<Alt-{shortcut.upper()}>", lambda e, k=key: self.navigate(k))

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        u = self.ctx.user
        self.user_chip = chip = ctk.CTkFrame(sidebar, fg_color=theme.color("sidebar_hover"), corner_radius=10)
        chip.pack(fill="x", padx=8, pady=(0, 6))
        initials = "".join(p[0] for p in (u.full_name or u.username).split()[:2]).upper() or "?"
        ctk.CTkLabel(
            chip,
            text=initials,
            width=34,
            height=34,
            corner_radius=17,
            fg_color=theme.color("accent"),
            text_color=theme.color("accent_text"),
            font=theme.font(12, "bold"),
        ).pack(side="left", padx=(8, 8), pady=8)
        self.user_text = ctk.CTkFrame(chip, fg_color="transparent")
        self.user_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            self.user_text,
            text=u.full_name or u.username,
            font=theme.font(12, "bold"),
            text_color=theme.color("sidebar_text"),
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            self.user_text,
            text=f"@{u.username} · {ROLES.get(u.role, u.role)}",
            font=theme.font(10),
            text_color=theme.color("muted"),
            anchor="w",
        ).pack(fill="x")

        self.account_buttons = row = ctk.CTkFrame(sidebar, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(0, 14))
        row.grid_columnconfigure((0, 1), weight=1)
        self.lock_button = self._side_button(row, "Lock", lambda: self.lock())
        self.lock_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.signout_button = self._side_button(row, "Sign out", self.logout)
        self.signout_button.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        header = ctk.CTkFrame(shell, height=60, fg_color="transparent")
        header.grid(row=0, column=1, sticky="ew", padx=18, pady=(12, 0))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        self.header_title = ctk.CTkLabel(titles, text="", font=theme.font(22, "bold"), anchor="w")
        self.header_title.pack(fill="x")
        self.header_subtitle = ctk.CTkLabel(
            titles, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w"
        )
        self.header_subtitle.pack(fill="x")
        self.theme_button = ctk.CTkButton(
            header,
            text=self._theme_icon(),
            font=icons.font(15),
            width=38,
            height=34,
            fg_color=theme.color("surface2"),
            hover_color=theme.color("surface3"),
            text_color=theme.color("text"),
            command=self.toggle_theme,
        )
        self.theme_button.pack(side="right")
        ctk.CTkButton(
            header,
            text="Search      Ctrl+K",
            width=170,
            height=34,
            font=theme.font(12),
            anchor="w",
            fg_color=theme.color("surface2"),
            hover_color=theme.color("surface3"),
            text_color=theme.color("muted"),
            command=self.open_search,
        ).pack(side="right", padx=8)
        self.date_label = ctk.CTkLabel(
            header,
            text=i18n.date_text(self._today, "%A, %d %B %Y"),
            font=theme.font(13),
            text_color=theme.color("muted"),
        )
        self.date_label.pack(side="right", padx=14)

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
        self.backup_label = ctk.CTkLabel(status, text="", font=theme.font(11), text_color=theme.color("muted"))
        self.backup_label.pack(side="right", padx=8)
        self.refresh_backup_label()
        self._apply_sidebar_mode(compact)

    def _side_button(self, master, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            master,
            text=text,
            height=32,
            font=theme.font(12),
            fg_color="transparent",
            border_width=1,
            border_color=theme.color("surface3"),
            text_color=theme.color("sidebar_text"),
            hover_color=theme.color("sidebar_hover"),
            command=command,
        )

    def refresh_backup_label(self) -> None:
        if not hasattr(self, "backup_label"):
            return
        last = self.ctx.backup.last_backup()
        if last is None:
            text = "No backup yet"
        else:
            when = dt.datetime.fromtimestamp(last.stat().st_mtime)
            text = f"Last backup {i18n.date_text(when, '%d %b %H:%M')}"
        self.backup_label.configure(text=text)

    def show_shortcuts(self) -> None:
        """F1: every keyboard shortcut on one sheet."""
        if not self.is_signed_in or self.is_locked:
            return
        from hth.ui.widgets.dialogs import ShortcutSheet

        if self._modern is not None:
            from hth.ui.widgets.dialogs import COUNTER_SHORTCUTS

            ShortcutSheet(self, self._modern.shortcut_list(), "Counter", COUNTER_SHORTCUTS)
            return
        screens = [(f"Alt+{s.upper()}", label) for _k, label, s, perm, _c in self._registry if s and self.ctx.can(perm)]
        ShortcutSheet(self, screens)

    # Sidebar mode ------------------------------------------------------------------------
    def toggle_sidebar(self) -> None:
        compact = self.sidebar.cget("width") > SIDEBAR_COMPACT
        self.prefs.set_sidebar_compact(compact)
        self._apply_sidebar_mode(compact)

    def _apply_sidebar_mode(self, compact: bool) -> None:
        self.sidebar.configure(width=SIDEBAR_COMPACT if compact else SIDEBAR_WIDE)
        for item in self._nav_buttons.values():
            item.set_compact(compact)
        if compact:
            self.brand_text.pack_forget()
            self.user_text.pack_forget()
            self.lock_button.configure(text=icons.icon("lock"), font=icons.font(13))
            self.signout_button.configure(text=icons.icon("signout"), font=icons.font(13))
            self.lock_button.grid_configure(row=0, column=0, columnspan=2, padx=0, pady=(0, 4))
            self.signout_button.grid_configure(row=1, column=0, columnspan=2, padx=0)
        else:
            self.brand_text.pack(side="left", padx=(6, 0), fill="x", expand=True)
            self.user_text.pack(side="left", fill="x", expand=True)
            self.lock_button.configure(text="Lock", font=theme.font(12))
            self.signout_button.configure(text="Sign out", font=theme.font(12))
            self.lock_button.grid_configure(row=0, column=0, columnspan=1, padx=(0, 3), pady=0)
            self.signout_button.grid_configure(row=0, column=1, columnspan=1, padx=(3, 0))

    # Navigation --------------------------------------------------------------------------
    def navigate(self, key: str, **kwargs) -> None:
        if self._modern is not None:  # the new layout: classic keys land in their area
            self._modern.navigate(key, **kwargs)
            return
        entry = next((e for e in self._registry if e[0] == key), None)
        if entry is None or not self.ctx.can(entry[3]) or self._shell is None or self.is_locked:
            return
        _key, label, _s, _p, cls = entry
        self.refresh_names()
        view = self._views.get(key)
        if view is None:
            view = cls(self.content, self.ctx)
            self._views[key] = view
        if self._active and self._active != key:
            self._views[self._active].pack_forget()
        view.pack(fill="both", expand=True)
        self._active = key
        self.header_title.configure(text=label)
        self.header_subtitle.configure(text=SUBTITLES.get(key, ""))
        for k, b in self._nav_buttons.items():
            b.set_active(k == key)
        try:
            view.on_show(**kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("on_show failed for %s", key)
            self.toast(f"Could not load {label}: {exc}", "error")

    def find_view(self, key: str):
        """The built screen for a classic key in either layout, or None."""
        if self._modern is not None:
            return self._modern.find_view(key)
        return self._views.get(key)

    # Feedback ----------------------------------------------------------------------------
    def toast(self, message: str, kind: str = "info") -> None:
        self.toasts.show(message, kind)
        if kind in ("error", "warning"):
            log.warning("toast[%s]: %s", kind, message)

    def set_status(self, message: str) -> None:
        if hasattr(self, "status_label"):
            self.status_label.configure(text=message)

    # Theme -------------------------------------------------------------------------------
    def _theme_icon(self) -> str:
        return icons.icon("moon") if ctk.get_appearance_mode().lower() == "dark" else icons.icon("sun")

    # Language ----------------------------------------------------------------------------
    def refresh_names(self) -> None:
        """Hindi copies of customer / item names for the screens (cheap: one query each)."""
        if i18n.is_hindi():
            try:
                i18n.set_names(*HindiNamesService(self.ctx.db).lookup())
            except Exception:  # noqa: BLE001 - names are a nicety, never block a screen
                log.exception("could not load Hindi names")

    def apply_language(self, lang: str) -> None:
        """Switch English / Hindi now: every screen is rebuilt in the new language."""
        self.prefs.set_language(lang)
        i18n.set_language(lang)
        theme.set_language_font(i18n.is_hindi())
        theme.style_treeview()
        self.refresh_names()
        self.title(f"{__app_name__} {__version__}")
        if not self.is_signed_in or self.is_locked:
            return
        self._teardown_shell()
        self._build_shell()
        self.navigate("settings")

    # Layout ------------------------------------------------------------------------------
    def ask_layout(self, layout: str) -> None:
        """Confirm, then switch the shop to ``layout`` (admin).  Unsaved typing is lost."""
        from hth.ui.widgets.dialogs import confirm

        if layout == self.layout:
            return
        tr = i18n.tr
        question = (
            "Switch the whole shop to the new layout?"
            if layout == "new"
            else "Switch the whole shop to the classic layout?"
        )
        rebuilt = (
            "Every screen is rebuilt: anything typed but not saved is lost. "
            "You can switch back at any time in Settings."
        )
        if not confirm(self, tr("Switch layout"), f"{tr(question)}\n\n{tr(rebuilt)}"):
            return
        # after the click returns: the rebuild destroys the button that was clicked
        self.after(20, lambda: self.apply_layout(layout))

    def apply_layout(self, layout: str) -> None:
        self.prefs.set_layout(layout)
        self.ctx.audit.log("09", f"layout -> {layout}", self.ctx.username)
        if not self.is_signed_in or self.is_locked:
            return
        self._teardown_shell()
        self._build_shell()
        self.navigate("settings")
        self.toast("New layout on" if layout == "new" else "Classic layout on", "success")

    def apply_text_scale(self, scale: float) -> None:
        self.prefs.set_text_scale(scale)
        theme.set_text_scale(scale)
        theme.style_treeview()
        for view in self._views.values():
            try:
                view.on_theme_change()
            except Exception:  # noqa: BLE001
                log.exception("restyle failed for %s", view.key)

    def toggle_theme(self) -> None:
        self.apply_theme("light" if ctk.get_appearance_mode().lower() == "dark" else "dark")

    def apply_theme(self, mode: str) -> None:
        self.appearance = mode
        theme.apply_appearance(mode)
        try:
            self.prefs.set_theme(mode)
        except Exception:  # noqa: BLE001 - a read-only database must not break the toggle
            log.exception("could not save theme")
        if hasattr(self, "theme_button"):
            self.theme_button.configure(text=self._theme_icon())
        for view in self._views.values():
            try:
                view.on_theme_change()
            except Exception:  # noqa: BLE001
                log.exception("theme change failed for %s", view.key)


def run_app(db: Database, settings: Settings) -> None:
    app = App(db, settings)
    app.mainloop()
