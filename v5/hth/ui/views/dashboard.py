"""Overview: KPIs, charts, promised payments and what needs attention."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth import i18n
from hth.services.insights import Insight, InsightsService
from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import compact_money, money
from hth.ui.views.base import BaseView
from hth.ui.widgets.charts import ChartCard, compact_axis
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.forms import secondary_button
from hth.ui.widgets.kpi import KpiTile

CHART_H = 240  # chart body height in px
SEVERITY_COLOR = {"danger": "danger", "warning": "warning", "info": "muted", "ok": "success"}


def _money_balances(db) -> tuple[float, str] | None:
    """(total, 'CASH 1,000 · SBI 5,000') from the finance module, or None without it."""
    from hth.services.sales import money_flow_handler

    flow = money_flow_handler(db)
    if flow is None:
        return None
    try:
        balances = flow.balances()
    except Exception:  # noqa: BLE001
        return None
    total = round(sum(b for _, b in balances), 2)
    detail = " · ".join(f"{a.name} {compact_money(b)}" for a, b in balances[:3])
    return total, detail


def _month_label(ym: str) -> str:
    try:
        return dt.date(int(ym[:4]), int(ym[5:7]), 1).strftime("%b\n%y")
    except ValueError:
        return ym


class DashboardView(BaseView):
    key = "dashboard"
    title = "Dashboard"
    permission = Permission.VIEW_DASHBOARD

    def build(self) -> None:
        self._data: dict | None = None
        # Everything lives in a scrollable body with fixed-height cards, so nothing is
        # squeezed or overlapped on small screens - it scrolls instead.
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure((0, 1), weight=3, uniform="c")
        body.grid_columnconfigure(2, weight=2, uniform="c")

        bar = ctk.CTkFrame(body, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=(0, 8))
        self.refreshed = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color=theme.color("muted"))
        self.refreshed.pack(side="left")
        secondary_button(bar, "↻ Refresh", self.reload, width=110).pack(side="right")
        self.scope_label = ctk.CTkLabel(bar, text="", font=theme.font(11), text_color=theme.color("muted"))
        self.scope_label.pack(side="right", padx=12)

        tiles = ctk.CTkFrame(body, fg_color="transparent")
        tiles.grid(row=1, column=0, columnspan=3, sticky="ew", padx=0, pady=(0, 8))
        nav = self.ctx.navigate
        self.k_recv = KpiTile(tiles, "Receivable", accent="danger", command=lambda: nav("customers"))
        self.k_pay = KpiTile(tiles, "Payable", accent="warning", command=lambda: nav("customers"))
        self.k_today = KpiTile(tiles, "Today", accent="chart2", command=lambda: nav("reports", report="daybook"))
        self.k_krar = KpiTile(tiles, "Krar overdue", accent="chart4", command=lambda: nav("karar"))
        self.k_stock = KpiTile(tiles, "Stock value", accent="success", command=lambda: nav("items"))
        self.k_money = KpiTile(tiles, "Cash & bank", accent="chart3", command=lambda: nav("finance"))
        self.k_cust = KpiTile(tiles, "Accounts", accent="chart5", command=lambda: nav("customers"))
        all_tiles = (self.k_recv, self.k_pay, self.k_today, self.k_krar, self.k_stock, self.k_money, self.k_cust)
        for i, t in enumerate(all_tiles):
            tiles.grid_columnconfigure(i, weight=1, uniform="k")
            t.grid(row=0, column=i, sticky="ew", padx=4)

        self.c_flow = ChartCard(body, "Debits vs credits - last 12 months", height=CHART_H)
        self.c_flow.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        self.c_aging = ChartCard(body, "Receivables by age (days since last entry)", height=CHART_H)
        self.c_aging.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)
        self.c_top = ChartCard(body, "Top 10 debtors", height=CHART_H)
        self.c_top.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)
        self.c_activity = ChartCard(body, "Entries per day - last 14 days", height=CHART_H)
        self.c_activity.grid(row=3, column=1, sticky="nsew", padx=4, pady=4)

        att = self._side_card(body, "Needs attention")
        att.grid(row=2, column=2, sticky="nsew", padx=4, pady=4)
        self.attention = InsightList(att, self._open_insight)
        self.attention.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        krar = self._side_card(body, "Promised payments (krar)")
        krar.grid(row=3, column=2, sticky="nsew", padx=4, pady=4)
        self.krar_table = DataTable(
            krar,
            [
                Column("name", "Customer", 130, stretch=True),
                Column("date", "Date", 76),
                Column("balance", "Balance", 92, "e", "money"),
            ],
            row_tags=lambda r: ["neg"] if r[3] == "Overdue" else (["warn"] if r[3] == "Today" else []),
            on_double_click=lambda r: self.ctx.navigate("customers", customer_id=r[4]),
        )
        self.krar_table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _side_card(self, master, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(master, fg_color=theme.color("surface"), corner_radius=10, height=CHART_H + 44)
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=theme.font(14, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))
        return card

    def on_show(self, **kwargs) -> None:
        if self._data is None:
            self.reload()

    def on_day_change(self) -> None:
        super().on_day_change()
        self.reload()

    def on_theme_change(self) -> None:
        self.krar_table.restyle()
        for c in (self.c_activity, self.c_flow, self.c_aging, self.c_top):
            c.redraw()

    def _open_insight(self, insight: Insight) -> None:
        if insight.view:
            if insight.view == "karar" and "bucket" in insight.args:
                self.ctx.navigate("karar", bucket=insight.args["bucket"])
            else:
                self.ctx.navigate(insight.view, **insight.args)

    # Loading ----------------------------------------------------------------------------
    def reload(self) -> None:
        self.refreshed.configure(text="Loading…")
        rep = self.ctx.reports
        settings = self.ctx.settings

        def work():
            summaries = rep.categories.customer_summaries()
            cats = ",".join(sorted(rep.categories.customer_report_categories())) or "none"
            balances = {s.id: s.balance for s in summaries}
            krar_rows = []
            for bucket, label in (("past", "Overdue"), ("today", "Today"), ("future", "Upcoming")):
                for e in rep.krar.entries(bucket):
                    promised = i18n.date_text(dt.date.fromisoformat(e.last_date), "%d %b %y") if e.last_date else ""
                    krar_rows.append((e.customer_name, promised, balances.get(e.customer_id, 0), label, e.customer_id))
            return {
                "kpis": rep.kpis(summaries),
                "today": rep.day_totals(),
                "activity": rep.daily_activity(14),
                "flow": rep.monthly_flow(12),
                "aging": rep.aging(summaries),
                "top": rep.top_debtors(10, summaries),
                "krar": krar_rows,
                "cats": cats,
                "money": _money_balances(rep.db),
                "insights": InsightsService(rep.db, settings).collect(summaries),
            }

        self.run_async(work, self._render)

    def _render(self, data: dict) -> None:
        self._data = data
        k = data["kpis"]
        t = data["today"]
        self.k_recv.set(compact_money(k.receivable), money(k.receivable))
        self.k_pay.set(compact_money(k.payable), money(k.payable))
        if t.entries:
            self.k_today.set(compact_money(t.debit), f"in {compact_money(t.credit)} · {t.entries} entries")
        else:
            self.k_today.set("—", "nothing entered yet")
        overdue_tone = "danger" if k.krar_overdue else None
        self.k_krar.set(f"{k.krar_overdue:,}", f"{k.krar_today} due today", tone=overdue_tone)
        self.k_stock.set(compact_money(k.stock_value), f"{k.items} items at cost")
        if data["money"] is None:
            self.k_money.set("—", "finance module off")
        else:
            total, detail = data["money"]
            self.k_money.set(compact_money(total), detail or "no money accounts")
        self.k_cust.set(f"{k.customers:,}", f"{k.debtors:,} owe us")
        self.scope_label.configure(text=f"Customer categories in view: {data['cats']}  (Settings → Categories)")
        self.refreshed.configure(text=f"Updated {dt.datetime.now():%H:%M:%S}")

        flow = data["flow"]
        if flow:

            def build_flow(fig, ax):
                import numpy as np

                x = np.arange(len(flow))
                ax.bar(x - 0.2, [m.debit for m in flow], 0.4, label="Debit", color=theme.current("chart1"))
                ax.bar(x + 0.2, [m.credit for m in flow], 0.4, label="Credit", color=theme.current("chart2"))
                ax.set_xticks(x, [_month_label(m.month) for m in flow])
                compact_axis(ax, "y")
                ax.legend(
                    fontsize=7,
                    frameon=False,
                    labelcolor=theme.current("muted"),
                    loc="lower right",
                    bbox_to_anchor=(1.0, 1.0),
                    ncol=2,
                    borderaxespad=0.1,
                )

            self.c_flow.draw(build_flow)
        else:
            self.c_flow.show_empty()

        aging = [(lbl, n, amt) for lbl, n, amt in data["aging"] if amt > 0]
        if aging:

            def build_aging(fig, ax):
                colors = [theme.current(c) for c in ("chart2", "chart1", "chart3", "chart4")]
                labels = [lbl for lbl, _n, _a in aging]
                ax.barh(labels[::-1], [a for *_x, a in aging][::-1], color=colors[: len(aging)][::-1], height=0.6)
                for i, (_lbl, n, a) in enumerate(aging[::-1]):
                    ax.text(
                        a,
                        i,
                        f"  {compact_money(a)}  ({n} customers)",
                        va="center",
                        fontsize=8,
                        color=theme.current("muted"),
                    )
                compact_axis(ax, "x")
                ax.margins(x=0.25)
                ax.tick_params(axis="y", labelsize=8)

            self.c_aging.draw(build_aging)
        else:
            self.c_aging.show_empty()

        top = data["top"]
        if top:

            def build_top(fig, ax):
                names = [s.name[:16].title() for s in top][::-1]
                values = [s.balance for s in top][::-1]
                ax.barh(names, values, color=theme.current("chart5"), height=0.65)
                for i, v in enumerate(values):
                    ax.text(v, i, f" {compact_money(v)}", va="center", fontsize=7, color=theme.current("muted"))
                compact_axis(ax, "x")
                ax.margins(x=0.18)
                ax.tick_params(axis="y", labelsize=7)

            self.c_top.draw(build_top)
        else:
            self.c_top.show_empty()

        activity = data["activity"]
        if any(n for _, n in activity):

            def build_activity(fig, ax):
                labels = [dt.date.fromisoformat(d).strftime("%a\n%d") for d, _ in activity]
                ax.bar(labels, [n for _, n in activity], color=theme.current("chart1"), width=0.65)
                ax.tick_params(axis="x", labelsize=7)

            self.c_activity.draw(build_activity)
        else:
            self.c_activity.show_empty("No entries in the last 14 days")

        rows = data["krar"]
        overdue = sum(1 for r in rows if r[3] == "Overdue")
        self.krar_table.set_rows(rows, f"{len(rows)} open · {overdue} overdue · double-click opens the ledger")

        self.attention.set_items(data["insights"])


class InsightList(ctk.CTkScrollableFrame):
    """Wrapped, clickable rows: a coloured dot, the finding, and the detail under it."""

    def __init__(self, master, on_open):
        super().__init__(master, fg_color="transparent")
        self.on_open = on_open
        self._labels: list[ctk.CTkLabel] = []
        self._wrap = 200
        self.bind("<Configure>", self._rewrap, add="+")

    def _rewrap(self, event=None) -> None:
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        wrap = max(120, int(self.winfo_width() / scaling) - 52)
        if abs(wrap - self._wrap) > 4:
            self._wrap = wrap
            for label in self._labels:
                label.configure(wraplength=wrap)

    def set_items(self, insights: list[Insight]) -> None:
        for w in self.winfo_children():
            w.destroy()
        self._labels = []
        for ins in insights:
            row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=6)
            row.pack(fill="x", pady=1)
            dot = ctk.CTkLabel(
                row,
                text="✓" if ins.severity == "ok" else "●",
                width=18,
                font=theme.font(12),
                text_color=theme.color(SEVERITY_COLOR.get(ins.severity, "muted")),
            )
            dot.pack(side="left", anchor="n", padx=(4, 4), pady=(2, 0))
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, pady=2)
            title = ctk.CTkLabel(
                text,
                text=ins.title,
                font=theme.font(12, "bold"),
                anchor="w",
                justify="left",
                wraplength=self._wrap,
                height=20,
            )
            title.pack(fill="x")
            self._labels.append(title)
            parts = [row, dot, text, title]
            if ins.detail:
                detail = ctk.CTkLabel(
                    text,
                    text=ins.detail,
                    font=theme.font(11),
                    anchor="w",
                    justify="left",
                    text_color=theme.color("muted"),
                    wraplength=self._wrap,
                    height=16,
                )
                detail.pack(fill="x")
                self._labels.append(detail)
                parts.append(detail)
            if ins.view:
                for w in parts:
                    w.configure(cursor="hand2")
                    w.bind("<Button-1>", lambda e, i=ins: self.on_open(i))
                    w.bind("<Enter>", lambda e, r=row: r.configure(fg_color=theme.color("surface_hover")))
                    w.bind("<Leave>", lambda e, r=row: r.configure(fg_color="transparent"))
