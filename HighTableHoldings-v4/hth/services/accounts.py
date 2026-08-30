"""Customer accounts and ledger.  Balance / interest / settlement rules are the v3 rules."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable

from hth.db.connection import Database
from hth.domain.constants import CATEGORIES, DATE_FMT, AuditCode, Tag, TxType
from hth.domain.interest import calculate_interest, parse_date
from hth.domain.models import Customer, CustomerSummary, LedgerRow, Transaction
from hth.services.audit import AuditService


class ValidationError(ValueError):
    pass


def _customer(row) -> Customer:
    keys = row.keys()
    return Customer(
        id=row["id"],
        name=row["name"],
        other_details=row["other_details"],
        category=row["category"] if "category" in keys else "C",
        category_locked=bool(row["category_locked"]) if "category_locked" in keys else False,
    )


def _tx(row) -> Transaction:
    return Transaction(
        id=row["id"],
        customer_id=row["customer_id"],
        date=row["date"],
        description=row["description"],
        amount=float(row["amount"]),
        type=row["type"],
        tag=str(row["tag"]),
    )


def _validate_date(value: str) -> str:
    try:
        return parse_date(value).strftime(DATE_FMT)
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"Invalid date '{value}', expected YYYY-MM-DD.") from exc


def _validate_amount(value: str | float, allow_negative: bool = False) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid amount '{value}'.") from exc
    if amount < 0 and not allow_negative:
        raise ValidationError("Amount cannot be negative.")
    return amount


def _validate_type(value: str) -> str:
    value = (value or "").strip().upper()
    if value not in (TxType.DEBIT.value, TxType.CREDIT.value):
        raise ValidationError("Type must be P (debit) or M (credit).")
    return value


def _validate_tag(value: str | int) -> str:
    value = str(value).strip()[:1]
    if value not in {t.value for t in Tag}:
        raise ValidationError("Tag must be 0 (settle), 1 (normal) or 2 (no interest).")
    return value


class AccountsService:
    def __init__(self, db: Database):
        self.db = db
        self.audit = AuditService(db)

    # Customers --------------------------------------------------------------------
    def list_customers(self, search: str | None = None, categories: Iterable[str] | None = None) -> list[Customer]:
        clauses, params = [], []
        if search:
            like = f"%{search.strip()}%"
            clauses.append("(name LIKE ? OR other_details LIKE ? OR CAST(id AS TEXT) LIKE ?)")
            params += [like, like, like]
        if categories is not None:
            cats = sorted(set(categories))
            if not cats:
                return []
            clauses.append(f"category IN ({','.join('?' * len(cats))})")
            params += cats
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        rows = self.db.fetchall(f"SELECT * FROM customers {where}ORDER BY id", tuple(params))
        return [_customer(r) for r in rows]

    def set_category(self, customer_id: int, category: str, username: str, locked: bool = True) -> None:
        category = (category or "").strip().upper()
        if category not in CATEGORIES:
            raise ValidationError(f"Category must be one of {', '.join(CATEGORIES)}.")
        with self.db.connect():
            self.db.execute(
                "UPDATE customers SET category = ?, category_locked = ? WHERE id = ?",
                (category, 1 if locked else 0, customer_id),
            )
            self.audit.log(
                AuditCode.MODIFY,
                f"customer {customer_id} category -> {category}{' (locked)' if locked else ''}",
                username,
            )

    def get_customer(self, customer_id: int) -> Customer | None:
        row = self.db.fetchone("SELECT * FROM customers WHERE id = ?", (customer_id,))
        return _customer(row) if row else None

    def add_customer(
        self,
        name: str,
        other_details: str = "",
        opening_balance: str | float = 0,
        date: str | None = None,
        description: str = "NEW ACCOUNT",
        tx_type: str = "P",
        tag: str = "1",
        username: str = "system",
    ) -> Customer:
        name = (name or "").strip().upper()
        if not name:
            raise ValidationError("Customer name is required.")
        other_details = (other_details or "").strip().upper()
        date = _validate_date(date or dt.date.today().strftime(DATE_FMT))
        amount = _validate_amount(opening_balance or 0)
        tx_type = _validate_type(tx_type)
        tag = _validate_tag(tag)

        with self.db.connect():
            default_cat = self.db.fetchone("SELECT value FROM settings WHERE key = 'customer.default_category'")
            category = default_cat["value"].upper() if default_cat else "C"
            if category not in CATEGORIES or category == "E":
                category = "C"
            customer_id = self.db.execute(
                "INSERT INTO customers (name, other_details, category) VALUES (?, ?, ?)",
                (name, other_details, category),
            )
            if amount > 0:
                self.add_transaction(
                    customer_id,
                    date,
                    description.upper(),
                    amount,
                    tx_type,
                    tag,
                    username,
                    audit=False,
                )
            self.audit.log(
                AuditCode.ACCOUNT_ADDED,
                f"{name}, {date}, {other_details}, {amount}, {description.upper()}, {tx_type}, {tag}",
                username,
            )
        return Customer(customer_id, name, other_details, category)

    def update_customer(self, customer_id: int, name: str, other_details: str, username: str) -> None:
        name = (name or "").strip().upper()
        if not name:
            raise ValidationError("Customer name is required.")
        with self.db.connect():
            self.db.execute(
                "UPDATE customers SET name = ?, other_details = ? WHERE id = ?",
                (name, (other_details or "").strip().upper(), customer_id),
            )
            self.audit.log(AuditCode.MODIFY, f"customer {customer_id}: {name} | {other_details}", username)

    def delete_customer(self, customer_id: int, username: str) -> None:
        customer = self.get_customer(customer_id)
        with self.db.connect():
            self.db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            self.audit.log(
                AuditCode.DELETE,
                f"customer {customer_id} {customer.name if customer else ''}",
                username,
            )

    # Transactions -----------------------------------------------------------------
    def add_transaction(
        self,
        customer_id: int,
        date: str,
        description: str,
        amount: str | float,
        tx_type: str,
        tag: str | int,
        username: str = "system",
        audit: bool = True,
        allow_negative: bool = False,
    ) -> int:
        date = _validate_date(date)
        amount_f = _validate_amount(amount, allow_negative)
        tx_type = _validate_type(tx_type)
        tag = _validate_tag(tag)
        with self.db.connect():
            tx_id = self.db.execute(
                "INSERT INTO transactions (customer_id, date, description, amount, type, tag, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (customer_id, date, description, amount_f, tx_type, tag, username),
            )
            if audit:
                self.audit.log(
                    AuditCode.MODIFY,
                    f"tx added customer {customer_id}: {date}, {description}, {amount_f}, {tx_type}, {tag}",
                    username,
                )
        return tx_id

    def get_transactions(self, customer_id: int) -> list[Transaction]:
        rows = self.db.fetchall("SELECT * FROM transactions WHERE customer_id = ? ORDER BY date, id", (customer_id,))
        return [_tx(r) for r in rows]

    def get_transaction(self, tx_id: int) -> Transaction | None:
        row = self.db.fetchone("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        return _tx(row) if row else None

    def update_transaction(
        self,
        tx_id: int,
        date: str,
        description: str,
        amount: str | float,
        tx_type: str,
        tag: str | int,
        username: str,
    ) -> None:
        date = _validate_date(date)
        amount_f = _validate_amount(amount)
        tx_type = _validate_type(tx_type)
        tag = _validate_tag(tag)
        with self.db.connect():
            self.db.execute(
                "UPDATE transactions SET date=?, description=?, amount=?, type=?, tag=? WHERE id=?",
                (date, description, amount_f, tx_type, tag, tx_id),
            )
            self.audit.log(
                AuditCode.MODIFY,
                f"tx {tx_id}: {date}, {description}, {amount_f}, {tx_type}, {tag}",
                username,
            )

    def delete_transaction(self, tx_id: int, username: str) -> None:
        tx = self.get_transaction(tx_id)
        with self.db.connect():
            self.db.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
            self.audit.log(
                AuditCode.DELETE,
                f"tx {tx_id} customer {tx.customer_id if tx else '?'}: "
                f"{tx.date if tx else ''}, {tx.description if tx else ''}, {tx.amount if tx else ''}",
                username,
            )

    # Balance rules (v3) -----------------------------------------------------------
    def last_settlement(self, customer_id: int) -> tuple[str, int] | None:
        """(date, id) of the most recent tag-0 row, ordering by date then id."""
        row = self.db.fetchone(
            "SELECT date, id FROM transactions WHERE customer_id = ? AND tag = '0' ORDER BY date DESC, id DESC LIMIT 1",
            (customer_id,),
        )
        return (row["date"], row["id"]) if row else None

    def current_period_transactions(self, customer_id: int) -> list[Transaction]:
        """Transactions after the last settlement (or all, if never settled)."""
        last = self.last_settlement(customer_id)
        if last is None:
            return self.get_transactions(customer_id)
        date, tx_id = last
        rows = self.db.fetchall(
            "SELECT * FROM transactions WHERE customer_id = ? AND (date > ? OR (date = ? AND id > ?)) "
            "ORDER BY date, id",
            (customer_id, date, date, tx_id),
        )
        return [_tx(r) for r in rows]

    def get_balance(self, customer_id: int, as_of: dt.date | None = None) -> float:
        """Principal + compound interest of the current (unsettled) period.

        Positive = customer owes the business; negative = business owes customer.
        """
        balance = 0.0
        for tx in self.current_period_transactions(customer_id):
            if tx.tag == Tag.NORMAL.value:
                total = tx.amount + calculate_interest(tx.amount, tx.date, as_of)
            else:  # no-interest (2); settlement rows (0) never appear in the current period
                total = tx.amount
            balance += total if tx.is_debit else -total
        return round(balance, 2)

    def ledger(self, customer_id: int, as_of: dt.date | None = None) -> list[LedgerRow]:
        """Full statement with per-row interest and a running balance (v3 report logic)."""
        txs = self.get_transactions(customer_id)
        last = self.last_settlement(customer_id)
        last_date = parse_date(last[0]) if last else None
        last_id = last[1] if last else -1

        rows: list[LedgerRow] = []
        principal_period = 0.0
        interest_period = 0.0
        balance = 0.0
        for tx in txs:
            tx_date = parse_date(tx.date)
            in_current_period = last_date is None or tx_date > last_date or (tx_date == last_date and tx.id > last_id)
            interest = 0.0
            debit = tx.amount if tx.is_debit else None
            credit = None if tx.is_debit else tx.amount
            if tx.is_settlement:
                shown_interest = None
            else:
                if in_current_period:
                    sign = 1 if tx.is_debit else -1
                    principal_period += sign * tx.amount
                    if tx.tag == Tag.NORMAL.value:
                        interest = calculate_interest(tx.amount, tx.date, as_of)
                        interest_period += sign * interest
                balance = principal_period + interest_period
                shown_interest = interest
            rows.append(
                LedgerRow(
                    id=tx.id,
                    date=tx.date,
                    particulars=tx.description,
                    interest=shown_interest,
                    debit=debit,
                    credit=credit,
                    balance=round(balance, 2),
                    tag=tx.tag,
                    type=tx.type,
                    amount=tx.amount,
                )
            )
            if tx.is_settlement:
                principal_period = interest_period = balance = 0.0
        return rows

    def record_settlement(
        self,
        customer_id: int,
        date: str,
        detail: str,
        amount: float,
        tx_type: str,
        username: str,
    ) -> None:
        """Tag-0 flow from v3 Sales: the transaction, the settled balance, and the discount.

        All three rows carry tag 0 so they close the interest period; the next period
        starts from zero.  The derived rows may be negative (overpayment, or a customer
        who was in credit) - v3 stored them that way and the ledger shows them as such.
        """
        with self.db.connect():
            balance_before = self.get_balance(customer_id)
            discount = round(balance_before + amount if tx_type == "P" else balance_before - amount, 2)
            self.add_transaction(customer_id, date, detail, amount, tx_type, "0", username, audit=False)
            self.add_transaction(
                customer_id,
                date,
                "Settled Amount",
                balance_before,
                "M",
                "0",
                username,
                audit=False,
                allow_negative=True,
            )
            self.add_transaction(
                customer_id,
                date,
                "Discount",
                discount,
                "M",
                "0",
                username,
                audit=False,
                allow_negative=True,
            )

    # Summaries --------------------------------------------------------------------
    def days_since_last_activity(self, customer_id: int, today: dt.date | None = None) -> int:
        """v3 'Days': days since the newest non-settlement transaction (0 if none)."""
        row = self.db.fetchone(
            "SELECT MAX(date) AS d FROM transactions WHERE customer_id = ? AND tag != '0'",
            (customer_id,),
        )
        if not row or not row["d"]:
            return 0
        today = today or dt.date.today()
        return (today - parse_date(row["d"])).days

    def summaries(
        self,
        as_of: dt.date | None = None,
        categories: Iterable[str] | None = None,
        exclude_from_score: Iterable[str] | None = None,
    ) -> list[CustomerSummary]:
        """Every customer with balance, days since activity and the v3 account score.

        ``exclude_from_score``: categories left out of the min/max normalisation (they get
        no score) so defaulters do not distort everyone else.  ``categories``: only these
        are returned (all when None).
        """
        excluded = set(exclude_from_score or ())
        base = []
        for c in self.list_customers():
            base.append((c, self.get_balance(c.id, as_of), self.days_since_last_activity(c.id, as_of)))
        population = [(b, d) for c, b, d in base if c.category not in excluded]
        pop_scores = iter(account_scores(population))
        out = []
        for c, balance, days in base:
            scored = c.category not in excluded
            score = next(pop_scores) if scored else 0.0
            out.append(CustomerSummary(c.id, c.name, c.other_details, balance, days, score, c.category, scored))
        if categories is not None:
            wanted = set(categories)
            out = [s for s in out if s.category in wanted]
        return out


def account_scores(pairs: list[tuple[float, int]], alpha: float = 0.6, beta: float = 0.4) -> list[float]:
    """v3 'account score': weighted, min-max normalised log(amount) and log(days)."""
    if not pairs:
        return []
    log_amount = [math.log(a + 1) if a > 0 else 0.0 for a, _ in pairs]
    log_days = [math.log(d + 1) if d > 0 else 0.0 for _, d in pairs]

    def normalise(values: list[float]) -> list[float]:
        lo, hi = min(values), max(values)
        return [(v - lo) / (hi - lo) if hi != lo else 0.0 for v in values]

    return [round(alpha * a + beta * d, 4) for a, d in zip(normalise(log_amount), normalise(log_days), strict=True)]
