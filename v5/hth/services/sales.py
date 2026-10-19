"""Sale / Receive workflow - orchestrates accounts, inventory and the audit log.

Mirrors ``SalesPage._process_transaction`` from v3, as one atomic transaction: if any
step fails nothing is written.

v4 additions:
* quantities are fractional and may be entered in any unit compatible with the item's
  stock unit (100 G of a KG item, 2 QTL of a KG crop); stock and price stay in the item's
  own unit (v3 truncated both to whole numbers)
* **crop items (type C)** are handed to the crop-trading handler: a receipt is a purchase
  lot from a farmer (gross, deduction, quality), a sale is FIFO-costed with margin.  The
  handler is registered by ``hth.modules.crop_trading`` when it loads; this is the one
  place the core knows that module exists (as a fallback import), so crop trades entered
  from the Sales screen and from tools behave identically.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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

log = logging.getLogger(__name__)

CROP_ITEM_TYPE = "C"
_crop_handler_factory: Callable[[Database], Any] | None = None
_money_flow_factory: Callable[[Database], Any] | None = None


def register_money_flow_handler(factory: Callable[[Database], Any]) -> None:
    """Called by the finance module; ``factory(db)`` must provide ``money_accounts()``,
    ``default_account_id()`` and ``record_customer_flow(...)``."""
    global _money_flow_factory
    _money_flow_factory = factory


def money_flow_handler(db: Database):
    if _money_flow_factory is None:
        try:
            importlib.import_module("hth.modules.finance")  # registers itself on import
        except ImportError:
            return None
    return _money_flow_factory(db) if _money_flow_factory else None


def register_crop_handler(factory: Callable[[Database], Any]) -> None:
    """Called by the crop-trading module; ``factory(db)`` must provide
    ``record_purchase(...)`` and ``record_sale(...)`` (see CropService)."""
    global _crop_handler_factory
    _crop_handler_factory = factory


def crop_handler(db: Database):
    if _crop_handler_factory is None:
        try:
            importlib.import_module("hth.modules.crop_trading")  # registers itself on import
        except ImportError:
            log.warning("crop trading module not available - crop items are treated as plain stock")
            return None
    return _crop_handler_factory(db) if _crop_handler_factory else None


@dataclass(frozen=True)
class SaleResult:
    transaction_ids: list[int]
    amount: float
    inventory_updated: bool
    audit_id: int
    stock_quantity: float = 0.0  # quantity in the item's stock unit
    stock_unit: str = ""
    # crop trades only
    crop_lot_id: int | None = None
    crop_sale_id: int | None = None
    money_account_id: int | None = None
    cost: float | None = None
    margin: float | None = None
    short_qty: float = 0.0

    @property
    def is_crop(self) -> bool:
        return self.crop_lot_id is not None or self.crop_sale_id is not None


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
        deduction: str | float | None = None,
        quality: str = "",
        notes: str = "",
        allow_short: bool = False,
        money_account_id: int | None = None,
    ) -> SaleResult:
        """``kind`` is 'P' for a sale (customer debited) or 'M' for a receipt (credited).

        ``price`` is per stock unit of the item.  ``unit`` is the unit the quantity was
        entered in; when it differs from the item's unit the quantity is converted.
        ``deduction``, ``quality``, ``notes`` and ``allow_short`` only apply to crop items.
        ``money_account_id``: for entries that move money rather than stock (no stock item),
        the cash/bank account the money went into (credit) or came out of (debit); recorded
        in the finance cash book when the finance module is present.
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

        if item is not None and item.item_type == CROP_ITEM_TYPE:
            crop = crop_handler(self.db)
            if crop is not None:
                return self._record_crop(
                    crop,
                    kind,
                    date,
                    customer_id,
                    item,
                    qty,
                    price_f,
                    tag,
                    username,
                    entry_unit or normalize(item.unit),
                    deduction,
                    quality,
                    notes,
                    allow_short,
                )

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
                    value=amount,
                )
                self.inventory.set_last_value(item.id, price_f)
                inventory_updated = True
            elif money_account_id is not None and tx_ids:
                flow = money_flow_handler(self.db)
                if flow is not None:
                    flow.record_customer_flow(
                        "receipt" if kind == "M" else "payment",
                        date,
                        money_account_id,
                        customer_id,
                        amount,
                        detail,
                        tx_ids[0],
                        username,
                    )

            code = AuditCode.SALE if kind == "P" else AuditCode.RECEIVE
            qty_note = f"{quantity} {entry_unit}".strip()
            audit_id = self.accounts.audit.log(
                code, f"{date}, {item_name}, {customer.name}, {qty_note}, {price}, {tag}", username
            )
        return SaleResult(
            tx_ids,
            amount,
            inventory_updated,
            audit_id,
            stock_qty,
            stock_unit,
            money_account_id=None if item is not None else money_account_id,
        )

    def _record_crop(
        self,
        crop,
        kind,
        date,
        customer_id,
        item,
        qty,
        price,
        tag,
        username,
        unit,
        deduction,
        quality,
        notes,
        allow_short,
    ) -> SaleResult:
        if tag == Tag.SETTLE.value:
            raise ValidationError(
                "Crop trades cannot carry tag 0. Record the trade with tag 1 or 2 and settle "
                "the account with a separate CASH entry."
            )
        with self.db.connect():
            if kind == "M":  # receipt of goods = purchase from a farmer
                lot = crop.record_purchase(
                    date,
                    customer_id,
                    item.id,
                    qty,
                    deduction or 0,
                    price,
                    unit,
                    username,
                    quality=quality or "",
                    notes=notes or "",
                    tag=tag,
                )
                self.inventory.set_last_value(item.id, price)
                return SaleResult(
                    [lot.tx_id] if lot.tx_id else [],
                    lot.amount,
                    True,
                    0,
                    lot.qty,
                    normalize(item.unit),
                    crop_lot_id=lot.id,
                )
            sale = crop.record_sale(
                date,
                item.id,
                qty,
                price,
                unit,
                username,
                buyer_id=customer_id,
                tag=tag,
                notes=notes or "",
                allow_short=allow_short,
            )
            self.inventory.set_last_value(item.id, price)
            return SaleResult(
                [sale.tx_id] if sale.tx_id else [],
                sale.amount,
                True,
                0,
                sale.qty,
                normalize(item.unit),
                crop_sale_id=sale.id,
                cost=sale.cost,
                margin=sale.margin,
                short_qty=sale.short_qty,
            )
