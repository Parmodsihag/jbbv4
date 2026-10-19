"""Entry point: ``python -m hth`` or the ``hth`` console script."""

from __future__ import annotations

import sys


def main() -> int:
    from hth.config import get_settings
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.logging_setup import setup_logging
    from hth.services.auth import AuthService

    settings = get_settings()
    setup_logging(settings.log_dir)
    db = Database(settings.db_path)
    initialize(db)
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
