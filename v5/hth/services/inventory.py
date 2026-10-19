"""Items and stock movements."""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable

from hth.db.connection import Database
from hth.domain.constants import CATEGORIES, DATE_FMT, AuditCode
from hth.domain.interest import parse_date
from hth.domain.models import Item, ItemSummary, ItemTransaction
from hth.domain.units import UnitError, convert, normalize
from hth.services.accounts import ValidationError, _count_if_table, _validate_date
from hth.services.audit import AuditService


def _item(row) -> Item:
    return Item(
        id=row["id"],
        name=row["name"],
        stock_value=float(row["stock_value"]),
        last_value=float(row["last_value"]),
        unit=row["unit"],
        batch=row["batch"],
        expiry_date=row["expiry_date"],
        gst_rate=float(row["gst_rate"]),
        item_type=row["item_type"],
        pakka_kacha=str(row["pakka_kacha"]),
        category=row["category"] if "category" in row.keys() else "C",
        category_locked=bool(row["category_locked"]) if "category_locked" in row.keys() else False,
        name_hi=row["name_hi"] if "name_hi" in row.keys() else "",
        hi_manual=bool(row["hi_manual"]) if "hi_manual" in row.keys() else False,
    )


def _itx(row) -> ItemTransaction:
    return ItemTransaction(
        id=row["id"],
        item_id=row["item_id"],
        date=row["date"],
        received=float(row["received"]),
        sale=float(row["sale"]),
        description=row["description"],
        tags=row["tags"],
    )


