"""Today - the admin's home in the new layout: what needs doing now, each with its button.

Promises due (late and today), stock running out, and housekeeping (backup, expenses to
post, data problems, default passwords) on the left; today's figures, who owes us by age
and the latest entries at the counter on the right.  The data is the classic dashboard's
(InsightsService, the reports service); only the way it is shown changes.
"""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth import i18n
from hth.services.insights import InsightsService
from hth.services.permissions import Permission
from hth.services.sales import money_flow_handler
from hth.ui import theme
from hth.ui.format import compact_money
from hth.ui.modern import actions
from hth.ui.modern.widgets import card, pill, rupees
from hth.ui.views.base import BaseView

PROMISE_ROWS = 4
STOCK_ROWS = 3
# insights the left-hand cards already show in full
_SHOWN_ELSEWHERE = ("promised payment(s) overdue", "promise(s) due today", "may run out within a month", "All clear")


def _initials(name: str) -> str:
    return "".join(p[0] for p in name.split()[:2]).upper() or "?"


class _Button(ctk.CTkButton):
    def __init__(self, master, text, command, primary=False, **kw):
        if primary:
            colors = {
                "fg_color": theme.color("accent"),
                "hover_color": theme.color("accent_hover"),
                "text_color": theme.color("accent_text"),
            }
        else:
            colors = {
                "fg_color": theme.color("surface"),
                "border_width": 1,
                "border_color": theme.color("line"),
                "hover_color": theme.color("surface_hover"),
                "text_color": theme.color("text"),
            }
        kw.setdefault("height", 30)
        super().__init__(
            master, text=text, command=command, width=10, corner_radius=8, font=theme.font(12, "bold"), **colors, **kw
        )


def _link(master, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=10,
        height=24,
        fg_color="transparent",
        hover_color=theme.color("surface_hover"),
        text_color=theme.color("accent"),
        font=theme.font(12, "bold"),
    )


