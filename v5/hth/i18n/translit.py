"""Roman (as typed at the counter) -> Devanagari, for customer and item names.

Offline and deterministic: a word list first (``hindi_words``), then compound names split
into a known ending (AMARSINGH -> अमर + सिंह), then phonetic rules.  The result is a
*suggestion* stored next to the English name; anything can be corrected by hand and a
corrected name is never regenerated.

Rules, in short: digraphs (KH GH CH JH TH DH PH BH SH) and doubles (DD -> ड्ड) first;
consonant clusters join with a halant (SHARMA -> शर्मा); N / M before a consonant become
anusvara (CHAND -> चंद); a word-final A, I, U are long (VERMA, SAINI, BHADU); a lone
consonant at the end keeps no vowel (RAMESH -> रमेश); I+A reads -iya (PONIA -> पोनिया);
vowel-less short words are spelt as letters (FMC -> एफएमसी).  Item words use retroflex
T / D (TATA -> टाटा) as English loanwords do; names use dental त / द.
"""

from __future__ import annotations

import re

from hth.i18n.hindi_words import ITEM_WORDS, LETTERS, NAME_WORDS, SUFFIXES, UNITS

HALANT = "्"
ANUSVARA = "ं"

# independent vowel, matra
VOWELS: list[tuple[str, str, str]] = [
    ("AA", "आ", "ा"),
    ("EE", "ई", "ी"),
    ("II", "ई", "ी"),
    ("OO", "ऊ", "ू"),
    ("UU", "ऊ", "ू"),
    ("AI", "ऐ", "ै"),
    ("AU", "औ", "ौ"),
    ("OU", "औ", "ौ"),
    ("EI", "ई", "ी"),
    ("A", "अ", ""),
    ("E", "ए", "े"),
    ("I", "इ", "ि"),
    ("O", "ओ", "ो"),
    ("U", "उ", "ु"),
]
LONG_FINAL = {"A": ("आ", "ा"), "I": ("ई", "ी"), "U": ("ऊ", "ू")}

CONSONANTS_NAME: list[tuple[str, str]] = [
    ("CHH", "छ"),
    ("KSH", "क्ष"),
    ("SHR", "श्र"),
    ("TR", "त्र"),
    ("KH", "ख"),
    ("GH", "घ"),
    ("CH", "च"),
    ("JH", "झ"),
    ("TH", "थ"),
    ("DH", "ध"),
    ("PH", "फ"),
    ("BH", "भ"),
    ("SH", "श"),
    ("RH", "ढ़"),
    ("DD", "ड्ड"),
    ("TT", "ट्ट"),
    ("K", "क"),
    ("G", "ग"),
    ("C", "क"),
    ("J", "ज"),
    ("T", "त"),
    ("D", "द"),
    ("N", "न"),
    ("P", "प"),
    ("F", "फ़"),
    ("B", "ब"),
    ("M", "म"),
    ("Y", "य"),
    ("R", "र"),
    ("L", "ल"),
    ("V", "व"),
    ("W", "व"),
    ("S", "स"),
    ("H", "ह"),
    ("Z", "ज़"),
    ("Q", "क"),
    ("X", "क्स"),
]
_RETROFLEX = {"T": "ट", "D": "ड"}  # English t / d sound retroflex in Hindi; th / dh stay थ / ध
CONSONANTS_ITEM = [(r, _RETROFLEX.get(r, d)) for r, d in CONSONANTS_NAME if r != "TR"] + [("TR", "ट्र")]
CONSONANTS_ITEM.sort(key=lambda c: -len(c[0]))
NASAL_BEFORE = set("KGCJTDPBSHFZQXL")  # N / M before these -> anusvara

_TOKEN = re.compile(r"[A-Za-z]+|\d+(?:[.,]\d+)*|\s+|.", re.UNICODE)
_VOWEL_CHARS = set("AEIOU")


def _match(table, text: str, i: int):
    for roman, deva in table:
        if text.startswith(roman, i):
            return roman, deva
    return None


def _vowel(text: str, i: int):
    for roman, independent, matra in VOWELS:
        if text.startswith(roman, i):
            return roman, independent, matra
    return None


def _english_spelling(word: str) -> str:
    """Item names are mostly English brand words: normalise the spelling to how it sounds."""
    word = re.sub(r"([B-DF-HJ-NP-TV-Z])\1", r"\1", word)  # KILL -> KIL, TRAXX -> TRAX
    word = re.sub(r"C(?=[EIY])", "S", word)  # CYPER -> SYPER (soft c)
    word = re.sub(r"CH(?=[LR])", "K", word)  # CHLOR -> KLOR
    word = re.sub(r"(?<=[B-DF-HJ-NP-TV-Z])Y(?=[B-DF-HJ-NP-TV-Z])", "AAI", word)  # SYPER -> साइपर
    if len(word) > 3 and word.endswith("E") and word[-2] not in "AEIOU":  # AZOLE -> AZOL
        word = word[:-1]
    return word


