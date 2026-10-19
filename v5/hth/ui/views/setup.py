"""First-run wizard: shop details, passwords, optional v3 import."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from hth import __app_name__
from hth.config import LEGACY_DATA_DIR_WINDOWS
from hth.migration.from_v3 import MigrationError, migrate
from hth.services.auth import AuthError
from hth.services.settings import SettingsService
from hth.ui import theme
from hth.ui.views.base import BaseView
from hth.ui.widgets.forms import LabeledEntry, primary_button, secondary_button

SETUP_KEY = "setup.completed"


def setup_completed(db) -> bool:
    return SettingsService(db).get(SETUP_KEY) == "1"


def mark_setup(db, done: bool) -> None:
    SettingsService(db).set(SETUP_KEY, "1" if done else "0")


class SetupView(BaseView):
    key = "setup"
    title = "Welcome"

    def build(self) -> None:
        self.configure(fg_color=theme.color("bg"))
        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True)
        card = ctk.CTkFrame(outer, fg_color=theme.color("surface"), corner_radius=16)
        card.pack(padx=120, pady=30, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=36, pady=28)

        ctk.CTkLabel(inner, text=f"Welcome to {__app_name__}", font=theme.font(24, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(
            inner,
            text="Three quick steps and the shop is ready. You can change all of this later in Settings.",
            font=theme.font(13),
            text_color=theme.color("muted"),
            anchor="w",
        ).pack(fill="x", pady=(2, 16))

        p = self.ctx.company.profile()
        self._section(inner, "1 · Shop details (printed on statements and invoices)")
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1), weight=1)
        self.name = LabeledEntry(grid, "Shop name", default=p.name)
        self.name.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.phone = LabeledEntry(grid, "Phone", default=p.phone)
        self.phone.grid(row=0, column=1, sticky="ew", pady=3)
        self.address = LabeledEntry(grid, "Address", default=p.address)
        self.address.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.gstin = LabeledEntry(grid, "GSTIN", default=p.gstin)
        self.gstin.grid(row=1, column=1, sticky="ew", pady=3)

        self._section(inner, "2 · Passwords (the defaults admin/admin and emp1/emp1 must change)")
        pw = ctk.CTkFrame(inner, fg_color="transparent")
        pw.pack(fill="x")
        pw.grid_columnconfigure((0, 1), weight=1)
        self.admin_pw = LabeledEntry(pw, "Administrator password", show="•")
        self.admin_pw.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.admin_pw2 = LabeledEntry(pw, "Repeat", show="•")
        self.admin_pw2.grid(row=0, column=1, sticky="ew", pady=3)
        self.emp_pw = LabeledEntry(pw, "Employee (emp1) password", show="•")
        self.emp_pw.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.emp_pw2 = LabeledEntry(pw, "Repeat", show="•")
        self.emp_pw2.grid(row=1, column=1, sticky="ew", pady=3)

        self._section(inner, "3 · Bring in v3 data (optional)")
        imp = ctk.CTkFrame(inner, fg_color="transparent")
        imp.pack(fill="x")
        self.legacy = LabeledEntry(
            imp,
            "Folder with accounts.db / inventory.db / krar.db / daily_notes.db (leave blank to skip)",
            default=str(LEGACY_DATA_DIR_WINDOWS) if LEGACY_DATA_DIR_WINDOWS.exists() else "",
        )
        self.legacy.pack(side="left", fill="x", expand=True)
        secondary_button(imp, "Browse…", self.browse, width=90).pack(side="left", padx=(8, 0), pady=(18, 0))

        self.error = ctk.CTkLabel(
            inner,
            text="",
            text_color=theme.color("danger"),
            font=theme.font(12),
            anchor="w",
            wraplength=700,
            justify="left",
        )
        self.error.pack(fill="x", pady=(10, 0))
        buttons = ctk.CTkFrame(inner, fg_color="transparent")
        buttons.pack(fill="x", pady=(10, 0))
        primary_button(buttons, "Finish setup", self.finish, width=160).pack(side="left")
        secondary_button(buttons, "Skip for now", self.skip, width=120).pack(side="left", padx=8)
        ctk.CTkLabel(
            buttons,
            text=f"data folder: {self.ctx.settings.data_dir}",
            font=theme.font(10),
            text_color=theme.color("muted"),
        ).pack(side="right")

    def _section(self, master, text: str) -> None:
        ctk.CTkLabel(
            master, text=text.upper(), font=theme.font(11, "bold"), text_color=theme.color("accent"), anchor="w"
        ).pack(fill="x", pady=(14, 4))

    def browse(self) -> None:
        folder = filedialog.askdirectory(title="v3 data folder", parent=self)
        if folder:
            self.legacy.set(folder)

    def _validate_passwords(self) -> tuple[str, str]:
        a, a2, e, e2 = self.admin_pw.get(), self.admin_pw2.get(), self.emp_pw.get(), self.emp_pw2.get()
        if not a or not e:
            raise AuthError("Set both passwords.")
        if a != a2 or e != e2:
            raise AuthError("Passwords do not match.")
        if a == "admin" or e == "emp1":
            raise AuthError("Please choose passwords different from the defaults.")
        return a, e

    def finish(self) -> None:
        try:
            admin_pw, emp_pw = self._validate_passwords()
            if not self.name.get():
                raise AuthError("Shop name is required.")
            users = {u.username: u for u in self.ctx.auth.list_users()}
            self.ctx.auth.set_password(users["admin"].id, admin_pw, actor="setup")
            if "emp1" in users:
                self.ctx.auth.set_password(users["emp1"].id, emp_pw, actor="setup")
            self.ctx.company.update(
                name=self.name.get(), phone=self.phone.get(), address=self.address.get(), gstin=self.gstin.get()
            )
            folder = self.legacy.get().strip()
            if folder:
                self.ctx.backup.manual()
                report = migrate(Path(folder), self.ctx.db)
                self.ctx.audit.log("09", f"setup: imported v3 data ({report.customers} customers)", "setup")
                report.write(self.ctx.settings.data_dir / "migration_report.txt")
        except (AuthError, MigrationError, ValueError) as exc:
            self.error.configure(text=str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - import problems must be visible, not fatal
            self.error.configure(text=f"Import failed: {exc}")
            return
        mark_setup(self.ctx.db, True)
        self.ctx.audit.log("09", "first-run setup completed", "setup")
        self.ctx.app.setup_done()

    def skip(self) -> None:
        mark_setup(self.ctx.db, True)
        self.ctx.app.setup_done()
