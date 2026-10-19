"""Find customers and items named in a question - typed in Roman or Devanagari, with typos.

The linker is deliberately deterministic: names are where a wrong answer hurts most, so it
never guesses between close matches.  It returns *mentions*; a mention with several
equally good candidates is **ambiguous** and the assistant asks back ("कौन से रमेश?").
Linked spans are replaced by placeholders (``<C1>``, ``<I1>``) before any model sees the text.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field

from hth.assistant.normalize import key, romanize

_RAW_TOKEN = re.compile(r"[ऀ-ॿ]+|[A-Za-z0-9]+")
_DEV = re.compile(r"[ऀ-ॿ]")

# Words that are never (the start of) a name: question words, grammar, intent words.
_STOP = {
    key(w)
    for w in (
        "ka ki ke hai h hain kitna kitni kitne batao btao bata dikhao dikha kya kab kaun kis kiska kiski kiske kisne kisse "
        "aaj kal parso mahine mahina hafte hafta saal sal hisab hisaab baaki baki bakaya udhaar udhar paise paisa lena "
        "dena becha bika bikri kharcha kharch munafa fayda mein me se ko ne wala wali wale hua hui tha thi nahi karo kar "
        "bacha bache pada mangwana mangana dawai saman maal galle bhai zara tarikh din khata karar krar vada vaada aana "
        "aane agle sabse jyada zyada kul bazar market hamein hume mujhe mera meri tera ab abhi aur bhi to toh do de dena "
        "the a an of for in on at to is are was what how much many who whom whose which when show tell me my give list "
        "please can you do does did have has balance owe owes due dues stock rate price sale sales sold left ledger "
        "account statement entries entry interest number phone mobile contact promise promised date today yesterday "
        "last this month week year profit expense expenses cash bank top total pichle pichhle pichla is es ji please "
        "name naam byaj byaaj interest entri entriyan rojnamcha kitna"
    ).split()
}


@dataclass(frozen=True)
class Candidate:
    kind: str  # customer | item
    id: int
    name: str  # English, as stored
    name_hi: str
    details: str  # village / phone for customers, unit + batch for items
    details_hi: str
    score: float

    def label(self, lang: str) -> str:
        name = self.name_hi if lang == "hi" and self.name_hi else self.name.title()
        details = self.details_hi if lang == "hi" and self.details_hi else self.details
        details = "" if details.strip().upper() in ("", "NA") else details
        return f"{name}  ({details})" if details else name


@dataclass
class Mention:
    kind: str
    start: int  # char span in the original text
    end: int
    text: str
    candidates: list[Candidate] = field(default_factory=list)
    margin: float = 0.25  # wider when the best match was only a near-spelling

    @property
    def ambiguous(self) -> bool:
        if len(self.candidates) < 2:
            return False
        return self.candidates[1].score >= self.candidates[0].score - self.margin

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None


@dataclass
class LinkResult:
    text: str
    mentions: list[Mention]

    def first(self, kind: str) -> Mention | None:
        return next((m for m in self.mentions if m.kind == kind), None)

    def placeholder_text(self) -> str:
        """The question with linked names replaced: '<C1> ka kitna baaki hai'."""
        out, last, counters = [], 0, {"customer": 0, "item": 0}
        for m in sorted(self.mentions, key=lambda m: m.start):
            counters[m.kind] += 1
            tag = ("C" if m.kind == "customer" else "I") + str(counters[m.kind])
            out.append(self.text[last : m.start])
            out.append(f"<{tag}>")
            last = m.end
        out.append(self.text[last:])
        return " ".join("".join(out).split())


def _edit1(a: str, b: str, limit: int) -> bool:
    """Levenshtein distance <= limit (small strings, early exit)."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        best = cur[0]
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            best = min(best, cur[j])
        if best > limit:
            return False
        prev = cur
    return prev[-1] <= limit


@dataclass
class _Record:
    kind: str
    id: int
    name: str
    name_hi: str
    details: str
    details_hi: str
    name_keys: list[str]
    detail_keys: set[str]
    hi_tokens: set[str]
    recent: bool


