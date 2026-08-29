"""Import v3 data into the v4 database.

python tools/migrate_v3.py                # from C:/JBB/data (Windows default)
python tools/migrate_v3.py /path/to/data  # explicit legacy folder
python tools/migrate_v3.py --force ...    # import even if the v4 database has data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hth.config import LEGACY_DATA_DIR_WINDOWS, get_settings  # noqa: E402
from hth.db.connection import Database  # noqa: E402
from hth.db.schema import initialize  # noqa: E402
from hth.logging_setup import setup_logging  # noqa: E402
from hth.migration.from_v3 import MigrationError, migrate  # noqa: E402
from hth.services.auth import AuthService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("legacy_dir", nargs="?", default=str(LEGACY_DATA_DIR_WINDOWS))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_dir)
    db = Database(settings.db_path)
    initialize(db)
    AuthService(db).ensure_default_users()
    try:
        report = migrate(Path(args.legacy_dir), db, force=args.force)
    except MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Imported into {settings.db_path}")
    print("\n".join(report.as_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
