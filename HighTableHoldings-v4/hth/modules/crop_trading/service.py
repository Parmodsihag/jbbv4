"""Crop trading rules.

* A crop is an inventory item with ``item_type = 'C'``; stock is kept in its unit (KG).
* A purchase from a farmer is a **lot**: gross quantity, deduction ("kaat" - v3 k_quantity),
  net = gross - deduction, rate per unit, quality grade.  It credits the farmer's ledger
  (we owe them), adds stock, and stays as a cost layer.
* A sale to a buyer is costed **FIFO against open lots**; margin = amount - cost.  It debits
  the buyer's ledger (unless a cash sale) and reduces stock.
* Stock value = remaining lot quantity x lot rate (what we actually paid);
  market value = remaining quantity x latest market rate.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.models import Customer, Item
from hth.domain.units import UnitError, convert, normalize
from hth.modules.crop_trading.rates import RatesService
from hth.services.accounts import AccountsService, ValidationError, _validate_amount, _validate_date
from hth.services.audit import AuditService
from hth.services.inventory import InventoryService

CROP_TYPE = "C"
QUALITY_GRADES = ["A", "B", "C", "MIX"]
CASH_BUYER = "CASH"


@dataclass(frozen=True)
class Lot:
    id: int
    date: str
    farmer_id: int
    farmer_name: str
    item_id: int
    crop_name: str
    unit: str
    gross_qty: float
    deduction_qty: float
    qty: float
    remaining_qty: float
    rate: float
    amount: float
    quality: str
    notes: str
    tx_id: int | None
    stock_tx_id: int | None


@dataclass(frozen=True)
class Allocation:
    lot_id: int | None
    qty: float
    cost_rate: float
    cost: float


@dataclass(frozen=True)
class Sale:
    id: int
    date: str
    buyer_id: int | None
    buyer_name: str
    item_id: int
    crop_name: str
    unit: str
    qty: float
    rate: float
    amount: float
    cost: float
    margin: float
    short_qty: float
    notes: str
    tx_id: int | None
    stock_tx_id: int | None
    allocations: list[Allocation] = field(default_factory=list)

    @property
    def margin_pct(self) -> float:
        return round(self.margin / self.cost * 100, 2) if self.cost else 0.0


@dataclass(frozen=True)
class CropStock:
    item: Item
    qty: float  # remaining across lots
    inventory_qty: float  # per item_transactions (should match; differs if stock edited elsewhere)
    cost_value: float
    avg_cost: float
    market_rate: float | None
    market_date: str | None
    market_value: float | None
    unrealized: float | None
    lots: int


@dataclass(frozen=True)
class CostPreview:
    covered_qty: float
    cost: float
    short_qty: float
    allocations: list[Allocation]


class CropService:
    def __init__(self, db: Database):
        self.db = db
        self.accounts = AccountsService(db)
        self.inventory = InventoryService(db)
        self.rates = RatesService(db)
        self.audit = AuditService(db)

    # Masters -----------------------------------------------------------------------------
    def crops(self) -> list[Item]:
        return [i for i in self.inventory.list_items() if i.item_type == CROP_TYPE]

    def add_crop(self, name: str, unit: str = "KG", username: str = "system") -> Item:
        unit = normalize(unit) or "KG"
        for existing in self.crops():
            if existing.name == (name or "").strip().upper():
                raise ValidationError(f"Crop '{existing.name}' already exists (#{existing.id}).")
        return self.inventory.add_item(
            name,
            0,
            0,
            unit=unit,
            item_type=CROP_TYPE,
            pakka_kacha="K",
            opening_quantity=0,
            source="CROP",
            username=username,
        )

    def get_crop(self, item_id: int) -> Item:
        item = self.inventory.get_item(item_id)
        if item is None or item.item_type != CROP_TYPE:
            raise ValidationError("Pick a crop (an item of type C).")
        return item

    def parties(self) -> list[Customer]:
        return self.accounts.list_customers()

    def add_party(self, name: str, details: str = "", username: str = "system") -> Customer:
        return self.accounts.add_customer(name, details, 0, username=username)

    # Purchases ---------------------------------------------------------------------------
    def record_purchase(
        self,
        date: str,
        farmer_id: int,
        item_id: int,
        gross_qty,
        deduction_qty,
        rate,
        unit: str | None,
        username: str,
        quality: str = "",
        notes: str = "",
        tag: str = "2",
    ) -> Lot:
        date = _validate_date(date)
        farmer = self.accounts.get_customer(farmer_id)
        if farmer is None:
            raise ValidationError("Pick a farmer account.")
        item = self.get_crop(item_id)
        gross = _validate_amount(gross_qty)
        ded = _validate_amount(deduction_qty or 0)
        rate_f = _validate_amount(rate)
        if gross <= 0:
            raise ValidationError("Gross quantity must be greater than zero.")
        if ded > gross:
            raise ValidationError("Deduction cannot exceed the gross quantity.")
        entry_unit = normalize(unit) if unit else normalize(item.unit)
        try:
            gross = round(convert(gross, entry_unit, item.unit), 4)
            ded = round(convert(ded, entry_unit, item.unit), 4)
        except UnitError as exc:
            raise ValidationError(f"{exc} Enter quantities in {normalize(item.unit)} or a compatible unit.") from exc
        net = round(gross - ded, 4)
        if net <= 0:
            raise ValidationError("Net quantity must be greater than zero.")
        amount = round(net * rate_f, 2)
        quality = (quality or "").strip().upper()
        desc = f"CROP PURCHASE {net:g} {normalize(item.unit)} {item.name} @ {rate_f:g}"
        if quality:
            desc += f" [{quality}]"
        with self.db.connect():
            tx_id = self.accounts.add_transaction(farmer_id, date, desc, amount, "M", tag, username, audit=False)
            stock_tx = self.inventory.add_item_transaction(
                item.id, date, net, 0, f"CROP {farmer.name}", "crop", username, audit=False
            )
            lot_id = self.db.execute(
                "INSERT INTO crop_lots (date, farmer_id, item_id, gross_qty, deduction_qty, qty, remaining_qty,"
                " rate, amount, quality, notes, tx_id, stock_tx_id, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    date,
                    farmer_id,
                    item.id,
                    gross,
                    ded,
                    net,
                    net,
                    rate_f,
                    amount,
                    quality,
                    (notes or "").strip(),
                    tx_id,
                    stock_tx,
                    username,
                ),
            )
            self.audit.log(
                AuditCode.CROP, f"purchase lot {lot_id}: {date}, {farmer.name}, {desc}, {amount:.2f}", username
            )
        return self.get_lot(lot_id)  # type: ignore[return-value]

    def _lot(self, r) -> Lot:
        return Lot(
            r["id"],
            r["date"],
            r["farmer_id"],
            r["farmer_name"],
            r["item_id"],
            r["crop_name"],
            r["unit"],
            r["gross_qty"],
            r["deduction_qty"],
            r["qty"],
            r["remaining_qty"],
            r["rate"],
            r["amount"],
            r["quality"],
            r["notes"],
            r["tx_id"],
            r["stock_tx_id"],
        )

    _LOT_SQL = (
        "SELECT l.*, c.name AS farmer_name, i.name AS crop_name, i.unit FROM crop_lots l "
        "JOIN customers c ON c.id = l.farmer_id JOIN items i ON i.id = l.item_id "
    )

    def get_lot(self, lot_id: int) -> Lot | None:
        r = self.db.fetchone(self._LOT_SQL + "WHERE l.id = ?", (lot_id,))
        return self._lot(r) if r else None

    def lots(
        self,
        item_id: int | None = None,
        farmer_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        open_only: bool = False,
        limit: int = 2000,
    ) -> list[Lot]:
        clauses, params = [], []
        if item_id:
            clauses.append("l.item_id = ?")
            params.append(item_id)
        if farmer_id:
            clauses.append("l.farmer_id = ?")
            params.append(farmer_id)
        if date_from:
            clauses.append("l.date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("l.date <= ?")
            params.append(date_to)
        if open_only:
            clauses.append("l.remaining_qty > 0")
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        rows = self.db.fetchall(self._LOT_SQL + where + "ORDER BY l.date DESC, l.id DESC LIMIT ?", (*params, limit))
        return [self._lot(r) for r in rows]

    def delete_lot(self, lot_id: int, username: str) -> None:
        lot = self.get_lot(lot_id)
        if lot is None:
            return
        if lot.remaining_qty < lot.qty:
            raise ValidationError("This lot has already been (partly) sold - delete those sales first.")
        with self.db.connect():
            self.db.execute("DELETE FROM crop_lots WHERE id = ?", (lot_id,))
            if lot.tx_id:
                self.db.execute("DELETE FROM transactions WHERE id = ?", (lot.tx_id,))
            if lot.stock_tx_id:
                self.db.execute("DELETE FROM item_transactions WHERE id = ?", (lot.stock_tx_id,))
            self.audit.log(
                AuditCode.DELETE, f"purchase lot {lot_id} ({lot.farmer_name}, {lot.crop_name} {lot.qty:g})", username
            )

    # Sales -------------------------------------------------------------------------------
    def preview_cost(self, item_id: int, qty: float) -> CostPreview:
        rows = self.db.fetchall(
            "SELECT id, rate, remaining_qty FROM crop_lots WHERE item_id = ? AND remaining_qty > 0 ORDER BY date, id",
            (item_id,),
        )
        left, allocations, cost = round(float(qty), 4), [], 0.0
        for r in rows:
            if left <= 0:
                break
            take = min(left, float(r["remaining_qty"]))
            line_cost = round(take * float(r["rate"]), 2)
            allocations.append(Allocation(r["id"], take, float(r["rate"]), line_cost))
            cost += line_cost
            left = round(left - take, 4)
        return CostPreview(round(float(qty) - left, 4), round(cost, 2), left, allocations)

    def fallback_rate(self, item_id: int) -> float:
        r = self.db.fetchone(
            "SELECT rate FROM crop_lots WHERE item_id = ? ORDER BY date DESC, id DESC LIMIT 1", (item_id,)
        )
        if r:
            return float(r["rate"])
        latest = self.rates.latest(item_id)
        return latest[0] if latest else 0.0

    def record_sale(
        self,
        date: str,
        item_id: int,
        qty,
        rate,
        unit: str | None,
        username: str,
        buyer_id: int | None = None,
        buyer_name: str = "",
        tag: str = "2",
        notes: str = "",
        allow_short: bool = False,
    ) -> Sale:
        date = _validate_date(date)
        item = self.get_crop(item_id)
        q = _validate_amount(qty)
        rate_f = _validate_amount(rate)
        if q <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        entry_unit = normalize(unit) if unit else normalize(item.unit)
        try:
            q = round(convert(q, entry_unit, item.unit), 4)
        except UnitError as exc:
            raise ValidationError(f"{exc} Enter the quantity in {normalize(item.unit)} or a compatible unit.") from exc
        buyer = self.accounts.get_customer(buyer_id) if buyer_id else None
        if buyer_id and buyer is None:
            raise ValidationError("Pick a buyer account, or leave it blank for a cash sale.")
        name = buyer.name if buyer else ((buyer_name or "").strip().upper() or CASH_BUYER)
        amount = round(q * rate_f, 2)

        preview = self.preview_cost(item.id, q)
        if preview.short_qty > 0 and not allow_short:
            raise ValidationError(
                f"Only {preview.covered_qty:g} {normalize(item.unit)} of {item.name} in stock "
                f"({preview.short_qty:g} short). Record the purchase first, or allow selling short."
            )
        allocations = list(preview.allocations)
        cost = preview.cost
        if preview.short_qty > 0:
            fb = self.fallback_rate(item.id)
            allocations.append(Allocation(None, preview.short_qty, fb, round(preview.short_qty * fb, 2)))
            cost = round(cost + preview.short_qty * fb, 2)
        margin = round(amount - cost, 2)
        desc = f"CROP SALE {q:g} {normalize(item.unit)} {item.name} @ {rate_f:g}"
        with self.db.connect():
            tx_id = None
            if buyer:
                tx_id = self.accounts.add_transaction(buyer.id, date, desc, amount, "P", tag, username, audit=False)
            stock_tx = self.inventory.add_item_transaction(
                item.id, date, 0, q, f"CROP {name}", "crop", username, audit=False
            )
            sale_id = self.db.execute(
                "INSERT INTO crop_sales (date, buyer_id, buyer_name, item_id, qty, rate, amount, cost, margin,"
                " short_qty, notes, tx_id, stock_tx_id, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    date,
                    buyer.id if buyer else None,
                    name,
                    item.id,
                    q,
                    rate_f,
                    amount,
                    cost,
                    margin,
                    preview.short_qty,
                    (notes or "").strip(),
                    tx_id,
                    stock_tx,
                    username,
                ),
            )
            for a in allocations:
                self.db.execute(
                    "INSERT INTO crop_sale_lots (sale_id, lot_id, qty, cost_rate, cost) VALUES (?, ?, ?, ?, ?)",
                    (sale_id, a.lot_id, a.qty, a.cost_rate, a.cost),
                )
                if a.lot_id is not None:
                    self.db.execute(
                        "UPDATE crop_lots SET remaining_qty = ROUND(remaining_qty - ?, 4) WHERE id = ?",
                        (a.qty, a.lot_id),
                    )
            self.audit.log(
                AuditCode.CROP, f"sale {sale_id}: {date}, {name}, {desc}, {amount:.2f}, margin {margin:.2f}", username
            )
        return self.get_sale(sale_id)  # type: ignore[return-value]

    _SALE_SQL = "SELECT s.*, i.name AS crop_name, i.unit FROM crop_sales s JOIN items i ON i.id = s.item_id "

    def _sale(self, r, with_allocations: bool = True) -> Sale:
        allocs = []
        if with_allocations:
            allocs = [
                Allocation(a["lot_id"], a["qty"], a["cost_rate"], a["cost"])
                for a in self.db.fetchall("SELECT * FROM crop_sale_lots WHERE sale_id = ? ORDER BY id", (r["id"],))
            ]
        return Sale(
            r["id"],
            r["date"],
            r["buyer_id"],
            r["buyer_name"],
            r["item_id"],
            r["crop_name"],
            r["unit"],
            r["qty"],
            r["rate"],
            r["amount"],
            r["cost"],
            r["margin"],
            r["short_qty"],
            r["notes"],
            r["tx_id"],
            r["stock_tx_id"],
            allocs,
        )

    def get_sale(self, sale_id: int) -> Sale | None:
        r = self.db.fetchone(self._SALE_SQL + "WHERE s.id = ?", (sale_id,))
        return self._sale(r) if r else None

    def sales(
        self,
        item_id: int | None = None,
        buyer_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 2000,
    ) -> list[Sale]:
        clauses, params = [], []
        if item_id:
            clauses.append("s.item_id = ?")
            params.append(item_id)
        if buyer_id:
            clauses.append("s.buyer_id = ?")
            params.append(buyer_id)
        if date_from:
            clauses.append("s.date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("s.date <= ?")
            params.append(date_to)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        rows = self.db.fetchall(self._SALE_SQL + where + "ORDER BY s.date DESC, s.id DESC LIMIT ?", (*params, limit))
        return [self._sale(r, with_allocations=False) for r in rows]

    def delete_sale(self, sale_id: int, username: str) -> None:
        sale = self.get_sale(sale_id)
        if sale is None:
            return
        with self.db.connect():
            for a in sale.allocations:
                if a.lot_id is not None:
                    self.db.execute(
                        "UPDATE crop_lots SET remaining_qty = ROUND(remaining_qty + ?, 4) WHERE id = ?",
                        (a.qty, a.lot_id),
                    )
            self.db.execute("DELETE FROM crop_sales WHERE id = ?", (sale_id,))
            if sale.tx_id:
                self.db.execute("DELETE FROM transactions WHERE id = ?", (sale.tx_id,))
            if sale.stock_tx_id:
                self.db.execute("DELETE FROM item_transactions WHERE id = ?", (sale.stock_tx_id,))
            self.audit.log(
                AuditCode.DELETE, f"crop sale {sale_id} ({sale.buyer_name}, {sale.crop_name} {sale.qty:g})", username
            )

    # Money in / out (plain ledger entries) -------------------------------------------------
    def pay_farmer(self, farmer_id: int, date: str, amount, username: str, notes: str = "") -> int:
        amt = _validate_amount(amount)
        if amt <= 0:
            raise ValidationError("Amount must be greater than zero.")
        desc = "CROP PAYMENT" + (f" - {notes.strip()}" if notes.strip() else "")
        with self.db.connect():
            tx = self.accounts.add_transaction(
                farmer_id, _validate_date(date), desc, amt, "P", "2", username, audit=False
            )
            self.audit.log(AuditCode.CROP, f"payment to farmer {farmer_id}: {amt:.2f}", username)
        return tx

    def receive_from_buyer(self, buyer_id: int, date: str, amount, username: str, notes: str = "") -> int:
        amt = _validate_amount(amount)
        if amt <= 0:
            raise ValidationError("Amount must be greater than zero.")
        desc = "CROP RECEIPT" + (f" - {notes.strip()}" if notes.strip() else "")
        with self.db.connect():
            tx = self.accounts.add_transaction(
                buyer_id, _validate_date(date), desc, amt, "M", "2", username, audit=False
            )
            self.audit.log(AuditCode.CROP, f"receipt from buyer {buyer_id}: {amt:.2f}", username)
        return tx

    # Stock & metrics ---------------------------------------------------------------------
    def stock(self, on_date: dt.date | None = None) -> list[CropStock]:
        rows = self.db.fetchall(
            "SELECT i.id, COALESCE(SUM(l.remaining_qty), 0) AS q, COALESCE(SUM(l.remaining_qty * l.rate), 0) AS cost,"
            " SUM(CASE WHEN l.remaining_qty > 0 THEN 1 ELSE 0 END) AS lots FROM items i "
            "LEFT JOIN crop_lots l ON l.item_id = i.id WHERE i.item_type = ? GROUP BY i.id ORDER BY i.name",
            (CROP_TYPE,),
        )
        out = []
        for r in rows:
            item = self.inventory.get_item(r["id"])
            if item is None:
                continue
            q, cost = round(float(r["q"]), 4), round(float(r["cost"]), 2)
            latest = self.rates.latest(item.id, on_date)
            market_value = round(q * latest[0], 2) if latest else None
            out.append(
                CropStock(
                    item,
                    q,
                    self.inventory.quantity(item.id),
                    cost,
                    round(cost / q, 2) if q else 0.0,
                    latest[0] if latest else None,
                    latest[1] if latest else None,
                    market_value,
                    round(market_value - cost, 2) if market_value is not None else None,
                    int(r["lots"] or 0),
                )
            )
        return out

    def summary(self, date_from: str, date_to: str) -> dict[str, float]:
        p = self.db.fetchone(
            "SELECT COALESCE(SUM(qty), 0) AS q, COALESCE(SUM(amount), 0) AS a, COUNT(*) AS n "
            "FROM crop_lots WHERE date BETWEEN ? AND ?",
            (date_from, date_to),
        )
        s = self.db.fetchone(
            "SELECT COALESCE(SUM(qty), 0) AS q, COALESCE(SUM(amount), 0) AS a, COALESCE(SUM(cost), 0) AS c,"
            " COALESCE(SUM(margin), 0) AS m, COUNT(*) AS n FROM crop_sales WHERE date BETWEEN ? AND ?",
            (date_from, date_to),
        )
        stock = self.stock()
        return {
            "purchased_qty": round(p["q"], 4),
            "purchased_amount": round(p["a"], 2),
            "purchases": p["n"],
            "sold_qty": round(s["q"], 4),
            "sold_amount": round(s["a"], 2),
            "sold_cost": round(s["c"], 2),
            "margin": round(s["m"], 2),
            "margin_pct": round(s["m"] / s["c"] * 100, 2) if s["c"] else 0.0,
            "sales": s["n"],
            "stock_cost": round(sum(x.cost_value for x in stock), 2),
            "stock_market": round(sum(x.market_value or 0 for x in stock), 2),
            "unrealized": round(sum(x.unrealized or 0 for x in stock), 2),
        }

    def margin_by_crop(self, date_from: str, date_to: str) -> list[tuple]:
        rows = self.db.fetchall(
            "SELECT i.id, i.name, i.unit, COUNT(*) AS n, SUM(s.qty) AS q, SUM(s.amount) AS a, SUM(s.cost) AS c,"
            " SUM(s.margin) AS m FROM crop_sales s JOIN items i ON i.id = s.item_id "
            "WHERE s.date BETWEEN ? AND ? GROUP BY i.id ORDER BY m DESC",
            (date_from, date_to),
        )
        return [
            (
                r["id"],
                r["name"],
                r["n"],
                r["q"],
                r["unit"],
                round(r["a"], 2),
                round(r["c"], 2),
                round(r["m"], 2),
                round(r["m"] / r["c"] * 100, 2) if r["c"] else 0.0,
                round(r["a"] / r["q"], 2) if r["q"] else 0.0,
                round(r["c"] / r["q"], 2) if r["q"] else 0.0,
            )
            for r in rows
        ]

    def margin_by_buyer(self, date_from: str, date_to: str) -> list[tuple]:
        rows = self.db.fetchall(
            "SELECT s.buyer_id, s.buyer_name, COUNT(*) AS n, SUM(s.qty) AS q, SUM(s.amount) AS a, SUM(s.cost) AS c,"
            " SUM(s.margin) AS m FROM crop_sales s WHERE s.date BETWEEN ? AND ? "
            "GROUP BY s.buyer_id, s.buyer_name ORDER BY m DESC",
            (date_from, date_to),
        )
        return [
            (
                r["buyer_id"] or "",
                r["buyer_name"],
                r["n"],
                r["q"],
                round(r["a"], 2),
                round(r["c"], 2),
                round(r["m"], 2),
                round(r["m"] / r["c"] * 100, 2) if r["c"] else 0.0,
            )
            for r in rows
        ]

    def purchases_by_farmer(self, date_from: str, date_to: str) -> list[tuple]:
        rows = self.db.fetchall(
            "SELECT c.id, c.name, c.other_details, COUNT(*) AS n, SUM(l.gross_qty) AS g, SUM(l.deduction_qty) AS d,"
            " SUM(l.qty) AS q, SUM(l.amount) AS a, GROUP_CONCAT(DISTINCT i.name) AS crops "
            "FROM crop_lots l JOIN customers c ON c.id = l.farmer_id JOIN items i ON i.id = l.item_id "
            "WHERE l.date BETWEEN ? AND ? GROUP BY c.id ORDER BY a DESC",
            (date_from, date_to),
        )
        return [
            (
                r["id"],
                r["name"],
                r["other_details"],
                r["n"],
                r["g"],
                r["d"],
                r["q"],
                round(r["a"], 2),
                round(r["a"] / r["q"], 2) if r["q"] else 0.0,
                r["crops"],
            )
            for r in rows
        ]

    def purchases_by_quality(self, date_from: str, date_to: str) -> list[tuple]:
        rows = self.db.fetchall(
            "SELECT i.name, COALESCE(NULLIF(l.quality, ''), '-') AS grade, COUNT(*) AS n, SUM(l.qty) AS q,"
            " SUM(l.amount) AS a, MIN(l.rate) AS lo, MAX(l.rate) AS hi "
            "FROM crop_lots l JOIN items i ON i.id = l.item_id "
            "WHERE l.date BETWEEN ? AND ? GROUP BY i.id, grade ORDER BY i.name, grade",
            (date_from, date_to),
        )
        return [
            (
                r["name"],
                r["grade"],
                r["n"],
                r["q"],
                round(r["a"], 2),
                round(r["a"] / r["q"], 2) if r["q"] else 0.0,
                r["lo"],
                r["hi"],
            )
            for r in rows
        ]

    @staticmethod
    def today() -> str:
        return dt.date.today().strftime(DATE_FMT)


def as_rows(items: Sequence) -> list[tuple]:
    return [tuple(x) for x in items]
