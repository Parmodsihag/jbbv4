"""Sale / Receive workflow - orchestrates accounts, inventory and the audit log.

Mirrors ``SalesPage._process_transaction`` from v3, as one atomic transaction: if any
step fails nothing is written.

v4 changes (requested): quantities are fractional and may be entered in any unit
compatible with the item's stock unit (100 G of a KG item, 2 QTL of a KG crop).  Stock and
price stay in the item's own unit; v3 truncated both to whole numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from hth.db.connection import Database
from hth.domain.constants import AuditCode, Tag
from hth.domain.units import UnitError, convert, normalize
from hth.services.accounts import (
    AccountsService,
    ValidationError,
    _validate_amount,
    _validate_date,
)
from hth.services.inventory import InventoryService


@dataclass(frozen=True)
class SaleResult:
    transaction_ids: list[int]
    amount: float
    inventory_updated: bool
    audit_id: int
    stock_quantity: float = 0.0  # quantity in the item's stock unit
    stock_unit: str = ""


def _qty_text(q: float) -> str:
    return f"{q:.4f}".rstrip("0").rstrip(".") if not float(q).is_integer() else str(int(q))


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
        unit: str | None = None,
    ) -> SaleResult:
        """``kind`` is 'P' for a sale (customer debited) or 'M' for a receipt (credited).

        ``price`` is per stock unit of the item.  ``unit`` is the unit the quantity was
        entered in; when it differs from the item's unit the quantity is converted.
        """
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
        if qty <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        price_f = _validate_amount(price)
        tag = str(tag).strip()[:1]
        if tag not in {t.value for t in Tag}:
            raise ValidationError("Tag must be 0, 1 or 2.")

        item = self.inventory.get_item(item_id) if item_id is not None else None
        entry_unit = normalize(unit) if unit else ""
        stock_unit = normalize(item.unit) if item else entry_unit
        stock_qty = qty
        if item and entry_unit and entry_unit != stock_unit:
            try:
                stock_qty = convert(qty, entry_unit, stock_unit)
            except UnitError as exc:
                raise ValidationError(f"{exc} Enter the quantity in {stock_unit} or a compatible unit.") from exc
        stock_qty = round(stock_qty, 4)

        amount = round(price_f * stock_qty, 2)
        if not entry_unit:
            detail = f"{quantity} = {item_name}"  # v3 format
        elif entry_unit == stock_unit:
            detail = f"{_qty_text(qty)} {entry_unit} = {item_name}"
        else:
            detail = f"{_qty_text(qty)} {entry_unit} ({_qty_text(stock_qty)} {stock_unit}) = {item_name}"

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
            if item is not None:
                self.inventory.add_item_transaction(
                    item.id,
                    date,
                    received=stock_qty if kind == "M" else 0,
                    sale=stock_qty if kind == "P" else 0,
                    description=customer.name,
                    username=username,
                    audit=False,
                )
                self.inventory.set_last_value(item.id, price_f)
                inventory_updated = True

            code = AuditCode.SALE if kind == "P" else AuditCode.RECEIVE
            qty_note = f"{quantity} {entry_unit}".strip()
            audit_id = self.accounts.audit.log(
                code, f"{date}, {item_name}, {customer.name}, {qty_note}, {price}, {tag}", username
            )
        return SaleResult(tx_ids, amount, inventory_updated, audit_id, stock_qty, stock_unit)
