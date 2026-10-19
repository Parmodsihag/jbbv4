"""Bills: tax computation, storage, month-end batch generation, DOCX/PDF rendering.

Business rules carried over from v3:
  * CGST = SGST = 9 % for pesticides (type P), 2.5 % for fertiliser (F), 0 for seeds/other
  * grand total = taxable + CGST + SGST (IGST never applies - all sales are in-state)
  * amount in words in Hindi
  * a bill of 20,000 or more is not rendered (cash-sale limit) - the batch reports them
  * month batch: monthly item totals are split at random across ~N bills over the month's
    dates (not before each item's start date) with random customer names, from a start number
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import math
import random
import re
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from hth.config import Settings
from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.interest import parse_date
from hth.modules.bills.numwords import to_currency
from hth.services.accounts import ValidationError, _validate_date
from hth.services.audit import AuditService

log = logging.getLogger(__name__)

GST_HALF_RATE: dict[str, float] = {"P": 9.0, "F": 2.5}  # CGST (= SGST) percent by item type
MAX_RENDER_TOTAL = 20000.0
DEFAULT_ADDRESS = "Dhansu"
TEMPLATE = Path(__file__).parent / "templates" / "invoice.docx"

RANDOM_NAMES = [
    "रमेश",
    "लेखरम",
    "सुभाष",
    "राजेश",
    "महावीर",
    "सुरेश",
    "माईलाल",
    "हवासिंघ",
    "बलबीर",
    "मोमन",
    "संदीप",
    "लुणाराम",
    "सोनू",
    "लिलु",
    "मोलुराम",
    "हनुमान",
    "सतबीर",
    "हंशराज",
    "विजय",
    "अनूप",
    "सुशील",
    "उमेद",
    "सतपाल",
    "शंकर",
    "ईस्वर",
    "कृष्ण",
    "मंजीत",
    "मनीराम",
    "दिलबाग",
    "बुधराम",
    "उग्रसेन",
    "राहुल",
    "बजीर",
    "मंगतुराम",
    "विष्णु",
    "रोहताश",
    "रामभगत",
    "बंशी",
    "दारासिंह",
    "दर्शन",
    "जोगेन्दर",
    "पप्पू",
    "संतलाल",
    "बिंदर",
    "रामनिवास",
    "भूप",
    "भूपसिंघ",
    "बलवंत",
    "ज्वाहरलाल",
    "फुसाराम",
    "नेकीराम",
    "सुरेंदर",
    "मदन",
    "आत्माराम",
    "कालूरम",
    "सज्जन",
    "जगमाल",
    "रामजीलाल",
    "नवीन",
    "विक्रम",
    "दीपक",
    "दिनेश",
    "बंटी",
    "राजबीर",
    "रामलाल",
    "रणवीर",
    "मोहित",
    "जगदीश",
    "नरेंदर",
    "सुमित",
    "सिशपाल",
    "भालसिंघ",
    "विकास",
    "मंदीप",
    "बलराज",
    "ओमप्रकाश",
    "अशोक",
    "विनोद",
    "रामफल",
    "संजय",
    "सुल्तान",
    "राजेंदर",
    "विरेंदर",
    "अनिल",
]


@dataclass(frozen=True)
class BillLine:
    name: str
    unit: str
    batch: str
    expiry_date: str
    rate: float
    item_type: str
    quantity: float
    amount: float
    gst_rate: float  # CGST percent (SGST is the same)
    cgst: float
    sgst: float
    id: int = 0


@dataclass(frozen=True)
class Bill:
    id: int
    bill_number: int
    date: str
    customer_name: str
    customer_address: str
    customer_id: int | None
    taxable: float
    cgst: float
    sgst: float
    grand_total: float
    source: str
    docx_path: str | None
    lines: list[BillLine] = field(default_factory=list)


@dataclass(frozen=True)
class MonthItem:
    id: int
    month_year: str
    item_id: int | None
    name: str
    unit: str
    rate: float
    item_type: str
    start_date: str
    batch: str
    expiry_date: str
    quantity: float


@dataclass
class BatchResult:
    created: int = 0
    rendered: int = 0
    not_rendered: list[int] = field(default_factory=list)  # bill numbers >= MAX_RENDER_TOTAL
    unsold: dict[str, float] = field(default_factory=dict)  # item name -> leftover quantity
    first_number: int = 0
    last_number: int = 0


# --- pure tax maths -------------------------------------------------------------------------
def compute_line(name, unit, batch, expiry_date, rate, item_type, quantity) -> BillLine:
    rate_f, qty_f = float(rate), float(quantity)
    if qty_f <= 0:
        raise ValidationError(f"{name}: quantity must be greater than zero.")
    if rate_f < 0:
        raise ValidationError(f"{name}: rate cannot be negative.")
    item_type = (item_type or "O").strip().upper()[:1]
    amount = round(rate_f * qty_f, 2)
    half = GST_HALF_RATE.get(item_type, 0.0)
    cgst = round(amount * half / 100, 2)
    return BillLine(
        (name or "").strip(),
        (unit or "").strip().upper(),
        (batch or "NA").strip(),
        (expiry_date or "NA").strip(),
        rate_f,
        item_type,
        qty_f,
        amount,
        half,
        cgst,
        cgst,
    )


def totals(lines: Sequence[BillLine]) -> tuple[float, float, float, float]:
    taxable = round(sum(line.amount for line in lines), 2)
    cgst = round(sum(line.cgst for line in lines), 2)
    sgst = round(sum(line.sgst for line in lines), 2)
    return taxable, cgst, sgst, round(taxable + cgst + sgst, 2)


def _month_bounds(month_year: str) -> tuple[dt.date, dt.date]:
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", (month_year or "").strip())
    if not m:
        raise ValidationError("Month must be YYYY-MM.")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValidationError("Month must be 01-12.")
    start = dt.date(year, month, 1)
    end = (dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)) - dt.timedelta(days=1)
    return start, end


def normalize_month(month_year: str) -> str:
    start, _ = _month_bounds(month_year)
    return start.strftime("%Y-%m")


def _n(v: float) -> str:
    """Number as printed on the invoice: exact to 4 dp, trailing zeros dropped, never an exponent.

    (``:g`` keeps only 6 significant digits, so 19999.99 printed as 20000 and 1234567 as 1.23457e+06.)
    """
    return f"{round(float(v), 4) + 0.0:.4f}".rstrip("0").rstrip(".")


class BillsService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.audit = AuditService(db)
        self.bills_dir = settings.data_dir / "bills"
        self.pdf_dir = settings.data_dir / "pdfs"
        self.merged_dir = settings.data_dir / "merged_pdfs"

    # Month items --------------------------------------------------------------------------
    def add_month_item(
        self,
        month_year,
        name,
        unit,
        rate,
        item_type,
        start_date,
        batch,
        expiry_date,
        quantity,
        item_id: int | None = None,
        username: str = "system",
    ) -> MonthItem:
        month_year = normalize_month(month_year)
        start_date = _validate_date(start_date)
        start, end = _month_bounds(month_year)
        if not start <= parse_date(start_date) <= end:
            raise ValidationError(f"Start date must be within {month_year}.")
        name = (name or "").strip()
        if not name:
            raise ValidationError("Item name is required.")
        try:
            qty = float(quantity)
            rate_f = float(rate)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Quantity and rate must be numbers.") from exc
        if not (math.isfinite(qty) and math.isfinite(rate_f)):
            raise ValidationError("Quantity and rate must be numbers.")
        if qty <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if rate_f < 0:  # caught here, not half-way through generating the month
            raise ValidationError("Rate cannot be negative.")
        with self.db.connect():
            row_id = self.db.execute(
                "INSERT INTO bill_month_items (month_year, item_id, name, unit, rate, item_type, start_date, batch,"
                " expiry_date, quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    month_year,
                    item_id,
                    name,
                    (unit or "").upper(),
                    rate_f,
                    (item_type or "O").upper()[:1],
                    start_date,
                    batch or "NA",
                    expiry_date or "NA",
                    qty,
                ),
            )
            self.audit.log(AuditCode.MODIFY, f"bill month item {month_year}: {name} x {qty:g}", username)
        return self.get_month_item(row_id)  # type: ignore[return-value]

    def get_month_item(self, row_id: int) -> MonthItem | None:
        r = self.db.fetchone("SELECT * FROM bill_month_items WHERE id = ?", (row_id,))
        return MonthItem(**{k: r[k] for k in MonthItem.__dataclass_fields__}) if r else None

    def month_items(self, month_year: str) -> list[MonthItem]:
        rows = self.db.fetchall(
            "SELECT * FROM bill_month_items WHERE month_year = ? ORDER BY id", (normalize_month(month_year),)
        )
        return [MonthItem(**{k: r[k] for k in MonthItem.__dataclass_fields__}) for r in rows]

    def delete_month_item(self, row_id: int, username: str = "system") -> None:
        with self.db.connect():
            self.db.execute("DELETE FROM bill_month_items WHERE id = ?", (row_id,))
            self.audit.log(AuditCode.DELETE, f"bill month item {row_id}", username)

    def month_years(self) -> list[str]:
        a = {r[0] for r in self.db.fetchall("SELECT DISTINCT month_year FROM bill_month_items")}
        b = {r[0] for r in self.db.fetchall("SELECT DISTINCT substr(date, 1, 7) FROM bills")}
        return sorted(a | b, reverse=True)

    # Bills --------------------------------------------------------------------------------
    def next_bill_number(self, on_date: dt.date | None = None) -> int:
        """Next number in the financial year of ``on_date`` (default today): 2627001, 2627002, ...

        Each FY (April-March) restarts at 001 under its own prefix.  Past 999 the sequence
        just grows (26271000) instead of rolling into what looks like another year's prefix.
        Numbers typed outside the scheme (e.g. 1, 2, 3) do not affect it.
        """
        d = on_date or dt.date.today()
        fy = d.year if d.month >= 4 else d.year - 1
        prefix = f"{fy % 100:02d}{(fy + 1) % 100:02d}"  # e.g. 2627 for FY 2026-27
        row = self.db.fetchone(
            "SELECT MAX(CAST(substr(CAST(bill_number AS TEXT), 5) AS INTEGER)) AS m FROM bills"
            " WHERE CAST(bill_number AS TEXT) LIKE ?",
            (f"{prefix}___%",),
        )
        last = int(row["m"]) if row and row["m"] else 0
        return int(f"{prefix}{last + 1:03d}")

    def create_bill(
        self,
        date: str,
        customer_name: str,
        customer_address: str,
        lines: Sequence[dict],
        username: str,
        bill_number: int | None = None,
        customer_id: int | None = None,
        source: str = "manual",
    ) -> Bill:
        date = _validate_date(date)
        customer_name = (customer_name or "").strip()
        if not customer_name:
            raise ValidationError("Customer name is required.")
        if not lines:
            raise ValidationError("Add at least one item.")
        computed = [compute_line(**line) for line in lines]
        taxable, cgst, sgst, grand = totals(computed)
        with self.db.connect():
            number = int(bill_number) if bill_number else self.next_bill_number(parse_date(date))
            if self.db.fetchone("SELECT 1 FROM bills WHERE bill_number = ?", (number,)):
                raise ValidationError(f"Bill number {number} already exists.")
            bill_id = self.db.execute(
                "INSERT INTO bills (bill_number, date, customer_name, customer_address, customer_id, taxable, cgst,"
                " sgst, grand_total, source, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    number,
                    date,
                    customer_name,
                    (customer_address or "").strip(),
                    customer_id,
                    taxable,
                    cgst,
                    sgst,
                    grand,
                    source,
                    username,
                ),
            )
            for line in computed:
                self.db.execute(
                    "INSERT INTO bill_lines (bill_id, name, unit, batch, expiry_date, rate, item_type, quantity,"
                    " amount, gst_rate, cgst, sgst) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        bill_id,
                        line.name,
                        line.unit,
                        line.batch,
                        line.expiry_date,
                        line.rate,
                        line.item_type,
                        line.quantity,
                        line.amount,
                        line.gst_rate,
                        line.cgst,
                        line.sgst,
                    ),
                )
            if source == "manual":
                self.audit.log(AuditCode.SALE, f"bill {number} {date} {customer_name} total {grand:.2f}", username)
        return self.get_bill(bill_id)  # type: ignore[return-value]

    def _bill(self, r, with_lines: bool = True) -> Bill:
        lines = []
        if with_lines:
            lines = [
                BillLine(
                    x["name"],
                    x["unit"],
                    x["batch"],
                    x["expiry_date"],
                    x["rate"],
                    x["item_type"],
                    x["quantity"],
                    x["amount"],
                    x["gst_rate"],
                    x["cgst"],
                    x["sgst"],
                    x["id"],
                )
                for x in self.db.fetchall("SELECT * FROM bill_lines WHERE bill_id = ? ORDER BY id", (r["id"],))
            ]
        return Bill(
            r["id"],
            r["bill_number"],
            r["date"],
            r["customer_name"],
            r["customer_address"],
            r["customer_id"],
            r["taxable"],
            r["cgst"],
            r["sgst"],
            r["grand_total"],
            r["source"],
            r["docx_path"],
            lines,
        )

    def get_bill(self, bill_id: int) -> Bill | None:
        r = self.db.fetchone("SELECT * FROM bills WHERE id = ?", (bill_id,))
        return self._bill(r) if r else None

    def get_by_number(self, number: int) -> Bill | None:
        r = self.db.fetchone("SELECT * FROM bills WHERE bill_number = ?", (number,))
        return self._bill(r) if r else None

    def list_bills(self, month_year: str | None = None, search: str | None = None, limit: int = 2000) -> list[Bill]:
        clauses, params = [], []
        if month_year:
            clauses.append("substr(date, 1, 7) = ?")
            params.append(normalize_month(month_year))
        if search:
            clauses.append("(customer_name LIKE ? OR CAST(bill_number AS TEXT) LIKE ?)")
            params += [f"%{search}%", f"%{search}%"]
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.fetchall(f"SELECT * FROM bills {where} ORDER BY bill_number DESC LIMIT ?", (*params, limit))
        return [self._bill(r, with_lines=False) for r in rows]

    def bills_exist_for_month(self, month_year: str) -> bool:
        return (
            self.db.fetchone("SELECT 1 FROM bills WHERE substr(date, 1, 7) = ? LIMIT 1", (normalize_month(month_year),))
            is not None
        )

    def delete_bill(self, bill_id: int, username: str) -> None:
        bill = self.get_bill(bill_id)
        with self.db.connect():
            self.db.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
            self.audit.log(AuditCode.DELETE, f"bill {bill.bill_number if bill else bill_id}", username)
        if bill:
            self._remove_files(bill.bill_number)

    def delete_month(self, month_year: str, username: str) -> int:
        month_year = normalize_month(month_year)
        numbers = [
            r[0] for r in self.db.fetchall("SELECT bill_number FROM bills WHERE substr(date, 1, 7) = ?", (month_year,))
        ]
        with self.db.connect():
            self.db.execute("DELETE FROM bills WHERE substr(date, 1, 7) = ?", (month_year,))
            self.audit.log(AuditCode.DELETE, f"bills for {month_year}: {len(numbers)} deleted", username)
        for n in numbers:
            self._remove_files(n)
        return len(numbers)

    def _remove_files(self, number: int) -> None:
        for path in (self.bills_dir / f"{number}.docx", self.pdf_dir / f"{number}.pdf"):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                log.warning("could not delete %s", path)

    def month_summary(self, month_year: str) -> tuple[int, float, float, float]:
        r = self.db.fetchone(
            "SELECT COUNT(*) AS n, COALESCE(SUM(taxable), 0) AS t, COALESCE(SUM(cgst + sgst), 0) AS g,"
            " COALESCE(SUM(grand_total), 0) AS gt FROM bills WHERE substr(date, 1, 7) = ?",
            (normalize_month(month_year),),
        )
        return (r["n"], round(r["t"], 2), round(r["g"], 2), round(r["gt"], 2)) if r else (0, 0.0, 0.0, 0.0)

    # Rendering ----------------------------------------------------------------------------
    @staticmethod
    def _pad(values, width: int) -> str:
        """v3 ``convert_to_str``: fixed-width columns inside one template cell."""
        return "".join(f"{v}{' ' * (width - len(str(v))) * 2}    " for v in values)

    def template_context(self, bill: Bill) -> dict:
        lines = bill.lines
        n = len(lines)
        dashes = lambda w: self._pad(["-"] * n, w)  # noqa: E731
        return {
            "bill_number": bill.bill_number,
            "given_date": parse_date(bill.date).strftime("%d-%m-%Y"),
            "customer_name": bill.customer_name,
            "customer_address": bill.customer_address,
            "all_items_details": self._pad([line.name for line in lines], 30),
            "serial_number": self._pad(range(1, n + 1), 3),
            "quantity": self._pad([_n(line.quantity) for line in lines], 4),
            "item_unit": self._pad([line.unit for line in lines], 8),
            "batch_number": self._pad([line.batch for line in lines], 11),
            "expiry_date": self._pad([line.expiry_date for line in lines], 10),
            "rate": self._pad([_n(line.rate) for line in lines], 4),
            "total_sale": self._pad([_n(line.amount) for line in lines], 7),
            "total_discount": dashes(6),
            "taxable_amount": self._pad([_n(line.amount) for line in lines], 7),
            "crate": self._pad([_n(line.gst_rate) for line in lines], 3),
            "ccost": self._pad([_n(line.cgst) for line in lines], 8),
            "srate": self._pad([_n(line.gst_rate) for line in lines], 3),
            "scost": self._pad([_n(line.sgst) for line in lines], 7),
            "irate": dashes(3),
            "icost": dashes(6),
            "taxable_amount_total": _n(bill.taxable),
            "ctotal": _n(bill.cgst),
            "stotal": _n(bill.sgst),
            "grand_total": _n(bill.grand_total),
            "total_amount_in_words": to_currency(bill.grand_total),
        }

    @staticmethod
    def missing_dependencies() -> list[str]:
        missing = []
        for module, package in (("docxtpl", "docxtpl"), ("pypdf", "pypdf")):
            try:
                __import__(module)
            except ImportError:
                missing.append(package)
        return missing

    @staticmethod
    def _check_renderable() -> None:
        try:
            import docxtpl  # noqa: F401
        except ImportError as exc:
            raise ValidationError("Cannot create the DOCX: run  pip install docxtpl  and restart.") from exc
        if not TEMPLATE.exists():
            raise ValidationError(f"Invoice template missing: {TEMPLATE}")

    @staticmethod
    def _fingerprint(context: dict) -> str:
        """Identifies exactly what a rendered invoice shows (stored in the DOCX properties)."""
        payload = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _rendered_fingerprint(path: Path) -> str | None:
        try:
            from docx import Document

            return Document(str(path)).core_properties.identifier or None
        except Exception:  # noqa: BLE001 - unreadable or pre-fingerprint file: render it again
            return None

    def render_docx(self, bill: Bill, force: bool = False) -> Path:
        return self._ensure_docx(bill, force)[0]

    def _ensure_docx(self, bill: Bill, force: bool = False) -> tuple[Path, bool]:
        """Return (path, rendered_now).

        An existing ``<number>.docx`` is reused only if it was rendered from this exact bill.
        Files are named by bill number, so one left behind by another bill with the same
        number (a deleted bill whose file was open in Word, a restored backup) used to be
        handed out as this bill's invoice.
        """
        self._check_renderable()
        from docxtpl import DocxTemplate

        self.bills_dir.mkdir(parents=True, exist_ok=True)
        out = self.bills_dir / f"{bill.bill_number}.docx"
        context = self.template_context(bill)
        fingerprint = self._fingerprint(context)
        if out.exists() and not force and self._rendered_fingerprint(out) == fingerprint:
            return out, False
        tpl = DocxTemplate(str(TEMPLATE))
        tpl.render(context)
        tpl.docx.core_properties.identifier = fingerprint
        tpl.save(str(out))
        self.db.execute("UPDATE bills SET docx_path = ? WHERE id = ?", (str(out), bill.id))
        return out, True

    def docx_path(self, bill: Bill) -> Path | None:
        p = self.bills_dir / f"{bill.bill_number}.docx"
        return p if p.exists() else None

    def pdf_path(self, bill_number: int) -> Path | None:
        p = self.pdf_dir / f"{bill_number}.pdf"
        return p if p.exists() else None

    def render_pdf(self, bill: Bill, force: bool = False) -> Path:
        """DOCX -> PDF via Microsoft Word (docx2pdf).  Windows/macOS with Word only."""
        try:
            from docx2pdf import convert
        except ImportError as exc:
            raise ValidationError(
                "PDF export needs the 'docx2pdf' package and Microsoft Word (pip install docx2pdf)."
            ) from exc
        docx, rendered_now = self._ensure_docx(bill)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        out = self.pdf_dir / f"{bill.bill_number}.pdf"
        # A PDF is only as current as the DOCX it came from.
        if out.exists() and not force and not rendered_now and out.stat().st_mtime >= docx.stat().st_mtime:
            return out
        with _com_initialized():
            convert(str(docx), str(out))
        return out

    def merge_pdfs(self, from_number: int, to_number: int) -> Path:
        try:
            from pypdf import PdfWriter
        except ImportError as exc:
            raise ValidationError("Merging needs the 'pypdf' package (pip install pypdf).") from exc
        # Only bills that exist: a leftover PDF of a deleted bill must not end up in the merge.
        numbers = [
            r[0]
            for r in self.db.fetchall(
                "SELECT bill_number FROM bills WHERE bill_number BETWEEN ? AND ? ORDER BY bill_number",
                (int(from_number), int(to_number)),
            )
            if self.pdf_path(r[0])
        ]
        if not numbers:
            raise ValidationError("No PDFs found in that range - make PDFs first.")
        self.merged_dir.mkdir(parents=True, exist_ok=True)
        out = self.merged_dir / f"{from_number}to{to_number}.pdf"
        writer = PdfWriter()
        for n in numbers:
            writer.append(str(self.pdf_path(n)))
        with open(out, "wb") as fh:
            writer.write(fh)
        writer.close()
        return out

    # Month batch --------------------------------------------------------------------------
    @staticmethod
    def distribute_dates(total_bills: int, start: dt.date, end: dt.date, rng: random.Random) -> list[dt.date]:
        """v3 ``distribute_bills_to_dates``: ~N bills spread over the month, +-1 per day."""
        days = (end - start).days + 1
        per_day = round(total_bills / days)
        out = []
        for i in range(days):
            day = start + dt.timedelta(days=i)
            for _ in range(max(0, rng.randint(per_day - 1, per_day + 1))):
                out.append(day)
        return out

    @staticmethod
    def distribute_quantities(
        items: list[tuple[int, float, dt.date]], dates: list[dt.date], rng: random.Random
    ) -> tuple[list[tuple[dt.date, dict[int, float]]], dict[int, float]]:
        """Split each item's monthly quantity across the bill dates (never before its start date).

        Returns ([(date, {item_id: qty})...], leftovers).  Quantities are whole numbers, as
        in v3; items whose total is fractional get the fraction on their last bill.
        """
        remaining = {item_id: qty for item_id, qty, _ in items}
        start_of = {item_id: sd for item_id, _, sd in items}
        per_bill = {item_id: round(qty / max(1, len(dates))) + 1 for item_id, qty, _ in items}
        bills: list[tuple[dt.date, dict[int, float]]] = []
        for date in dates:
            available = [i for i, q in remaining.items() if q > 0 and start_of[i] <= date]
            if not available:
                continue
            count = rng.randint(1, min(3, len(available))) if len(available) > 1 else 1
            chosen = rng.sample(available, count)
            lines: dict[int, float] = {}
            for item_id in chosen:
                left = remaining[item_id]
                x = per_bill[item_id]
                # Once less than a usual bill's worth is left, cap the low end too, or
                # randint(low, high) gets low > high and raises "empty range for randrange".
                high = max(1, min(x + 1, int(left)))
                take = float(rng.randint(min(max(1, x - 2), high), high))
                if left - take < 1:  # do not strand a fraction
                    take = left
                lines[item_id] = take
                remaining[item_id] = round(left - take, 4)
            bills.append((date, lines))
        # Whatever is left (v3 reported it as "unsold") is spread over the existing bills
        # that fall on or after the item's start date, so the month's totals always match.
        for item_id, left in list(remaining.items()):
            eligible = [b for b in bills if b[0] >= start_of[item_id]]
            if not eligible:
                continue
            x = max(1, per_bill[item_id])
            while left > 0 and eligible:
                _date, lines = rng.choice(eligible)
                take = min(float(x), left)
                if left - take < 1:
                    take = left
                lines[item_id] = round(lines.get(item_id, 0) + take, 4)
                left = round(left - take, 4)
            remaining[item_id] = left
        leftovers = {i: q for i, q in remaining.items() if q > 0}
        return bills, leftovers

    def generate_month(
        self,
        month_year: str,
        number_of_bills: int,
        start_number: int,
        username: str,
        render: bool = True,
        rng: random.Random | None = None,
        address: str = DEFAULT_ADDRESS,
        progress=None,
    ) -> BatchResult:
        rng = rng or random.Random()
        month_year = normalize_month(month_year)
        if self.bills_exist_for_month(month_year):
            raise ValidationError(f"Bills for {month_year} already exist - delete them first.")
        items = self.month_items(month_year)
        if not items:
            raise ValidationError(f"No items entered for {month_year}.")
        if int(number_of_bills) <= 0:
            raise ValidationError("Number of bills must be positive.")
        if render:
            self._check_renderable()  # fail before creating anything, not after the commit
        start, end = _month_bounds(month_year)
        dates = self.distribute_dates(int(number_of_bills), start, end, rng)
        plan, leftovers = self.distribute_quantities(
            [(it.id, it.quantity, parse_date(it.start_date)) for it in items], dates, rng
        )
        by_id = {it.id: it for it in items}
        first = int(start_number)
        last = first + len(plan) - 1
        clash = [
            r[0]
            for r in self.db.fetchall(
                "SELECT bill_number FROM bills WHERE bill_number BETWEEN ? AND ? ORDER BY bill_number", (first, last)
            )
        ]
        if clash:
            raise ValidationError(
                f"This batch needs bill numbers {first}-{last}, but {', '.join(map(str, clash[:5]))}"
                f"{' and more' if len(clash) > 5 else ''} already exist. Choose another start number."
            )
        result = BatchResult(first_number=first)
        bills: list[Bill] = []
        # One transaction for the whole month: a failure part-way rolls every bill back
        # instead of leaving a partial month that then blocks a retry.
        with self.db.connect():
            for number, (date, lines) in enumerate(plan, start=first):
                bills.append(
                    self.create_bill(
                        date.strftime(DATE_FMT),
                        rng.choice(RANDOM_NAMES),
                        address,
                        [
                            dict(
                                name=by_id[i].name,
                                unit=by_id[i].unit,
                                batch=by_id[i].batch,
                                expiry_date=by_id[i].expiry_date,
                                rate=by_id[i].rate,
                                item_type=by_id[i].item_type,
                                quantity=q,
                            )
                            for i, q in lines.items()
                        ],
                        username,
                        bill_number=number,
                        source="batch",
                    )
                )
            self.audit.log(AuditCode.MODIFY, f"bills batch {month_year}: {len(bills)} bills from {first}", username)
        result.created = len(bills)
        result.last_number = bills[-1].bill_number if bills else 0
        # Rendering happens after the commit, so slow DOCX work never holds the write lock.
        for idx, bill in enumerate(bills):
            if render:
                if bill.grand_total < MAX_RENDER_TOTAL:
                    self.render_docx(bill)
                    result.rendered += 1
                else:
                    result.not_rendered.append(bill.bill_number)
            if progress:
                progress(idx + 1, len(bills))
        result.unsold = {by_id[i].name: q for i, q in leftovers.items()}
        return result

    def open_folder(self) -> Path:
        self.bills_dir.mkdir(parents=True, exist_ok=True)
        return self.bills_dir


@contextmanager
def _com_initialized() -> Iterator[None]:
    """docx2pdf drives Word over COM but never initialises COM, which every thread must do.

    Without this, "PDF + merge range" (a worker thread) failed with "CoInitialize has not
    been called".  On the Tk thread COM is already up; the extra init/uninit pair is harmless.
    """
    if not sys.platform.startswith("win"):
        yield
        return
    import pythoncom  # pywin32, installed with docx2pdf on Windows

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


def word_available() -> bool:
    if not (sys.platform.startswith("win") or sys.platform == "darwin"):
        return False
    try:
        import docx2pdf  # noqa: F401
    except ImportError:
        return False
    return True
