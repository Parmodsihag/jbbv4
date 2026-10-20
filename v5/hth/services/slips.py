"""Counter slip: a small print-ready receipt for the entry just made on the Sales screen.

Sized for 80 mm thermal printers but prints fine on A4 too; opened in the browser, where
Print (or Save as PDF) takes over - the same approach as customer statements.
"""

from __future__ import annotations

import datetime as dt
from html import escape
from pathlib import Path

from hth.db.connection import Database
from hth.domain import numbers
from hth.i18n import name as hi_name
from hth.i18n import tr as t
from hth.i18n import tr_cell
from hth.services.accounts import AccountsService, ValidationError
from hth.services.company import CompanyService

_CSS = """
body{font-family:'Segoe UI','Nirmala UI',Mangal,Arial,sans-serif;font-size:12px;color:#111;margin:0;padding:12px}
.slip{max-width:300px;margin:0 auto}
h1{font-size:16px;margin:0;text-align:center;letter-spacing:.5px}
.c{text-align:center}.m{color:#555}.r{text-align:right}
table{width:100%;border-collapse:collapse;margin-top:6px}
td{padding:3px 0;vertical-align:top}
.rule{border-top:1px dashed #555;margin:6px 0}
.tot td{font-weight:700;font-size:14px;border-top:1px solid #111;padding-top:5px}
@media print{body{padding:0}.noprint{display:none}@page{size:80mm auto;margin:4mm}}
button{margin:12px auto;display:block;padding:6px 16px}
"""


class SlipService:
    def __init__(self, db: Database):
        self.db = db
        self.accounts = AccountsService(db)
        self.company = CompanyService(db)

    def html(self, results: list, customer_id: int, username: str = "", now: dt.datetime | None = None) -> str:
        """``results``: SaleResults from one Sales-screen post (same account)."""
        if not results:
            raise ValidationError("Nothing to print.")
        c = self.accounts.get_customer(customer_id)
        if c is None:
            raise ValidationError("Customer not found.")
        now = now or dt.datetime.now()
        shop = self.company.profile()
        kind = results[0].kind
        title = t("SALE" if kind == "P" else "RECEIPT")
        lines = "".join(
            f"<tr><td>{escape(tr_cell(r.description or ''))}</td><td class='r'>{numbers.amount(r.amount)}</td></tr>"
            for r in results
        )
        total = round(sum(r.amount for r in results), 2)
        balance = self.accounts.get_balance(customer_id)
        state = t("due" if balance > 0 else ("in your favour" if balance < 0 else "settled"))
        ref = min((tx for r in results for tx in r.transaction_ids), default=0)
        gstin = f"<div class='c m'>GSTIN {escape(shop.gstin)}</div>" if shop.gstin else ""
        details = escape(hi_name(c.other_details))
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title} {ref}</title>
<style>{_CSS}</style></head><body><div class="slip">
<h1>{escape(shop.name)}</h1>
<div class="c m">{escape(shop.address)}</div>
<div class="c m">{escape(shop.phone)}</div>{gstin}
<div class="rule"></div>
<table><tr><td><b>{title}</b> #{ref}</td><td class="r">{now:%d-%m-%Y %H:%M}</td></tr>
<tr><td colspan="2">{escape(hi_name(c.name))} <span class="m">#{c.id} {details}</span></td></tr></table>
<div class="rule"></div>
<table>{lines}<tr class="tot"><td>{t("Total")}</td><td class="r">{numbers.amount(total)}</td></tr></table>
<div class="rule"></div>
<table><tr><td>{t("Account balance")}</td><td class="r">{numbers.amount(abs(balance))} {state}</td></tr></table>
<div class="c m" style="margin-top:8px">{t("Thank you")}{(" · " + escape(username)) if username else ""}</div>
<button class="noprint" onclick="window.print()">{t("Print")}</button>
</div></body></html>"""

    def write(self, results: list, customer_id: int, out_dir: Path, username: str = "") -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        ref = min((tx for r in results for tx in r.transaction_ids), default=0)
        path = out_dir / f"slip_{ref}_{dt.datetime.now():%Y%m%d_%H%M%S}.html"
        path.write_text(self.html(results, customer_id, username), encoding="utf-8")
        return path