class _Card:
    """A titled card with a count and a link, and a body the rows go into."""

    def __init__(self, master, title: str, link: str | None = None, command=None):
        self.frame = card(master)
        head = ctk.CTkFrame(self.frame, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(head, text=title, font=theme.font(15, "bold")).pack(side="left")
        self.count = pill(head, "", "soon")
        self.count.pack(side="left", padx=8)
        self.note = ctk.CTkLabel(head, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.note.pack(side="left")
        if link:
            _link(head, link, command).pack(side="right")
        self.body = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    def clear(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()

    def set_count(self, n: int | None) -> None:
        if n is None:
            self.count.pack_forget()
        else:
            self.count.configure(text=f"  {n}  ")
            if not self.count.winfo_manager():
                self.count.pack(side="left", padx=8, before=self.note)

    def row(self) -> ctk.CTkFrame:
        ctk.CTkFrame(self.body, height=1, fg_color=theme.color("line")).pack(fill="x")
        r = ctk.CTkFrame(self.body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        return r

    def empty(self, text: str) -> None:
        ctk.CTkLabel(self.body, text=text, font=theme.font(12), text_color=theme.color("muted"), anchor="w").pack(
            fill="x", pady=8
        )


class TodayView(BaseView):
    key = "today"
    title = "Today"
    permission = Permission.VIEW_DASHBOARD

    def build(self) -> None:
        self._data: dict | None = None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        self.sub = ctk.CTkLabel(titles, text="", font=theme.font(12), text_color=theme.color("muted"), anchor="w")
        self.sub.pack(fill="x")
        self.headline = ctk.CTkLabel(titles, text="", font=theme.font(24, "bold"), anchor="w")
        self.headline.pack(fill="x")
        nav = self.ctx.navigate
        if self.ctx.can(Permission.RECORD_SALE):
            _Button(head, "Counter   Alt+S", lambda: nav("counter"), primary=True, height=36).pack(side="right")
            _Button(head, "Payment in", lambda: nav("counter", intent="in"), height=36).pack(side="right", padx=8)
        if self.ctx.can(Permission.ADD_CUSTOMER):
            _Button(head, "+ New customer", self.new_customer, height=36).pack(side="right")
        _Button(head, "↻", self.reload, height=36).pack(side="right", padx=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=360)
        body.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.promises = _Card(left, "Promises due", "All in Collections", lambda: nav("karar"))
        self.promises.frame.pack(fill="x")
        pair = ctk.CTkFrame(left, fg_color="transparent")
        pair.pack(fill="both", expand=True, pady=(14, 0))
        pair.grid_columnconfigure((0, 1), weight=1, uniform="p")
        pair.grid_rowconfigure(0, weight=1)
        self.stock = _Card(pair, "Stock running out", "Reorder list", lambda: nav("reports", report="reorder"))
        self.stock.frame.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.house = _Card(pair, "Housekeeping")
        self.house.frame.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.today_card = _Card(right, "Today so far", "Day book", lambda: nav("reports", report="daybook"))
        self.today_card.frame.pack(fill="x")
        self.owed_card = _Card(right, "Owed to us", "Aging", lambda: nav("reports", report="aging"))
        self.owed_card.frame.pack(fill="x", pady=12)
        self.latest = _Card(right, "Latest entries")
        self.latest.frame.pack(fill="both", expand=True)

    # Loading ---------------------------------------------------------------------------
    def on_show(self, **kwargs) -> None:
        self.reload()

    def on_day_change(self) -> None:
        super().on_day_change()
        self.reload()

    def reload(self) -> None:
        self.headline.configure(text=self.headline.cget("text") or "Loading…")
        ctx = self.ctx

        def work() -> dict:
            rep = ctx.reports
            today = dt.date.today()
            today_s = today.isoformat()
            summaries = rep.categories.customer_summaries()
            insights = InsightsService(ctx.db, ctx.settings)
            due = ctx.krar.entries("today") + ctx.krar.entries("past")
            balances = ctx.accounts.balances(customer_ids=[e.customer_id for e in due])
            promises = []
            for e in due:
                days = (dt.date.fromisoformat(e.last_date) - today).days
                promises.append((e, days, balances.get(e.customer_id, 0.0)))
            # due today first, then the late ones with the most at stake
            promises.sort(key=lambda p: (p[1] < 0, -p[2]))
            flow = money_flow_handler(ctx.db)
            money, recurring = None, []
            if flow is not None:
                try:
                    money = flow.balances()
                    recurring = flow.due_recurring() if hasattr(flow, "due_recurring") else []
                except Exception:  # noqa: BLE001 - finance tables missing on a partial install
                    money = None
            return {
                "promises": promises,
                "insights": insights.collect(summaries),
                "reorder": insights.reorder_suggestions(),
                "day": rep.day_totals(),
                "kpis": rep.kpis(summaries),
                "aging": rep.aging(summaries),
                "latest": rep.day_book(today_s)[-4:][::-1],
                "money": money,
                "recurring": recurring,
                "backup": ctx.backup.last_backup(),
            }

        self.run_async(work, self._render)

    def _render(self, data: dict) -> None:
        self._data = data
        n = self._render_promises(data) + self._render_stock(data) + self._render_house(data)
        self.headline.configure(text=f"{n} things need you today" if n else "All clear today")
        last = data["backup"]
        when = "no backup yet"
        if last is not None:
            age = (dt.datetime.now() - dt.datetime.fromtimestamp(last.stat().st_mtime)).days
            when = "backed up today" if age == 0 else f"last backup {age} days ago"
        self.sub.configure(text=f"{i18n.date_text(dt.date.today(), '%A, %d %B')} · {when}")
        self._render_today(data)
        self._render_owed(data)
        self._render_latest(data)

    def _render_promises(self, data: dict) -> int:
        c = self.promises
        c.clear()
        rows = data["promises"]
        c.set_count(len(rows))
        c.note.configure(text=f"{rupees(sum(max(b, 0) for _e, _d, b in rows))} at stake" if rows else "")
        if not rows:
            c.empty("No promise is due today or late.")
            return 0
        for e, days, balance in rows[:PROMISE_ROWS]:
            r = c.row()
            ctk.CTkLabel(
                r,
                text=_initials(e.customer_name),
                width=34,
                height=34,
                corner_radius=17,
                fg_color=theme.color("surface2"),
                font=theme.font(11, "bold"),
            ).pack(side="left")
            who = ctk.CTkFrame(r, fg_color="transparent")
            who.pack(side="left", fill="x", expand=True, padx=10)
            ctk.CTkLabel(
                who, text=i18n.tr_cell(e.customer_name), font=theme.font(13, "bold"), anchor="w", height=18
            ).pack(fill="x")
            details = e.other_details if e.other_details and e.other_details != "NA" else ""
            times = len(e.dates)
            sub = " · ".join(x for x in (i18n.tr_cell(details)[:30], f"promise {times}" if times > 1 else "") if x)
            ctk.CTkLabel(
                who, text=sub, font=theme.font(11), text_color=theme.color("muted"), anchor="w", height=16
            ).pack(fill="x")
            pill(r, "Due today" if days == 0 else f"{-days} days late", "due" if days == 0 else "late").pack(
                side="left", padx=6
            )
            ctk.CTkLabel(
                r,
                text=rupees(balance),
                font=theme.font(13, "bold"),
                text_color=theme.color("owe"),
                width=110,
                anchor="e",
            ).pack(side="left", padx=(0, 10))
            cid = e.customer_id
            _Button(r, "WhatsApp", lambda cid=cid, d=e.last_date: self.whatsapp(cid, d)).pack(side="left")
            if self.ctx.can(Permission.RECORD_SALE):
                _Button(
                    r, "Got payment", lambda cid=cid: self.ctx.navigate("counter", customer_id=cid, intent="in")
                ).pack(side="left", padx=4)
            _Button(r, "New date", lambda cid=cid: self.new_date(cid)).pack(side="left")
        more = rows[PROMISE_ROWS:]
        if more:
            names = ", ".join(i18n.tr_cell(e.customer_name).title() for e, _d, _b in more[:4])
            ctk.CTkFrame(c.body, height=1, fg_color=theme.color("line")).pack(fill="x")
            _link(
                c.body,
                f"{len(more)} more - {names}" + (" …" if len(more) > 4 else ""),
                lambda: self.ctx.navigate("karar"),
            ).pack(anchor="w", pady=(6, 0))
        return len(rows)

    def _render_stock(self, data: dict) -> int:
        c = self.stock
        c.clear()
        lines = data["reorder"]
        expiring = [i for i in data["insights"] if "expiring" in i.title]
        c.set_count(len(lines) + len(expiring))
        if not lines and not expiring:
            c.empty("Nothing is about to run out.")
            return 0
        for line in lines[:STOCK_ROWS]:
            r = c.row()
            text = ctk.CTkFrame(r, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text, text=i18n.tr_cell(line.name), font=theme.font(13, "bold"), anchor="w", height=18).pack(
                fill="x"
            )
            left = f"{line.in_stock:g} {line.unit} left" if line.in_stock > 0 else "none left"
            ctk.CTkLabel(
                text,
                text=f"{left} · {line.sold_window:g} sold in 30 days",
                font=theme.font(11),
                text_color=theme.color("muted"),
                anchor="w",
                height=16,
            ).pack(fill="x")
            days = line.days_left or 0
            pill(
                r,
                "Out" if line.in_stock <= 0 else f"{days:g} days",
                "late" if line.in_stock <= 0 or days < 3 else "due",
            ).pack(side="right")
        for ins in expiring:
            r = c.row()
            ctk.CTkLabel(r, text=ins.title, font=theme.font(13, "bold"), anchor="w").pack(side="left")
            _Button(r, "See", lambda i=ins: self.open_insight(i)).pack(side="right")
        return len(lines) + len(expiring)

    def _render_house(self, data: dict) -> int:
        c = self.house
        c.clear()
        items = [
            i for i in data["insights"] if not any(s in i.title for s in _SHOWN_ELSEWHERE) and "expiring" not in i.title
        ]
        recurring = data["recurring"]
        count = len(items) + (1 if recurring else 0)
        c.set_count(count)
        for ins in items:
            r = c.row()
            text = ctk.CTkFrame(r, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text, text=ins.title, font=theme.font(13, "bold"), anchor="w", height=18).pack(fill="x")
            if ins.detail:
                ctk.CTkLabel(
                    text,
                    text=ins.detail,
                    font=theme.font(11),
                    text_color=theme.color("muted"),
                    anchor="w",
                    height=16,
                    wraplength=260,
                    justify="left",
                ).pack(fill="x")
            if "backup" in ins.title.lower() and self.ctx.can(Permission.BACKUP):
                _Button(r, "Back up now", self.backup_now, primary=True).pack(side="right")
            elif ins.view:
                _Button(r, "Open", lambda i=ins: self.open_insight(i)).pack(side="right")
        if recurring:
            r = c.row()
            text = ctk.CTkFrame(r, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            months = sum(len(m) for _r, m in recurring)
            ctk.CTkLabel(
                text, text=f"{months} monthly expense(s) to post", font=theme.font(13, "bold"), anchor="w", height=18
            ).pack(fill="x")
            ctk.CTkLabel(
                text,
                text=", ".join(rec.head_name.title() for rec, _m in recurring[:3]),
                font=theme.font(11),
                text_color=theme.color("muted"),
                anchor="w",
                height=16,
            ).pack(fill="x")
            if self.ctx.can(Permission.FINANCE_REPORTS):
                _Button(r, "Post now", self.post_recurring).pack(side="right")
            else:
                _Button(r, "Open", lambda: self.ctx.navigate("finance")).pack(side="right")
        if not count:
            c.empty("Nothing to tidy up.")
        return count

    def _tile(self, master, row: int, col: int, label: str, value: str, color: str = "text") -> None:
        t = ctk.CTkFrame(master, fg_color=theme.color("stripe"), corner_radius=10)
        t.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 5, 5 if col == 0 else 0), pady=4)
        ctk.CTkLabel(t, text=label, font=theme.font(11), text_color=theme.color("muted"), anchor="w").pack(
            fill="x", padx=12, pady=(8, 0)
        )
        ctk.CTkLabel(t, text=value, font=theme.font(16, "bold"), text_color=theme.color(color), anchor="w").pack(
            fill="x", padx=12, pady=(0, 8)
        )

    def _render_today(self, data: dict) -> None:
        c = self.today_card
        c.clear()
        c.set_count(None)
        grid = ctk.CTkFrame(c.body, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1), weight=1, uniform="t")
        d = data["day"]
        self._tile(grid, 0, 0, f"Gave · {d.entries} entries", rupees(d.debit))
        self._tile(grid, 0, 1, "Got", rupees(d.credit), "weowe")
        money = data["money"]
        if money:
            first, rest = money[0], money[1:]
            self._tile(grid, 1, 0, i18n.tr_cell(first[0].name), rupees(first[1]))
            self._tile(grid, 1, 1, "Other accounts", rupees(sum(b for _a, b in rest)))
        else:
            k = data["kpis"]
            self._tile(grid, 1, 0, "Receivable", rupees(k.receivable), "owe")
            self._tile(grid, 1, 1, "Payable", rupees(k.payable), "weowe")

    def _render_owed(self, data: dict) -> None:
        c = self.owed_card
        c.clear()
        c.set_count(None)
        k = data["kpis"]
        top = ctk.CTkFrame(c.body, fg_color="transparent")
        top.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            top, text=f"₹{compact_money(k.receivable)}", font=theme.font(24, "bold"), text_color=theme.color("owe")
        ).pack(side="left")
        ctk.CTkLabel(top, text=f"{k.debtors} accounts", font=theme.font(12), text_color=theme.color("muted")).pack(
            side="left", padx=10, pady=(8, 0)
        )
        aging = data["aging"]
        biggest = max((a for _l, _n, a in aging), default=0) or 1
        colors = ("accent", "accent", "warning", "owe")
        for i, (label, _n, amount) in enumerate(aging):
            r = ctk.CTkFrame(c.body, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(
                r, text=label, font=theme.font(11), text_color=theme.color("muted"), width=86, anchor="w"
            ).pack(side="left")
            track = ctk.CTkFrame(r, height=10, corner_radius=5, fg_color=theme.color("surface2"))
            track.pack(side="left", fill="x", expand=True, padx=8)
            if amount > 0:
                ctk.CTkFrame(track, height=10, corner_radius=5, fg_color=theme.color(colors[min(i, 3)])).place(
                    relx=0, rely=0, relheight=1, relwidth=max(0.02, amount / biggest)
                )
            ctk.CTkLabel(r, text=f"₹{compact_money(amount)}", font=theme.font(11, "bold"), width=70, anchor="e").pack(
                side="left"
            )

    def _render_latest(self, data: dict) -> None:
        c = self.latest
        c.clear()
        c.set_count(None)
        rows = data["latest"]
        if not rows:
            c.empty("Nothing entered yet today.")
            return
        for _tx, name, description, amount, kind, _tag, user in rows:
            r = c.row()
            ctk.CTkLabel(
                r,
                text=f"{i18n.tr_cell(name).title()} · {i18n.tr_cell(description)[:22]}",
                font=theme.font(12),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(r, text=user, font=theme.font(11), text_color=theme.color("muted")).pack(side="left", padx=6)
            ctk.CTkLabel(
                r,
                text=("+" if kind == "P" else "−") + rupees(amount)[1:],
                font=theme.font(12, "bold"),
                text_color=theme.color("owe" if kind == "P" else "weowe"),
            ).pack(side="left")

    # Actions ---------------------------------------------------------------------------
    def open_insight(self, insight) -> None:
        if insight.view == "karar":
            self.ctx.navigate("karar")
        elif insight.view:
            self.ctx.navigate(insight.view, **insight.args)

    def whatsapp(self, customer_id: int, promised: str) -> None:
        r = self.ctx.reminders.build(customer_id, promised)
        if r.whatsapp_url:
            import webbrowser

            webbrowser.open(r.whatsapp_url)
            self.ctx.audit.log("07", f"whatsapp reminder to customer {customer_id}", self.ctx.username)
        else:
            self.clipboard_clear()
            self.clipboard_append(r.text)
            self.ctx.toast("No phone number in the account details - reminder copied instead", "warning")

    def new_date(self, customer_id: int) -> None:
        if actions.promise(self, self.ctx, customer_id):
            self.reload()

    def new_customer(self) -> None:
        c = actions.new_customer(self, self.ctx)
        if c is not None:
            self.ctx.navigate("customers", customer_id=c.id)

    def backup_now(self) -> None:
        dest = self.ctx.backup.manual()
        self.ctx.audit.log("09", f"backup {dest.name}", self.ctx.username)
        self.ctx.app.refresh_backup_label()
        self.ctx.toast(f"Backup saved: {dest.name}", "success")
        self.reload()

    def post_recurring(self) -> None:
        flow = money_flow_handler(self.ctx.db)
        if flow is None:
            return
        n = flow.post_due(self.ctx.username)
        self.ctx.toast(f"{n} expense entr{'y' if n == 1 else 'ies'} posted", "success")
        self.reload()
