"""Settings in the new layout: sections on the left instead of one long scroll.

It *is* the classic Settings screen (a subclass): every card is built by the same method,
just into its own section, so every control behaves exactly as before.  Users - its own
screen in the classic sidebar - is a section here.
"""

from __future__ import annotations

import customtkinter as ctk

from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.views.settings import SettingsView
from hth.ui.views.users import UsersView

# (section, card builders on SettingsView, permission to see it, changes need an admin)
SECTIONS: tuple[tuple[str, tuple[str, ...], Permission | None, bool], ...] = (
    ("Shop details", ("_build_company",), None, True),
    ("Appearance & language", ("_build_look",), None, False),
    ("My password", ("_build_account",), None, False),
    ("Users", (), Permission.MANAGE_USERS, True),
    ("Backup & data", ("_build_data",), None, True),
    ("Reminder messages", ("_build_reminders",), None, False),
    ("Categories", ("_build_categories",), None, True),
    ("Hindi names", ("_build_hindi",), None, False),
    ("Assistant & voice", ("_build_assistant",), None, False),
    ("Updates", ("_build_updates",), None, True),
    ("About", ("_build_about",), None, False),
)
FIRST = "Appearance & language"


class SettingsArea(SettingsView):
    def build(self) -> None:
        self.sections = [s for s in SECTIONS if self.ctx.can(s[2])]
        self.grid_columnconfigure(0, weight=0, minsize=250)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        nav = ctk.CTkFrame(
            self, fg_color=theme.color("surface"), corner_radius=12, border_width=1, border_color=theme.color("line")
        )
        nav.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        ctk.CTkLabel(nav, text="Settings", font=theme.font(19, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(14, 8)
        )
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for name, _builders, _perm, admin in self.sections:
            row = ctk.CTkFrame(nav, fg_color="transparent")
            row.pack(fill="x", padx=8)
            b = ctk.CTkButton(
                row,
                text=name,
                anchor="w",
                height=34,
                corner_radius=8,
                font=theme.font(13, "bold"),
                fg_color="transparent",
                hover_color=theme.color("surface_hover"),
                text_color=theme.color("text"),
                command=lambda n=name: self.show_section(n),
            )
            b.pack(side="left", fill="x", expand=True)
            if admin:
                ctk.CTkLabel(row, text="ADMIN", font=theme.font(9, "bold"), text_color=theme.color("muted")).pack(
                    side="right", padx=(0, 6)
                )
            self.nav_buttons[name] = b
        ctk.CTkFrame(nav, height=1, fg_color=theme.color("line")).pack(fill="x", padx=14, pady=10)
        app = self.ctx.app
        for text, command in (("Lock screen   Ctrl+L", app.lock), ("Sign out", app.logout)):
            ctk.CTkButton(
                nav,
                text=text,
                anchor="w",
                height=30,
                fg_color="transparent",
                hover_color=theme.color("surface_hover"),
                text_color=theme.color("muted"),
                font=theme.font(12, "bold"),
                command=command,
            ).pack(fill="x", padx=8, pady=(0, 2))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=1, sticky="nsew")
        # every card is built now, as on the classic screen (they refer to each other)
        self.section_frames: dict[str, ctk.CTkFrame] = {}
        self.users: UsersView | None = None
        for name, builders, _perm, _admin in self.sections:
            frame = ctk.CTkFrame(self.body, fg_color="transparent")
            if name == "Users":
                self.users = UsersView(frame, self.ctx)
                self.users.pack(fill="both", expand=True)
            for builder in builders:
                getattr(self, builder)(frame)
            self.section_frames[name] = frame
        self.current_section: str | None = None
        self.show_section(FIRST)

    def show_section(self, name: str) -> None:
        if name not in self.section_frames:
            name = FIRST
        for frame in self.section_frames.values():
            frame.pack_forget()
        self.section_frames[name].pack(fill="both", expand=True)
        self.current_section = name
        for n, b in self.nav_buttons.items():
            on = n == name
            b.configure(
                fg_color=theme.color("accent_soft") if on else "transparent",
                text_color=theme.color("accent") if on else theme.color("text"),
            )
        if name == "Users" and self.users is not None:
            self.users.on_show()
        try:
            self.body._parent_canvas.yview_moveto(0)  # noqa: SLF001 - start each section at the top
        except Exception:  # noqa: BLE001
            pass

    def child(self, key: str):
        return {"settings": self, "users": self.users}.get(key)

    def on_show(self, tab: str | None = None, section: str | None = None, **kwargs) -> None:
        if tab == "users" and self.users is not None:
            self.show_section("Users")
        elif section:
            self.show_section(section)
        elif tab == "settings" and self.current_section == "Users":
            self.show_section(FIRST)  # the gear / "settings" opens Settings itself

    def on_theme_change(self) -> None:
        super().on_theme_change()
        if self.users is not None:
            self.users.on_theme_change()
