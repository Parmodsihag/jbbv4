"""Payment reminder messages for krar (promised dates) and overdue balances."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from urllib.parse import quote

from hth.db.connection import Database
from hth.domain import numbers
from hth.domain.interest import parse_date
from hth.services.accounts import AccountsService
from hth.services.company import CompanyService
from hth.services.krar import KrarService
from hth.services.settings import SettingsService

DEFAULT_TEMPLATE = (
    "Namaste {name} ji, your balance at {shop} is Rs {amount}. "
    "As agreed, please clear it by {date}. Thank you.\n- {shop}, {phone}"
)
PLACEHOLDERS = ["name", "amount", "date", "days", "shop", "phone", "village"]
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{9})(?!\d)")


@dataclass(frozen=True)
class Reminder:
    customer_id: int
    customer_name: str
    balance: float
    promised: str
    days_overdue: int
    phone: str | None
    text: str

    @property
    def whatsapp_url(self) -> str | None:
        return f"https://wa.me/91{self.phone}?text={quote(self.text)}" if self.phone else None


def extract_phone(text: str) -> str | None:
    m = PHONE_RE.search(text or "")
    return m.group(1) if m else None


class ReminderService:
    def __init__(self, db: Database):
        self.db = db
        self.settings = SettingsService(db, {"reminder.template": DEFAULT_TEMPLATE})
        self.accounts = AccountsService(db)
        self.krar = KrarService(db)
        self.company = CompanyService(db)

    def template(self) -> str:
        return self.settings.get("reminder.template") or DEFAULT_TEMPLATE

    def set_template(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            raise ValueError("Template cannot be empty.")
        try:
            text.format(**{k: "x" for k in PLACEHOLDERS})
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f"Unknown placeholder in template: {exc}. Use {{{'}, {'.join(PLACEHOLDERS)}}}.") from exc
        self.settings.set("reminder.template", text)

    def build(self, customer_id: int, promised: str | None = None, today: dt.date | None = None) -> Reminder:
        today = today or dt.date.today()
        c = self.accounts.get_customer(customer_id)
        if c is None:
            raise ValueError("Customer not found.")
        if promised is None:
            dates = self.krar.unsettled_dates(customer_id)
            promised = max(dates) if dates else today.strftime("%Y-%m-%d")
        balance = self.accounts.get_balance(customer_id, today)
        days = (today - parse_date(promised)).days
        shop = self.company.profile()
        text = self.template().format(
            name=c.name.title(),
            amount=numbers.amount(balance),
            date=parse_date(promised).strftime("%d-%m-%Y"),
            days=max(0, days),
            shop=shop.name.title(),
            phone=shop.phone,
            village=c.other_details.title(),
        )
        return Reminder(c.id, c.name, balance, promised, days, extract_phone(c.other_details), text)

    def balance_message(self, customer_id: int, today: dt.date | None = None) -> Reminder:
        """'Your balance as of <date> is ...' - for any account, promise or not."""
        today = today or dt.date.today()
        c = self.accounts.get_customer(customer_id)
        if c is None:
            raise ValueError("Customer not found.")
        balance = self.accounts.get_balance(customer_id, today)
        shop = self.company.profile()
        if balance > 0:
            line = f"your balance at {shop.name.title()} as of {today:%d-%m-%Y} is Rs {numbers.amount(balance)}."
        elif balance < 0:
            line = f"as of {today:%d-%m-%Y} {shop.name.title()} owes you Rs {numbers.amount(-balance)}."
        else:
            line = f"your account at {shop.name.title()} is fully settled as of {today:%d-%m-%Y}. Thank you."
        text = f"Namaste {c.name.title()} ji, {line}\n- {shop.name.title()}, {shop.phone}"
        return Reminder(c.id, c.name, balance, today.isoformat(), 0, extract_phone(c.other_details), text)

    def for_bucket(self, bucket: str = "past", today: dt.date | None = None) -> list[Reminder]:
        return [self.build(e.customer_id, e.last_date, today) for e in self.krar.entries(bucket, today)]
