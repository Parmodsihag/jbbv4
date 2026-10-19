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


def test_first_start_copies_v4_database_read_only(tmp_path):
    from hth.config import Settings, copy_previous_version, previous_version_db
    from hth.services.accounts import AccountsService

    v4_dir, v5_dir = tmp_path / "v4", tmp_path / "v5"
    v4 = Database(v4_dir / "hth.db")
    schema.initialize(v4)
    AccountsService(v4).add_customer("ram", "", 500, "2026-01-01")
    before = (v4_dir / "hth.db").read_bytes()

    settings = Settings(v5_dir)
    settings.ensure_dirs()
    source = previous_version_db(settings, previous_dir=v4_dir)
    assert source == v4_dir / "hth.db"
    copy_previous_version(source, settings.db_path)
    v5 = Database(settings.db_path)
    schema.initialize(v5, settings.backup_dir)
    assert [c.name for c in AccountsService(v5).list_customers()] == ["RAM"]
    assert (v4_dir / "hth.db").read_bytes() == before  # v4 untouched
    # once v5 has its own database nothing is copied again
    assert previous_version_db(settings, previous_dir=v4_dir) is None


def test_ledger_edits_keep_the_cash_book_in_step(accounts, sales, db):
    from hth.modules.finance.service import FinanceService

    fin = FinanceService(db)
    fin.ensure_defaults()
    cash = fin.default_account_id()
    c = accounts.add_customer("ram", "", 1000, "2026-08-01")
    r = sales.record("M", "2026-08-29", c.id, "CASH", 1, 400, "1", "admin", money_account_id=cash)
    tx_id = r.transaction_ids[0]
    accounts.update_transaction(tx_id, "2026-08-30", "CASH", 450, "M", "1", "admin")
    assert fin.balance(cash) == 450 and fin.get_entry(r.finance_entry_id).date == "2026-08-30"
    accounts.update_transaction(tx_id, "2026-08-30", "CASH", 450, "P", "1", "admin")  # now money paid out
    assert fin.balance(cash) == -450
    accounts.delete_transaction(tx_id, "admin")
    assert fin.balance(cash) == 0 and fin.get_entry(r.finance_entry_id) is None


def test_crop_ledger_rows_are_changed_in_crop_trade_only(accounts, inventory, sales):
    farmer = accounts.add_customer("farmer", "", 0)
    wheat = inventory.add_item("WHEAT", unit="KG", item_type="C")
    lot = sales.record("M", "2026-08-01", farmer.id, wheat.name, 100, 25, "2", "admin", item_id=wheat.id)
    tx_id = lot.transaction_ids[0]
    with pytest.raises(ValidationError, match="crop purchase lot"):
        accounts.update_transaction(tx_id, "2026-08-01", "x", 1, "M", "2", "admin")
    with pytest.raises(ValidationError, match="crop purchase lot"):
        accounts.delete_transaction(tx_id, "admin")
    assert accounts.get_transaction(tx_id).amount == 2500
