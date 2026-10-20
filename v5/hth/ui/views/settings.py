"""Settings: appearance, backup, v3 import, own password, about."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from hth import __app_name__, __version__
from hth.config import LEGACY_DATA_DIR_WINDOWS
from hth.domain.constants import ANNUAL_INTEREST_RATE_PERCENT, AuditCode
from hth.migration.from_v3 import MigrationError, migrate
from hth.services.accounts import ValidationError
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import open_path
from hth.ui.views.base import BaseView
from hth.ui.widgets.dialogs import Field, confirm, info, run_form
from hth.ui.widgets.forms import Card, primary_button, secondary_button

_SPEAK = {"voice": "When I speak", "always": "Always", "never": "Never"}  # Settings -> Assistant -> Speak answers


class SettingsView(BaseView):
    key = "settings"
    title = "Settings"
    permission = None

    def build(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self._build_look(scroll)
        self._build_account(scroll)
        self._build_data(scroll)
        self._build_hindi(scroll)
        self._build_assistant(scroll)
        self._build_company(scroll)
        self._build_reminders(scroll)
        self._build_categories(scroll)
        self._build_updates(scroll)
        self._build_about(scroll)

    # Cards - one method each, so the new layout can show them as sections ------------------
    def _build_look(self, scroll) -> None:
        look = Card(scroll, "Appearance & security")
        look.pack(fill="x", padx=4, pady=4)
        prefs = self.ctx.prefs
        can_edit = self.ctx.can(Permission.MANAGE_SETTINGS)
        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(4, 6))
        ctk.CTkLabel(row, text="Language", font=theme.font(13), width=120, anchor="w").pack(side="left")
        self.language = ctk.CTkSegmentedButton(
            row,
            values=["English", "हिन्दी"],
            command=self._set_language,
            font=theme.font(13),
            state="normal" if can_edit else "disabled",
        )
        self.language.set("हिन्दी" if prefs.language() == "hi" else "English")
        self.language.pack(side="left")
        ctk.CTkLabel(
            row,
            text="   screens, reports, statements and names (Hindi copies, editable below)",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="left")

        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(row, text="Layout", font=theme.font(13), width=120, anchor="w").pack(side="left")
        self.layout_choice = ctk.CTkSegmentedButton(
            row,
            values=["Classic", "New"],
            command=self._set_layout,
            font=theme.font(13),
            state="normal" if can_edit else "disabled",
        )
        self.layout_choice.set("New" if prefs.layout() == "new" else "Classic")
        self.layout_choice.pack(side="left")
        ctk.CTkLabel(
            row,
            text="   Classic: menu on the left, as before.  New: six areas across the top.  For the whole shop.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="left")

        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(row, text="Theme", font=theme.font(13), width=120, anchor="w").pack(side="left")
        self.mode = ctk.CTkSegmentedButton(
            row, values=["Light", "Dark", "System"], command=self._set_mode, font=theme.font(13)
        )
        self.mode.set(self.ctx.app.appearance.title())
        self.mode.pack(side="left")
        ctk.CTkLabel(
            row, text="   remembered for next time", font=theme.font(11), text_color=theme.color("muted")
        ).pack(side="left")

        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(row, text="Numbers", font=theme.font(13), width=120, anchor="w").pack(side="left")
        self.number_style = ctk.CTkSegmentedButton(
            row,
            values=["Indian  12,34,567.00", "International  1,234,567.00"],
            command=self._set_number_style,
            font=theme.font(13),
            state="normal" if can_edit else "disabled",
        )
        self.number_style.set(
            "Indian  12,34,567.00" if prefs.number_style() == "indian" else "International  1,234,567.00"
        )
        self.number_style.pack(side="left")

        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(row, text="Text size", font=theme.font(13), width=120, anchor="w").pack(side="left")
        self.text_size = ctk.CTkSegmentedButton(
            row, values=["90%", "100%", "115%", "130%"], command=self._set_text_size, font=theme.font(13)
        )
        self.text_size.set(f"{round(prefs.text_scale() * 100)}%")
        self.text_size.pack(side="left")
        ctk.CTkLabel(
            row, text="   bigger text and rows on every screen", font=theme.font(11), text_color=theme.color("muted")
        ).pack(side="left")

        row = ctk.CTkFrame(look, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(6, 16))
        ctk.CTkLabel(row, text="Auto-lock", font=theme.font(13), width=120, anchor="w").pack(side="left")
        lock_choices = ["Never", "2 min", "5 min", "10 min", "15 min", "30 min", "60 min"]
        current = prefs.lock_minutes()
        self.lock_menu = ctk.CTkOptionMenu(
            row,
            values=lock_choices,
            width=110,
            height=32,
            font=theme.font(13),
            command=self._set_lock,
            state="normal" if can_edit else "disabled",
        )
        self.lock_menu.set(f"{current} min" if f"{current} min" in lock_choices else "Never")
        self.lock_menu.pack(side="left")
        ctk.CTkLabel(
            row,
            text="   after this much idle time the screen locks; work in progress stays.  Ctrl+L locks now.",
            font=theme.font(11),
            text_color=theme.color("muted"),
        ).pack(side="left")

    def _build_account(self, scroll) -> None:
        acct = Card(scroll, "My account")
        acct.pack(fill="x", padx=4, pady=4)
        row = ctk.CTkFrame(acct, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(4, 16))
        u = self.ctx.user
        ctk.CTkLabel(row, text=f"Signed in as {u.username} ({u.role})", font=theme.font(13)).pack(
            side="left", padx=(0, 12)
        )
        secondary_button(row, "Change my password", self.change_password, width=170).pack(side="left")

    def _build_data(self, scroll) -> None:
        s = self.ctx.settings
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
            secondary_button(row, "Restore a backup…", self.restore, width=160).pack(side="left", padx=(0, 8))
        b = self.ctx.backup
        last = b.last_backup()
        self.auto_backup = ctk.BooleanVar(value=b.enabled())
        auto_row = ctk.CTkFrame(body, fg_color="transparent")
        auto_row.pack(fill="x", pady=(8, 0))
        ctk.CTkCheckBox(
            auto_row,
            text="Automatic backup on the first start each day",
            variable=self.auto_backup,
            font=theme.font(13),
            command=self.save_backup_prefs,
        ).pack(side="left")
        ctk.CTkLabel(auto_row, text="  keep last", font=theme.font(13)).pack(side="left")
        self.keep_entry = ctk.CTkEntry(auto_row, width=50, height=30, font=theme.font(13))
        self.keep_entry.insert(0, str(b.keep()))
        self.keep_entry.pack(side="left", padx=4)
        self.keep_entry.bind("<FocusOut>", lambda e: self.save_backup_prefs())
        ctk.CTkLabel(
            auto_row,
            text=f"   last backup: {last.name if last else 'none yet'}",
            font=theme.font(12),
            text_color=theme.color("muted"),
        ).pack(side="left")
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            secondary_button(row, "Import v3 data…", self.import_v3, width=150).pack(side="left")
            secondary_button(row, "Run setup wizard", self.rerun_setup, width=140).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            body,
            text="Tip: back up before month-end and keep copies of the backups folder off this computer.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

    def _build_about(self, scroll) -> None:
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

    # Reminders -------------------------------------------------------------------------
    def _build_reminders(self, scroll) -> None:
        card = Card(scroll, "Payment reminders (Karar → Copy reminder / WhatsApp)")
        card.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        self.reminder_box = ctk.CTkTextbox(body, height=80, font=theme.font(13))
        self.reminder_box.insert("1.0", self.ctx.reminders.template())
        self.reminder_box.pack(fill="x")
        ctk.CTkLabel(
            body,
            text="Placeholders: {name} {amount} {date} {days} {shop} {phone} {village}.  "
            "WhatsApp opens when the account details contain a 10-digit mobile number.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
            wraplength=900,
            justify="left",
        ).pack(fill="x", pady=(4, 0))
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            secondary_button(body, "Save template", self.save_reminder, width=130).pack(anchor="w", pady=(8, 0))

    def save_reminder(self) -> None:
        try:
            self.ctx.reminders.set_template(self.reminder_box.get("1.0", "end"))
        except ValueError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.toast("Reminder template saved", "success")

    # Company profile ------------------------------------------------------------------
    def _build_company(self, scroll) -> None:
        card = Card(scroll, "Shop details (statements and invoices)")
        card.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        p = self.ctx.company.profile()
        self.company_text = ctk.CTkLabel(
            body,
            text=f"{p.name} · {p.tagline}\n{p.address} · {p.phone} · GSTIN {p.gstin}\n{p.licences}",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
        )
        self.company_text.pack(fill="x")
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            secondary_button(body, "Edit shop details", self.edit_company, width=150).pack(anchor="w", pady=(8, 0))

    def edit_company(self) -> None:
        p = self.ctx.company.profile()
        fields = [
            Field("name", "Shop name", default=p.name),
            Field("tagline", "Tagline", default=p.tagline),
            Field("address", "Address", default=p.address),
            Field("phone", "Phone", default=p.phone),
            Field("gstin", "GSTIN", default=p.gstin),
            Field("licences", "Licence numbers", default=p.licences),
            Field("footer", "Statement footer note", default=p.footer),
        ]
        if run_form(self, "Shop details", fields, lambda v: self.ctx.company.update(**v)):
            p = self.ctx.company.profile()
            self.company_text.configure(
                text=f"{p.name} · {p.tagline}\n{p.address} · {p.phone} · GSTIN {p.gstin}\n{p.licences}"
            )
            self.ctx.audit.log("09", "shop details updated", self.ctx.username)
            self.ctx.toast("Shop details saved", "success")

    # Categories -----------------------------------------------------------------------
    def _build_categories(self, scroll) -> None:
        cats = self.ctx.categories
        can_edit = self.ctx.can(Permission.MANAGE_SETTINGS)
        card = Card(scroll, "Categories")
        card.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkLabel(
            body,
            text=(
                "A best … D worst by score; E = defaulter (customers) / discontinued (items), set by hand only. "
                "Tick the categories that feed the dashboard and reports."
            ),
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x", pady=(0, 6))

        self.cust_cat_vars = {}
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="Customers in reports:", font=theme.font(13), width=170, anchor="w").pack(side="left")
        chosen = cats.customer_report_categories()
        for c in "ABCDE":
            var = ctk.BooleanVar(value=c in chosen)
            self.cust_cat_vars[c] = var
            ctk.CTkCheckBox(row, text=c, variable=var, width=50, font=theme.font(13)).pack(side="left", padx=4)

        self.item_cat_vars = {}
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="Items in reports:", font=theme.font(13), width=170, anchor="w").pack(side="left")
        chosen = cats.item_report_categories()
        for c in "ABCDE":
            var = ctk.BooleanVar(value=c in chosen)
            self.item_cat_vars[c] = var
            ctk.CTkCheckBox(row, text=c, variable=var, width=50, font=theme.font(13)).pack(side="left", padx=4)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(row, text="Score thresholds  A <", font=theme.font(13), width=170, anchor="w").pack(side="left")
        t = cats.thresholds()
        self.thr = []
        for i, label in enumerate(("B <", "C <", "D ≥")):
            e = ctk.CTkEntry(row, width=70, height=32, font=theme.font(13))
            e.insert(0, f"{t[i]:g}")
            e.pack(side="left", padx=(0, 4))
            self.thr.append(e)
            if i < 2:
                ctk.CTkLabel(row, text=label, font=theme.font(13)).pack(side="left", padx=(4, 4))
        self.exclude_e = ctk.BooleanVar(value=cats.exclude_defaulters_from_score())
        ctk.CTkCheckBox(row, text="Keep E out of the score maths", variable=self.exclude_e, font=theme.font(13)).pack(
            side="left", padx=16
        )

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="New customers start as", font=theme.font(13), width=170, anchor="w").pack(side="left")
        self.default_cat = ctk.CTkOptionMenu(row, values=["A", "B", "C", "D"], width=70, height=32, font=theme.font(13))
        self.default_cat.set(cats.default_customer_category())
        self.default_cat.pack(side="left")
        ctk.CTkLabel(row, text="   Item velocity (days since last sale)  A ≤", font=theme.font(13)).pack(side="left")
        v = cats.velocity_days()
        self.vel = []
        for i, label in enumerate(("B ≤", "C ≤", "else D")):
            e = ctk.CTkEntry(row, width=60, height=32, font=theme.font(13))
            e.insert(0, str(v[i]))
            e.pack(side="left", padx=(4, 2))
            self.vel.append(e)
            ctk.CTkLabel(row, text=label, font=theme.font(13)).pack(side="left", padx=(2, 2))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))
        if can_edit:
            primary_button(actions, "Save category settings", self.save_categories, width=190).pack(side="left")
            secondary_button(actions, "Re-score customers now", self.rescore, width=180).pack(side="left", padx=8)
            secondary_button(actions, "Auto-categorise items", self.auto_items, width=170).pack(side="left")
        else:
            ctk.CTkLabel(
                actions,
                text="Only an administrator can change these.",
                font=theme.font(12),
                text_color=theme.color("muted"),
            ).pack(side="left")
        self.cat_status = ctk.CTkLabel(
            body, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w", justify="left"
        )
        self.cat_status.pack(fill="x", pady=(8, 0))

    def save_categories(self) -> None:
        cats = self.ctx.categories
        try:
            cats.set_customer_report_categories([c for c, v in self.cust_cat_vars.items() if v.get()])
            cats.set_item_report_categories([c for c, v in self.item_cat_vars.items() if v.get()])
            cats.set_thresholds(*[float(e.get()) for e in self.thr])
            cats.set_exclude_defaulters_from_score(bool(self.exclude_e.get()))
            cats.set_default_customer_category(self.default_cat.get())
            cats.set_velocity_days(*[int(float(e.get())) for e in self.vel])
        except (ValidationError, ValueError) as exc:
            self.ctx.toast(str(exc), "error")
            return
        self.ctx.audit.log("09", "category settings saved", self.ctx.username)
        self.ctx.toast("Category settings saved", "success")
        self.cat_status.configure(text="Saved. Dashboard and reports use the ticked categories from now on.")

    def rescore(self) -> None:
        if not confirm(
            self, "Re-score", "Assign A-D to every customer by score?\nLocked and E customers are left as they are."
        ):
            return
        report = self.ctx.categories.rescore_customers(self.ctx.username)
        self.cat_status.configure(text="Customers re-scored: " + report.as_text())
        self.ctx.toast(f"{report.changed} customers changed category", "success")

    def auto_items(self) -> None:
        if not confirm(
            self,
            "Auto-categorise items",
            "Assign A-D to every item by days since its last sale?\nLocked and E items are left as they are.",
        ):
            return
        report = self.ctx.categories.auto_categorize_items(self.ctx.username)
        self.cat_status.configure(text="Items categorised: " + report.as_text())
        self.ctx.toast(f"{report.changed} items changed category", "success")

    def _set_mode(self, value: str) -> None:
        self.ctx.app.apply_theme(value.lower())

    def _set_language(self, value: str) -> None:
        lang = "hi" if value == "हिन्दी" else "en"
        if lang == self.ctx.prefs.language():
            return
        self.ctx.audit.log("09", f"language -> {lang}", self.ctx.username)
        # after the button callback returns: the rebuild destroys this screen
        self.ctx.app.after(20, lambda: self.ctx.app.apply_language(lang))

    def _set_layout(self, value: str) -> None:
        layout = "new" if value == "New" else "classic"
        if layout != self.ctx.prefs.layout():
            self.ctx.app.ask_layout(layout)
        # until the rebuild (or after "No"), the button shows the layout actually in use
        self.layout_choice.set("New" if self.ctx.prefs.layout() == "new" else "Classic")

    # Hindi names -----------------------------------------------------------------------
    def _build_hindi(self, scroll) -> None:
        card = Card(scroll, "Hindi names (हिन्दी नाम)")
        card.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        rows = self.ctx.hindi.rows()
        manual = sum(1 for r in rows if r.manual)
        self.hindi_status = ctk.CTkLabel(
            body,
            text=(
                f"Every customer and item keeps a Hindi copy of its name, made automatically from the English "
                f"spelling. {len(rows)} names · {manual} corrected by hand (never overwritten). English stays "
                "the original for ledgers, bills and search."
            ),
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.hindi_status.pack(fill="x")
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(8, 0))
        secondary_button(actions, "Review / correct names…", self.review_hindi, width=190).pack(side="left")
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            secondary_button(actions, "Fill missing", self.fill_hindi, width=120).pack(side="left", padx=8)
            secondary_button(actions, "Regenerate automatic ones", self.regenerate_hindi, width=200).pack(side="left")

    # Updates -----------------------------------------------------------------------------
    def _build_updates(self, scroll) -> None:
        card = Card(scroll, "Updates")
        card.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        self.update_status = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.update_status.pack(fill="x")
        self.update_notes = ctk.CTkLabel(body, text="", font=theme.font(12), anchor="w", justify="left", wraplength=900)
        self.update_notes.pack(fill="x", pady=(4, 0))
        self._update_found = None
        self._update_progress: tuple[int, int, str] | None = None
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            actions = ctk.CTkFrame(body, fg_color="transparent")
            actions.pack(fill="x", pady=(8, 0))
            secondary_button(actions, "Check for updates", self.check_updates, width=160).pack(side="left")
            self.update_install = primary_button(actions, "Install update", self.install_update, width=150)
            self.update_install.pack(side="left", padx=8)
            self.update_install.configure(state="disabled")
            self.update_restart = secondary_button(actions, "Restart now", self.restart_for_update, width=130)
            self.update_restart.pack(side="left")
            self.update_undo = secondary_button(actions, "Undo last update", self.undo_update, width=150)
            self.update_undo.pack(side="left", padx=8)
            where = ctk.CTkFrame(body, fg_color="transparent")
            where.pack(fill="x", pady=(10, 0))
            source = self.ctx.prefs.update_source()
            ctk.CTkLabel(where, text="Repository", font=theme.font(12)).pack(side="left", padx=(0, 6))
            self.update_repo = ctk.CTkEntry(where, width=220, font=theme.font(12))
            self.update_repo.insert(0, source.repo)
            self.update_repo.pack(side="left")
            ctk.CTkLabel(where, text="Branch", font=theme.font(12)).pack(side="left", padx=(12, 6))
            self.update_branch = ctk.CTkEntry(where, width=110, font=theme.font(12))
            self.update_branch.insert(0, source.branch)
            self.update_branch.pack(side="left")
            secondary_button(where, "Save", self.save_update_source, width=80).pack(side="left", padx=8)
        self._show_update_status()

    def _updater(self):
        from hth.services.updates import Updater

        return Updater(self.ctx.settings.data_dir, self.ctx.prefs.update_source())

    def _say_update(self, en: str, hi: str) -> None:
        from hth import i18n

        self.update_status.configure(text=i18n.Raw(hi if i18n.is_hindi() else en))

    def _show_update_status(self) -> None:
        from hth import i18n
        from hth.services import updates

        up = self._updater()
        source = up.source
        hi = i18n.is_hindi()
        text = (
            f"यह कॉपी: संस्करण {__version__} · अपडेट यहाँ से: {source.web}"
            if hi
            else f"This copy: version {__version__} · updates from {source.web}"
        )
        if up.mode == "git":
            text += " · डेवलपर कॉपी (git): अपडेट git pull से" if hi else " · a developer copy (git): updates with git pull"
        elif up.mode == "frozen":
            text += (
                " · पैक की हुई कॉपी: नया संस्करण हाथ से लगाएँ" if hi else " · a packaged copy: install new versions by hand"
            )
        staged = updates.pending(self.ctx.settings.data_dir)
        if staged:
            what = "पिछला संस्करण" if staged.get("kind") == "undo" else staged.get("to")
            text += f"\n{what} तैयार है - पूरा करने के लिए फिर से शुरू करें।" if hi else f"\n{what} is ready - restart to finish."
        last = updates.last_result(self.ctx.settings.data_dir)
        if last:
            if last.get("ok"):
                text += (
                    f"\nपिछला अपडेट: {last.get('from')} → {last.get('to')} ({last.get('when', '')[:16]})"
                    if hi
                    else f"\nLast update: {last.get('from')} → {last.get('to')} ({last.get('when', '')[:16]})"
                )
            else:
                text += (
                    f"\nपिछला अपडेट नहीं लग पाया, पुराना संस्करण वैसा ही रहा: {last.get('error', '')}"
                    if hi
                    else f"\nThe last update could not be put in; the old version was kept: {last.get('error', '')}"
                )
        self.update_status.configure(text=i18n.Raw(text))
        if hasattr(self, "update_restart"):
            self.update_restart.configure(state="normal" if staged or getattr(self, "_pulled", False) else "disabled")
            self.update_undo.configure(
                state="normal" if updates.backups(self.ctx.settings.data_dir) and not staged else "disabled"
            )

    def check_updates(self) -> None:
        up = self._updater()
        self._say_update("Looking on GitHub…", "GitHub पर देख रहा है…")
        self.update_notes.configure(text="")
        self.update_install.configure(state="disabled")

        def done(found) -> None:
            from hth import i18n

            self._update_found = found
            if not found.newer:
                self._say_update(
                    f"Up to date: version {found.current} (GitHub has {found.version}).",
                    f"नया कुछ नहीं: संस्करण {found.current} (GitHub पर {found.version})।",
                )
                return
            if found.mode == "git":
                self._say_update(
                    f"Version {found.version} is available ({found.behind} new commits) - Install runs git pull.",
                    f"संस्करण {found.version} आया है ({found.behind} नए commit) - 'अपडेट लगाएँ' git pull चलाएगा।",
                )
            else:
                self._say_update(
                    f"Version {found.version} is available: {len(found.changed)} files, {found.download_mb:.1f} MB"
                    + (" (with new Python packages)" if found.requirements_changed else "")
                    + ".",
                    f"संस्करण {found.version} आया है: {len(found.changed)} फ़ाइलें, {found.download_mb:.1f} MB"
                    + (" (नए Python पैकेज के साथ)" if found.requirements_changed else "")
                    + "।",
                )
            notes = "\n".join(found.notes.splitlines()[:18])
            self.update_notes.configure(text=i18n.Raw(notes))
            self.update_install.configure(state="normal")

        self.run_async(up.check, done, lambda exc: self._say_update(str(exc), str(exc)))

    def install_update(self) -> None:
        found = self._update_found
        if found is None or not found.newer:
            return
        if not confirm(
            self,
            "Install update",
            f"Download version {found.version} now?\n\nThe app changes only when it restarts; a copy of every "
            "file it replaces is kept, so the update can be undone. Your data is not touched.",
        ):
            return
        up = self._updater()
        self.update_install.configure(state="disabled")
        if found.mode == "git":
            self._say_update("Running git pull…", "git pull चल रहा है…")

            def pulled(_out) -> None:
                self._pulled = True
                self._say_update("Updated with git pull - restart to use it.", "git pull हो गया - फिर से शुरू करें।")
                self.update_restart.configure(state="normal")

            self.run_async(up.pull, pulled, lambda exc: self._say_update(str(exc), str(exc)))
            return

        def progress(k: int, n: int, rel: str) -> None:
            self._update_progress = (k, n, rel)  # read by _poll_update_progress on the Tk thread

        def done(_staging) -> None:
            self._update_progress = None
            self.ctx.audit.log(
                AuditCode.UPDATE, f"update {found.current} -> {found.version} downloaded", self.ctx.username
            )
            self._show_update_status()
            self.ctx.toast(f"Version {found.version} is ready - restart to finish", "success")

        def failed(exc: Exception) -> None:
            self._update_progress = None
            self._say_update(str(exc), str(exc))

        self._update_progress = (0, len(found.changed), "")
        self.after(200, self._poll_update_progress)
        self.run_async(lambda: up.stage(found, progress), done, failed)

    def _poll_update_progress(self) -> None:
        if not self._alive or self._update_progress is None:
            return
        k, n, rel = self._update_progress
        self._say_update(f"Downloading {k}/{n}: {rel}", f"डाउनलोड {k}/{n}: {rel}")
        self.after(200, self._poll_update_progress)

    def restart_for_update(self) -> None:
        from hth.services import updates

        if not confirm(self, "Restart now", "Close and start the app again now?"):
            return
        updates.relaunch(wait_for_me=True)
        self.ctx.app.destroy()

    def undo_update(self) -> None:
        from hth.services import updates

        found = updates.backups(self.ctx.settings.data_dir)
        if not found or not confirm(
            self,
            "Undo last update",
            "Put back the files from before the last update?\nThe app changes when it restarts.",
        ):
            return
        updates.stage_undo(self.ctx.settings.data_dir, found[0])
        self.ctx.audit.log(AuditCode.UPDATE, f"update undo staged from {found[0].name}", self.ctx.username)
        self._show_update_status()

    def save_update_source(self) -> None:
        try:
            self.ctx.prefs.set_update_source(self.update_repo.get(), self.update_branch.get())
        except ValueError as exc:
            self.ctx.toast(str(exc), "error")
            return
        self._show_update_status()
        self.ctx.toast("Saved", "success")

    # Assistant ---------------------------------------------------------------------------
    def _build_assistant(self, scroll) -> None:
        card = Card(scroll, "Assistant (सहायक)")
        card.pack(fill="x", padx=4, pady=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(4, 16))
        self.assistant_status = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.assistant_status.pack(fill="x")
        if self.ctx.can(Permission.MANAGE_SETTINGS):
            actions = ctk.CTkFrame(body, fg_color="transparent")
            actions.pack(fill="x", pady=(8, 0))
            secondary_button(actions, "Install model…", self.install_model, width=150).pack(side="left")
            secondary_button(actions, "Remove model", self.remove_model, width=130).pack(side="left", padx=8)
            secondary_button(actions, "Install voice model…", self.install_voice, width=180).pack(
                side="left", padx=(16, 0)
            )
            speak = ctk.CTkFrame(body, fg_color="transparent")
            speak.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(speak, text="Speak answers", font=theme.font(12), anchor="w").pack(side="left", padx=(0, 10))
            self.speak_mode = ctk.CTkSegmentedButton(
                speak, values=list(_SPEAK.values()), command=self._set_speak_mode, font=theme.font(12)
            )
            self.speak_mode.set(_SPEAK[self.ctx.prefs.assistant_speak()])
            self.speak_mode.pack(side="left")
            self._build_mic_row(body)
        self._show_assistant_status()

    def _build_mic_row(self, body) -> None:
        from hth.assistant import voice

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text="Microphone", font=theme.font(12), anchor="w").pack(side="left", padx=(0, 10))
        saved = self.ctx.prefs.assistant_mic()
        self.mic_menu = ctk.CTkOptionMenu(
            row,
            values=["Automatic", *([saved] if saved else [])],
            command=self._set_mic,
            font=theme.font(12),
            width=280,
        )
        self.mic_menu.set(saved or "Automatic")
        self.mic_menu.pack(side="left")
        secondary_button(row, "Test microphone", self.test_mic, width=150).pack(side="left", padx=8)
        self.mic_result = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.mic_result.pack(fill="x", pady=(4, 0))

        # asking Windows for its microphones starts the sound system (a second on the shop
        # PC): done in the background, so Settings opens without waiting for it
        def find():
            devices = voice.input_devices()
            return devices, voice.choose_device(saved, devices)

        self.run_async(find, self._mics_found, lambda _exc: None)

    def _mics_found(self, found) -> None:
        devices, chosen = found
        names = [d.name for d in devices if not d.loopback] + [d.name for d in devices if d.loopback]
        saved = self.ctx.prefs.assistant_mic()
        self.mic_menu.configure(values=["Automatic", *names])
        self.mic_menu.set(saved if saved in names else "Automatic")
        if chosen is not None:
            self._mic_note(f"Listening with: {chosen.name}", f"इससे सुनता है: {chosen.name}")

    def _mic_note(self, en: str, hi: str) -> None:
        from hth import i18n

        self.mic_result.configure(text=i18n.Raw(hi if i18n.is_hindi() else en))

    def _set_mic(self, value: str) -> None:
        from hth.assistant import voice

        self.ctx.prefs.set_assistant_mic("" if value == "Automatic" else value)
        chosen = voice.choose_device(self.ctx.prefs.assistant_mic())
        if chosen is not None:
            self._mic_note(f"Listening with: {chosen.name}", f"इससे सुनता है: {chosen.name}")

    def test_mic(self) -> None:
        """Record three seconds from the chosen microphone; show how loud it was and what was heard."""
        from hth.assistant import voice

        chosen = voice.choose_device(self.ctx.prefs.assistant_mic())
        if chosen is None:
            self._mic_note("No microphone found on this PC.", "इस कंप्यूटर में कोई माइक नहीं मिला।")
            return
        self._mic_note(
            f"Speak now for 3 seconds (e.g. “Ramesh ka balance batao”) - {chosen.name}",
            f"अब 3 सेकंड बोलिए (जैसे “रमेश का बैलेंस बताओ”) - {chosen.name}",
        )

        def work():
            level, pcm, rate = voice.record_test(chosen.index)
            model = voice.VoiceModel(voice.voice_dir(self.ctx.settings.data_dir))
            heard = model.transcribe(pcm, None, rate).text if model.available() else None
            return level, heard

        def done(result) -> None:
            level, heard = result
            bars = "▮" * int(level * 10 + 0.5) + "▯" * (10 - int(level * 10 + 0.5))
            if level < 0.01:
                self._mic_note(
                    f"{bars}  No sound from “{chosen.name}”. Choose another microphone above, or check that it is "
                    "not muted (Windows: Settings → System → Sound → Input).",
                    f"{bars}  “{chosen.name}” से कोई आवाज़ नहीं आई। ऊपर दूसरा माइक चुनें, या देखें कि माइक बंद तो नहीं "
                    "(Windows: Settings → System → Sound → Input)।",
                )
            elif heard is None:
                self._mic_note(f"{bars}  The microphone works.", f"{bars}  माइक ठीक काम कर रहा है।")
            else:
                self._mic_note(
                    f"{bars}  The microphone works. Heard: “{heard or '…'}”",
                    f"{bars}  माइक ठीक काम कर रहा है। सुना: “{heard or '…'}”",
                )

        self.run_async(work, done, lambda exc: self._mic_note(f"Microphone: {exc}", f"माइक: {exc}"))

    def _show_assistant_status(self) -> None:
        from hth import i18n
        from hth.assistant.system2 import backend_available, find_model, models_dir

        hi = i18n.is_hindi()
        info_ = find_model(models_dir(self.ctx.settings.data_dir))
        if info_ is None:
            model = (
                "भाषा मॉडल: नहीं लगा (ज़रूरी नहीं - बिना इसके भी सहायक चलता है; Kaggle सेल से बनाकर यहाँ लगाएँ)।"
                if hi
                else "Language model: not installed (optional - the assistant works without it; train one with "
                "tools/assistant/kaggle_train_cell.py on Kaggle and install the zip here)."
            )
        else:
            m = info_.manifest
            acc = m.get("eval", {}).get("intent_accuracy")
            details = f"{info_.path.name}, {info_.size_mb:.0f} MB, {m.get('base_model', '?')}"
            if acc is not None:
                details += f", {acc:.0%}"
            model = f"भाषा मॉडल: लगा है ({details})।" if hi else f"Language model: installed ({details})."
            if not backend_available():
                model += (
                    " इसे चलाने के लिए llama-cpp-python पैकेज चाहिए।"
                    if hi
                    else " It needs the llama-cpp-python package to run (pip install llama-cpp-python)."
                )
        intro = (
            "सहायक हिंदी, हिंग्लिश या अंग्रेज़ी में पूछे सवालों के जवाब देता है - केवल देखता है, कुछ बदलता नहीं। "
            "समझने वाला हिस्सा इसी में बना है और हमेशा चालू है।"
            if hi
            else "The assistant answers questions in Hindi, Hinglish or English - it only looks things up, it never "
            "changes anything. Its built-in understanding is always on."
        )
        self.assistant_status.configure(text=i18n.Raw(intro + "\n" + model + "\n" + self._voice_status(hi)))

    def _voice_status(self, hi: bool) -> str:
        from hth.assistant import speech, voice

        folder = voice.find_model_dir(voice.voice_dir(self.ctx.settings.data_dir))
        if folder is None and voice.bundled_zip() is not None:
            text = (
                "आवाज़ से पूछना: मॉडल ऐप के साथ आता है - सहायक पहली बार खुलने पर अपने-आप लग जाएगा।"
                if hi
                else "Asking by voice: the model comes with the app and is set up the first time the Assistant opens."
            )
        elif folder is None:
            text = (
                "आवाज़ से पूछना: मॉडल नहीं लगा - alphacephei.com/vosk/models से vosk-model-small-hi-0.22.zip "
                "(42 MB) लेकर 'आवाज़ मॉडल लगाएँ' से लगाएँ।"
                if hi
                else "Asking by voice: no voice model - download vosk-model-small-hi-0.22.zip (42 MB) from "
                "alphacephei.com/vosk/models and install it with Install voice model…."
            )
        else:
            size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e6
            text = (
                f"आवाज़ से पूछना: {folder.name}, {size:.0f} MB।"
                if hi
                else f"Asking by voice: {folder.name}, {size:.0f} MB."
            )
            if not voice.backend_available():
                text += " इसके लिए vosk और sounddevice पैकेज चाहिए।" if hi else " It needs pip install vosk sounddevice."
        names = speech.voice_names()
        if "hi" in names:
            text += f" जवाब बोलने वाली आवाज़: {names['hi']}।" if hi else f" Spoken answers: {names['hi']}."
        else:
            text += (
                " Windows की हिंदी आवाज़ नहीं मिली (Settings → Time & language → Speech → Add voices → Hindi)।"
                if hi
                else " No Windows Hindi voice for spoken answers (Settings → Time & language → Speech → Add voices"
                " → Hindi)."
            )
        return text

    def _set_speak_mode(self, label: str) -> None:
        mode = next(k for k, v in _SPEAK.items() if v == label)
        self.ctx.prefs.set_assistant_speak(mode)

    def install_voice(self) -> None:
        from hth.assistant import voice

        path = filedialog.askopenfilename(
            title="Choose the voice model (vosk-model-small-hi-0.22.zip)",
            filetypes=[("Voice model", "*.zip"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        view = self.ctx.app.find_view("assistant")
        if getattr(view, "voice", None) is not None:
            view.voice.unload()
        self.ctx.toast("Installing the voice model…")

        def done(folder) -> None:
            self.ctx.audit.log(AuditCode.ASSISTANT, f"voice model installed {folder.name}", self.ctx.username)
            if view is not None and getattr(view, "_ready", False):
                view.voice = voice.VoiceModel(voice.voice_dir(self.ctx.settings.data_dir))
                view.run_async(view._prepare_voice, view._voice_prepared, lambda exc: None)
            self._show_assistant_status()
            self.ctx.toast(f"Voice model installed: {folder.name}", "success")

        self.run_async(lambda: voice.install_zip(Path(path), self.ctx.settings.data_dir), done, self._model_failed)

    def _assistant_model(self):
        view = self.ctx.app.find_view("assistant")
        return getattr(view, "system2", None)

    def install_model(self) -> None:
        from hth.assistant.system2 import install_zip

        path = filedialog.askopenfilename(
            title="Choose the assistant model (hth_assistant_model.zip)",
            filetypes=[("Assistant model", "*.zip"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        model = self._assistant_model()
        if model is not None:
            model.unload()  # Windows keeps an open model file locked
        self.ctx.toast("Installing the model…")

        def done(info_) -> None:
            if model is not None:
                model.error = None
            self.ctx.audit.log(AuditCode.ASSISTANT, f"assistant model installed {info_.path.name}", self.ctx.username)
            self._show_assistant_status()
            self.ctx.toast(f"Model installed: {info_.path.name}", "success")

        self.run_async(lambda: install_zip(Path(path), self.ctx.settings.data_dir), done, self._model_failed)

    def _model_failed(self, exc: Exception) -> None:
        self.ctx.toast(f"Could not install the model: {exc}", "error")

    def remove_model(self) -> None:
        import shutil

        from hth.assistant.system2 import models_dir

        folder = models_dir(self.ctx.settings.data_dir)
        if not folder.exists() or not confirm(self, "Remove model", "Remove the assistant's language model?"):
            return
        model = self._assistant_model()
        if model is not None:
            model.unload()
        try:
            shutil.rmtree(folder)
        except OSError as exc:
            self.ctx.toast(f"Could not remove the model: {exc}", "error")
            return
        self.ctx.audit.log(AuditCode.ASSISTANT, "assistant model removed", self.ctx.username)
        self._show_assistant_status()
        self.ctx.toast("Model removed", "success")

    def review_hindi(self) -> None:
        from hth.ui.widgets.hindi_review import HindiReview

        HindiReview(self, self.ctx)

    def fill_hindi(self) -> None:
        c, i = self.ctx.hindi.fill_missing(self.ctx.username)
        self.ctx.app.refresh_names()
        self.ctx.toast(f"Hindi names added: {c} customers, {i} items", "success")

    def regenerate_hindi(self) -> None:
        if not confirm(
            self,
            "Regenerate Hindi names",
            "Make every automatic Hindi name again from its English spelling?\nNames corrected by hand are kept.",
        ):
            return
        c, i = self.ctx.hindi.fill_missing(self.ctx.username, regenerate=True)
        self.ctx.app.refresh_names()
        self.ctx.toast(f"Hindi names regenerated: {c} customers, {i} items", "success")

    def _set_text_size(self, value: str) -> None:
        self.ctx.app.apply_text_scale(int(value.rstrip("%")) / 100)
        self.ctx.toast(f"Text size {value} - table columns follow the next time you sign in", "success")

    def _set_number_style(self, value: str) -> None:
        style = "indian" if value.startswith("Indian") else "international"
        self.ctx.prefs.set_number_style(style)
        self.ctx.audit.log("09", f"number style -> {style}", self.ctx.username)
        self.ctx.toast("Number style saved - screens show it as they reload", "success")

    def _set_lock(self, value: str) -> None:
        minutes = 0 if value == "Never" else int(value.split()[0])
        self.ctx.prefs.set_lock_minutes(minutes)
        self.ctx.audit.log("09", f"auto-lock -> {value}", self.ctx.username)
        self.ctx.toast(f"Auto-lock: {value}", "success")

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

    def save_backup_prefs(self) -> None:
        try:
            self.ctx.backup.set_enabled(bool(self.auto_backup.get()))
            self.ctx.backup.set_keep(int(self.keep_entry.get() or 14))
        except ValueError as exc:
            self.ctx.toast(str(exc), "error")

    def rerun_setup(self) -> None:
        if confirm(self, "Setup wizard", "Sign out and run the first-run setup again?"):
            from hth.ui.views.setup import mark_setup

            mark_setup(self.ctx.db, False)
            self.ctx.app.logout()

    def backup(self) -> None:
        dest = self.ctx.backup.manual()
        self.ctx.toast(f"Backup saved: {dest.name}", "success")
        self.ctx.audit.log("09", f"backup {dest.name}", self.ctx.username)
        self.ctx.app.refresh_backup_label()

    def restore(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a backup to restore",
            initialdir=str(self.ctx.settings.backup_dir),
            filetypes=[("Database backups", "*.db"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            backup = self.ctx.backup.inspect(Path(path))
        except ValueError as exc:
            self.ctx.toast(str(exc), "error")
            return
        when = backup.last_activity[:16] or "unknown"
        if not confirm(
            self,
            "Restore backup",
            f"Replace ALL current data with\n{backup.path.name}?\n\n"
            f"It holds {backup.customers:,} accounts and {backup.entries:,} ledger entries; "
            f"last activity {when}.\n\nEverything entered after that is replaced. The current data is saved "
            "first as a 'before_restore' backup, so this can be undone by restoring that file.\n\n"
            "Everyone is signed out afterwards.",
        ):
            return
        try:
            safety = self.ctx.backup.restore(backup.path, self.ctx.username)
        except Exception as exc:  # noqa: BLE001 - report, never leave the user guessing
            self.ctx.toast(f"Restore failed: {exc}", "error")
            return
        info(self, "Restore complete", f"Restored {backup.path.name}.\nPrevious data saved as {safety.name}.")
        self.ctx.app.show_login()

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
        out = report.write(self.ctx.settings.data_dir / "migration_report.txt")
        lines = report.as_lines()
        summary = "\n".join(lines[:8])
        if report.warnings:
            summary += (
                f"\n\n{len(report.warnings)} value(s) were skipped or normalised. The full list is in\n{out}\n\n"
                "Cross-check them with Reports -> Audit log and fix them from the ledger screens, "
                "then run Reports -> Data check."
            )
        info(self, "Import complete", summary)
        self.ctx.audit.log("09", "imported v3 data", self.ctx.username)
