"""Overview: KPIs, charts and today's krar list."""

from __future__ import annotations

import datetime as dt

import customtkinter as ctk

from hth.services.permissions import Permission
from hth.ui import theme
from hth.ui.format import money
from hth.ui.views.base import BaseView
from hth.ui.widgets.charts import ChartCard
from hth.ui.widgets.datatable import Column, DataTable
from hth.ui.widgets.forms import secondary_button
from hth.ui.widgets.kpi import KpiTile

CHART_H = 250  # chart body height in px


def _money_balances(db) -> tuple[float, str]:
    """(total, 'CASH 1,000 · SBI 5,000') from the finance module, or (0, '') without it."""
    from hth.services.sales import money_flow_handler

    flow = money_flow_handler(db)
    if flow is None:
        return 0.0, "finance module off"
    try:
        balances = flow.balances()
    except Exception:  # noqa: BLE001
        return 0.0, ""
    total = round(sum(b for _, b in balances), 2)
    detail = " · ".join(f"{a.name} {money(b)}" for a, b in balances[:3])
    return total, detail


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

        tiles = ctk.CTkFrame(body, fg_color="transparent")
        tiles.grid(row=1, column=0, columnspan=3, sticky="ew", padx=0, pady=(0, 10))
        for i in range(7):
            tiles.grid_columnconfigure(i, weight=1, uniform="k")
        self.k_recv = KpiTile(tiles, "Receivable", accent="accent")
        self.k_pay = KpiTile(tiles, "Payable", accent="warning")
        self.k_cust = KpiTile(tiles, "Customers", accent="chart5")
        self.k_stock = KpiTile(tiles, "Stock value", accent="success")
        self.k_krar = KpiTile(tiles, "Krar due", accent="danger")
        self.k_today = KpiTile(tiles, "Today", accent="chart2")
        self.k_money = KpiTile(tiles, "Cash & bank", accent="chart3")
        for i, t in enumerate(
            (self.k_recv, self.k_pay, self.k_cust, self.k_stock, self.k_krar, self.k_today, self.k_money)
        ):
            t.grid(row=0, column=i, sticky="ew", padx=4)

        self.c_activity = ChartCard(body, "Activity - last 14 days", height=CHART_H)
        self.c_activity.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        self.c_flow = ChartCard(body, "Debits vs credits - last 12 months", height=CHART_H)
        self.c_flow.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)
        self.c_aging = ChartCard(body, "Receivables by age", height=CHART_H)
        self.c_aging.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)
        self.c_top = ChartCard(body, "Top 10 debtors", height=CHART_H)
        self.c_top.grid(row=3, column=1, sticky="nsew", padx=4, pady=4)

        krar_card = ctk.CTkFrame(body, fg_color=theme.color("surface"), corner_radius=10, height=2 * CHART_H + 8)
        krar_card.grid_propagate(False)
        krar_card.grid(row=2, column=2, rowspan=2, sticky="nsew", padx=4, pady=4)
        ctk.CTkLabel(krar_card, text="Krar (promised payments)", font=theme.font(14, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(10, 4)
        )
        self.krar_table = DataTable(
            krar_card,
            [
                Column("when", "When", 90),
                Column("name", "Customer", 170, stretch=True),
                Column("date", "Promised", 100),
                Column("balance", "Balance", 100, "e", "money"),
            ],
            row_tags=lambda r: ["neg"] if r[0] == "Overdue" else (["warn"] if r[0] == "Today" else []),
            on_double_click=lambda r: self.ctx.navigate("customers", customer_id=r[4]),
        )
        self.krar_table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def on_show(self, **kwargs) -> None:
        if self._data is None:
            self.reload()

    def on_theme_change(self) -> None:
        self.krar_table.restyle()
        for c in (self.c_activity, self.c_flow, self.c_aging, self.c_top):
            c.redraw()

    # Loading ----------------------------------------------------------------------------
    def reload(self) -> None:
        self.refreshed.configure(text="Loading…")
        rep = self.ctx.reports

        def work():
            summaries = rep.categories.customer_summaries()
            cats = ",".join(sorted(rep.categories.customer_report_categories())) or "none"
            balances = {s.id: s.balance for s in summaries}
            krar_rows = []
            for bucket, label in (("past", "Overdue"), ("today", "Today"), ("future", "Upcoming")):
                for e in rep.krar.entries(bucket):
                    krar_rows.append(
                        (
                            label,
                            e.customer_name,
                            e.last_date,
                            balances.get(e.customer_id, 0),
                            e.customer_id,
                        )
                    )
            return {
                "kpis": rep.kpis(summaries),
                "activity": rep.daily_activity(14),
                "flow": rep.monthly_flow(12),
                "aging": rep.aging(summaries),
                "top": rep.top_debtors(10, summaries),
                "krar": krar_rows,
                "cats": cats,
                "money": _money_balances(rep.db),
            }

        self.run_async(work, self._render)

    def _render(self, data: dict) -> None:
        self._data = data
        k = data["kpis"]
        self.k_recv.set(money(k.receivable), f"{k.debtors} debtors")
        self.k_pay.set(money(k.payable), "owed to customers")
        self.k_cust.set(str(k.customers), f"{k.items} items · categories {data['cats']}")
        self.k_stock.set(money(k.stock_value), "at stock value")
        self.k_krar.set(str(k.krar_today), f"{k.krar_overdue} overdue")
        self.k_today.set(f"{k.sales_today} / {k.receipts_today}", "sales / receipts")
        total, detail = data["money"]
        self.k_money.set(money(total), detail)
        self.refreshed.configure(text=f"Updated {dt.datetime.now():%H:%M:%S}")

        activity = data["activity"]
        if any(n for _, n in activity):

            def build_activity(fig, ax):
                labels = [d[-2:] for d, _ in activity]
                ax.bar(labels, [n for _, n in activity], color=theme.current("chart1"), width=0.7)
                ax.set_ylabel("entries")

            self.c_activity.draw(build_activity)
        else:
            self.c_activity.show_empty()

        flow = data["flow"]
        if flow:

            def build_flow(fig, ax):
                import numpy as np

                x = np.arange(len(flow))
                ax.bar(
                    x - 0.2,
                    [m.debit for m in flow],
                    0.4,
                    label="Debit",
                    color=theme.current("chart1"),
                )
                ax.bar(
                    x + 0.2,
                    [m.credit for m in flow],
                    0.4,
                    label="Credit",
                    color=theme.current("chart2"),
                )
                ax.set_xticks(x, [m.month[2:] for m in flow], rotation=45)
                ax.legend(fontsize=7, frameon=False, labelcolor=theme.current("muted"))

            self.c_flow.draw(build_flow)
        else:
            self.c_flow.show_empty()

        aging = [(lbl, amt) for lbl, _, amt in data["aging"] if amt > 0]
        if aging:

            def build_aging(fig, ax):
                colors = [theme.current(c) for c in ("chart2", "chart1", "chart3", "chart4")]
                wedges, _texts, autotexts = ax.pie(
                    [a for _, a in aging],
                    labels=[lbl for lbl, _ in aging],
                    colors=colors[: len(aging)],
                    autopct="%1.0f%%",
                    startangle=90,
                    wedgeprops={"width": 0.45},
                    textprops={"fontsize": 8},
                )
                for t in _texts:
                    t.set_color(theme.current("muted"))
                for t in autotexts:
                    t.set_color(theme.current("text"))
                ax.axis("equal")

            self.c_aging.draw(build_aging)
        else:
            self.c_aging.show_empty()

        top = data["top"]
        if top:

            def build_top(fig, ax):
                names = [s.name[:18] for s in top][::-1]
                ax.barh(names, [s.balance for s in top][::-1], color=theme.current("chart5"))
                ax.tick_params(axis="y", labelsize=7)

            self.c_top.draw(build_top)
        else:
            self.c_top.show_empty()

        rows = data["krar"]
        self.krar_table.set_rows(rows, f"{len(rows)} open krar")
