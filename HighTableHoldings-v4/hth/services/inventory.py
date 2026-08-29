"""Items and stock movements."""

from __future__ import annotations

import datetime as dt

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.interest import parse_date
from hth.domain.models import Item, ItemSummary, ItemTransaction
from hth.services.accounts import ValidationError, _validate_date
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
            item_id = self.db.execute(
                "INSERT INTO items (name, stock_value, last_value, unit, batch, expiry_date, gst_rate,"
                " item_type, pakka_kacha) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        with self.db.connect():
            self.db.execute(f"UPDATE items SET {sets} WHERE id = ?", (*fields.values(), item_id))
            self.audit.log(AuditCode.MODIFY, f"item {item_id}: {fields}", username)

    def delete_item(self, item_id: int, username: str) -> None:
        item = self.get_item(item_id)
        with self.db.connect():
            self.db.execute("DELETE FROM items WHERE id = ?", (item_id,))
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
    ) -> int:
        date = _validate_date(date)
        received_f = _num(received, "Received")
        sale_f = _num(sale, "Sale")
        with self.db.connect():
            tx_id = self.db.execute(
                "INSERT INTO item_transactions (item_id, date, received, sale, description, tags, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item_id, date, received_f, sale_f, description, tags, username),
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

    def summaries(self) -> list[ItemSummary]:
        rows = self.db.fetchall(
            "SELECT i.*, COALESCE(SUM(t.received - t.sale), 0) AS q FROM items i "
            "LEFT JOIN item_transactions t ON t.item_id = i.id GROUP BY i.id ORDER BY i.id"
        )
        out = []
        for r in rows:
            item = _item(r)
            q = float(r["q"])
            out.append(ItemSummary(item, q, round(q * item.stock_value, 2)))
        return out

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
