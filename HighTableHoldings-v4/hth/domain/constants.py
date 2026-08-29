"""Business constants shared by services and UI.  Values are identical to v3."""

from __future__ import annotations

from enum import Enum

# 24% per annum simple daily rate; compounded at each financial year end (31 March).
DAILY_INTEREST_RATE = 0.0006575342465753425  # 0.24 / 365
ANNUAL_INTEREST_RATE_PERCENT = 24.0
FINANCIAL_YEAR_END_MONTH = 3
FINANCIAL_YEAR_END_DAY = 31

DATE_FMT = "%Y-%m-%d"


class TxType(str, Enum):
    DEBIT = "P"  # customer owes more (sale / "P" in v3)
    CREDIT = "M"  # customer paid / owes less ("M" in v3)

    @property
    def label(self) -> str:
        return "Debit (P)" if self is TxType.DEBIT else "Credit (M)"


class Tag(str, Enum):
    SETTLE = "0"  # settlement marker; resets the interest period
    NORMAL = "1"  # interest bearing
    NO_INTEREST = "2"  # principal only

    @property
    def label(self) -> str:
        return {"0": "0 Settle", "1": "1 Normal", "2": "2 No interest"}[self.value]


TAG_CHOICES = [Tag.NORMAL.label, Tag.NO_INTEREST.label, Tag.SETTLE.label]


class AuditCode(str, Enum):
    """v3 daily-note prefixes, preserved so old notes and new ones read the same."""

    ACCOUNT_ADDED = "01"
    ITEM_ADDED = "02"
    SALE = "03"
    RECEIVE = "04"
    MODIFY = "05"
    DELETE = "06"
    KRAR = "07"
    LOGIN = "08"
    USER = "09"

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


ITEM_TYPES = ["F", "P", "S", "O"]  # fertiliser, pesticide, seed, other (v3 convention)
PAKKA_KACHA = ["P", "K"]

from hth.domain.units import ALL_UNITS  # noqa: E402  (units module has no back-dependency)

UNITS = ALL_UNITS  # stock units offered in the UI
