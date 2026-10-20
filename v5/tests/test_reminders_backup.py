import datetime as dt

import pytest

from hth.config import Settings
from hth.services.backup import BackupService
from hth.services.reminders import ReminderService, extract_phone

TODAY = dt.date(2026, 8, 30)


def test_extract_phone():
    assert extract_phone("DHANSU 9812345678") == "9812345678"
    assert extract_phone("+91 98123-45678") is None  # dash breaks the run: not a clean number
    assert extract_phone("+91 9812345678 village") == "9812345678"
    assert extract_phone("12345") is None and extract_phone("") is None


def test_reminder_text_and_bucket(db, accounts, krar):
    svc = ReminderService(db)
    c = accounts.add_customer("ram kumar", "dhansu 9812345678", 1000, "2026-01-01")
    krar.add_or_update(c.id, "2026-08-20")
    r = svc.build(c.id, today=TODAY)
    assert r.promised == "2026-08-20" and r.days_overdue == 10 and r.phone == "9812345678"
    assert "Ram Kumar ji" in r.text and "20-08-2026" in r.text and "Jaat Beej Bhandar" in r.text
    assert f"Rs {r.balance:,.2f}" in r.text
    assert r.whatsapp_url.startswith("https://wa.me/919812345678?text=Namaste%20Ram")
    past = svc.for_bucket("past", TODAY)
    assert [x.customer_id for x in past] == [c.id]
    assert svc.for_bucket("future", TODAY) == []
    svc.set_template("{name}: {amount} due {date} ({days} days) - {shop} {village}")
    assert svc.build(c.id, today=TODAY).text.startswith("Ram Kumar: ")
    with pytest.raises(ValueError):
        svc.set_template("hello {unknown}")
    with pytest.raises(ValueError):
        svc.set_template("")
    no_phone = accounts.add_customer("shyam", "village only", 0)
    assert svc.build(no_phone.id, today=TODAY).whatsapp_url is None


def test_daily_backup(db, tmp_path):
    settings = Settings(data_dir=tmp_path)
    settings.ensure_dirs()
    b = BackupService(db, settings)
    assert b.enabled() and b.keep() == 14
    assert b.daily(dt.date(2026, 8, 30)).name == "hth_auto_20260830.db"
    assert b.daily(dt.date(2026, 8, 30)) is None  # once per day
    b.set_keep(2)
    b.daily(dt.date(2026, 8, 31))
    b.daily(dt.date(2026, 9, 1))
    assert [p.name for p in b.auto_backups()] == ["hth_auto_20260831.db", "hth_auto_20260901.db"]
    b.set_enabled(False)
    assert b.daily(dt.date(2026, 9, 2)) is None
    with pytest.raises(ValueError):
        b.set_keep(0)
    assert b.manual().exists() and b.last_backup() is not None
