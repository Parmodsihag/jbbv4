"""Small building blocks of the new layout, drawn from the design on the canvas."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import customtkinter as ctk

from hth.ui import theme


def segmented(master, values: Sequence[str], command: Callable[[str], None], height: int = 34):
    """A white pill on a grey track - section switches (Customers | Collections …)."""
    return ctk.CTkSegmentedButton(
        master,
        values=list(values),
        command=command,
        height=height,
        font=theme.font(13, "bold"),
        corner_radius=9,
        border_width=3,
        fg_color=theme.color("surface2"),
        selected_color=theme.color("surface"),
        selected_hover_color=theme.color("surface"),
        unselected_color=theme.color("surface2"),
        unselected_hover_color=theme.color("surface3"),
        text_color=theme.color("text"),
    )
