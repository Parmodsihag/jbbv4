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
    (
        2,
        # bills module (hth/modules/bills)
        """
        CREATE TABLE IF NOT EXISTS bill_month_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year  TEXT NOT NULL,
            item_id     INTEGER,
            name        TEXT NOT NULL,
            unit        TEXT NOT NULL DEFAULT '',
            rate        REAL NOT NULL DEFAULT 0,
            item_type   TEXT NOT NULL DEFAULT 'O',
            start_date  TEXT NOT NULL,
            batch       TEXT NOT NULL DEFAULT 'NA',
            expiry_date TEXT NOT NULL DEFAULT 'NA',
            quantity    REAL NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS ix_bmi_month ON bill_month_items(month_year);

        CREATE TABLE IF NOT EXISTS bills (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number      INTEGER NOT NULL UNIQUE,
            date             TEXT NOT NULL,
            customer_name    TEXT NOT NULL,
            customer_address TEXT NOT NULL DEFAULT '',
            customer_id      INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            taxable          REAL NOT NULL DEFAULT 0,
            cgst             REAL NOT NULL DEFAULT 0,
            sgst             REAL NOT NULL DEFAULT 0,
            grand_total      REAL NOT NULL DEFAULT 0,
            source           TEXT NOT NULL DEFAULT 'manual',
            docx_path        TEXT,
            created_by       TEXT,
            created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_bills_date ON bills(date);

        CREATE TABLE IF NOT EXISTS bill_lines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id     INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            unit        TEXT NOT NULL DEFAULT '',
            batch       TEXT NOT NULL DEFAULT 'NA',
            expiry_date TEXT NOT NULL DEFAULT 'NA',
            rate        REAL NOT NULL,
            item_type   TEXT NOT NULL DEFAULT 'O',
            quantity    REAL NOT NULL,
            amount      REAL NOT NULL,
            gst_rate    REAL NOT NULL DEFAULT 0,
            cgst        REAL NOT NULL DEFAULT 0,
            sgst        REAL NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS ix_bill_lines_bill ON bill_lines(bill_id);
        """,
    ),
    (
        3,
        """
        -- crop trading module (hth/modules/crop_trading)
        CREATE TABLE IF NOT EXISTS crop_lots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT NOT NULL,
            farmer_id     INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
            gross_qty     REAL NOT NULL,
            deduction_qty REAL NOT NULL DEFAULT 0,
            qty           REAL NOT NULL,            -- net = gross - deduction, in the item's unit
            remaining_qty REAL NOT NULL,            -- not yet sold (FIFO)
            rate          REAL NOT NULL,            -- per item unit
            amount        REAL NOT NULL,
            quality       TEXT NOT NULL DEFAULT '',
            notes         TEXT NOT NULL DEFAULT '',
            tx_id         INTEGER,                  -- ledger entry (customers credit)
            stock_tx_id   INTEGER,                  -- item_transactions row
            created_by    TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_crop_lots_item ON crop_lots(item_id, date, id);
        CREATE INDEX IF NOT EXISTS ix_crop_lots_farmer ON crop_lots(farmer_id, date);

        CREATE TABLE IF NOT EXISTS crop_sales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            buyer_id    INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            buyer_name  TEXT NOT NULL DEFAULT 'CASH',
            item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
            qty         REAL NOT NULL,
            rate        REAL NOT NULL,
            amount      REAL NOT NULL,
            cost        REAL NOT NULL DEFAULT 0,    -- FIFO cost of the quantity sold
            margin      REAL NOT NULL DEFAULT 0,    -- amount - cost
            short_qty   REAL NOT NULL DEFAULT 0,    -- sold without a lot to cost against
            notes       TEXT NOT NULL DEFAULT '',
            tx_id       INTEGER,
            stock_tx_id INTEGER,
            created_by  TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_crop_sales_item ON crop_sales(item_id, date);
        CREATE INDEX IF NOT EXISTS ix_crop_sales_buyer ON crop_sales(buyer_id, date);

        CREATE TABLE IF NOT EXISTS crop_sale_lots (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id   INTEGER NOT NULL REFERENCES crop_sales(id) ON DELETE CASCADE,
            lot_id    INTEGER REFERENCES crop_lots(id) ON DELETE SET NULL,
            qty       REAL NOT NULL,
            cost_rate REAL NOT NULL,
            cost      REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_crop_sale_lots_sale ON crop_sale_lots(sale_id);

        CREATE TABLE IF NOT EXISTS crop_rates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            date       TEXT NOT NULL,
            rate       REAL NOT NULL,               -- market rate per item unit
            source     TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE (item_id, date, source)
        );
        CREATE INDEX IF NOT EXISTS ix_crop_rates_item ON crop_rates(item_id, date);
        """,
    ),
    (
        4,
        """
        -- categories (A-E) on customers and items; E = defaulter / discontinued, manual only
        ALTER TABLE customers ADD COLUMN category TEXT NOT NULL DEFAULT 'C';
        ALTER TABLE customers ADD COLUMN category_locked INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE items ADD COLUMN category TEXT NOT NULL DEFAULT 'C';
        ALTER TABLE items ADD COLUMN category_locked INTEGER NOT NULL DEFAULT 0;
        CREATE INDEX IF NOT EXISTS ix_customers_category ON customers(category);
        CREATE INDEX IF NOT EXISTS ix_items_category ON items(category);
        """,
    ),
    (
        5,
        """
        -- finance module (hth/modules/finance)
        CREATE TABLE IF NOT EXISTS money_accounts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
            kind            TEXT NOT NULL DEFAULT 'cash' CHECK (kind IN ('cash', 'bank', 'upi', 'other')),
            opening_balance REAL NOT NULL DEFAULT 0,
            opening_date    TEXT NOT NULL DEFAULT (date('now','localtime')),
            is_active       INTEGER NOT NULL DEFAULT 1,
            notes           TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS expense_heads (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL UNIQUE COLLATE NOCASE,
            kind      TEXT NOT NULL DEFAULT 'expense' CHECK (kind IN ('expense', 'income')),
            is_active INTEGER NOT NULL DEFAULT 1
        );

        -- kind: expense | income | transfer | owner_in | owner_out | receipt | payment
        -- account_id is the money account the entry moves; counter_account_id for transfers.
        CREATE TABLE IF NOT EXISTS finance_entries (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            date               TEXT NOT NULL,
            kind               TEXT NOT NULL CHECK (kind IN ('expense','income','transfer','owner_in',
                                                          'owner_out','receipt','payment')),
            account_id         INTEGER NOT NULL REFERENCES money_accounts(id) ON DELETE RESTRICT,
            counter_account_id INTEGER REFERENCES money_accounts(id) ON DELETE RESTRICT,
            head_id            INTEGER REFERENCES expense_heads(id) ON DELETE RESTRICT,
            customer_id        INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            amount             REAL NOT NULL,
            description        TEXT NOT NULL DEFAULT '',
            tx_id              INTEGER,
            created_by         TEXT,
            created_at         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS ix_fin_account_date ON finance_entries(account_id, date, id);
        CREATE INDEX IF NOT EXISTS ix_fin_date ON finance_entries(date);
        CREATE INDEX IF NOT EXISTS ix_fin_head ON finance_entries(head_id);

        CREATE TABLE IF NOT EXISTS finance_recurring (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            head_id      INTEGER NOT NULL REFERENCES expense_heads(id) ON DELETE RESTRICT,
            account_id   INTEGER NOT NULL REFERENCES money_accounts(id) ON DELETE RESTRICT,
            amount       REAL NOT NULL,
            day_of_month INTEGER NOT NULL DEFAULT 1,
            description  TEXT NOT NULL DEFAULT '',
            is_active    INTEGER NOT NULL DEFAULT 1,
            start_month  TEXT NOT NULL,             -- YYYY-MM of the first month to post
            last_posted  TEXT                       -- YYYY-MM of the last month posted
        );

        -- value of a stock movement (sale price x qty for sales, cost x qty for receipts)
        ALTER TABLE item_transactions ADD COLUMN value REAL NOT NULL DEFAULT 0;
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
