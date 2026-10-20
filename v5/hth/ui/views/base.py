"""Base class for screens."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from hth.services.permissions import Permission
from hth.ui.context import AppContext

log = logging.getLogger(__name__)


class BaseView(ctk.CTkFrame):
    key = "base"
    title = ""
    permission: Permission | None = None

    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self._alive = True
        self.build()

    def build(self) -> None:  # override
        pass

    def on_show(self, **kwargs) -> None:  # override: called every time the view is displayed
        pass

    def on_theme_change(self) -> None:  # override
        pass

    def on_day_change(self) -> None:
        """Called once after midnight while the app is open: untouched date fields move to
        the new day.  Override to also reload day-based data (call super())."""
        from hth.ui.widgets.forms import DateField

        stack = list(self.winfo_children())
        while stack:
            w = stack.pop()
            if isinstance(w, DateField):
                w.refresh_today()
            stack.extend(w.winfo_children())

    def destroy(self) -> None:
        self._alive = False
        super().destroy()

    # Background work ----------------------------------------------------------------
    def run_async(
        self,
        work: Callable[[], Any],
        done: Callable[[Any], None],
        fail: Callable[[Exception], None] | None = None,
        poll_ms: int = 40,
    ) -> None:
        """Run ``work`` in a thread, then ``done(result)`` on the Tk thread.

        Tk is not thread-safe, so the worker never touches widgets: it drops its result in
        a queue that the Tk thread polls with ``after``.
        """
        results: queue.Queue = queue.Queue(maxsize=1)

        def target():
            try:
                results.put(("ok", work()))
            except Exception as exc:  # noqa: BLE001
                log.exception("background task failed")
                results.put(("err", exc))

        def poll():
            if not self._alive:
                return
            try:
                status, payload = results.get_nowait()
            except queue.Empty:
                self.after(poll_ms, poll)
                return
            if status == "ok":
                done(payload)
            else:
                (fail or self._default_fail)(payload)

        threading.Thread(target=target, daemon=True).start()
        self.after(poll_ms, poll)

    def _default_fail(self, exc: Exception) -> None:
        self.ctx.toast(f"Error: {exc}", "error")