class EntityIndex:
    """Customers and items of the shop, indexed for fuzzy, script-independent lookup."""

    def __init__(self, records: list[_Record]):
        self.records = {(r.kind, r.id): r for r in records}
        self.by_key: dict[str, set[tuple[str, int]]] = defaultdict(set)
        self.by_hi: dict[str, set[tuple[str, int]]] = defaultdict(set)
        for r in records:
            for k in r.name_keys:
                self.by_key[k].add((r.kind, r.id))
            for t in r.hi_tokens:
                self.by_hi[t].add((r.kind, r.id))
        n = max(1, len(records))
        self.idf = {k: math.log(1 + n / len(ids)) for k, ids in self.by_key.items()}
        self.vocab = sorted(self.by_key)

    # Building ---------------------------------------------------------------------------
    @classmethod
    def from_db(cls, db, today: dt.date | None = None) -> EntityIndex:
        today = today or dt.date.today()
        recent_since = (today - dt.timedelta(days=120)).isoformat()
        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(customers)")}
        hi = "name_hi" in cols
        recent = {
            r["customer_id"]
            for r in db.fetchall("SELECT DISTINCT customer_id FROM transactions WHERE date >= ?", (recent_since,))
        }
        records = []
        for r in db.fetchall(
            "SELECT id, name, other_details" + (", name_hi, details_hi" if hi else "") + " FROM customers"
        ):
            records.append(
                _record(
                    "customer",
                    r["id"],
                    r["name"],
                    r["name_hi"] if hi else "",
                    r["other_details"],
                    r["details_hi"] if hi else "",
                    r["id"] in recent,
                )
            )
        icols = {r["name"] for r in db.fetchall("PRAGMA table_info(items)")}
        ihi = "name_hi" in icols
        for r in db.fetchall("SELECT id, name, unit, batch" + (", name_hi" if ihi else "") + " FROM items"):
            batch = "" if (r["batch"] or "NA").upper() == "NA" else r["batch"]
            records.append(
                _record(
                    "item", r["id"], r["name"], r["name_hi"] if ihi else "", f"{r['unit']} {batch}".strip(), "", False
                )
            )
        return cls(records)

    # Linking -----------------------------------------------------------------------------
    def link(self, text: str, kinds: tuple[str, ...] = ("customer", "item")) -> LinkResult:
        toks = [(m.start(), m.end(), m.group(0)) for m in _RAW_TOKEN.finditer(text)]
        hits: list[tuple[int, dict[tuple[str, int], float], set[tuple[str, int]]]] = []
        fuzzy: set[tuple[str, int]] = set()  # records matched only through a near-spelling
        for pos, (_s, _e, raw) in enumerate(toks):
            matches: dict[tuple[str, int], float] = {}
            detail_hits: set[tuple[str, int]] = set()
            if _DEV.search(raw):
                for rid in self.by_hi.get(raw, ()):
                    matches[rid] = 1.0
            k = key(romanize(raw))
            if k in _STOP or (len(k) < 3 and not k.isdigit()):
                if matches:
                    hits.append((pos, matches, detail_hits))
                continue
            for rid in self.by_key.get(k, ()):
                matches[rid] = max(matches.get(rid, 0), self.idf.get(k, 1.0))
            if not matches and len(k) >= 4 and not k.isdigit():
                limit = 2 if len(k) >= 7 else 1
                for v in self.vocab:
                    if v[0] == k[0] and _edit1(k, v, limit):
                        for rid in self.by_key[v]:
                            matches[rid] = max(matches.get(rid, 0), 0.7 * self.idf.get(v, 1.0))
                            fuzzy.add(rid)
            if matches:
                hits.append((pos, matches, detail_hits))
        mentions: list[Mention] = []
        for kind in kinds:
            groups = self._group(hits, kind)
            for positions in groups:
                scores: dict[int, float] = defaultdict(float)
                matched: dict[int, int] = defaultdict(int)
                for pos, matches, _d in hits:
                    if pos not in positions:
                        continue
                    for (k2, rid), w in matches.items():
                        if k2 == kind:
                            scores[rid] += w
                            matched[rid] += 1
                if not scores:
                    continue
                # words around the name that fit a candidate's details (village, phone) break ties
                other = {key(romanize(toks[p][2])) for p in range(len(toks)) if p not in positions}
                ranked = []
                for rid, sc in scores.items():
                    rec = self.records[(kind, rid)]
                    coverage = matched[rid] / max(1, len(rec.name_keys))
                    bonus = 0.6 * len(other & rec.detail_keys) + (0.05 if rec.recent else 0.0)
                    ranked.append((sc + 0.5 * coverage + bonus, rid))
                ranked.sort(reverse=True)
                best_score = ranked[0][0]
                # a misspelt name ("rmesh kumr") is a guess: offer the close ones instead of picking
                margin = 0.6 if (kind, ranked[0][1]) in fuzzy else 0.25
                keep = [(s, rid) for s, rid in ranked if s >= best_score - margin][:8]
                start, end = toks[min(positions)][0], toks[max(positions)][1]
                cands = [
                    Candidate(
                        kind,
                        rid,
                        (r := self.records[(kind, rid)]).name,
                        r.name_hi,
                        r.details,
                        r.details_hi,
                        round(s, 3),
                    )
                    for s, rid in keep
                ]
                mentions.append(Mention(kind, start, end, text[start:end], cands, margin))
        mentions = _drop_overlaps(mentions)
        return LinkResult(text, mentions)

    @staticmethod
    def _group(hits, kind: str) -> list[set[int]]:
        """Runs of neighbouring token positions that match something of ``kind``."""
        positions = [pos for pos, matches, _d in hits if any(k == kind for k, _ in matches)]
        groups: list[set[int]] = []
        for pos in positions:
            if groups and pos - max(groups[-1]) <= 2:  # allow one gap word ("ramesh s sihag")
                groups[-1].add(pos)
            else:
                groups.append({pos})
        return groups

    # Choices -----------------------------------------------------------------------------
    def candidate(self, kind: str, record_id: int) -> Candidate | None:
        r = self.records.get((kind, record_id))
        return Candidate(kind, r.id, r.name, r.name_hi, r.details, r.details_hi, 1.0) if r else None


