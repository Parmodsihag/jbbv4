"""Regression tests for bugs fixed in v5."""

from __future__ import annotations

import pytest

from hth.db import schema
from hth.db.connection import Database
from hth.services.accounts import ValidationError


def test_deleting_a_farmer_or_crop_with_lots_is_refused_cleanly(accounts, inventory, sales):
    farmer = accounts.add_customer("farmer", "", 0)
    wheat = inventory.add_item("WHEAT", unit="KG", item_type="C")
    sales.record("M", "2026-08-01", farmer.id, wheat.name, 100, 25, "2", "admin", item_id=wheat.id)
    with pytest.raises(ValidationError, match="crop lot"):
        accounts.delete_customer(farmer.id, "admin")
    with pytest.raises(ValidationError, match="crop lot"):
        inventory.delete_item(wheat.id, "admin")
    assert accounts.get_customer(farmer.id) is not None and inventory.get_item(wheat.id) is not None
    # an ordinary customer still deletes
    other = accounts.add_customer("other", "", 50)
    accounts.delete_customer(other.id, "admin")
    assert accounts.get_customer(other.id) is None


def test_negative_settlement_rows_can_be_edited(accounts):
    c = accounts.add_customer("x", "", 1000, "2026-01-01")
    accounts.record_settlement(c.id, "2026-02-01", "cash", 2000, "M", "admin")
    discount = next(t for t in accounts.get_transactions(c.id) if t.description == "Discount")
    assert discount.amount < 0
    accounts.update_transaction(discount.id, "2026-02-02", "Discount", discount.amount, "M", "0", "admin")
    assert accounts.get_transaction(discount.id).date == "2026-02-02"
    with pytest.raises(ValidationError):  # ordinary rows stay non-negative
        accounts.update_transaction(discount.id, "2026-02-02", "x", -5, "M", "1", "admin")


def test_failed_migration_leaves_database_untouched(tmp_path, monkeypatch):
    db = Database(tmp_path / "hth.db")
    schema.initialize(db)
    version = schema.current_version(db)
    broken = [*schema.MIGRATIONS, (version + 1, "CREATE TABLE t_new (x);\nALTER TABLE no_such_table ADD COLUMN y;")]
    monkeypatch.setattr(schema, "MIGRATIONS", broken)
    with pytest.raises(Exception, match="no_such_table"):
        schema.initialize(db, tmp_path / "backups")
    assert schema.current_version(db) == version
    assert db.fetchone("SELECT 1 FROM sqlite_master WHERE name = 't_new'") is None
    # the pre-migration backup was taken
    assert list((tmp_path / "backups").glob("hth_pre_migration_v*.db"))


def test_fresh_database_takes_no_pre_migration_backup(tmp_path):
    db = Database(tmp_path / "hth.db")
    assert schema.initialize(db, tmp_path / "backups") is None
    assert not (tmp_path / "backups").exists()
