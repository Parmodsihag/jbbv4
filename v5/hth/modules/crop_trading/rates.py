"""Market rates: storage, providers and a rough trend estimate.

Today rates are entered by hand or imported from a CSV.  A daily API feed is a
``RateProvider`` implementation - drop it in ``PROVIDERS`` and the *Fetch rates* button
picks it up.  The estimator is deliberately simple (linear trend over the last N quotes);
replace ``estimate_rate`` with a real predictor when one exists.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hth.db.connection import Database
from hth.domain.constants import DATE_FMT, AuditCode
from hth.domain.interest import parse_date
from hth.domain.models import Item
from hth.services.accounts import ValidationError, _validate_date
from hth.services.audit import AuditService


@dataclass(frozen=True)
class RateQuote:
    item_id: int
    date: str
    rate: float
    source: str = "manual"


@dataclass(frozen=True)
class RateEstimate:
    rate: float  # estimated rate on the target date
    trend_per_day: float  # slope of the fitted line
    based_on: int  # number of quotes used
    latest: float  # most recent actual quote


class RateProvider(Protocol):
    """Anything that can return quotes for a list of crops on a date."""

    name: str

    def fetch(self, crops: list[Item], on_date: dt.date) -> list[RateQuote]: ...


class CsvRateProvider:
    """CSV with columns ``crop,date,rate`` (crop = item id or exact name)."""

    name = "csv"

    def __init__(self, path: Path):
        self.path = Path(path)

    def fetch(self, crops: list[Item], on_date: dt.date) -> list[RateQuote]:
        by_id = {c.id: c for c in crops}
        by_name = {c.name.strip().upper(): c for c in crops}
        quotes, problems = [], []
        with open(self.path, newline="", encoding="utf-8-sig") as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                key = (row.get("crop") or "").strip()
                item = by_id.get(int(key)) if key.isdigit() else by_name.get(key.upper())
                if item is None:
                    problems.append(f"line {n}: unknown crop {key!r}")
                    continue
                try:
                    date = _validate_date(row.get("date") or on_date.strftime(DATE_FMT))
                    rate = float(row.get("rate") or "")
                except (ValidationError, ValueError):
                    problems.append(f"line {n}: bad date/rate")
                    continue
                quotes.append(RateQuote(item.id, date, rate, "csv"))
        if problems and not quotes:
            raise ValidationError("; ".join(problems[:5]))
        return quotes


# Register API providers here, e.g. ("agmarknet", AgmarknetProvider(api_key=...)).
PROVIDERS: dict[str, RateProvider] = {}


class RatesService:
    def __init__(self, db: Database):
        self.db = db
        self.audit = AuditService(db)

    def set_rate(self, item_id: int, date: str, rate: float, source: str = "manual", username: str = "system") -> None:
        date = _validate_date(date)
        try:
            rate_f = float(rate)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Rate must be a number.") from exc
        if rate_f <= 0:
            raise ValidationError("Rate must be greater than zero.")
        with self.db.connect():
            self.db.execute(
                "INSERT INTO crop_rates (item_id, date, rate, source) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(item_id, date, source) DO UPDATE SET rate = excluded.rate",
                (item_id, date, rate_f, source),
            )
            self.audit.log(AuditCode.RATE, f"rate item {item_id} {date} {rate_f:g} ({source})", username)

    def apply_quotes(self, quotes: list[RateQuote], username: str = "system") -> int:
        with self.db.connect():
            for q in quotes:
                self.set_rate(q.item_id, q.date, q.rate, q.source, username)
        return len(quotes)

    def latest(self, item_id: int, on_or_before: dt.date | None = None) -> tuple[float, str, str] | None:
        """(rate, date, source) of the newest quote on or before the date."""
        limit = (on_or_before or dt.date.today()).strftime(DATE_FMT)
        r = self.db.fetchone(
            "SELECT rate, date, source FROM crop_rates WHERE item_id = ? AND date <= ? "
            "ORDER BY date DESC, id DESC LIMIT 1",
            (item_id, limit),
        )
        return (float(r["rate"]), r["date"], r["source"]) if r else None

    def history(self, item_id: int, limit: int = 60) -> list[tuple[str, float, str]]:
        rows = self.db.fetchall(
            "SELECT date, rate, source FROM crop_rates WHERE item_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (item_id, limit),
        )
        return [(r["date"], float(r["rate"]), r["source"]) for r in rows]

    def delete_rate(self, item_id: int, date: str, source: str, username: str = "system") -> None:
        with self.db.connect():
            self.db.execute(
                "DELETE FROM crop_rates WHERE item_id = ? AND date = ? AND source = ?", (item_id, date, source)
            )
            self.audit.log(AuditCode.DELETE, f"rate item {item_id} {date} ({source})", username)

    def estimate_rate(self, item_id: int, days_ahead: int = 7, window: int = 30) -> RateEstimate | None:
        """Least-squares line through the last ``window`` quotes, extrapolated ``days_ahead``.

        A placeholder for a real predictor: it knows nothing about seasons or markets.
        """
        points = list(reversed(self.history(item_id, window)))
        if len(points) < 2:
            return None
        origin = parse_date(points[0][0])
        xs = [(parse_date(d) - origin).days for d, _, _ in points]
        ys = [r for _, r, _ in points]
        n = len(xs)
        mean_x, mean_y = sum(xs) / n, sum(ys) / n
        var = sum((x - mean_x) ** 2 for x in xs)
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / var if var else 0.0
        intercept = mean_y - slope * mean_x
        target = (parse_date(points[-1][0]) - origin).days + days_ahead
        return RateEstimate(round(max(0.0, intercept + slope * target), 2), round(slope, 4), n, ys[-1])