def _num(value, field: str, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number.") from exc


class InventoryService:
    def __init__(self, db: Database):
        self.db = db
        self.audit = AuditService(db)

    # Items ------------------------------------------------------------------------
    def list_items(self, search: str | None = None) -> list[Item]:
        if search:
            like = f"%{search.strip()}%"
            rows = self.db.fetchall(
                "SELECT * FROM items WHERE name LIKE ? OR batch LIKE ? OR CAST(id AS TEXT) LIKE ? ORDER BY id",
                (like, like, like),
            )
        else:
            rows = self.db.fetchall("SELECT * FROM items ORDER BY id")
        return [_item(r) for r in rows]

    def get_item(self, item_id: int) -> Item | None:
        row = self.db.fetchone("SELECT * FROM items WHERE id = ?", (item_id,))
        return _item(row) if row else None

    def add_item(
        self,
        name: str,
        stock_value: str | float = 0,
        last_value: str | float = 0,
        unit: str = "PCS",
        batch: str = "NA",
        expiry_date: str = "NA",
        gst_rate: str | float = 0,
        item_type: str = "O",
        pakka_kacha: str = "P",
        date: str | None = None,
        opening_quantity: str | float = 0,
        source: str = "",
        username: str = "system",
    ) -> Item:
        name = (name or "").strip().upper()
        if not name:
            raise ValidationError("Item name is required.")
        date = _validate_date(date or dt.date.today().strftime(DATE_FMT))
        stock_value_f = _num(stock_value, "Stock value")
        last_value_f = _num(last_value, "Last value")
        gst_f = _num(gst_rate, "GST rate")
        opening_f = _num(opening_quantity, "Opening quantity")
        unit = (unit or "PCS").strip().upper()
        batch = (batch or "NA").strip().upper()
        expiry_date = (expiry_date or "NA").strip()
        item_type = (item_type or "O").strip().upper()
        pakka_kacha = (pakka_kacha or "P").strip().upper()
        source = (source or "").strip().upper()

        with self.db.connect():
            from hth.i18n.translit import to_hindi

            item_id = self.db.execute(
                "INSERT INTO items (name, stock_value, last_value, unit, batch, expiry_date, gst_rate,"
                " item_type, pakka_kacha, name_hi) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    stock_value_f,
                    last_value_f,
                    unit,
                    batch,
                    expiry_date,
                    gst_f,
                    item_type,
                    pakka_kacha,
                    to_hindi(name, item=True),
                ),
            )
            # v3 always wrote an opening stock row (received = opening balance, description = source)
            self.add_item_transaction(item_id, date, opening_f, 0, source, "", username, audit=False)
            self.audit.log(
                AuditCode.ITEM_ADDED,
                f"{name}, {date}, {stock_value_f}, {source}, {opening_f}, {last_value_f}, {unit}, "
                f"{batch}, {expiry_date}, {gst_f}, {item_type}, {pakka_kacha}",
                username,
            )
        return self.get_item(item_id)  # type: ignore[return-value]

    def update_item(self, item_id: int, username: str, **fields) -> None:
        allowed = {
            "name",
            "stock_value",
            "last_value",
            "unit",
            "batch",
            "expiry_date",
            "gst_rate",
            "item_type",
            "pakka_kacha",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValidationError(f"Unknown item fields: {sorted(unknown)}")
        if "name" in fields:
            fields["name"] = (fields["name"] or "").strip().upper()
            if not fields["name"]:
                raise ValidationError("Item name is required.")
        for key in ("stock_value", "last_value", "gst_rate"):
            if key in fields:
                fields[key] = _num(fields[key], key)
        for key in ("unit", "batch", "item_type", "pakka_kacha"):
            if key in fields:
                fields[key] = str(fields[key]).strip().upper()
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values())
        if "name" in fields:  # follow a rename unless the Hindi name was corrected by hand
            from hth.i18n.translit import to_hindi

            sets += ", name_hi = CASE WHEN hi_manual = 1 THEN name_hi ELSE ? END"
            params.append(to_hindi(fields["name"], item=True))
        with self.db.connect():
            self.db.execute(f"UPDATE items SET {sets} WHERE id = ?", (*params, item_id))
            self.audit.log(AuditCode.MODIFY, f"item {item_id}: {fields}", username)

    def delete_item(self, item_id: int, username: str) -> None:
        item = self.get_item(item_id)
        lots = _count_if_table(self.db, "crop_lots", "item_id = ?", item_id)
        sold = _count_if_table(self.db, "crop_sales", "item_id = ?", item_id)
        if lots or sold:
            raise ValidationError(
                f"{item.name if item else 'This item'} has {lots} crop lot(s) and {sold} crop sale(s). "
                "Delete them in Crop Trade first, or mark the item E (discontinued) instead."
            )
        with self.db.connect():
            try:
                self.db.execute("DELETE FROM items WHERE id = ?", (item_id,))
            except sqlite3.IntegrityError as exc:
                raise ValidationError(f"Cannot delete: other records still use this item ({exc}).") from exc
            self.audit.log(AuditCode.DELETE, f"item {item_id} {item.name if item else ''}", username)

    # Stock movements --------------------------------------------------------------
    def add_item_transaction(
        self,
        item_id: int,
        date: str,
        received: str | float,
        sale: str | float,
        description: str = "",
        tags: str = "",
        username: str = "system",
        audit: bool = True,
        value: float = 0.0,
    ) -> int:
        date = _validate_date(date)
        received_f = _num(received, "Received")
        sale_f = _num(sale, "Sale")
        with self.db.connect():
            tx_id = self.db.execute(
                "INSERT INTO item_transactions (item_id, date, received, sale, description, tags, created_by, value)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, date, received_f, sale_f, description, tags, username, round(float(value or 0), 2)),
            )
            if audit:
                self.audit.log(
                    AuditCode.MODIFY,
                    f"stock added item {item_id}: {date}, +{received_f}, -{sale_f}, {description}",
                    username,
                )
        return tx_id

    def get_item_transactions(self, item_id: int) -> list[ItemTransaction]:
        rows = self.db.fetchall("SELECT * FROM item_transactions WHERE item_id = ? ORDER BY date, id", (item_id,))
        return [_itx(r) for r in rows]

    def get_item_transaction(self, tx_id: int) -> ItemTransaction | None:
        row = self.db.fetchone("SELECT * FROM item_transactions WHERE id = ?", (tx_id,))
        return _itx(row) if row else None

    def update_item_transaction(
        self, tx_id: int, date: str, received, sale, description: str, tags: str, username: str
    ) -> None:
        date = _validate_date(date)
        with self.db.connect():
            self.db.execute(
                "UPDATE item_transactions SET date=?, received=?, sale=?, description=?, tags=? WHERE id=?",
                (date, _num(received, "Received"), _num(sale, "Sale"), description, tags, tx_id),
            )
            self.audit.log(
                AuditCode.MODIFY,
                f"stock tx {tx_id}: {date}, {received}, {sale}, {description}",
                username,
            )

    def delete_item_transaction(self, tx_id: int, username: str) -> None:
        tx = self.get_item_transaction(tx_id)
        with self.db.connect():
            self.db.execute("DELETE FROM item_transactions WHERE id = ?", (tx_id,))
            self.audit.log(
                AuditCode.DELETE,
                f"stock tx {tx_id} item {tx.item_id if tx else '?'}: {tx.date if tx else ''}",
                username,
            )

    # Derived figures --------------------------------------------------------------
    def quantity(self, item_id: int) -> float:
        row = self.db.fetchone(
            "SELECT COALESCE(SUM(received - sale), 0) AS q FROM item_transactions WHERE item_id = ?",
            (item_id,),
        )
        return float(row["q"]) if row else 0.0

    def get_last_value(self, item_id: int) -> float:
        row = self.db.fetchone("SELECT last_value FROM items WHERE id = ?", (item_id,))
        return float(row["last_value"]) if row else 0.0

    def set_last_value(self, item_id: int, value: float) -> None:
        self.db.execute("UPDATE items SET last_value = ? WHERE id = ?", (value, item_id))

    def summaries(self, categories: Iterable[str] | None = None) -> list[ItemSummary]:
        rows = self.db.fetchall(
            "SELECT i.*, COALESCE(SUM(t.received - t.sale), 0) AS q FROM items i "
            "LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id ORDER BY i.id"
        )
        wanted = None if categories is None else set(categories)
        out = []
        for r in rows:
            item = _item(r)
            if wanted is not None and item.category not in wanted:
                continue
            q = float(r["q"])
            out.append(ItemSummary(item, q, round(q * item.stock_value, 2)))
        return out

    def conversion_factor(self, item_id: int, new_unit: str) -> float | None:
        """How many ``new_unit`` one current unit is, or None when the units are unrelated."""
        item = self.get_item(item_id)
        if item is None:
            raise ValidationError("Item not found.")
        try:
            return convert(1, item.unit, new_unit)
        except UnitError:
            return None

    def change_unit(self, item_id: int, new_unit: str, username: str, factor: float | None = None) -> float:
        """Relabel the item in ``new_unit`` and convert its whole history.

        ``factor`` = how many new units make one old unit (1 QTL = 100 KG -> factor 100 when
        going QTL -> KG).  Derived automatically for units of the same family; required for
        unrelated units (1 PKT = 25 KG).  Quantities are multiplied, per-unit prices divided,
        money amounts left alone.  Returns the factor used.
        """
        item = self.get_item(item_id)
        if item is None:
            raise ValidationError("Item not found.")
        new_unit = normalize(new_unit)
        if not new_unit:
            raise ValidationError("Unit is required.")
        old_unit = normalize(item.unit)
        if new_unit == old_unit:
            return 1.0
        if factor is None:
            factor = self.conversion_factor(item_id, new_unit)
            if factor is None:
                raise ValidationError(
                    f"{old_unit} and {new_unit} are not related - say how many {new_unit} one {old_unit} is."
                )
        factor = float(factor)
        if factor <= 0:
            raise ValidationError("Factor must be greater than zero.")
        q, p = f"ROUND({{}} * {factor!r}, 4)", f"ROUND({{}} / {factor!r}, 4)"
        with self.db.connect():
            self.db.execute(
                f"UPDATE items SET unit = ?, stock_value = {p.format('stock_value')},"
                f" last_value = {p.format('last_value')} WHERE id = ?",
                (new_unit, item_id),
            )
            self.db.execute(
                f"UPDATE item_transactions SET received = {q.format('received')}, sale = {q.format('sale')}"
                " WHERE item_id = ?",
                (item_id,),
            )
            tables = {r[0] for r in self.db.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if "crop_lots" in tables:
                self.db.execute(
                    f"UPDATE crop_lots SET gross_qty = {q.format('gross_qty')},"
                    f" deduction_qty = {q.format('deduction_qty')},"
                    f" qty = {q.format('qty')}, remaining_qty = {q.format('remaining_qty')}, rate = {p.format('rate')}"
                    " WHERE item_id = ?",
                    (item_id,),
                )
                self.db.execute(
                    f"UPDATE crop_sales SET qty = {q.format('qty')}, short_qty = {q.format('short_qty')},"
                    f" rate = {p.format('rate')} WHERE item_id = ?",
                    (item_id,),
                )
                self.db.execute(
                    f"UPDATE crop_sale_lots SET qty = {q.format('qty')}, cost_rate = {p.format('cost_rate')}"
                    " WHERE sale_id IN (SELECT id FROM crop_sales WHERE item_id = ?)",
                    (item_id,),
                )
                self.db.execute(f"UPDATE crop_rates SET rate = {p.format('rate')} WHERE item_id = ?", (item_id,))
            self.audit.log(
                AuditCode.MODIFY,
                f"item {item_id} unit {old_unit} -> {new_unit} (1 {old_unit} = {factor:g} {new_unit}),"
                " history converted",
                username,
            )
        return factor

    def set_category(self, item_id: int, category: str, username: str, locked: bool = True) -> None:
        category = (category or "").strip().upper()
        if category not in CATEGORIES:
            raise ValidationError(f"Category must be one of {', '.join(CATEGORIES)}.")
        with self.db.connect():
            self.db.execute(
                "UPDATE items SET category = ?, category_locked = ? WHERE id = ?",
                (category, 1 if locked else 0, item_id),
            )
            self.audit.log(
                AuditCode.MODIFY, f"item {item_id} category -> {category}{' (locked)' if locked else ''}", username
            )

    def last_sale_dates(self) -> dict[int, str | None]:
        rows = self.db.fetchall(
            "SELECT i.id, MAX(CASE WHEN t.sale > 0 THEN t.date END) AS last_sale FROM items i "
            "LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id"
        )
        return {r["id"]: r["last_sale"] for r in rows}

    def total_stock_value(self) -> float:
        return round(sum(s.total_value for s in self.summaries()), 2)

    def low_stock(self, threshold: float = 5) -> list[ItemSummary]:
        return [s for s in self.summaries() if s.in_stock <= threshold]

    def expiring(self, within_days: int = 60, today: dt.date | None = None) -> list[tuple[ItemSummary, int]]:
        """Items whose expiry_date parses and falls within ``within_days`` (negative = expired)."""
        today = today or dt.date.today()
        out = []
        for s in self.summaries():
            try:
                exp = parse_date(s.item.expiry_date)
            except ValueError:
                continue
            remaining = (exp - today).days
            if remaining <= within_days:
                out.append((s, remaining))
        return sorted(out, key=lambda t: t[1])
