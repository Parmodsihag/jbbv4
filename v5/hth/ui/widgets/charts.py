"""Matplotlib figures embedded in a themed card.

matplotlib takes most of a second to load, and only the classic dashboard draws charts:
it is loaded the first time a chart is drawn, not when the program starts.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import TYPE_CHECKING

import customtkinter as ctk

from hth.ui import theme

if TYPE_CHECKING:
    import matplotlib.axes
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

Builder = Callable[["Figure", "matplotlib.axes.Axes"], None]


class ChartCard(ctk.CTkFrame):
    def __init__(self, master, title: str, height: int = 240, **kwargs):
        super().__init__(master, fg_color=theme.color("surface"), corner_radius=10, **kwargs)
        ctk.CTkLabel(self, text=title, font=theme.font(14, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent", height=height)
        self.body.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        self.body.pack_propagate(False)
        self._figure_canvas: FigureCanvasTkAgg | None = None
        self._return_focus: tk.Misc | None = None
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

    def _focused(self):
        try:
            return self.focus_get()
        except (KeyError, tk.TclError):  # the focus is in a widget tkinter has no object for
            return None

    def _give_focus_back(self, _event=None) -> None:
        """matplotlib gives a chart the keyboard focus when it is made or clicked.  A chart takes
        no keys, and a light/dark switch redraws (destroys) the charts while customtkinter is
        about to re-focus whatever had the focus - that was a "Something went wrong" toast.
        So the focus goes back where it was before the chart was made (once), else the window."""
        target, self._return_focus = self._return_focus, None
        if target is None or not target.winfo_exists():
            target = self.winfo_toplevel()
        target.focus_set()

    def _dispose(self) -> None:
        if self._figure_canvas is not None:
            self._figure_canvas.get_tk_widget().destroy()
            self._figure_canvas.figure.clear()
            self._figure_canvas = None
        if self.empty_label is not None:
            self.empty_label.destroy()
            self.empty_label = None

    def _render(self) -> None:
        import matplotlib

        matplotlib.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

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
        self._return_focus = self._focused()
        self._figure_canvas = FigureCanvasTkAgg(fig, master=self.body)
        self._figure_canvas.get_tk_widget().bind("<FocusIn>", self._give_focus_back, add="+")
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