def _record(kind, rid, name, name_hi, details, details_hi, recent) -> _Record:
    name_keys = [key(t) for t in _RAW_TOKEN.findall(romanize(name or ""))]
    detail_keys = {key(t) for t in _RAW_TOKEN.findall(romanize(details or "")) if len(t) >= 3}
    hi_tokens = set(_RAW_TOKEN.findall(name_hi or "")) | set(_RAW_TOKEN.findall(details_hi or ""))
    hi_tokens = {t for t in hi_tokens if _DEV.search(t)}
    return _Record(
        kind, rid, name or "", name_hi or "", details or "", details_hi or "", name_keys, detail_keys, hi_tokens, recent
    )


def _drop_overlaps(mentions: list[Mention]) -> list[Mention]:
    """A span matching both a customer and an item keeps the kind with the stronger match."""
    out: list[Mention] = []
    for m in sorted(mentions, key=lambda m: -(m.best.score if m.best else 0)):
        if any(not (m.end <= o.start or m.start >= o.end) for o in out):
            continue
        out.append(m)
    return sorted(out, key=lambda m: m.start)


_ORDINALS = {
    key(w): i
    for words, i in (
        ("1 pehla pehle pahla pahle first ek one pehli", 0),
        ("2 dusra dusre doosra second do two dusri", 1),
        ("3 teesra tisra third teen three teesri", 2),
        ("4 chautha chotha fourth char four", 3),
        ("5 panchva fifth paanch five", 4),
        ("6 chhatha sixth chhe six", 5),
    )
    for w in words.split()
}


def resolve_choice(text: str, options: list[Candidate]) -> Candidate | None:
    """Which option does the reply pick?  A number / ordinal word, or words that fit only one
    option (village, surname, phone digits, part of the name)."""
    toks = [key(romanize(t)) for t in _RAW_TOKEN.findall(text)]
    raw = _RAW_TOKEN.findall(text)
    if len(toks) <= 3:
        for t in toks:
            if t in _ORDINALS and _ORDINALS[t] < len(options):
                return options[_ORDINALS[t]]
    words = {t for t in toks if t not in _STOP and len(t) >= 2} | {r for r in raw if _DEV.search(r)}
    if not words:
        return None
    fits = []
    for opt in options:
        hay = {key(t) for t in _RAW_TOKEN.findall(romanize(f"{opt.name} {opt.details}"))}
        hay |= set(_RAW_TOKEN.findall(f"{opt.name_hi} {opt.details_hi}"))
        digits = re.sub(r"\D", "", opt.details)
        score = sum(1 for w in words if w in hay or (w.isdigit() and len(w) >= 3 and w in digits))
        fits.append((score, opt))
    fits.sort(key=lambda f: -f[0])
    if fits and fits[0][0] > 0 and (len(fits) == 1 or fits[0][0] > fits[1][0]):
        return fits[0][1]
    return None
