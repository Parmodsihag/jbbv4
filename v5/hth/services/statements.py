"""Customer statement: a print-ready HTML page for a date range.

Uses the same ledger rows as the screen (per-row interest, running balance that resets at
settlements), so what the customer receives matches what the shop sees.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from html import escape
from pathlib import Path

from hth.db.connection import Database
from hth.domain import numbers
from hth.domain.constants import ANNUAL_INTEREST_RATE_PERCENT, DATE_FMT
from hth.domain.interest import parse_date
from hth.domain.models import LedgerRow
from hth.i18n import name as hi_name
from hth.i18n import tr as t
from hth.i18n import tr_cell
from hth.services.accounts import AccountsService, ValidationError, _validate_date
from hth.services.company import CompanyService
from hth.services.export import safe_filename


@dataclass(frozen=True)
class Statement:
    customer_id: int
    customer_name: str
    customer_details: str
    date_from: str
    date_to: str
    rows: list[LedgerRow]
    opening_balance: float
    closing_balance: float
    total_debit: float
    total_credit: float
    total_interest: float
    generated_at: str


def _money(v: float | None) -> str:
    return "" if v is None else numbers.amount(v)


class StatementService:
    def __init__(self, db: Database):
        self.db = db
        self.accounts = AccountsService(db)
        self.company = CompanyService(db)

    def build(self, customer_id: int, date_from: str, date_to: str, as_of: dt.date | None = None) -> Statement:
        customer = self.accounts.get_customer(customer_id)
        if customer is None:
            raise ValidationError("Customer not found.")
        date_from, date_to = _validate_date(date_from), _validate_date(date_to)
        if date_from > date_to:
            raise ValidationError("'From' must not be after 'To'.")
        as_of = as_of or parse_date(date_to)
        all_rows = self.accounts.ledger(customer_id, as_of)
        before = [r for r in all_rows if r.date < date_from]
        rows = [r for r in all_rows if date_from <= r.date <= date_to]
        opening = before[-1].balance if before else 0.0
        closing = rows[-1].balance if rows else opening
        return Statement(
            customer.id,
            customer.name,
            customer.other_details,
            date_from,
            date_to,
            rows,
            round(opening, 2),
            round(closing, 2),
            round(sum(r.debit or 0 for r in rows), 2),
            round(sum(r.credit or 0 for r in rows), 2),
            round(sum(r.interest or 0 for r in rows if r.tag != "0"), 2),
            dt.datetime.now().strftime("%d-%m-%Y %H:%M"),
        )

    def html(self, statement: Statement) -> str:
        c = self.company.profile()
        s = statement
        owes = s.closing_balance > 0
        body_rows = "\n".join(
            f"<tr class='{'settle' if r.tag == '0' else ''}'><td>{escape(r.date)}</td>"
            f"<td class='l'>{escape(tr_cell(r.particulars))}</td><td>{_money(r.interest) if r.tag != '0' else ''}</td>"
            f"<td>{_money(r.debit)}</td><td>{_money(r.credit)}</td><td>{_money(r.balance)}</td></tr>"
            for r in s.rows
        )
        if not body_rows:
            body_rows = f"<tr><td colspan='6' class='l muted'>{t('No entries in this period.')}</td></tr>"
        name, details = hi_name(s.customer_name), hi_name(s.customer_details)
        state = t("due from you") if owes else (t("in your favour") if s.closing_balance < 0 else t("(settled)"))
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(t(f"Statement - {name}"))}</title>
<style>
  body {{ font-family: 'Segoe UI', 'Nirmala UI', Mangal, Helvetica, Arial, sans-serif; color: #111; margin: 24px; font-size: 13px; }}
  .head {{ display: flex; justify-content: space-between; border-bottom: 2px solid #0e7490; padding-bottom: 10px; }}
  .head h1 {{ margin: 0; font-size: 22px; color: #0e7490; }} .head .sub {{ color: #555; }}
  .meta {{ display: flex; justify-content: space-between; margin: 14px 0; }}
  .box {{ border: 1px solid #ddd; border-radius: 6px; padding: 10px 14px; min-width: 260px; }}
  .box b {{ display: block; font-size: 15px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ border-bottom: 1px solid #e5e7eb; padding: 6px 8px; text-align: right; white-space: nowrap; }}
  th {{ background: #f1f5f9; text-align: right; }} th.l, td.l {{ text-align: left; white-space: normal; }}
  tr.settle td {{ color: #6b7280; font-style: italic; }} .muted {{ color: #6b7280; }}
  .totals td {{ font-weight: bold; border-top: 2px solid #0e7490; }}
  .closing {{ margin-top: 16px; font-size: 16px; }} .closing b {{ color: {"#b91c1c" if owes else "#15803d"}; }}
  .foot {{ margin-top: 28px; color: #555; font-size: 11px; border-top: 1px solid #ddd; padding-top: 8px; }}
  .sign {{ margin-top: 40px; display: flex; justify-content: space-between; }}
  @media print {{ body {{ margin: 10mm; }} .noprint {{ display: none; }} }}
</style></head><body>
<div class="noprint" style="text-align:right"><button onclick="window.print()">{t("Print / Save as PDF")}</button></div>
<div class="head">
  <div><h1>{escape(c.name)}</h1><div class="sub">{escape(c.tagline)}</div><div class="sub">{escape(c.address)}</div></div>
  <div style="text-align:right" class="sub">{t(f"Mobile {c.phone}")}<br>GSTIN {escape(c.gstin)}<br>{escape(c.licences)}</div>
</div>
<div class="meta">
  <div class="box"><span class="muted">{t("Statement of account")}</span><b>{escape(name)}</b>
    {escape(details)}<br><span class="muted">{t(f"Account #{s.customer_id}")}</span></div>
  <div class="box"><span class="muted">{t("Period")}</span><b>{t(f"{s.date_from} to {s.date_to}")}</b>
    {t(f"Generated {s.generated_at}")}<br><span class="muted">{t(f"Interest {ANNUAL_INTEREST_RATE_PERCENT:g}% p.a. on tag-1 entries, compounded 31 March")}</span></div>
</div>
<table>
  <thead><tr><th class="l">{t("Date")}</th><th class="l">{t("Particulars")}</th><th>{t("Interest")}</th><th>{t("Debit")}</th><th>{t("Credit")}</th><th>{t("Balance")}</th></tr></thead>
  <tbody>
    <tr><td></td><td class="l">{t("Opening balance")}</td><td></td><td></td><td></td><td>{_money(s.opening_balance)}</td></tr>
    {body_rows}
    <tr class="totals"><td></td><td class="l">{t("Totals for period")}</td><td>{_money(s.total_interest)}</td><td>{_money(s.total_debit)}</td><td>{_money(s.total_credit)}</td><td>{_money(s.closing_balance)}</td></tr>
  </tbody>
</table>
<div class="closing">{t("Closing balance:")} <b>{_money(abs(s.closing_balance))} {state}</b></div>
<div class="sign"><div>{t("Customer signature: ______________________")}</div><div>{escape(t(f"For {c.name}: ______________________"))}</div></div>
<div class="foot">{escape(c.footer)}</div>
</body></html>
"""

    def write(self, statement: Statement, export_dir: Path) -> Path:
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / (
            f"statement_{safe_filename(statement.customer_name)}_{statement.date_from}_{statement.date_to}.html"
        )
        path.write_text(self.html(statement), encoding="utf-8")
        return path


def financial_year_start(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    year = today.year if today.month >= 4 else today.year - 1
    return dt.date(year, 4, 1).strftime(DATE_FMT)
