"""Units of measure and conversion.

Mass and volume units convert within their family (100 G of a KG item = 0.1 KG; 1 QTL
= 100 KG).  Count units (PCS, BAG, ...) are each their own family - a bag is not a box.
Stock is always kept in the item's own unit; sales may be entered in any compatible unit.
"""

from __future__ import annotations

FAMILIES: dict[str, dict[str, float]] = {
    "mass": {"G": 0.001, "KG": 1.0, "QTL": 100.0},
    "volume": {"ML": 0.001, "LTR": 1.0},
}
COUNT_UNITS: list[str] = ["PCS", "BAG", "BOX", "PKT", "BTL"]
ALL_UNITS: list[str] = ["KG", "G", "QTL", "LTR", "ML", *COUNT_UNITS]

ALIASES: dict[str, str] = {
    "KGS": "KG",
    "KILO": "KG",
    "KILOGRAM": "KG",
    "GM": "G",
    "GMS": "G",
    "GRAM": "G",
    "GRAMS": "G",
    "Q": "QTL",
    "QT": "QTL",
    "QUINTAL": "QTL",
    "QUINTALS": "QTL",
    "L": "LTR",
    "LT": "LTR",
    "LITRE": "LTR",
    "LITER": "LTR",
    "LTRS": "LTR",
    "PC": "PCS",
    "PIECE": "PCS",
    "PIECES": "PCS",
    "NOS": "PCS",
    "NO": "PCS",
    "PACKET": "PKT",
    "PACKETS": "PKT",
    "BOTTLE": "BTL",
    "BAGS": "BAG",
}


class UnitError(ValueError):
    pass


def normalize(unit: str | None) -> str:
    u = (unit or "").strip().upper().rstrip(".")
    return ALIASES.get(u, u)


def family(unit: str) -> str | None:
    u = normalize(unit)
    for name, members in FAMILIES.items():
        if u in members:
            return name
    return None


def compatible_units(unit: str) -> list[str]:
    """Units a quantity of ``unit`` may be entered in (the unit itself first)."""
    u = normalize(unit)
    fam = family(u)
    if fam is None:
        return [u] if u else []
    return [u] + [m for m in FAMILIES[fam] if m != u]


def convert(quantity: float, from_unit: str, to_unit: str) -> float:
    src, dst = normalize(from_unit), normalize(to_unit)
    if src == dst:
        return float(quantity)
    fam = family(src)
    if fam is None or fam != family(dst):
        raise UnitError(f"Cannot convert {src or '?'} to {dst or '?'}.")
    factors = FAMILIES[fam]
    return round(float(quantity) * factors[src] / factors[dst], 6)


def format_qty(quantity: float, unit: str = "") -> str:
    q = float(quantity)
    text = f"{q:,.3f}".rstrip("0").rstrip(".") if not q.is_integer() else f"{int(q):,}"
    return f"{text} {normalize(unit)}".strip()
