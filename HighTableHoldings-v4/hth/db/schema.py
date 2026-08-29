"""Versioned schema.  Add a new entry to MIGRATIONS to evolve the database; never edit
an existing one once it has shipped."""

from __future__ import annotations

import logging

from hth.db.connection import Database

log = logging.getLogger(__name__)

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
            full_name     TEXT NOT NULL DEFAULT '',
            role          TEXT NOT NULL CHECK (role IN ('admin', 'employee')),
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS customers (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            other_details TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_customers_name ON customers(name);

        -- One ledger for all customers (v3 had a table per customer).
        -- type: P = debit (customer owes more), M = credit (customer paid / owes less)
        -- tag : 0 = settlement marker, 1 = normal (interest bearing), 2 = no interest
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            date        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            amount      REAL NOT NULL,
            type        TEXT NOT NULL CHECK (type IN ('P', 'M')),
            tag         TEXT NOT NULL CHECK (tag IN ('0', '1', '2')),
            legacy_id   INTEGER,
            created_by  TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_tx_customer_date ON transactions(customer_id, date, id);

        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            stock_value REAL NOT NULL DEFAULT 0,
            last_value  REAL NOT NULL DEFAULT 0,
            unit        TEXT NOT NULL DEFAULT 'PCS',
            batch       TEXT NOT NULL DEFAULT 'NA',
            expiry_date TEXT NOT NULL DEFAULT 'NA',
            gst_rate    REAL NOT NULL DEFAULT 0,
            item_type   TEXT NOT NULL DEFAULT 'S',
            pakka_kacha TEXT NOT NULL DEFAULT 'P',
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_items_name ON items(name);

        CREATE TABLE IF NOT EXISTS item_transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            date        TEXT NOT NULL,
            received    REAL NOT NULL DEFAULT 0,
            sale        REAL NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            tags        TEXT NOT NULL DEFAULT '',
            legacy_id   INTEGER,
            created_by  TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_itx_item_date ON item_transactions(item_id, date, id);

        -- Krar: a promise to pay by a date.  One open krar per customer; each
        -- reschedule adds a date row.  is_nill = 1 once settled.
        CREATE TABLE IF NOT EXISTS krar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            is_nill     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_krar_customer ON krar(customer_id, is_nill);

        CREATE TABLE IF NOT EXISTS krar_dates (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            krar_id INTEGER NOT NULL REFERENCES krar(id) ON DELETE CASCADE,
            date    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_krar_dates ON krar_dates(krar_id, date);

        -- Audit log (v3 "daily notes").  code keeps the v3 prefixes 01..06.
        CREATE TABLE IF NOT EXISTS audit_log (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            date     TEXT NOT NULL DEFAULT (date('now','localtime')),
            username TEXT NOT NULL DEFAULT 'system',
            code     TEXT NOT NULL,
            message  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_audit_date ON audit_log(date);

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """,
    ),
]


def current_version(db: Database) -> int:
    with db.connect() as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def initialize(db: Database) -> None:
    """Apply any migrations newer than PRAGMA user_version."""
    version = current_version(db)
    for target, ddl in MIGRATIONS:
        if target <= version:
            continue
        log.info("Applying schema migration %d", target)
        with db.connect() as conn:
            conn.executescript(ddl)
            conn.execute(f"PRAGMA user_version = {int(target)}")
