"""How well the assistant finds the shop's real customers and items in a question.

    python tools/assistant/eval_names.py                 # the default data folder
    python tools/assistant/eval_names.py --db C:/JBB/v4/hth.db

The database is opened **read-only** and only totals are printed (no names), so it is safe to
run on the live shop data.  For every customer it asks with the full name, with a one-letter
typo, and with first name + village; for every item, with its name.  A question counts as
right when the right record is picked, or - when several records match equally (two people
with the same name) - when the assistant asks back and the right one is among its choices.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hth.assistant.entities import EntityIndex, resolve_choice  # noqa: E402
from hth.assistant.normalize import key  # noqa: E402
from hth.config import default_data_dir  # noqa: E402


class ReadOnlyDb:
    """Just what EntityIndex.from_db needs, on a connection that cannot write."""

    def __init__(self, path: Path):
        self.conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def fetchall(self, sql: str, params: tuple = ()):
        return self.conn.execute(sql, params).fetchall()


def _typo(word: str, rng: random.Random) -> str:
    if len(word) < 5:
        return word
    i = rng.randrange(1, len(word) - 1)
    return word[:i] + word[i + 1 :] if rng.random() < 0.5 else word[:i] + word[i + 1] + word[i] + word[i + 2 :]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=default_data_dir() / "hth.db")
    ap.add_argument("--limit", type=int, default=2000, help="customers to try (sampled)")
    args = ap.parse_args()
    if not args.db.exists():
        print(f"no database at {args.db}")
        return 1
    db = ReadOnlyDb(args.db)
    index = EntityIndex.from_db(db)
    rng = random.Random(7)
    customers = [r for r in index.records.values() if r.kind == "customer"]
    items = [r for r in index.records.values() if r.kind == "item"]
    by_name = Counter(key(r.name) for r in customers)
    sample = rng.sample(customers, min(args.limit, len(customers)))
    results: dict[str, Counter] = {}

    def check(kind: str, rid: int, text: str, form: str) -> None:
        m = index.link(text, (kind,)).first(kind)
        tally = results.setdefault(form, Counter())
        if m is None:
            tally["not found"] += 1
        elif not m.ambiguous:
            tally["right" if m.best.id == rid else "WRONG"] += 1
        elif any(c.id == rid for c in m.candidates[:6]):
            tally["asked back, right one offered"] += 1
        else:
            tally["asked back, right one missing"] += 1

    for r in sample:
        words = r.name.split()
        check("customer", r.id, f"{r.name.lower()} ka kitna baaki hai", "full name")
        typo = " ".join(_typo(w.lower(), rng) for w in words)
        check("customer", r.id, f"{typo} ka hisab", "name with a typo")
        detail = next((w for w in (r.details or "").split() if w.isalpha() and len(w) > 3), None)
        if detail and len(words) > 0:
            # what a reply to "which Ramesh?" looks like: first name asked, then the village
            m = index.link(f"{words[0].lower()} ka hisab", ("customer",)).first("customer")
            tally = results.setdefault("first name, then village", Counter())
            if m is None:
                tally["not found"] += 1
            elif not m.ambiguous:
                tally["right" if m.best.id == r.id else "first name alone picked another"] += 1
            else:
                pick = resolve_choice(f"{detail.lower()} wala", m.candidates[:6])
                tally["right" if pick and pick.id == r.id else "village did not settle it"] += 1
    for r in items:
        check("item", r.id, f"{r.name.lower()} kitna bacha hai", "item name")

    dup = sum(1 for n in by_name.values() if n > 1)
    print(f"{len(customers)} customers ({dup} names shared by two or more), {len(items)} items; read-only")
    for form, tally in results.items():
        total = sum(tally.values())
        good = tally["right"] + tally["asked back, right one offered"]
        detail = ", ".join(f"{k} {v}" for k, v in tally.most_common())
        print(f"  {form:28} {good / max(1, total):6.1%} of {total}   ({detail})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
