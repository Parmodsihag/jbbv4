"""Sale / Receive workflow - orchestrates accounts, inventory and the audit log.

Mirrors ``SalesPage._process_transaction`` from v3 exactly, but as one atomic
transaction: if any step fails nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass

from hth.db.connection import Database
from hth.domain.constants import AuditCode, Tag
from hth.services.accounts import AccountsService, ValidationError, _validate_amount, _validate_date
from hth.services.inventory import InventoryService


@dataclass(frozen=True)
class SaleResult:
    transaction_ids: list[int]
    amount: float
    inventory_updated: bool
    audit_id: int


class SalesService:
    def __init__(self, db: Database):
        self.db = db
        self.accounts = AccountsService(db)
        self.inventory = InventoryService(db)

    def record(
        self,
        kind: str,
        date: str,
        customer_id: int,
        item_name: str,
        quantity: str | float,
        price: str | float,
        tag: str | int,
        username: str,
        item_id: int | None = None,
    ) -> SaleResult:
        """``kind`` is 'P' for a sale (customer debited) or 'M' for a receipt (credited)."""
        kind = (kind or "").upper()
        if kind not in ("P", "M"):
            raise ValidationError("Kind must be P (sale) or M (receive).")
        date = _validate_date(date)
        customer = self.accounts.get_customer(customer_id)
        if customer is None:
            raise ValidationError("Select a valid account.")
        item_name = (item_name or "").strip()
        if not item_name:
            raise ValidationError("Item is required.")
        qty = _validate_amount(quantity)
        price_f = _validate_amount(price)
        tag = str(tag).strip()[:1]
        if tag not in {t.value for t in Tag}:
            raise ValidationError("Tag must be 0, 1 or 2.")

        amount = round(price_f * qty, 2)
        detail = f"{quantity} = {item_name}"

        with self.db.connect():
            before = self.db.fetchone("SELECT COALESCE(MAX(id), 0) AS m FROM transactions")["m"]
            if tag == Tag.SETTLE.value:
                self.accounts.record_settlement(customer_id, date, detail, amount, kind, username)
            else:
                self.accounts.add_transaction(customer_id, date, detail, amount, kind, tag, username, audit=False)
            tx_ids = [
                r["id"] for r in self.db.fetchall("SELECT id FROM transactions WHERE id > ? ORDER BY id", (before,))
            ]

            inventory_updated = False
            if item_id is not None and self.inventory.get_item(item_id) is not None:
                # v3 truncated quantity and price to int for the stock ledger / last price.
                whole_qty = int(qty)
                self.inventory.add_item_transaction(
                    item_id,
                    date,
                    received=whole_qty if kind == "M" else 0,
                    sale=whole_qty if kind == "P" else 0,
                    description=customer.name,
                    username=username,
                    audit=False,
                )
                self.inventory.set_last_value(item_id, int(price_f))
                inventory_updated = True

            code = AuditCode.SALE if kind == "P" else AuditCode.RECEIVE
            audit_id = self.accounts.audit.log(
                code, f"{date}, {item_name}, {customer.name}, {quantity}, {price}, {tag}", username
            )
        return SaleResult(tx_ids, amount, inventory_updated, audit_id)
