"""Make customtkinter translate its own visible text.

Only *display* text is translated.  Values the code reads back stay English:

* ``CTkSegmentedButton`` / ``CTkTabview`` - their buttons are ``CTkButton``s created with
  ``text=value``; the button shows Hindi, ``get()`` / ``set()`` still use the English value.
* ``CTkOptionMenu`` - the shown label and the dropdown entries are Hindi, the variable and
  ``get()`` stay English.

In English every hook is a no-op (``tr`` returns its input).
"""

from __future__ import annotations

import functools

import customtkinter as ctk
from customtkinter.windows.widgets.core_widget_classes import dropdown_menu

from hth.i18n import tr

_installed = False


def _wrap_text_kwargs(cls, *keys: str) -> None:
    original_init, original_configure = cls.__init__, cls.configure

    @functools.wraps(original_init)
    def __init__(self, *args, **kwargs):
        for key in keys:
            if isinstance(kwargs.get(key), str):
                kwargs[key] = tr(kwargs[key])
        original_init(self, *args, **kwargs)

    @functools.wraps(original_configure)
    def configure(self, *args, **kwargs):
        for key in keys:
            if isinstance(kwargs.get(key), str):
                kwargs[key] = tr(kwargs[key])
        return original_configure(self, *args, **kwargs)

    cls.__init__ = __init__
    cls.configure = configure


def _wrap_option_menu() -> None:
    cls = ctk.CTkOptionMenu

    def refresh(self) -> None:
        label = getattr(self, "_text_label", None)
        if label is not None:
            label.configure(text=tr(self._current_value))

    for method in ("__init__", "set", "_dropdown_callback", "_variable_callback", "configure"):
        original = getattr(cls, method)

        def make(orig):
            @functools.wraps(orig)
            def wrapper(self, *args, **kwargs):
                result = orig(self, *args, **kwargs)
                refresh(self)
                return result

            return wrapper

        setattr(cls, method, make(original))


def _wrap_dropdown() -> None:
    menu_cls = dropdown_menu.DropdownMenu
    original = menu_cls._add_menu_commands

    @functools.wraps(original)
    def _add_menu_commands(self):
        self.delete(0, "end")
        for value in self._values:
            self.add_command(
                label=tr(value).ljust(self._min_character_width),
                command=lambda v=value: self._button_callback(v),
                compound="left",
            )

    menu_cls._add_menu_commands = _add_menu_commands


def _wrap_titles() -> None:
    for cls in (ctk.CTkToplevel, ctk.CTk):
        original = cls.title

        def make(orig):
            @functools.wraps(orig)
            def title(self, string=None):
                return orig(self, tr(string) if isinstance(string, str) else string)

            return title

        cls.title = make(original)
        cls.wm_title = cls.title


def install() -> None:
    """Idempotent; call before the first widget is created."""
    global _installed
    if _installed:
        return
    _installed = True
    for cls in (ctk.CTkLabel, ctk.CTkButton, ctk.CTkCheckBox, ctk.CTkRadioButton, ctk.CTkSwitch):
        _wrap_text_kwargs(cls, "text")
    _wrap_text_kwargs(ctk.CTkEntry, "placeholder_text")
    _wrap_text_kwargs(ctk.CTkScrollableFrame, "label_text")
    _wrap_option_menu()
    _wrap_dropdown()
    _wrap_titles()
