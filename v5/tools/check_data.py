"""Print data-quality findings for the v4 database.

python tools/check_data.py            # all findings
python tools/check_data.py --errors   # ERROR only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hth.config import get_settings  # noqa: E402
from hth.db.connection import Database  # noqa: E402
from hth.db.schema import initialize  # noqa: E402
from hth.services.integrity import IntegrityService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--errors", action="store_true", help="show ERROR findings only")
    args = parser.parse_args()
    settings = get_settings()
    db = Database(settings.db_path)
    initialize(db)
    findings = IntegrityService(db).run()
    if args.errors:
        findings = [f for f in findings if f.severity == "ERROR"]
    for f in findings:
        print(f"{f.severity:5} {f.area:8} #{f.ref_id:<5} {f.name[:28]:28} {f.issue} - {f.detail}")
    print(f"\n{len(findings)} findings  (database: {settings.db_path})")
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
