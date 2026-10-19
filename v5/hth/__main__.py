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
        copy_previous_version(previous, settings.db_path)
        logging.getLogger("hth").info("first v5 start: copied %s (read-only) to %s", previous, settings.db_path)
    db = Database(settings.db_path)
    initialize(db, settings.backup_dir)
    if previous is not None:
        SettingsService(db).set("upgrade.copied_from", str(previous))
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


if __name__ == "__main__":
    sys.exit(main())
