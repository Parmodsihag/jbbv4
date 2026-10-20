"""User management (admin only)."""

from __future__ import annotations

import customtkinter as ctk

from hth.services.permissions import ROLES, Permission
from hth.ui import theme
from hth.ui.views.base import BaseView
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.dialogs import Field, confirm, run_form
from hth.ui.widgets.forms import Card, primary_button, secondary_button


class UsersView(BaseView):
    key = "users"
    title = "Users"
    permission = Permission.MANAGE_USERS

    def build(self) -> None:
        card = Card(self)
        card.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bar, text="Users & access", font=theme.font(17, "bold")).pack(side="left")
        primary_button(bar, "Add user", self.add_user, width=110).pack(side="right")
        secondary_button(bar, "Reset password", self.reset_password, width=130).pack(side="right", padx=6)
        secondary_button(bar, "Change role", self.change_role, width=110).pack(side="right", padx=6)
        secondary_button(bar, "Activate / deactivate", self.toggle_active, width=160).pack(side="right", padx=6)
        self.table = DataTable(
            card,
            [
                Column("id", "ID", 60, "e", "int"),
                Column("username", "Username", 160),
                Column("name", "Full name", 220, stretch=True),
                Column("role", "Role", 140),
                Column("active", "Active", 80, "center"),
            ],
            row_tags=lambda r: ["muted"] if r[4] == "no" else [],
        )
        self.table.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        ctk.CTkLabel(
            card,
            text=(
                "Administrator: everything.   Employee: dashboard, sales, add accounts/items, krar, reports & export - "
                "no editing or deleting of records, no user management, no audit log."
            ),
            font=theme.font(11),
            text_color=theme.color("muted"),
            wraplength=900,
            justify="left",
        ).pack(padx=12, pady=(0, 10), anchor="w")

    def on_show(self, **kwargs) -> None:
        self.reload()

    def on_theme_change(self) -> None:
        self.table.restyle()

    def reload(self) -> None:
        rows = [
            (
                u.id,
                u.username,
                u.full_name,
                ROLES.get(u.role, u.role),
                "yes" if u.is_active else "no",
            )
            for u in self.ctx.auth.list_users()
        ]
        self.table.set_rows(rows, f"{len(rows)} users")

    def _selected(self):
        row = self.table.selected_row()
        if row is None:
            self.ctx.toast("Select a user first", "warning")
            return None
        return self.ctx.auth.get_user(row[0])

    def add_user(self) -> None:
        fields = [
            Field("username", "Username"),
            Field("full_name", "Full name"),
            Field("password", "Password", "password"),
            Field("role", "Role", "option", "employee", list(ROLES)),
        ]
        if run_form(
            self,
            "Add user",
            fields,
            lambda v: self.ctx.auth.create_user(
                v["username"], v["password"], v["full_name"], v["role"], actor=self.ctx.username
            ),
            "Create",
        ):
            self.ctx.toast("User created", "success")
            self.reload()

    def reset_password(self) -> None:
        u = self._selected()
        if u and run_form(
            self,
            f"Reset password for {u.username}",
            [Field("password", "New password", "password")],
            lambda v: self.ctx.auth.set_password(u.id, v["password"], actor=self.ctx.username),
        ):
            self.ctx.toast("Password updated", "success")

    def change_role(self) -> None:
        u = self._selected()
        if u and run_form(
            self,
            f"Change role of {u.username}",
            [Field("role", "Role", "option", u.role, list(ROLES))],
            lambda v: self.ctx.auth.set_role(u.id, v["role"], actor=self.ctx.username),
        ):
            self.ctx.toast("Role updated", "success")
            self.reload()

    def toggle_active(self) -> None:
        u = self._selected()
        if u is None:
            return
        if u.id == self.ctx.user.id:
            self.ctx.toast("You cannot deactivate yourself", "error")
            return
        verb = "Deactivate" if u.is_active else "Activate"
        if confirm(self, verb, f"{verb} user {u.username}?"):
            try:
                self.ctx.auth.set_active(u.id, not u.is_active, actor=self.ctx.username)
            except Exception as exc:  # noqa: BLE001
                self.ctx.toast(str(exc), "error")
                return
            self.reload()
