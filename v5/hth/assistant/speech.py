"""Speaking answers aloud with Windows' own voices (offline).

Windows 10/11 ship Hindi voices (Kalpana, Hemant) as "OneCore" voices; SAPI can use them by
pointing its voice list at the OneCore registry key, so no extra download or package is
needed beyond pywin32.  A worker thread owns the COM objects; ``say`` replaces whatever is
being spoken.  ``synthesize`` renders 16 kHz audio instead (voice spellings, tests).

``summary(reply)`` turns an answer card into one or two short spoken sentences: amounts in
whole rupees, dates as "10 अक्टूबर", the ask-back choices as "रोहतक वाले, भिवानी वाले या …".
"""

from __future__ import annotations

import logging
import queue
import re
import sys
import threading

log = logging.getLogger(__name__)

_ONECORE = r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices"
_LANGS = {"hi": ("439",), "en": ("4009", "809", "409")}  # LCIDs in hex: hi-IN; en-IN, en-GB, en-US
_ASYNC, _PURGE = 1, 2
_MONTHS = {
    "hi": "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split(),
    "en": "January February March April May June July August September October November December".split(),
}


def _com():
    """(pythoncom, win32com.client), COM ready on this thread."""
    import win32com.client as com  # first: importing it puts pywin32's DLLs on the path

    # isort: split
    import pythoncom

    pythoncom.CoInitialize()
    return pythoncom, com


def _voices():
    """(token, language codes) for every SAPI and OneCore voice on this PC."""
    _pythoncom, com = _com()

    out = []
    for category in (None, _ONECORE):
        try:
            if category is None:
                tokens = com.Dispatch("SAPI.SpVoice").GetVoices()
            else:
                cat = com.Dispatch("SAPI.SpObjectTokenCategory")
                cat.SetId(category, False)
                tokens = cat.EnumerateTokens()
        except Exception:  # noqa: BLE001 - no OneCore voices
            continue
        for i in range(tokens.Count):
            tok = tokens.Item(i)
            try:
                langs = tuple(x.strip().lower() for x in tok.GetAttribute("Language").split(";"))
            except Exception:  # noqa: BLE001
                langs = ()
            out.append((tok, langs))
    return out


def _pick(voices, lang: str):
    for code in _LANGS.get(lang, ()):
        for tok, langs in voices:
            if code in langs:
                return tok
    return None


def voice_names() -> dict[str, str]:
    """{"hi": "Microsoft Kalpana - Hindi (India)", "en": ...} for the voices that would be used."""
    if not sys.platform.startswith("win"):
        return {}
    try:
        voices = _voices()
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for lang in ("hi", "en"):
        tok = _pick(voices, lang)
        if tok is not None:
            out[lang] = tok.GetDescription()
    return out


class Speaker:
    """Speaks in the background; ``say`` interrupts what is being said."""

    def __init__(self):
        self._jobs: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self.names: dict[str, str] = {}
        self.error: str | None = None

    def available(self, lang: str = "hi") -> bool:
        if not sys.platform.startswith("win") or self.error:
            return False
        if not self.names:
            self.names = voice_names()
        return lang in self.names

    def say(self, text: str, lang: str = "hi") -> None:
        if not text or not self.available(lang):
            return
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="hth-speech", daemon=True)
            self._thread.start()
        self._jobs.put((text, lang))

    def stop(self) -> None:
        self._jobs.put(("", "stop"))

    def close(self) -> None:
        self._jobs.put(None)

    def _run(self) -> None:
        try:
            _pythoncom, com = _com()
            voices = _voices()
            speaker = com.Dispatch("SAPI.SpVoice")
        except Exception as exc:  # noqa: BLE001
            log.exception("speech failed to start")
            self.error = str(exc)
            return
        current = None
        while True:
            job = self._jobs.get()
            if job is None:
                speaker.Speak("", _ASYNC | _PURGE)
                return
            text, lang = job
            try:
                if lang == "stop":
                    speaker.Speak("", _ASYNC | _PURGE)
                    continue
                tok = _pick(voices, lang)
                if tok is not None and tok is not current:
                    speaker.Voice = tok
                    current = tok
                speaker.Speak(text, _ASYNC | _PURGE)
            except Exception:  # noqa: BLE001 - one bad sentence must not stop the voice
                log.exception("could not speak")


