"""The new layout's frame: a top bar with the six areas, the Ask box, the date, the gear and
the user menu; the chosen area below it; a slim status line at the bottom.

The App keeps owning sign-in, lock, toasts, theme, language and the views it has built
(``App._views`` / ``App._active``), so everything that works in the classic layout - the
idle lock, midnight roll-over, F1, Ctrl+K - works here the same way.
"""

from __future__ import annotations

import datetime as dt
import logging
import tkinter as tk

import customtkinter as ctk

from hth import __app_name__, __company__, i18n
from hth.modules import discover
from hth.services.permissions import ROLES, Permission
from hth.ui import icons, theme
from hth.ui.modern import registry
from hth.ui.modern.areas.tabbed import TabbedArea

log = logging.getLogger(__name__)


def _initials(text: str) -> str:
    return "".join(p[0] for p in text.split()[:2]).upper() or "?"


class ModernShell(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=theme.color("bg"), corner_radius=0)
        self.app = app
        self.ctx = app.ctx
        self.areas = registry.allowed(registry.build_areas(discover()), self.ctx.can)
        self.area_buttons: dict[str, ctk.CTkButton] = {}
        self._build_top_bar()
        ctk.CTkFrame(self, height=1, fg_color=theme.color("line"), corner_radius=0).pack(fill="x")
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=16, pady=(12, 6))
        self._build_status_bar()
        self._bind_keys()

    # Areas -----------------------------------------------------------------------------
    def area(self, key: str) -> registry.Area | None:
        return next((a for a in self.areas if a.key == key), None)

    def home(self) -> str:
        user = self.ctx.user
        return registry.home(self.areas, bool(user and user.is_admin))

    def navigate(self, key: str, **kwargs) -> None:
        app = self.app
        area_key, kwargs = registry.resolve(self.areas, key, kwargs)
        area = self.area(area_key) if area_key else None
        if area is None or app.is_locked:
            return
        app.refresh_names()
        view = app._views.get(area.key)
        if view is None:
            factory = area.factory or (lambda master, ctx, a=area: TabbedArea(master, ctx, a))
            view = factory(self.content, self.ctx)
            app._views[area.key] = view
        if app._active and app._active != area.key and app._active in app._views:
            app._views[app._active].pack_forget()
        view.pack(fill="both", expand=True)
        app._active = area.key
        self.set_active(area.key)
        try:
            view.on_show(**kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("on_show failed for %s", area.key)
            app.toast(f"Could not load {area.label}: {exc}", "error")

    def find_view(self, key: str):
        """A screen by its classic key, wherever it sits (``assistant`` lives in Ask).  A
        screen inside an area wins over an area of the same name (Settings › Settings)."""
        area_key, _kwargs = registry.resolve(self.areas, key, {})
        view = self.app._views.get(area_key or key)
        child = getattr(view, "child", None)
        if callable(child):
            return child(key) or (view if area_key == key else None)
        return view

    def shortcut_list(self) -> list[tuple[str, str]]:
        """(keys, where) for the F1 sheet: every Alt-letter of this layout."""
        out = []
        for area in self.areas:
            for t in area.tabs:
                if t.shortcut:
                    one = t.label == area.label or len(area.tabs) == 1
                    where = i18n.tr(area.label) if one else f"{i18n.tr(area.label)} › {i18n.tr(t.label)}"
                    out.append((f"Alt+{t.shortcut.upper()}", where))
        return out

    # Top bar ---------------------------------------------------------------------------
    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=58, fg_color=theme.color("topbar"), corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(side="left", padx=(18, 10))
        ctk.CTkLabel(
            brand,
            text=_initials(__company__),
            width=34,
            height=34,
            corner_radius=9,
            fg_color=theme.color("accent"),
            text_color=theme.color("accent_text"),
            font=theme.font(13, "bold"),
        ).pack(side="left")
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(names, text=__company__.title(), font=theme.font(13, "bold"), anchor="w", height=18).pack(fill="x")
        ctk.CTkLabel(
            names, text=__app_name__, font=theme.font(10), text_color=theme.color("muted"), anchor="w", height=14
        ).pack(fill="x")

        nav = ctk.CTkFrame(bar, fg_color="transparent")
        nav.pack(side="left", padx=(8, 0))
        for area in self.areas:
            if not area.in_bar:
                continue
            b = ctk.CTkButton(
                nav,
                text=area.label,
                width=10,
                height=36,
                corner_radius=8,
                font=theme.font(14, "bold"),
                fg_color="transparent",
                hover_color=theme.color("surface_hover"),
                text_color=theme.color("text"),
                command=lambda k=area.key: self.app.navigate(k),
            )
            b.pack(side="left", padx=2)
            self.area_buttons[area.key] = b

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=(8, 18))
        self.user_button = ctk.CTkButton(
            right,
            text=_initials(self.ctx.user.full_name or self.ctx.user.username) if self.ctx.user else "?",
            width=34,
            height=34,
            corner_radius=17,
            font=theme.font(12, "bold"),
            fg_color=theme.color("accent_hover"),
            hover_color=theme.color("accent"),
            text_color=theme.color("accent_text"),
            command=self.open_user_menu,
        )
        self.user_button.pack(side="right")
        self.settings_button = ctk.CTkButton(
            right,
            text=icons.icon("settings"),
            font=icons.font(15),
            width=36,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=theme.color("line"),
            hover_color=theme.color("surface_hover"),
            text_color=theme.color("muted"),
            command=lambda: self.app.navigate("settings"),
        )
        self.settings_button.pack(side="right", padx=8)
        self.date_label = ctk.CTkLabel(right, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.date_label.pack(side="right", padx=(6, 4))
        self.refresh_date()

        ask = ctk.CTkFrame(
            bar,
            fg_color=theme.color("stripe"),
            border_width=1,
            border_color=theme.color("line"),
            corner_radius=10,
            height=38,
        )
        ask.pack(side="right", fill="x", expand=True, padx=(12, 4), pady=10)
        self.ask_button = ctk.CTkButton(
            ask,
            text=f"{icons.icon('search')}   Search a customer or item — or ask",
            anchor="w",
            height=32,
            font=theme.font(12),
            fg_color="transparent",
            hover_color=theme.color("surface_hover"),
            text_color=theme.color("muted"),
            command=self.app.open_search,
        )
        self.ask_button.pack(side="left", fill="x", expand=True, padx=(4, 0), pady=2)
        ctk.CTkLabel(ask, text="Ctrl K", font=theme.font(10, "bold"), text_color=theme.color("muted")).pack(
            side="left", padx=6
        )
        self.mic_button = ctk.CTkButton(
            ask,
            text=icons.icon("mic"),
            font=icons.font(14),
            width=30,
            height=28,
            corner_radius=8,
            fg_color=theme.color("accent_soft"),
            hover_color=theme.color("surface2"),
            text_color=theme.color("accent"),
            command=lambda: self.app.navigate("assistant", listen=True),
        )
        self.mic_button.pack(side="right", padx=4, pady=4)

    def set_active(self, key: str) -> None:
        for k, b in self.area_buttons.items():
            on = k == key
            b.configure(
                fg_color=theme.color("accent_soft") if on else "transparent",
                text_color=theme.color("accent") if on else theme.color("text"),
            )
        on = key == "settings"
        self.settings_button.configure(
            fg_color=theme.color("accent_soft") if on else "transparent",
            text_color=theme.color("accent") if on else theme.color("muted"),
        )

    def refresh_date(self) -> None:
        self.date_label.configure(text=i18n.date_text(dt.date.today(), "%a, %d %b"))

    # User menu -------------------------------------------------------------------------
    def open_user_menu(self) -> None:
        tr = i18n.tr
        u = self.ctx.user
        menu = tk.Menu(
            self,
            tearoff=0,
            bg=theme.current("surface"),
            fg=theme.current("text"),
            activebackground=theme.current("accent_soft"),
            activeforeground=theme.current("text"),
            font=theme.table_font(),
        )
        if u is not None:
            menu.add_command(label=f"{u.full_name or u.username} · {tr(ROLES.get(u.role, u.role))}", state="disabled")
            menu.add_separator()
        menu.add_command(label=tr("Lock screen"), accelerator="Ctrl+L", command=self.app.lock)
        dark = ctk.get_appearance_mode().lower() == "dark"
        menu.add_command(label=tr("Light theme" if dark else "Dark theme"), command=self.app.toggle_theme)
        menu.add_command(label=tr("Keyboard shortcuts"), accelerator="F1", command=self.app.show_shortcuts)
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            menu.add_command(label=tr("Switch to the classic layout"), command=lambda: self.app.ask_layout("classic"))
        menu.add_separator()
        menu.add_command(label=tr("Sign out"), command=self.app.logout)
        x = self.user_button.winfo_rootx() + self.user_button.winfo_width()
        y = self.user_button.winfo_rooty() + self.user_button.winfo_height() + 4
        try:
            menu.tk_popup(x - 220, y)
        finally:
            menu.grab_release()

    # Status line -----------------------------------------------------------------------
    def _build_status_bar(self) -> None:
        status = ctk.CTkFrame(self, height=26, fg_color=theme.color("surface"), corner_radius=0)
        status.pack(fill="x", side="bottom")
        self.status_label = ctk.CTkLabel(
            status, text="Ready", font=theme.font(11), text_color=theme.color("muted"), anchor="w"
        )
        self.status_label.pack(side="left", padx=16)
        self.backup_label = ctk.CTkLabel(status, text="", font=theme.font(11), text_color=theme.color("muted"))
        self.backup_label.pack(side="right", padx=16)

    # Keys ------------------------------------------------------------------------------
    def _speak(self, event=None) -> None:
        """F2 from anywhere: open the Assistant listening.  In the Assistant's own box F2
        is already its key - leave it to that, or the two would cancel each other out."""
        view = self.find_view("assistant")
        entry = getattr(view, "entry", None)
        if event is not None and entry is not None and str(event.widget).startswith(str(entry)):
            return
        self.app.navigate("assistant", listen=True)

    def _bind_keys(self) -> None:
        bind = self.app.bind_shell_key
        if any(t.key == "assistant" for a in self.areas for t in a.tabs):
            bind("<F2>", self._speak)
        for area in self.areas:
            for t in area.tabs:
                if t.shortcut:
                    bind(f"<Alt-{t.shortcut}>", lambda e, k=t.key: self.app.navigate(k))
                    bind(f"<Alt-{t.shortcut.upper()}>", lambda e, k=t.key: self.app.navigate(k))