def phonetic(word: str, item: bool = False, final_long: bool = True) -> str:
    """Rule-based transliteration of one upper-case Latin word.

    ``final_long=False`` for the first part of a compound name (RAGHU+BIR -> रघु, not रघू)."""
    word = word.upper()
    if not word:
        return ""
    if not (set(word) & _VOWEL_CHARS) and len(word) <= 5:  # FMC, HPM, NPK, RCH
        return "".join(LETTERS[ch] for ch in word)
    if item:
        if len(word) <= 3:  # IPL, GSP: short codes on labels are spelt out
            return "".join(LETTERS.get(ch, ch) for ch in word)
        word = _english_spelling(word)
    # unstressed -ER- as in SUNDER, NAMBERDAR, CHANDERMOHAN: no e-matra
    word = re.sub(r"(?<=[B-DF-HJ-NP-TV-Z])ER(?=[B-DF-HJ-NP-TV-Z]|$)", "AR", word)
    # a final Y after a consonant is a vowel: BODY, JONY -> ई
    word = re.sub(r"(?<=[B-DF-HJ-NP-TV-Z])Y$", "I", word)
    table = CONSONANTS_ITEM if item else CONSONANTS_NAME
    out: list[str] = []
    i, n = 0, len(word)
    prev_consonant = False  # last written unit is a consonant waiting for its vowel
    prev_was_i = False
    while i < n:
        v = _vowel(word, i)
        if v:
            roman, independent, matra = v
            end = i + len(roman)
            final = end == n
            if final and roman in LONG_FINAL and (final_long or roman == "A"):
                independent, matra = LONG_FINAL[roman]
            if prev_consonant:
                out.append(matra)
            elif prev_was_i and roman.startswith("A"):
                out.append("या" if final or roman == "AA" else "य")  # PONIA -> पोनिया
            else:
                out.append(independent)
            prev_consonant = False
            prev_was_i = roman in ("I", "EE", "II", "EI")
            i = end
            continue
        c = _match(table, word, i)
        if c is None:  # not a letter we know
            out.append(word[i])
            i += 1
            prev_consonant = prev_was_i = False
            continue
        roman, deva = c
        nxt = i + len(roman)
        nasal = roman in ("N", "M") and nxt < n and word[nxt] in NASAL_BEFORE and i > 0
        if roman == "M" and nasal and word[nxt] not in "PB":
            nasal = False
        if nasal and (out and not prev_consonant):
            out.append(ANUSVARA)  # CHAND -> चंद, SINGH -> सिंघ, AMBA -> अंबा
            i = nxt
            prev_was_i = False
            continue
        if prev_consonant:
            out.append(HALANT)  # SHARMA -> शर्मा
        out.append(deva)
        prev_consonant = True
        prev_was_i = False
        i = nxt
    return "".join(out)


def word(token: str, item: bool = False, final_long: bool = True) -> str:
    """One Latin word: word list, then known ending, then rules."""
    up = token.upper()
    table = ITEM_WORDS if item else NAME_WORDS
    if up in table:
        return table[up]
    other = NAME_WORDS if item else ITEM_WORDS
    if up in other:
        return other[up]
    if up in UNITS:
        return UNITS[up]
    if not item:
        for suffix in SUFFIXES:  # longest first
            head = up[: -len(suffix)] if up.endswith(suffix) else ""
            # OMPAL -> ओम + पाल, but not KARAM -> KA + RAM: a short head must be a known word
            if len(head) >= 3 or head in NAME_WORDS:
                return word(head, item, final_long=False) + NAME_WORDS[suffix]
    return phonetic(up, item, final_long)


def to_hindi(text: str, item: bool = False) -> str:
    """Whole name or details line; digits, punctuation and spacing are kept.

    ``250GM`` -> ``250 ग्राम`` (a unit glued to a number gets a space)."""
    if not text:
        return ""
    out = []
    prev_digit = False
    for tok in _TOKEN.findall(text):
        if tok[0].isalpha():
            up = tok.upper()
            if prev_digit and up in UNITS:
                out.append(" " + UNITS[up])
            elif up == "NA":
                out.append("NA")
            else:
                out.append(word(tok, item))
            prev_digit = False
        else:
            out.append(tok)
            prev_digit = tok[0].isdigit()
    return "".join(out)
