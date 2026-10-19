"""Finance rules: money accounts, entries, recurring expenses, cash flow and P&L.

Sign convention: every entry has a positive ``amount``; ``kind`` decides direction.
  money IN  to account_id : receipt, income, owner_in, transfer (into counter_account_id)
  money OUT of account_id : payment, expense, owner_out, transfer (out of account_id)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.interest import parse_date
from hth.services.accounts import ValidationError, _validate_amount, _validate_date
from hth.services.audit import AuditService
from hth.services.settings import SettingsService

ACCOUNT_KINDS = ["cash", "bank", "upi", "other"]
ENTRY_KINDS = ["expense", "income", "transfer", "owner_in", "owner_out", "receipt", "payment"]
IN_KINDS = {"receipt", "income", "owner_in"}
OUT_KINDS = {"payment", "expense", "owner_out"}
KIND_LABELS = {
    "expense": "Expense",
    "income": "Other income",
    "transfer": "Transfer",
    "owner_in": "Capital in",
    "owner_out": "Drawings",
    "receipt": "Customer receipt",
    "payment": "Payment out",
}
DEFAULT_HEADS = [
    ("RENT", "expense"),
    ("SALARIES", "expense"),
    ("ELECTRICITY", "expense"),
    ("TRANSPORT", "expense"),
    ("EMI", "expense"),
    ("INTEREST PAID", "expense"),
    ("REPAIRS", "expense"),
    ("OFFICE & STATIONERY", "expense"),
    ("BANK CHARGES", "expense"),
    ("TAXES & FEES", "expense"),
    ("OTHER EXPENSE", "expense"),
    ("COMMISSION", "income"),
    ("INTEREST RECEIVED", "income"),
    ("OTHER INCOME", "income"),
]


@dataclass(frozen=True)
class MoneyAccount:
    id: int
    name: str
    kind: str
    opening_balance: float
    opening_date: str
    is_active: bool
    notes: str


@dataclass(frozen=True)
class Head:
    id: int
    name: str
    kind: str
    is_active: bool


@dataclass(frozen=True)
class Entry:
    id: int
    date: str
    kind: str
    account_id: int
    account_name: str
    counter_account_id: int | None
    counter_account_name: str | None
    head_id: int | None
    head_name: str | None
    customer_id: int | None
    customer_name: str | None
    amount: float
    description: str
    tx_id: int | None
    created_by: str | None

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)


@dataclass(frozen=True)
class Recurring:
    id: int
    head_id: int
    head_name: str
    account_id: int
    account_name: str
    amount: float
    day_of_month: int
    description: str
    is_active: bool
    start_month: str
    last_posted: str | None


@dataclass
class CashFlow:
    date_from: str
    date_to: str
    inflows: dict[str, float] = field(default_factory=dict)  # label -> amount
    outflows: dict[str, float] = field(default_factory=dict)
    expenses_by_head: list[tuple[str, float]] = field(default_factory=list)
    accounts: list[tuple[str, float, float, float, float]] = field(
        default_factory=list
    )  # name, opening, in, out, closing

    @property
    def total_in(self) -> float:
        return round(sum(self.inflows.values()), 2)

    @property
    def total_out(self) -> float:
        return round(sum(self.outflows.values()), 2)

    @property
    def net(self) -> float:
        return round(self.total_in - self.total_out, 2)


@dataclass
class ProfitAndLoss:
    date_from: str
    date_to: str
    item_revenue: float = 0.0
    item_cogs: float = 0.0
    crop_revenue: float = 0.0
    crop_cost: float = 0.0
    other_income: float = 0.0
    expenses: list[tuple[str, float]] = field(default_factory=list)

    @property
    def item_margin(self) -> float:
        return round(self.item_revenue - self.item_cogs, 2)

    @property
    def crop_margin(self) -> float:
        return round(self.crop_revenue - self.crop_cost, 2)

    @property
    def gross_margin(self) -> float:
        return round(self.item_margin + self.crop_margin, 2)

    @property
    def total_expenses(self) -> float:
        return round(sum(a for _, a in self.expenses), 2)

    @property
    def net_profit(self) -> float:
        return round(self.gross_margin + self.other_income - self.total_expenses, 2)


def _month(d: dt.date) -> str:
    return d.strftime("%Y-%m")


def _next_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"


class FinanceService:
    def __init__(self, db: Database):
        self.db = db
        self.audit = AuditService(db)
        self.settings = SettingsService(db, {"finance.default_account": ""})

    # Bootstrap ---------------------------------------------------------------------------
    def ensure_defaults(self) -> None:
        # Read-only fast path: callers (including background threads) hit this often, and a
        # write here would contend with the main thread for the SQLite write lock.
        if self.db.fetchone("SELECT 1 FROM money_accounts LIMIT 1") is not None and self.db.fetchone(
            "SELECT COUNT(*) AS n FROM expense_heads"
        )["n"] >= len(DEFAULT_HEADS):
            return
        with self.db.connect():
            # INSERT OR IGNORE (name is UNIQUE): safe even if two threads seed at once.
            self.db.execute(
                "INSERT OR IGNORE INTO money_accounts (name, kind, opening_balance, opening_date)"
                " VALUES ('CASH', 'cash', 0, ?)",
                (dt.date.today().strftime(DATE_FMT),),
            )
            for name, kind in DEFAULT_HEADS:
                self.db.execute("INSERT OR IGNORE INTO expense_heads (name, kind) VALUES (?, ?)", (name, kind))

    # Money accounts ----------------------------------------------------------------------
    def _account(self, r) -> MoneyAccount:
        return MoneyAccount(
            r["id"],
            r["name"],
            r["kind"],
            float(r["opening_balance"]),
            r["opening_date"],
            bool(r["is_active"]),
            r["notes"],
        )

    def money_accounts(self, active_only: bool = True) -> list[MoneyAccount]:
        where = "WHERE is_active = 1 " if active_only else ""
        return [self._account(r) for r in self.db.fetchall(f"SELECT * FROM money_accounts {where}ORDER BY id")]

    def get_account(self, account_id: int) -> MoneyAccount | None:
        r = self.db.fetchone("SELECT * FROM money_accounts WHERE id = ?", (account_id,))
        return self._account(r) if r else None

    def add_account(
        self,
        name: str,
        kind: str = "cash",
        opening_balance=0,
        opening_date: str | None = None,
        notes: str = "",
        username: str = "system",
    ) -> MoneyAccount:
        name = (name or "").strip().upper()
        if not name:
            raise ValidationError("Account name is required.")
        if kind not in ACCOUNT_KINDS:
            raise ValidationError(f"Kind must be one of {', '.join(ACCOUNT_KINDS)}.")
        if self.db.fetchone("SELECT 1 FROM money_accounts WHERE name = ?", (name,)):
            raise ValidationError(f"Account '{name}' already exists.")
        ob = float(_validate_amount(opening_balance or 0, allow_negative=True))
        date = _validate_date(opening_date or dt.date.today().strftime(DATE_FMT))
        with self.db.connect():
            aid = self.db.execute(
                "INSERT INTO money_accounts (name, kind, opening_balance, opening_date, notes) VALUES (?, ?, ?, ?, ?)",
                (name, kind, ob, date, (notes or "").strip()),
            )
            self.audit.log(AuditCode.FINANCE, f"money account {name} ({kind}) opening {ob:g}", username)
        return self.get_account(aid)  # type: ignore[return-value]

    def update_account(self, account_id: int, username: str, **fields) -> None:
        allowed = {"name", "kind", "opening_balance", "opening_date", "notes", "is_active"}
        bad = set(fields) - allowed
        if bad:
            raise ValidationError(f"Unknown fields {sorted(bad)}")
        if "name" in fields:
            fields["name"] = (fields["name"] or "").strip().upper()
            if not fields["name"]:
                raise ValidationError("Account name is required.")
        if "kind" in fields and fields["kind"] not in ACCOUNT_KINDS:
            raise ValidationError("Bad account kind.")
        if "opening_balance" in fields:
            fields["opening_balance"] = float(_validate_amount(fields["opening_balance"] or 0, allow_negative=True))
        if "opening_date" in fields:
            fields["opening_date"] = _validate_date(fields["opening_date"])
        if "is_active" in fields:
            fields["is_active"] = 1 if fields["is_active"] else 0
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.db.connect():
            self.db.execute(f"UPDATE money_accounts SET {sets} WHERE id = ?", (*fields.values(), account_id))
            self.audit.log(AuditCode.FINANCE, f"money account {account_id}: {fields}", username)

    def default_account_id(self) -> int | None:
        v = self.settings.get("finance.default_account")
        if v.isdigit() and self.get_account(int(v)) and self.get_account(int(v)).is_active:
            return int(v)
        accounts = self.money_accounts()
        return accounts[0].id if accounts else None

    def set_default_account(self, account_id: int) -> None:
        if self.get_account(account_id) is None:
            raise ValidationError("Unknown money account.")
        self.settings.set("finance.default_account", str(account_id))

    def balance(self, account_id: int, as_of: str | None = None) -> float:
        acc = self.get_account(account_id)
        if acc is None:
            return 0.0
        limit = as_of or "9999-12-31"
        r = self.db.fetchone(
            "SELECT COALESCE(SUM(CASE WHEN (account_id = ? AND kind IN ('receipt','income','owner_in')) "
            " OR (counter_account_id = ? AND kind = 'transfer') THEN amount ELSE 0 END), 0) AS money_in, "
            "COALESCE(SUM(CASE WHEN account_id = ? AND kind IN ('payment','expense','owner_out','transfer') "
            " THEN amount ELSE 0 END), 0) AS money_out FROM finance_entries "
            "WHERE (account_id = ? OR counter_account_id = ?) AND date <= ?",
            (account_id, account_id, account_id, account_id, account_id, limit),
        )
        return round(acc.opening_balance + float(r["money_in"]) - float(r["money_out"]), 2)

    def balances(self, as_of: str | None = None, active_only: bool = True) -> list[tuple[MoneyAccount, float]]:
        return [(a, self.balance(a.id, as_of)) for a in self.money_accounts(active_only)]

    # Heads -------------------------------------------------------------------------------
    def heads(self, kind: str | None = None, active_only: bool = True) -> list[Head]:
        clauses, params = [], []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if active_only:
            clauses.append("is_active = 1")
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        return [
            Head(r["id"], r["name"], r["kind"], bool(r["is_active"]))
            for r in self.db.fetchall(f"SELECT * FROM expense_heads {where}ORDER BY kind, name", tuple(params))
        ]

    def get_head(self, head_id: int) -> Head | None:
        r = self.db.fetchone("SELECT * FROM expense_heads WHERE id = ?", (head_id,))
        return Head(r["id"], r["name"], r["kind"], bool(r["is_active"])) if r else None

    def add_head(self, name: str, kind: str = "expense", username: str = "system") -> Head:
        name = (name or "").strip().upper()
        if not name:
            raise ValidationError("Head name is required.")
        if kind not in ("expense", "income"):
            raise ValidationError("Kind must be expense or income.")
        if self.db.fetchone("SELECT 1 FROM expense_heads WHERE name = ?", (name,)):
            raise ValidationError(f"Head '{name}' already exists.")
        with self.db.connect():
            hid = self.db.execute("INSERT INTO expense_heads (name, kind) VALUES (?, ?)", (name, kind))
            self.audit.log(AuditCode.FINANCE, f"head {name} ({kind}) added", username)
        return self.get_head(hid)  # type: ignore[return-value]

    def set_head_active(self, head_id: int, active: bool, username: str = "system") -> None:
        with self.db.connect():
            self.db.execute("UPDATE expense_heads SET is_active = ? WHERE id = ?", (1 if active else 0, head_id))
            self.audit.log(AuditCode.FINANCE, f"head {head_id} {'activated' if active else 'deactivated'}", username)

    def rename_head(self, head_id: int, name: str, username: str = "system") -> None:
        name = (name or "").strip().upper()
        if not name:
            raise ValidationError("Head name is required.")
        with self.db.connect():
            self.db.execute("UPDATE expense_heads SET name = ? WHERE id = ?", (name, head_id))
            self.audit.log(AuditCode.FINANCE, f"head {head_id} renamed {name}", username)

    # Entries -----------------------------------------------------------------------------
    def _insert(
        self,
        date,
        kind,
        account_id,
        amount,
        description,
        username,
        counter_account_id=None,
        head_id=None,
        customer_id=None,
        tx_id=None,
    ) -> int:
        date = _validate_date(date)
        amt = _validate_amount(amount)
        if amt <= 0:
            raise ValidationError("Amount must be greater than zero.")
        acc = self.get_account(account_id)
        if acc is None or not acc.is_active:
            raise ValidationError("Pick an active money account.")
        if kind == "transfer":
            other = self.get_account(counter_account_id) if counter_account_id else None
            if other is None or not other.is_active:
                raise ValidationError("Pick the account to transfer to.")
            if other.id == acc.id:
                raise ValidationError("Cannot transfer to the same account.")
        if kind in ("expense", "income"):
            head = self.get_head(head_id) if head_id else None
            if head is None:
                raise ValidationError("Pick a head.")
            if head.kind != kind:
                raise ValidationError(f"'{head.name}' is an {head.kind} head.")
        with self.db.connect():
            eid = self.db.execute(
                "INSERT INTO finance_entries (date, kind, account_id, counter_account_id, head_id, customer_id, amount,"
                " description, tx_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    date,
                    kind,
                    account_id,
                    counter_account_id,
                    head_id,
                    customer_id,
                    round(amt, 2),
                    (description or "").strip(),
                    tx_id,
                    username,
                ),
            )
            self.audit.log(AuditCode.FINANCE, f"{kind} {amt:.2f} {acc.name}: {description}", username)
        return eid

    def add_expense(self, date, account_id, head_id, amount, description="", username="system") -> int:
        return self._insert(date, "expense", account_id, amount, description, username, head_id=head_id)

    def add_income(self, date, account_id, head_id, amount, description="", username="system") -> int:
        return self._insert(date, "income", account_id, amount, description, username, head_id=head_id)

    def transfer(self, date, from_account_id, to_account_id, amount, description="", username="system") -> int:
        return self._insert(
            date, "transfer", from_account_id, amount, description, username, counter_account_id=to_account_id
        )

    def owner(self, date, account_id, amount, direction: str, description="", username="system") -> int:
        kind = "owner_in" if direction == "in" else "owner_out"
        return self._insert(date, kind, account_id, amount, description, username)

    def record_customer_flow(self, kind, date, account_id, customer_id, amount, description, tx_id, username) -> int:
        """Called by the sales service for money entries on the Sales screen."""
        if kind not in ("receipt", "payment"):
            raise ValidationError("kind must be receipt or payment")
        return self._insert(date, kind, account_id, amount, description, username, customer_id=customer_id, tx_id=tx_id)

    _ENTRY_SQL = (
        "SELECT e.*, a.name AS account_name, b.name AS counter_account_name, h.name AS head_name,"
        " c.name AS customer_name "
        "FROM finance_entries e JOIN money_accounts a ON a.id = e.account_id "
        "LEFT JOIN money_accounts b ON b.id = e.counter_account_id LEFT JOIN expense_heads h ON h.id = e.head_id "
        "LEFT JOIN customers c ON c.id = e.customer_id "
    )

    def _entry(self, r) -> Entry:
        return Entry(
            r["id"],
            r["date"],
            r["kind"],
            r["account_id"],
            r["account_name"],
            r["counter_account_id"],
            r["counter_account_name"],
            r["head_id"],
            r["head_name"],
            r["customer_id"],
            r["customer_name"],
            float(r["amount"]),
            r["description"],
            r["tx_id"],
            r["created_by"],
        )

    def get_entry(self, entry_id: int) -> Entry | None:
        r = self.db.fetchone(self._ENTRY_SQL + "WHERE e.id = ?", (entry_id,))
        return self._entry(r) if r else None

    def entries(
        self,
        account_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        kind: str | None = None,
        limit: int = 5000,
    ) -> list[Entry]:
        clauses, params = [], []
        if account_id:
            clauses.append("(e.account_id = ? OR e.counter_account_id = ?)")
            params += [account_id, account_id]
        if date_from:
            clauses.append("e.date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("e.date <= ?")
            params.append(date_to)
        if kind:
            clauses.append("e.kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        rows = self.db.fetchall(self._ENTRY_SQL + where + "ORDER BY e.date, e.id LIMIT ?", (*params, limit))
        return [self._entry(r) for r in rows]

    def cash_book(self, account_id: int, date_from: str, date_to: str) -> tuple[float, list[tuple], float]:
        """(opening, rows, closing); rows = (id, date, kind label, description, in, out, balance)."""
        opening = self.balance(account_id, (parse_date(date_from) - dt.timedelta(days=1)).strftime(DATE_FMT))
        running = opening
        rows = []
        for e in self.entries(account_id, date_from, date_to):
            money_in = money_out = 0.0
            if e.kind == "transfer":
                if e.counter_account_id == account_id:
                    money_in = e.amount
                else:
                    money_out = e.amount
            elif e.kind in IN_KINDS:
                money_in = e.amount
            else:
                money_out = e.amount
            running = round(running + money_in - money_out, 2)
            who = (
                e.customer_name
                or e.head_name
                or (
                    f"→ {e.counter_account_name}"
                    if e.kind == "transfer" and e.counter_account_id != account_id
                    else f"← {e.account_name}"
                    if e.kind == "transfer"
                    else ""
                )
            )
            rows.append(
                (
                    e.id,
                    e.date,
                    e.label,
                    f"{who}  {e.description}".strip(),
                    money_in or None,
                    money_out or None,
                    running,
                    e.created_by or "",
                    e.tx_id,
                )
            )
        return opening, rows, running

    def delete_entry(self, entry_id: int, username: str) -> None:
        e = self.get_entry(entry_id)
        if e is None:
            return
        with self.db.connect():
            self.db.execute("DELETE FROM finance_entries WHERE id = ?", (entry_id,))
            self.audit.log(
                AuditCode.DELETE, f"finance entry {entry_id} ({e.kind} {e.amount:.2f} {e.account_name})", username
            )

    # Recurring ---------------------------------------------------------------------------
    def add_recurring(
        self,
        head_id,
        account_id,
        amount,
        day_of_month,
        description="",
        start_month: str | None = None,
        username="system",
    ) -> Recurring:
        head = self.get_head(head_id)
        if head is None or head.kind != "expense":
            raise ValidationError("Pick an expense head.")
        if self.get_account(account_id) is None:
            raise ValidationError("Pick a money account.")
        amt = _validate_amount(amount)
        if amt <= 0:
            raise ValidationError("Amount must be greater than zero.")
        day = int(day_of_month)
        if not 1 <= day <= 28:
            raise ValidationError("Day of month must be 1-28.")
        start = start_month or _month(dt.date.today())
        with self.db.connect():
            rid = self.db.execute(
                "INSERT INTO finance_recurring (head_id, account_id, amount, day_of_month, description, start_month)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (head_id, account_id, amt, day, (description or "").strip(), start),
            )
            self.audit.log(AuditCode.FINANCE, f"recurring {head.name} {amt:g} on day {day}", username)
        return self.get_recurring(rid)  # type: ignore[return-value]

    _REC_SQL = (
        "SELECT r.*, h.name AS head_name, a.name AS account_name FROM finance_recurring r "
        "JOIN expense_heads h ON h.id = r.head_id JOIN money_accounts a ON a.id = r.account_id "
    )

    def _rec(self, r) -> Recurring:
        return Recurring(
            r["id"],
            r["head_id"],
            r["head_name"],
            r["account_id"],
            r["account_name"],
            float(r["amount"]),
            int(r["day_of_month"]),
            r["description"],
            bool(r["is_active"]),
            r["start_month"],
            r["last_posted"],
        )

    def get_recurring(self, rid: int) -> Recurring | None:
        r = self.db.fetchone(self._REC_SQL + "WHERE r.id = ?", (rid,))
        return self._rec(r) if r else None

    def recurring(self, active_only: bool = False) -> list[Recurring]:
        where = "WHERE r.is_active = 1 " if active_only else ""
        return [self._rec(r) for r in self.db.fetchall(self._REC_SQL + where + "ORDER BY r.id")]

    def set_recurring_active(self, rid: int, active: bool, username="system") -> None:
        with self.db.connect():
            self.db.execute("UPDATE finance_recurring SET is_active = ? WHERE id = ?", (1 if active else 0, rid))
            self.audit.log(AuditCode.FINANCE, f"recurring {rid} {'on' if active else 'off'}", username)

    def delete_recurring(self, rid: int, username="system") -> None:
        with self.db.connect():
            self.db.execute("DELETE FROM finance_recurring WHERE id = ?", (rid,))
            self.audit.log(AuditCode.DELETE, f"recurring {rid}", username)

    def due_recurring(self, today: dt.date | None = None) -> list[tuple[Recurring, list[str]]]:
        """Each active recurring expense with the months (YYYY-MM) not yet posted and due."""
        today = today or dt.date.today()
        out = []
        for r in self.recurring(active_only=True):
            month = _next_month(r.last_posted) if r.last_posted else r.start_month
            due = []
            while month < _month(today) or (month == _month(today) and today.day >= r.day_of_month):
                due.append(month)
                month = _next_month(month)
            if due:
                out.append((r, due))
        return out

    def post_due(self, username: str, today: dt.date | None = None) -> int:
        today = today or dt.date.today()
        posted = 0
        with self.db.connect():
            for r, months in self.due_recurring(today):
                for ym in months:
                    date = f"{ym}-{r.day_of_month:02d}"
                    self.add_expense(
                        date, r.account_id, r.head_id, r.amount, f"{r.description or r.head_name} {ym}", username
                    )
                    posted += 1
                self.db.execute("UPDATE finance_recurring SET last_posted = ? WHERE id = ?", (months[-1], r.id))
        return posted

    # Reports -----------------------------------------------------------------------------
    def cash_flow(self, date_from: str, date_to: str) -> CashFlow:
        cf = CashFlow(date_from, date_to)
        rows = self.db.fetchall(
            "SELECT kind, COALESCE(SUM(amount), 0) AS a FROM finance_entries WHERE date BETWEEN ? AND ? GROUP BY kind",
            (date_from, date_to),
        )
        sums = {r["kind"]: round(float(r["a"]), 2) for r in rows}
        for k in ("receipt", "income", "owner_in"):
            if sums.get(k):
                cf.inflows[KIND_LABELS[k]] = sums[k]
        for k in ("payment", "expense", "owner_out"):
            if sums.get(k):
                cf.outflows[KIND_LABELS[k]] = sums[k]
        cf.expenses_by_head = self.expenses_by_head(date_from, date_to)
        prev = (parse_date(date_from) - dt.timedelta(days=1)).strftime(DATE_FMT)
        for a in self.money_accounts(active_only=False):
            opening = self.balance(a.id, prev)
            closing = self.balance(a.id, date_to)
            _o, rows_, _c = self.cash_book(a.id, date_from, date_to)
            money_in = round(sum(r[4] or 0 for r in rows_), 2)
            money_out = round(sum(r[5] or 0 for r in rows_), 2)
            if a.is_active or rows_ or opening or closing:
                cf.accounts.append((a.name, opening, money_in, money_out, closing))
        return cf

    def expenses_by_head(self, date_from: str, date_to: str, kind: str = "expense") -> list[tuple[str, float]]:
        rows = self.db.fetchall(
            "SELECT h.name, COALESCE(SUM(e.amount), 0) AS a FROM finance_entries e "
            "JOIN expense_heads h ON h.id = e.head_id "
            "WHERE e.kind = ? AND e.date BETWEEN ? AND ? GROUP BY h.id ORDER BY a DESC",
            (kind, date_from, date_to),
        )
        return [(r["name"], round(float(r["a"]), 2)) for r in rows]

    def monthly_expenses(self, months: int = 12, today: dt.date | None = None) -> list[tuple[str, float, float]]:
        """(YYYY-MM, expenses, other income) for the last N calendar months up to ``today``'s, oldest first."""
        today = today or dt.date.today()
        y, m = divmod(today.year * 12 + today.month - months, 12)  # first of the earliest month
        first = dt.date(y, m + 1, 1)
        rows = self.db.fetchall(
            "SELECT substr(date, 1, 7) AS m, "
            "COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount END), 0) AS ex, "
            "COALESCE(SUM(CASE WHEN kind = 'income' THEN amount END), 0) AS inc "
            "FROM finance_entries WHERE date >= ? GROUP BY m ORDER BY m",
            (first.strftime(DATE_FMT),),
        )
        return [(r["m"], round(float(r["ex"]), 2), round(float(r["inc"]), 2)) for r in rows]

    def profit_and_loss(self, date_from: str, date_to: str) -> ProfitAndLoss:
        """Gross margin on items (sale value - cost at the item's current stock value) and crops
        (FIFO margin), plus other income, minus expenses.  Interest on customer balances is
        not included - it is accrued, not received."""
        pl = ProfitAndLoss(date_from, date_to)
        r = self.db.fetchone(
            "SELECT COALESCE(SUM(t.value), 0) AS rev, COALESCE(SUM(t.sale * i.stock_value), 0) AS cogs "
            "FROM item_transactions t JOIN items i ON i.id = t.item_id "
            "WHERE t.sale > 0 AND t.value > 0 AND i.item_type != 'C' AND t.date BETWEEN ? AND ?",
            (date_from, date_to),
        )
        pl.item_revenue, pl.item_cogs = round(float(r["rev"]), 2), round(float(r["cogs"]), 2)
        if self.db.fetchone("SELECT 1 FROM sqlite_master WHERE name = 'crop_sales'"):
            c = self.db.fetchone(
                "SELECT COALESCE(SUM(amount), 0) AS rev, COALESCE(SUM(cost), 0) AS cost FROM crop_sales "
                "WHERE date BETWEEN ? AND ?",
                (date_from, date_to),
            )
            pl.crop_revenue, pl.crop_cost = round(float(c["rev"]), 2), round(float(c["cost"]), 2)
        pl.other_income = round(sum(a for _, a in self.expenses_by_head(date_from, date_to, "income")), 2)
        pl.expenses = self.expenses_by_head(date_from, date_to)
        return pl
