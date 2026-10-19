"""Global search across customers, items and bills (Ctrl+K)."""

from __future__ import annotations

from dataclasses import dataclass

from hth.db.connection import Database


@dataclass(frozen=True)
class SearchHit:
    kind: str  # customer | item | bill
    id: int
    title: str
    subtitle: str

    @property
    def label(self) -> str:
        icon = {"customer": "👤", "item": "📦", "bill": "🧾"}.get(self.kind, "•")
        return f"{icon}  {self.title}    {self.subtitle}".rstrip()


class SearchService:
    def __init__(self, db: Database):
        self.db = db

    def search(self, term: str, limit: int = 12, kinds: set[str] | None = None) -> list[SearchHit]:
        term = (term or "").strip()
        if not term:
            return []
        like = f"%{term}%"
        kinds = kinds or {"customer", "item", "bill"}
        hits: list[SearchHit] = []
        if "customer" in kinds:
            for r in self.db.fetchall(
                "SELECT id, name, other_details, category FROM customers "
                "WHERE name LIKE ? OR other_details LIKE ? OR CAST(id AS TEXT) = ? ORDER BY name LIMIT ?",
                (like, like, term, limit),
            ):
                hits.append(
                    SearchHit(
                        "customer", r["id"], f"#{r['id']} {r['name']}", f"{r['other_details']} · cat {r['category']}"
                    )
                )
        if "item" in kinds:
            for r in self.db.fetchall(
                "SELECT id, name, batch, unit, item_type FROM items "
                "WHERE name LIKE ? OR batch LIKE ? OR CAST(id AS TEXT) = ? ORDER BY name LIMIT ?",
                (like, like, term, limit),
            ):
                hits.append(
                    SearchHit(
                        "item",
                        r["id"],
                        f"#{r['id']} {r['name']}",
                        f"{r['batch']} · {r['unit']} · type {r['item_type']}",
                    )
                )
        if "bill" in kinds and self.db.fetchone("SELECT 1 FROM sqlite_master WHERE name = 'bills'"):
            for r in self.db.fetchall(
                "SELECT id, bill_number, date, customer_name, grand_total FROM bills "
                "WHERE CAST(bill_number AS TEXT) LIKE ? OR customer_name LIKE ? ORDER BY bill_number DESC LIMIT ?",
                (like, like, limit),
            ):
                hits.append(
                    SearchHit(
                        "bill",
                        r["bill_number"],
                        f"Bill {r['bill_number']}",
                        f"{r['date']} · {r['customer_name']} · {r['grand_total']:,.2f}",
                    )
                )
        return hits[:limit]
