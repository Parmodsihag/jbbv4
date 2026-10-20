"""Matplotlib figures embedded in a themed card."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from hth.ui import theme  # noqa: E402

Builder = Callable[[Figure, "matplotlib.axes.Axes"], None]


class ChartCard(ctk.CTkFrame):
    def __init__(self, master, title: str, height: int = 240, **kwargs):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10, **kwargs)
        ctk.CTkLabel(self, text=title, font=theme.font(14, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent", height=height)
        self.body.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        self.body.pack_propagate(False)
        self._figure_canvas: FigureCanvasTkAgg | None = None
        self._builder: Builder | None = None
        self.empty_label: ctk.CTkLabel | None = None

    def draw(self, builder: Builder) -> None:
        self._builder = builder
        self._render()

    def redraw(self) -> None:
        if self._builder:
            self._render()

    def show_empty(self, text: str = "No data yet") -> None:
        self._dispose()
        self.empty_label = ctk.CTkLabel(self.body, text=text, text_color=theme.color("muted"), font=theme.font(13))
        self.empty_label.pack(expand=True)

    def _dispose(self) -> None:
        if self._figure_canvas is not None:
            self._figure_canvas.get_tk_widget().destroy()
            self._figure_canvas.figure.clear()
            self._figure_canvas = None
        if self.empty_label is not None:
            self.empty_label.destroy()
            self.empty_label = None

    def _render(self) -> None:
        self._dispose()
        bg = theme.current("surface")
        fig = Figure(figsize=(4, 2.4), dpi=100, facecolor=bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg)
        try:
            self._builder(fig, ax)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            ax.text(0.5, 0.5, f"chart error: {exc}", ha="center", va="center", fontsize=8)
        style_axes(ax)
        fig.tight_layout(pad=1.2)
        self._figure_canvas = FigureCanvasTkAgg(fig, master=self.body)
        self._figure_canvas.draw()
        self._figure_canvas.get_tk_widget().pack(fill="both", expand=True)


def style_axes(ax) -> None:
    text = theme.current("text")
    muted = theme.current("muted")
    ax.tick_params(colors=muted, labelsize=8)
    ax.xaxis.label.set_color(muted)
    ax.yaxis.label.set_color(muted)
    ax.title.set_color(text)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(muted)
    ax.grid(axis="y", color=muted, alpha=0.15, linewidth=0.6)
    ax.set_axisbelow(True)


def compact_axis(ax, which: str = "y") -> None:
    """Tick labels as 1.5 L / 2 Cr (or K / M) instead of matplotlib's 1e6 offset."""
    from matplotlib.ticker import FuncFormatter

    from hth.ui.format import compact_money

    def fmt(v, _pos):
        return "0" if v == 0 else compact_money(v).replace(".00", "")

    axis = ax.yaxis if which == "y" else ax.xaxis
    axis.set_major_formatter(FuncFormatter(fmt))
