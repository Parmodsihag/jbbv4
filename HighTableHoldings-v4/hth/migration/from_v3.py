"""Import data from the v3 layout (one SQLite file per module, one table per entity).

Source files (all optional): accounts.db, inventory.db, krar.db, daily_notes.db.
IDs of customers, items and krars are preserved so old references stay meaningful.
Per-customer transaction ids are stored in ``legacy_id``; ordering within a customer
is preserved so the (date, id) settlement rule gives identical balances.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from hth.db.connection import Database

log = logging.getLogger(__name__)

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class MigrationError(Exception):
    pass


@dataclass
class MigrationReport:
    customers: int = 0
    transactions: int = 0
    items: int = 0
    item_transactions: int = 0
    krars: int = 0
    krar_dates: int = 0
    audit_entries: int = 0
    warnings: list[str] = field(default_factory=list)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.as_lines()) + "\n", encoding="utf-8")
        return path

    def as_lines(self) -> list[str]:
        return [
            f"customers:         {self.customers}",
            f"transactions:      {self.transactions}",
            f"items:             {self.items}",
            f"item transactions: {self.item_transactions}",
            f"krars:             {self.krars}",
            f"krar dates:        {self.krar_dates}",
            f"audit entries:     {self.audit_entries}",
            f"warnings:          {len(self.warnings)}",
            *[f"  - {w}" for w in self.warnings],
        ]


def _open(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn: sqlite3.Connection, pattern: str) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [r[0] for r in rows if re.fullmatch(pattern, r[0])]


def _clean_tag(value, where: str, report: MigrationReport) -> str:
    raw = "" if value is None else str(value).strip()
    v = raw[:1]
    if v in ("0", "1", "2"):
        return v
    report.warnings.append(f"{where}: tag {raw!r} is not 0/1/2 - imported as 1 (normal)")
    return "1"


def _clean_type(value, where: str, report: MigrationReport) -> str:
    raw = "" if value is None else str(value).strip()
    v = raw.upper()[:1]
    if v in ("P", "M"):
        return v
    report.warnings.append(f"{where}: type {raw!r} is not P/M - imported as P (debit)")
    return "P"


def _num(value, where: str = "", report: MigrationReport | None = None, default: float = 0.0) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        if report is not None:
            report.warnings.append(f"{where}: amount is blank - imported as {default:g}")
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        if report is not None:
            report.warnings.append(f"{where}: amount {value!r} is not a number - imported as {default:g}")
        return default


def migrate(legacy_dir: Path, db: Database, force: bool = False) -> MigrationReport:
    legacy_dir = Path(legacy_dir)
    if not legacy_dir.is_dir():
        raise MigrationError(f"Legacy folder not found: {legacy_dir}")
    if not force and db.fetchone("SELECT 1 FROM customers LIMIT 1"):
        raise MigrationError("Target database already has customers; pass force=True to import anyway.")

    report = MigrationReport()
    with db.connect() as conn:
        _migrate_accounts(legacy_dir / "accounts.db", conn, report)
        _migrate_inventory(legacy_dir / "inventory.db", conn, report)
        _migrate_krar(legacy_dir / "krar.db", conn, report)
        _migrate_daily_notes(legacy_dir / "daily_notes.db", conn, report)
    log.info("Migration complete: %s", report)
    return report


def _migrate_accounts(path: Path, conn: sqlite3.Connection, report: MigrationReport) -> None:
    src = _open(path)
    if src is None:
        report.warnings.append(f"{path.name} not found - skipped")
        return
    try:
        customers = src.execute("SELECT id, name, other_details FROM customers ORDER BY id").fetchall()
        tables = set(_tables(src, r"customer_\d+"))
        for c in customers:
            conn.execute(
                "INSERT INTO customers (id, name, other_details) VALUES (?, ?, ?)",
                (c["id"], (c["name"] or "").strip(), (c["other_details"] or "").strip()),
            )
            report.customers += 1
            table = f"customer_{c['id']}"
            if table not in tables:
                continue
            for t in src.execute(f"SELECT * FROM {table} ORDER BY id").fetchall():
                if not t["date"]:
                    report.warnings.append(f"{table} row {t['id']} has no date - skipped")
                    continue
                if not DATE_RE.fullmatch(str(t["date"]).strip()):
                    report.warnings.append(f"{table} row {t['id']}: date {t['date']!r} is not YYYY-MM-DD - skipped")
                    continue
                conn.execute(
                    "INSERT INTO transactions (customer_id, date, description, amount, type, tag,"
                    " legacy_id, created_by)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, 'v3')",
                    (
                        c["id"],
                        str(t["date"]).strip(),
                        t["description"] or "",
                        _num(t["amount"], f"{table} row {t['id']}", report),
                        _clean_type(t["type"], f"{table} row {t['id']}", report),
                        _clean_tag(t["tags"], f"{table} row {t['id']}", report),
                        t["id"],
                    ),
                )
                report.transactions += 1
    finally:
        src.close()


def _migrate_inventory(path: Path, conn: sqlite3.Connection, report: MigrationReport) -> None:
    src = _open(path)
    if src is None:
        report.warnings.append(f"{path.name} not found - skipped")
        return
    try:
        cols = {r[1] for r in src.execute("PRAGMA table_info(items)").fetchall()}
        items = src.execute("SELECT * FROM items ORDER BY id").fetchall()
        tables = set(_tables(src, r"item_\d+"))

        def col(row, name, default):
            return row[name] if name in cols and row[name] is not None else default

        for it in items:
            pk = str(col(it, "pakka_kacha", "P")).strip().upper()
            pk = {"1": "P", "0": "K"}.get(pk, pk or "P")
            conn.execute(
                "INSERT INTO items (id, name, stock_value, last_value, unit, batch, expiry_date, gst_rate,"
                " item_type, pakka_kacha) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    it["id"],
                    (it["name"] or "").strip(),
                    _num(it["stock_value"], f"items row {it['id']} stock_value", report),
                    _num(it["last_value"], f"items row {it['id']} last_value", report),
                    str(col(it, "unit", "PCS")),
                    str(col(it, "batch", "NA")),
                    str(col(it, "expiry_date", "NA")),
                    _num(col(it, "gst_rate", 0), f"items row {it['id']} gst_rate", report),
                    str(col(it, "item_type", "S")),
                    pk,
                ),
            )
            report.items += 1
            table = f"item_{it['id']}"
            if table not in tables:
                continue
            for t in src.execute(f"SELECT * FROM {table} ORDER BY id").fetchall():
                if not t["date"]:
                    report.warnings.append(f"{table} row {t['id']} has no date - skipped")
                    continue
                if not DATE_RE.fullmatch(str(t["date"]).strip()):
                    report.warnings.append(f"{table} row {t['id']}: date {t['date']!r} is not YYYY-MM-DD - skipped")
                    continue
                conn.execute(
                    "INSERT INTO item_transactions (item_id, date, received, sale, description, tags,"
                    " legacy_id, created_by)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, 'v3')",
                    (
                        it["id"],
                        str(t["date"]).strip(),
                        _num(t["received"], f"{table} row {t['id']} received", report),
                        _num(t["sale"], f"{table} row {t['id']} sale", report),
                        t["description"] or "",
                        t["tags"] or "",
                        t["id"],
                    ),
                )
                report.item_transactions += 1
    finally:
        src.close()


def _migrate_krar(path: Path, conn: sqlite3.Connection, report: MigrationReport) -> None:
    src = _open(path)
    if src is None:
        report.warnings.append(f"{path.name} not found - skipped")
        return
    try:
        known = {r[0] for r in conn.execute("SELECT id FROM customers").fetchall()}
        for k in src.execute("SELECT krar_id, customer_id, is_nill FROM all_krar ORDER BY krar_id"):
            if k["customer_id"] not in known:
                state = "settled" if k["is_nill"] else "OPEN"
                report.warnings.append(
                    f"krar {k['krar_id']} ({state}) references customer {k['customer_id']} which no longer exists"
                    " - skipped (check the audit log for '06 = accounts.db, customers, "
                    f"{k['customer_id']}')"
                )
                continue
            conn.execute(
                "INSERT INTO krar (id, customer_id, is_nill) VALUES (?, ?, ?)",
                (k["krar_id"], k["customer_id"], int(k["is_nill"] or 0)),
            )
            report.krars += 1
        krar_ids = {r[0] for r in conn.execute("SELECT id FROM krar").fetchall()}
        for d in src.execute("SELECT uid, kid, date FROM by_krar_id ORDER BY uid"):
            if d["kid"] not in krar_ids or not d["date"]:
                continue
            if not DATE_RE.fullmatch(str(d["date"]).strip()):
                report.warnings.append(f"by_krar_id row {d['uid']}: date {d['date']!r} is not YYYY-MM-DD - skipped")
                continue
            conn.execute(
                "INSERT INTO krar_dates (id, krar_id, date) VALUES (?, ?, ?)",
                (d["uid"], d["kid"], str(d["date"]).strip()),
            )
            report.krar_dates += 1
    finally:
        src.close()


def _migrate_daily_notes(path: Path, conn: sqlite3.Connection, report: MigrationReport) -> None:
    src = _open(path)
    if src is None:
        report.warnings.append(f"{path.name} not found - skipped")
        return
    try:
        for table in sorted(_tables(src, r"d\d{4}_\d{2}_\d{2}")):
            date = table[1:].replace("_", "-")
            for n in src.execute(f"SELECT id, description FROM {table} ORDER BY id"):
                text = (n["description"] or "").strip()
                m = re.match(r"^(\d{2})\s*=\s*(.*)$", text)
                code, message = (m.group(1), m.group(2)) if m else ("00", text)
                conn.execute(
                    "INSERT INTO audit_log (ts, date, username, code, message) VALUES (?, ?, 'v3', ?, ?)",
                    (f"{date} 00:00:00", date, code, message),
                )
                report.audit_entries += 1
    finally:
        src.close()
