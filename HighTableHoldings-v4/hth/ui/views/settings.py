"""Settings: appearance, backup, v3 import, own password, about."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from hth import __app_name__, __version__
from hth.config import LEGACY_DATA_DIR_WINDOWS
from hth.domain.constants import ANNUAL_INTEREST_RATE_PERCENT
from hth.migration.from_v3 import MigrationError, migrate
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import open_path
from hth.ui.views.base import BaseView
from hth.ui.widgets.dialogs import Field, confirm, info, run_form
from hth.ui.widgets.forms import Card, primary_button, secondary_button


class SettingsView(BaseView):
    key = "settings"
    title = "Settings"
    permission = None

    def build(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        s = self.ctx.settings

        look = Card(scroll, "Appearance")
        look.pack(fill="x", padx=4, pady=4)
        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkLabel(row, text="Theme", font=theme.font(13)).pack(side="left", padx=(0, 12))
        self.mode = ctk.CTkSegmentedButton(
            row, values=["Light", "Dark", "System"], command=self._set_mode, font=theme.font(13)
        )
        self.mode.set(self.ctx.app.appearance.title())
        self.mode.pack(side="left")

        acct = Card(scroll, "My account")
        acct.pack(fill="x", padx=4, pady=4)
        row = ctk.CTkFrame(acct, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(4, 16))
        u = self.ctx.user
        ctk.CTkLabel(row, text=f"Signed in as {u.username} ({u.role})", font=theme.font(13)).pack(
            side="left", padx=(0, 12)
        )
        secondary_button(row, "Change my password", self.change_password, width=170).pack(side="left")

        data = Card(scroll, "Data")
        data.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(data, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkLabel(
            body,
            text=f"Database: {s.db_path}",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            body,
            text=f"Exports: {s.export_dir}    Backups: {s.backup_dir}    Logs: {s.log_dir}",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            wraplength=900,
            justify="left",
        ).pack(fill="x", pady=(2, 8))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        secondary_button(row, "Open data folder", lambda: open_path(s.data_dir), width=150).pack(
            side="left", padx=(0, 8)
        )
        if self.ctx.can(Permission.BACKUP):
            primary_button(row, "Backup now", self.backup, width=130).pack(side="left", padx=(0, 8))
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            secondary_button(row, "Import v3 data…", self.import_v3, width=150).pack(side="left")
        ctk.CTkLabel(
            body,
            text="Tip: back up before month-end and keep copies of the backups folder off this computer.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

        about = Card(scroll, "About")
        about.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            about,
            text=(
                f"{__app_name__} v{__version__}\n"
                f"Interest: {ANNUAL_INTEREST_RATE_PERCENT:g}% p.a., simple daily, compounded each 31 March"
                " (financial year end).\n"
                "Tags: 1 normal (interest), 2 no interest, 0 settlement (closes the period).\n"
                "Type P = debit (customer owes more), M = credit (customer paid)."
            ),
            font=theme.font(12),
            text_color=theme.color("muted"),
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=18, pady=(4, 16))

    def _set_mode(self, value: str) -> None:
        self.ctx.app.apply_theme(value.lower())

    def change_password(self) -> None:
        u = self.ctx.user
        fields = [
            Field("old", "Current password", "password"),
            Field("new", "New password", "password"),
            Field("again", "Repeat new password", "password"),
        ]

        def submit(v):
            if v["new"] != v["again"]:
                raise ValueError("New passwords do not match.")
            self.ctx.auth.change_own_password(u, v["old"], v["new"])

        if run_form(self, "Change password", fields, submit):
            self.ctx.toast("Password changed", "success")

    def backup(self) -> None:
        dest = self.ctx.settings.backup_dir / f"hth_{dt.datetime.now():%Y%m%d_%H%M%S}.db"
        self.ctx.db.backup_to(dest)
        self.ctx.toast(f"Backup saved: {dest.name}", "success")
        self.ctx.audit.log("09", f"backup {dest.name}", self.ctx.username)

    def import_v3(self) -> None:
        initial = LEGACY_DATA_DIR_WINDOWS if LEGACY_DATA_DIR_WINDOWS.exists() else Path.home()
        folder = filedialog.askdirectory(
            title="Select the v3 data folder (contains accounts.db, inventory.db …)",
            initialdir=str(initial),
            parent=self,
        )
        if not folder:
            return
        has_data = self.ctx.db.fetchone("SELECT 1 FROM customers LIMIT 1") is not None
        msg = f"Import v3 data from\n{folder}\n\nA backup will be taken first."
        if has_data:
            msg += (
                "\n\nWARNING: this database already has customers. Importing again will fail on"
                " duplicate IDs unless the data is different."
            )
        if not confirm(self, "Import v3 data", msg):
            return
        self.backup()
        try:
            report = migrate(Path(folder), self.ctx.db, force=has_data)
        except MigrationError as exc:
            self.ctx.toast(str(exc), "error")
            return
        except Exception as exc:  # noqa: BLE001
            self.ctx.toast(f"Import failed: {exc}", "error")
            return
        info(self, "Import complete", "\n".join(report.as_lines()))
        self.ctx.audit.log("09", "imported v3 data", self.ctx.username)
