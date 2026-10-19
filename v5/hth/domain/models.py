"""Plain dataclasses returned by services.  The UI never touches sqlite rows directly."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class User:
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    other_details: str
    category: str = "C"
    category_locked: bool = False

    @property
    def display(self) -> str:
        return f"{self.id} {self.name} {self.other_details}".strip()


@dataclass(frozen=True)
class Transaction:
    id: int
    customer_id: int
    date: str
    description: str
    amount: float
    type: str  # 'P' | 'M'
    tag: str  # '0' | '1' | '2'

    @property
    def is_debit(self) -> bool:
        return self.type == "P"

    @property
    def is_settlement(self) -> bool:
        return self.tag == "0"


@dataclass(frozen=True)
class LedgerRow:
    id: int
    date: str
    particulars: str
    interest: float | None
    debit: float | None
    credit: float | None
    balance: float
    tag: str
    type: str
    amount: float


@dataclass(frozen=True)
class Item:
    id: int
    name: str
    stock_value: float
    last_value: float
    unit: str
    batch: str
    expiry_date: str
    gst_rate: float
    item_type: str
    pakka_kacha: str
    category: str = "C"
    category_locked: bool = False

    @property
    def display(self) -> str:
        return f"{self.id} {self.name} {self.batch}".strip()


@dataclass(frozen=True)
class ItemTransaction:
    id: int
    item_id: int
    date: str
    received: float
    sale: float
    description: str
    tags: str


@dataclass(frozen=True)
class CustomerSummary:
    id: int
    name: str
    other_details: str
    balance: float
    days: int
    score: float = 0.0
    category: str = "C"
    scored: bool = True  # False when kept out of the score population (defaulters)


@dataclass(frozen=True)
class ItemSummary:
    item: Item
    in_stock: float
    total_value: float


@dataclass(frozen=True)
class KrarEntry:
    krar_id: int
    customer_id: int
    customer_name: str
    other_details: str
    dates: list[str] = field(default_factory=list)

    @property
    def last_date(self) -> str:
        return max(self.dates) if self.dates else ""
