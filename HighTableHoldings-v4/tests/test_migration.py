"""Build a miniature v3 data folder and import it."""

import sqlite3

import pytest

from hth.migration.from_v3 import MigrationError, migrate
from hth.services.accounts import AccountsService


def make_v3(folder):
    a = sqlite3.connect(folder / "accounts.db")
    a.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, other_details TEXT);
        INSERT INTO customers VALUES (1, 'RAM', 'X'), (5, 'SHYAM', 'Y');
        CREATE TABLE customer_1 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, description TEXT,
            amount REAL, type TEXT, tags TEXT);
        INSERT INTO customer_1 (date, description, amount, type, tags) VALUES
          ('2025-01-01', 'NEW ACCOUNT', 1000, 'P', '1'),
          ('2025-06-01', 'paid', 500, 'M', '0'),
          ('2025-06-01', 'Settled Amount', 1071.2, 'M', '0'),
          ('2025-06-01', 'Discount', 571.2, 'M', '0'),
          ('2025-07-01', '2 = WHEAT', 300, 'p', '1');
        CREATE TABLE customer_5 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, description TEXT,
            amount REAL, type TEXT, tags TEXT);
        INSERT INTO customer_5 (date, description, amount, type, tags) VALUES ('2025-02-01', 'x', '150', 'M', '');
        """
    )
    a.commit()
    a.close()
    i = sqlite3.connect(folder / "inventory.db")
    i.executescript(
        """
        CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, stock_value INTEGER, last_value INTEGER,
            unit TEXT, batch TEXT, expiry_date TEXT, gst_rate INTEGER, item_type TEXT, pakka_kacha INTEGER);
        INSERT INTO items VALUES (3, 'WHEAT', 20, 25, 'KG', 'NA', 'NA', 5, 'S', 1);
        CREATE TABLE item_3 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, received INTEGER,
            sale INTEGER, description TEXT, tags TEXT);
        INSERT INTO item_3 (date, received, sale, description, tags) VALUES
            ('2025-01-01', 50, 0, 'OPEN', ''), ('2025-07-01', 0, 2, 'RAM', '');
        """
    )
    i.commit()
    i.close()
    k = sqlite3.connect(folder / "krar.db")
    k.executescript(
        """
        CREATE TABLE all_krar (krar_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER,
            is_nill INTEGER DEFAULT 0);
        CREATE TABLE by_krar_id (uid INTEGER PRIMARY KEY AUTOINCREMENT, kid INTEGER, date TEXT);
        INSERT INTO all_krar VALUES (1, 1, 0), (2, 99, 0);
        INSERT INTO by_krar_id VALUES (1, 1, '2025-08-01'), (2, 1, '2025-08-15'), (3, 2, '2025-08-01');
        """
    )
    k.commit()
    k.close()
    d = sqlite3.connect(folder / "daily_notes.db")
    d.executescript(
        """
        CREATE TABLE d2025_07_01 (id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT);
        INSERT INTO d2025_07_01 (description) VALUES ('03 = 2025-07-01, WHEAT, RAM, 2, 150, 1'), ('free text');
        """
    )
    d.commit()
    d.close()


def test_migrate_preserves_ids_and_balances(db, tmp_path):
    make_v3(tmp_path)
    report = migrate(tmp_path, db)
    assert (report.customers, report.transactions, report.items, report.item_transactions) == (
        2,
        6,
        1,
        2,
    )
    assert report.krars == 1 and report.krar_dates == 2 and report.audit_entries == 2
    assert any("missing customer 99" in w for w in report.warnings)

    acc = AccountsService(db)
    assert acc.get_customer(5).name == "SHYAM"
    txs = acc.get_transactions(1)
    assert [t.legacy_id if hasattr(t, "legacy_id") else t.description for t in txs][-1] == "2 = WHEAT"
    assert txs[-1].type == "P"  # lower-case 'p' normalised
    assert acc.get_transactions(5)[0].tag == "1"  # blank tag normalised to normal
    assert acc.last_settlement(1)[0] == "2025-06-01"
    assert acc.current_period_transactions(1)[0].description == "2 = WHEAT"

    from hth.services.inventory import InventoryService

    inv = InventoryService(db)
    assert inv.get_item(3).pakka_kacha == "P" and inv.quantity(3) == 48

    codes = [r["code"] for r in db.fetchall("SELECT code FROM audit_log WHERE username='v3' ORDER BY id")]
    assert codes == ["03", "00"]

    with pytest.raises(MigrationError):
        migrate(tmp_path, db)


def test_missing_folder(db, tmp_path):
    with pytest.raises(MigrationError):
        migrate(tmp_path / "nope", db)