def synthesize(text: str, lang: str = "hi", rate: int = 0) -> bytes | None:
    """``text`` spoken into 16 kHz mono int16 audio (None when no such voice)."""
    if not sys.platform.startswith("win"):
        return None
    try:
        _pythoncom, com = _com()
        tok = _pick(_voices(), lang)
        if tok is None:
            return None
        voice = com.Dispatch("SAPI.SpVoice")
        voice.Voice = tok
        voice.Rate = rate
        fmt = com.Dispatch("SAPI.SpAudioFormat")
        fmt.Type = 18  # SAFT16kHz16BitMono
        stream = com.Dispatch("SAPI.SpMemoryStream")
        stream.Format = fmt
        voice.AudioOutputStream = stream
        voice.Speak(text)
        return bytes(stream.GetData())
    except Exception:  # noqa: BLE001
        log.exception("could not synthesize speech")
        return None


# --- what to say -----------------------------------------------------------------------------
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_UNITS_HI = {
    "BAG": "बोरी",
    "BAGS": "बोरी",
    "KG": "किलो",
    "GM": "ग्राम",
    "LTR": "लीटर",
    "ML": "एमएल",
    "PCS": "पीस",
    "PKT": "पैकेट",
    "BOX": "डिब्बे",
    "QTL": "क्विंटल",
    "TON": "टन",
    "NOS": "नग",
}
_UNIT = re.compile(r"\b(" + "|".join(_UNITS_HI) + r")\b")
_AMOUNT = re.compile(r"₹\s?(-?[\d,]+(?:\.\d+)?)")
_DATE = re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b")
_RANGE = re.compile(r"\s*\(\d{1,2}-\d{1,2}-\d{4}\s*[–-]\s*\d{1,2}-\d{1,2}-\d{4}\)")


def speakable(text: str, lang: str) -> str:
    """Screen text -> something a voice reads well."""
    text = _RANGE.sub("", text)

    def amount(m: re.Match) -> str:
        value = round(float(m.group(1).replace(",", "")))
        return f"{value} रुपये" if lang == "hi" else f"{value} rupees"

    text = _AMOUNT.sub(amount, text)

    def date(m: re.Match) -> str:
        d, mo = int(m.group(1)), int(m.group(2))
        return f"{d} {_MONTHS[lang][mo - 1]}" if 1 <= mo <= 12 else m.group(0)

    text = _DATE.sub(date, text)
    if lang == "hi":
        text = _UNIT.sub(lambda m: _UNITS_HI[m.group(1)], text)
    if lang == "hi":  # the Hindi voices read digits in English: "छह हज़ार पाँच सौ अट्ठानवे" instead
        text = _INT.sub(lambda m: _hindi_number(int(m.group(0).replace(",", ""))), text)
    text = text.replace(" · ", ", ").replace("·", ",").replace("→", "").replace("(", ", ").replace(")", "")
    text = re.sub(r"\s+,", ",", text)
    return " ".join(text.split()).strip(" ,")


_INT = re.compile(r"(?<![\w.])\d[\d,]*(?![\w.])")


def _hindi_number(n: int) -> str:
    from hth.modules.bills.numwords import integer_words

    words = integer_words(str(abs(n))).replace("दौ", "दो").strip()  # (the invoice table keeps v3's spelling)
    return ("माइनस " if n < 0 else "") + words


def summary(reply) -> str:
    """One or two sentences for a reply card (the screen keeps the details)."""
    lang = reply.lang if reply.lang in ("hi", "en") else "hi"
    parts = [reply.text]
    if reply.kind == "answer":
        if reply.lines:
            parts.append(reply.lines[0])
        if reply.rows and reply.columns and reply.columns[0][1] == "text" and not _ISO.match(str(reply.rows[0][0])):
            names = [str(r[0]) for r in reply.rows[:3] if r and r[0]]
            if names and len(reply.rows) > 1:
                parts.append(("सबसे ऊपर: " if lang == "hi" else "First: ") + ", ".join(names))
    elif reply.kind in ("ask", "unsure") and reply.options:
        choices = [_choice(o.label) for o in reply.options[:4]]
        last = " या " if lang == "hi" else " or "
        parts.append(", ".join(choices[:-1]) + last + choices[-1] if len(choices) > 1 else choices[0])
    return speakable(". ".join(p.rstrip("।.?! ") for p in parts if p), lang)


def _choice(label: str) -> str:
    """ "2 · रमेश सैनी  (भिवानी 9812345678)" -> "रमेश सैनी, भिवानी वाले" (no phone digits)."""
    label = re.sub(r"^\d+\s*·\s*", "", label)
    m = re.match(r"(.*?)\s*\((.*)\)\s*$", label)
    if not m:
        return label.strip()
    name, details = m.group(1).strip(), m.group(2)
    place = next((w for w in details.split() if not any(ch.isdigit() for ch in w)), "")
    if not place:
        return name
    is_hindi = any("ऀ" <= ch <= "ॿ" for ch in place)
    return f"{name}, {place} वाले" if is_hindi else f"{name} from {place.title()}"
