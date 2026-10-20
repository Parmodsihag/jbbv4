"""Entry point: ``python -m hth`` or the ``hth`` console script."""

from __future__ import annotations

import sys


def main() -> int:
    import logging

    from hth.config import copy_previous_version, get_settings, previous_version_db
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.logging_setup import setup_logging
    from hth.services.auth import AuthService
    from hth.services.settings import SettingsService

    settings = get_settings()
    setup_logging(settings.log_dir)
    previous = previous_version_db(settings)
    if previous is not None:
        try:
            copy_previous_version(previous, settings.db_path)
        except Exception as exc:  # noqa: BLE001 - say what happened instead of a traceback
            # nothing was created (the copy goes to a temp file first), so the next start retries
            logging.getLogger("hth").exception("could not copy %s", previous)
            _startup_error(
                f"Could not copy the v4 data from\n{previous}\n\n{exc}\n\n"
                "Nothing was changed. Close High Table Holdings v4 if it is open and start v5 again."
            )
            return 1
        logging.getLogger("hth").info("first v5 start: copied %s (read-only) to %s", previous, settings.db_path)
    db = Database(settings.db_path)
    initialize(db, settings.backup_dir)
    if previous is not None:
        SettingsService(db).set("upgrade.copied_from", str(previous))
    from hth.services.hindi import HindiNamesService

    HindiNamesService(db).fill_missing()  # Hindi copies for records that have none yet
    AuthService(db).ensure_default_users()
    from hth.services.backup import BackupService

    BackupService(db, settings).daily()
    try:
        from hth.modules.finance.service import FinanceService

        FinanceService(db).ensure_defaults()
    except ImportError:
        pass

    from hth.ui.app import run_app

    run_app(db, settings)
    return 0


def _startup_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("High Table Holdings", message, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001 - no display: the log and stderr still have it
        print(message, file=sys.stderr)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()  # the packaged app starts the assistant's model process from itself
    sys.exit(main())
