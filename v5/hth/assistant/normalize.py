"""Turn a typed (later: spoken) question into comparable text, its language, dates and numbers.

* :func:`romanize` - Devanagari to Roman the way people type Hinglish, with Hindi schwa
  deletion (कितना -> kitna, बकाया -> bakaya, पिछले -> pichhle).
* :func:`key` - phonetic key so spellings meet: baaki / baki / बाकी -> ``baki``.
* :func:`language` - ``hi`` for Devanagari, ``hl`` for Roman Hindi, ``en`` for English.
  Answers follow the question: ``hi`` and ``hl`` get Hindi, ``en`` gets English.
* :func:`find_period` / :func:`find_day` / :func:`find_number` / :func:`find_category`.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

# --- Devanagari -> Roman ----------------------------------------------------------------
_CONS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "n",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "n",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
    "ळ": "l",
}
_NUKTA = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f"}
_VOWELS = {
    "अ": "a",
    "आ": "aa",
    "इ": "i",
    "ई": "ee",
    "उ": "u",
    "ऊ": "oo",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
    "ऑ": "o",
}
_MATRAS = {
    "ा": "aa",
    "ि": "i",
    "ी": "ee",
    "ु": "u",
    "ू": "oo",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
    "ॉ": "o",
    "ॅ": "e",
}
_HALANT, _NUKTA_SIGN = "्", "़"
_NASAL = {"ं": "n", "ँ": "n", "ः": "h"}
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _romanize_word(word: str) -> str:
    # units: [consonant or vowel-letter, vowel] where vowel None = inherent a, "" = halant
    units: list[list] = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        if ch in _CONS:
            cons = _CONS[ch]
            if i + 1 < n and word[i + 1] == _NUKTA_SIGN:
                cons = _NUKTA.get(ch, cons)
                i += 1
            units.append([cons, None])
        elif ch in _VOWELS:
            units.append(["", _VOWELS[ch]])
        elif ch in _MATRAS and units:
            units[-1][1] = _MATRAS[ch]
        elif ch == _HALANT and units:
            units[-1][1] = ""
        elif ch in _NASAL and units:
            if units[-1][1] is None:
                units[-1][1] = "a"
            nasal = _NASAL[ch]
            if ch == "ं" and i + 1 < n and word[i + 1] == "ह":
                nasal = "ng"  # सिंह -> singh
            units[-1].append(nasal)
        elif ch == _NUKTA_SIGN:
            pass
        else:
            units.append([ch, ""])
        i += 1

    # schwa deletion: drop the inherent a at the end, and in V C(a) C V
    def has_vowel(k: int) -> bool:
        return 0 <= k < len(units) and (units[k][1] not in ("",) and not (units[k][1] is None and k == len(units) - 1))

    out = []
    for k, u in enumerate(units):
        cons, vowel = u[0], u[1]
        if vowel is None:
            last = k == len(units) - 1
            nxt = units[k + 1] if k + 1 < len(units) else None
            nxt_will_have_vowel = (
                nxt is not None
                and nxt[0]
                and (nxt[1] not in ("", None) or (nxt[1] is None and k + 1 != len(units) - 1))
            )
            if last or (k > 0 and has_vowel(k - 1) and nxt is not None and nxt[0] and nxt_will_have_vowel):
                vowel = ""
            else:
                vowel = "a"
        out.append(cons + vowel + "".join(u[2:]))
    return "".join(out)


def romanize(text: str) -> str:
    """Devanagari parts of ``text`` in Roman letters; everything else unchanged."""
    text = text.translate(_DEV_DIGITS)
    if not _DEVANAGARI.search(text):
        return text
    return re.sub(r"[ऀ-ॿ]+", lambda m: _romanize_word(m.group(0)), text)


def key(word: str) -> str:
    """Phonetic key: long vowels, w/v, z/j, ph/f and doubled letters folded together."""
    w = word.lower()
    for a, b in (
        ("aa", "a"),
        ("ee", "i"),
        ("ii", "i"),
        ("oo", "u"),
        ("uu", "u"),
        ("chh", "ch"),
        ("ph", "f"),
        ("w", "v"),
        ("z", "j"),
        ("q", "k"),
        ("ck", "k"),
        ("y", "i"),
    ):
        w = w.replace(a, b)
    w = re.sub(r"(.)\1+", r"\1", w)
    return w


_WORD = re.compile(r"<[a-z]\d>|[a-z0-9]+")


def tokens(text: str) -> list[str]:
    """Lower-case Roman tokens (Devanagari romanised first); placeholders like <c1> kept."""
    return _WORD.findall(romanize(text).lower())


def keys(text: str) -> list[str]:
    return [t if t.startswith("<") else key(t) for t in tokens(text)]


# --- language -----------------------------------------------------------------------------
_HINGLISH = {
    key(w)
    for w in (
        "ka ki ke hai h hain kitna kitni kitne batao btao bata dikhao kya kab kaun kis kiska kiski kiske kisne kisse "
        "aaj kal parso mahine mahina hafte hafta saal sal hisab hisaab baaki baki bakaya udhaar udhar paise paisa lena "
        "dena becha bika bikri kharcha kharch munafa fayda mein me se ko ne wala wali wale hua hui tha thi nahi karo kar "
        "bacha bache pada mangwana mangana dawai saman maal galle namaste dhanyawad shukriya bhai zara tarikh din "
        "khata karar krar vada vaada aana aane agle sabse jyada zyada kul bazar market mausam gana sunao chalao "
        "aur bhi uska uski uske usi unka unki unke iska iski iske woh wo yeh ye pichle pichhle pichla ab abhi phir "
        "kuch koi kaise kaisa bolo dega denge diya liya"
    ).split()
}


def language(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    words = [key(t) for t in tokens(text) if not t.startswith("<")]
    strong = sum(1 for w in words if w in _HINGLISH and w not in _ALSO_ENGLISH)
    weak = sum(1 for w in words if w in _ALSO_ENGLISH)
    hits = strong + weak if strong else 0  # "show me the ledger" is English; "mujhe ... me" is not
    return "hl" if hits and hits >= max(1, len(words) // 5) else "en"


# Hinglish words that are also everyday English words - they only count next to a clear one.
_ALSO_ENGLISH = {key(w) for w in "me h ye wo to do hi kar bas".split()}


def answer_language(text: str) -> str:
    """Answers follow the question: Hindi for Devanagari and Hinglish, English for English."""
    return "en" if language(text) == "en" else "hi"


# --- periods, days, numbers -------------------------------------------------------------
@dataclass(frozen=True)
class Period:
    value: str  # canonical: today | last_month | month:3 | days:7 | range:2026-01-01:2026-01-31 ...
    start: dt.date
    end: dt.date

    @property
    def single_day(self) -> bool:
        return self.start == self.end


def _alt(words: str) -> str:
    """Regex alternatives in phonetic-key form, longest first."""
    keyed = sorted({" ".join(key(w) for w in phrase.split()) for phrase in words.split("|")}, key=len, reverse=True)
    return "(?:" + "|".join(re.escape(k) for k in keyed) + ")"


_PAST = _alt("pichle|pichhle|pichla|pichhla|pichli|pichhli|last|previous|past|pichhe|pichhle wale|gaye|bite")
_THIS = _alt("is|es|this|isi|current|iss|chalu|yeh|ye")
_WEEK = _alt("hafte|hafta|haftay|week|saptah|sapta")
_MONTH = _alt("mahine|mahina|mahne|month|maah|mahinay")
_YEAR = _alt("saal|sal|year|varsh|varash|baras|financial year")
_DAYS_WORD = _alt("din|dino|days|day|divas")
_TODAY = _alt("aaj|aj|today|aajka|abhi tak")
_YESTERDAY = _alt("kal|kl|yesterday|kalka|beete kal")
_DAY_BEFORE = _alt("parso|parson|day before yesterday")
_DOM = _alt("tarikh|tareekh|tarik|tarikh ko|date|th|st|nd|rd")
_MONTHS = {
    1: ("january", "jan", "janvari", "janavari"),
    2: ("february", "feb", "farvari", "pharvari", "febuari"),
    3: ("march", "mar", "marach"),
    4: ("april", "apr", "aprail", "aprel"),
    5: ("may", "mai"),
    6: ("june", "jun"),
    7: ("july", "jul", "julai"),
    8: ("august", "aug", "agast"),
    9: ("september", "sep", "sept", "sitambar", "sitanbar"),
    10: ("october", "oct", "aktubar", "aktoobar"),
    11: ("november", "nov", "navambar", "navanbar"),
    12: ("december", "dec", "disambar", "disanbar"),
}


def _fy_bounds(year_end: int) -> tuple[dt.date, dt.date]:
    return dt.date(year_end - 1, 4, 1), dt.date(year_end, 3, 31)


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    start = dt.date(year, month, 1)
    nxt = dt.date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return start, nxt - dt.timedelta(days=1)


def resolve(value: str, today: dt.date) -> Period:
    """Canonical period value -> dates (the same values the language model is trained on)."""
    if value == "today":
        return Period(value, today, today)
    if value == "yesterday":
        d = today - dt.timedelta(days=1)
        return Period(value, d, d)
    if value == "day_before":
        d = today - dt.timedelta(days=2)
        return Period(value, d, d)
    if value == "this_week":
        return Period(value, today - dt.timedelta(days=today.weekday()), today)
    if value == "last_week":
        monday = today - dt.timedelta(days=today.weekday() + 7)
        return Period(value, monday, monday + dt.timedelta(days=6))
    if value == "this_month":
        return Period(value, today.replace(day=1), today)
    if value == "last_month":
        last = today.replace(day=1) - dt.timedelta(days=1)
        return Period(value, last.replace(day=1), last)
    if value in ("this_fy", "last_fy"):
        fy_end = today.year + (today.month > 3)
        start, end = _fy_bounds(fy_end - (value == "last_fy"))
        return Period(value, start, min(end, today))
    if value.startswith("month:"):
        m = int(value.split(":")[1])
        year = today.year if m <= today.month else today.year - 1  # the latest such month
        start, end = _month_bounds(year, m)
        return Period(value, start, min(end, today))
    if value.startswith("days:"):
        n = max(1, int(value.split(":")[1]))
        return Period(value, today - dt.timedelta(days=n - 1), today)
    if value.startswith("dom:"):
        d = int(value.split(":")[1])
        month_start = today.replace(day=1)
        if d > today.day:  # "the 25th" said on the 10th means last month's
            month_start = (month_start - dt.timedelta(days=1)).replace(day=1)
        try:
            day = month_start.replace(day=d)
        except ValueError:
            day = _month_bounds(month_start.year, month_start.month)[1]
        return Period(value, day, day)
    if value.startswith("date:"):
        d = dt.date.fromisoformat(value[5:])
        return Period(value, d, d)
    if value.startswith("range:"):
        _r, a, b = value.split(":")
        return Period(value, dt.date.fromisoformat(a), dt.date.fromisoformat(b))
    raise ValueError(f"unknown period {value!r}")


def _text(text: str) -> str:
    """Space-padded phonetic keys - every spelling and both scripts meet here."""
    return " " + " ".join(keys(text)) + " "


def find_period(text: str, today: dt.date | None = None) -> Period | None:
    """A period mentioned in the question, or None."""
    today = today or dt.date.today()
    t = _text(text)
    checks = [
        (rf" {_PAST} (\d+) {_DAYS_WORD} ", lambda m: f"days:{m.group(1)}"),
        (rf" {_PAST} {_WEEK} ", lambda m: "last_week"),
        (rf" {_THIS} {_WEEK} ", lambda m: "this_week"),
        (rf" {_PAST} {_MONTH} ", lambda m: "last_month"),
        (rf" {_THIS} {_MONTH} ", lambda m: "this_month"),
        (rf" {_PAST} {_YEAR} ", lambda m: "last_fy"),
        (rf" {_THIS} {_YEAR} ", lambda m: "this_fy"),
    ]
    for pattern, make in checks:
        m = re.search(pattern, t)
        if m:
            return resolve(make(m), today)
    d = _explicit_date(t, today)
    if d:
        return d
    for month, names in _MONTHS.items():
        for name in names:
            k = key(name)
            if len(name) >= 3 and re.search(rf" {re.escape(k)} ", t):
                if month == 5 and not re.search(rf" {re.escape(k)} (?:mein|men|me|ka|ki|month|mahine) ", t):
                    continue  # "may" is also the English verb
                return resolve(f"month:{month}", today)
    day = find_day(text, today)
    return day


def _explicit_date(t: str, today: dt.date) -> Period | None:
    m = re.search(r" (\d{4}) (\d{1,2}) (\d{1,2}) ", t)
    if m:
        try:
            return resolve(f"date:{dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()}", today)
        except ValueError:
            return None
    m = re.search(r" (\d{1,2}) (\d{1,2}) (\d{2,4}) ", t)
    if m:
        year = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        try:
            return resolve(f"date:{dt.date(year, int(m.group(2)), int(m.group(1))).isoformat()}", today)
        except ValueError:
            return None
    return None


def find_day(text: str, today: dt.date | None = None) -> Period | None:
    today = today or dt.date.today()
    t = _text(text)
    if re.search(rf" {_TODAY} ", t):
        return resolve("today", today)
    if re.search(rf" {_DAY_BEFORE} ", t):
        return resolve("day_before", today)
    if re.search(rf" {_YESTERDAY} ", t):
        return resolve("yesterday", today)
    m = re.search(rf" (\d{{1,2}}) {_DOM} ", t)
    if not m:
        m = re.search(r" (?:on the )?(\d{1,2})(?:st|nd|rd|th) ", t)
    if m and 1 <= int(m.group(1)) <= 31:
        return resolve(f"dom:{int(m.group(1))}", today)
    return _explicit_date(t, today)


_NUM_WORDS = {
    "ek": 1,
    "one": 1,
    "do": 2,
    "two": 2,
    "teen": 3,
    "tin": 3,
    "three": 3,
    "char": 4,
    "chaar": 4,
    "four": 4,
    "panch": 5,
    "paanch": 5,
    "five": 5,
    "che": 6,
    "chhe": 6,
    "six": 6,
    "saat": 7,
    "sat": 7,
    "seven": 7,
    "aath": 8,
    "ath": 8,
    "eight": 8,
    "nau": 9,
    "nine": 9,
    "das": 10,
    "ten": 10,
    "bees": 20,
    "bis": 20,
    "twenty": 20,
    "pachas": 50,
    "pachaas": 50,
    "sau": 100,
    "hundred": 100,
}
_MULT = {
    "hazar": 1_000,
    "hazaar": 1_000,
    "hajar": 1_000,
    "thousand": 1_000,
    "k": 1_000,
    "lakh": 100_000,
    "lac": 100_000,
    "lakh rupaye": 100_000,
    "crore": 10_000_000,
    "karod": 10_000_000,
}


def find_number(text: str) -> float | None:
    """First quantity in the question: 5, 50k, 1.5 lakh, do hazaar, पचास हज़ार."""
    toks = tokens(text.replace(",", ""))
    for i, tok in enumerate(toks):
        val = None
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(k)?", tok)
        if m:
            val = float(m.group(1)) * (1000 if m.group(2) else 1)
        elif tok in _NUM_WORDS:
            val = float(_NUM_WORDS[tok])
        if val is None:
            continue
        if i + 1 < len(toks) and toks[i + 1] in _MULT:
            val *= _MULT[toks[i + 1]]
        return val
    return None


def find_category(text: str) -> str | None:
    m = re.search(r" (?:category|cat|shreni|shrenee|shrni|class|kategari) ([a-e]) ", " " + " ".join(tokens(text)) + " ")
    return m.group(1).upper() if m else None


def strip_period_words(text: str) -> str:
    """Remove recognised period phrases (so they are not mistaken for names)."""
    t = _text(text)
    for pattern in (rf" {_PAST} (?:\d+ )?\w+ ", rf" {_THIS} \w+ ", rf" {_TODAY} ", rf" {_YESTERDAY} "):
        t = re.sub(pattern, " ", t)
    return t.strip()
