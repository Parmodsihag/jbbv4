"""System 1 voice: a small Hindi speech recogniser limited to the shop's own words.

Spoken Hinglish comes out of a Hindi recogniser in Devanagari - *"रमेश का लास्ट मंथ का
बैलेंस बताओ"* - which the assistant reads like a typed question (the ``sp`` corpus style).

* Model: Vosk ``vosk-model-small-hi-0.22`` (42 MB download, Apache 2.0), installed from
  Settings -> Assistant -> Install voice model into ``<data>/voice``.  No AVX needed.
* **Restricted vocabulary** - the System 1 part: the recogniser may only choose among the
  question words of the corpus, numbers, and the Hindi copies of the shop's customer and item
  names (and their villages).  On synthetic Hinglish questions that took word errors from 21 %
  to 6 % and made recognition ~8x faster than the open vocabulary.
* The **open vocabulary** (the model's own 179k words) is the fallback for the same audio when
  the restricted hearing does not make sense (``Assistant.ask_heard``).
* Names missing from the model's dictionary get a *voice spelling*: the name is spoken by the
  Windows Hindi voice and heard with the open vocabulary once (``voice_spellings``); that
  spelling joins the vocabulary and the name index.

``Listener`` streams from the microphone in a worker thread and reports level, partial words
and the final hearing through one callback (the chat screen marshals it to Tk).
"""

from __future__ import annotations

import contextlib
import json
import logging
import queue
import shutil
import struct
import threading
import time
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from hth.assistant import data
from hth.assistant.spoken import NUMBER_WORDS, SPOKEN

log = logging.getLogger(__name__)

RATE = 16_000

# Words of short replies and fillers that are not in the question templates.
_EXTRA = (
    "वाले वाला वाली वालों पहला पहले पहली दूसरा दूसरे दूसरी तीसरा तीसरे तीसरी चौथा चौथे पांचवां नंबर "
    "छोड़ो छोड़ दो रहने दो हाँ हां नहीं ठीक सही और भी उसका उसकी उसके उनका उनकी उनके इसका इसकी इसके "
    "वही वो वह ये यह गांव गाँव शहर मोहल्ला जनवरी फरवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर "
    "नवंबर दिसंबर हफ्ते हफ़्ते साल महीने दिन तारीख"
)


# --- the model ------------------------------------------------------------------------------
def voice_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "voice"


def find_model_dir(folder: Path) -> Path | None:
    """The Vosk model folder (``am/final.mdl`` + ``conf/model.conf``) at or just below ``folder``."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    for cand in [folder, *sorted(p for p in folder.iterdir() if p.is_dir())]:
        if (cand / "am" / "final.mdl").exists() and (cand / "conf" / "model.conf").exists():
            return cand
    return None


def backend_available() -> bool:
    try:
        import vosk  # noqa: F401
    except Exception:  # noqa: BLE001 - not installed, or its DLL will not load
        return False
    return True


def model_words(model_dir: Path) -> frozenset[str]:
    """Every word the model can hear, read from the symbol table in ``graph/Gr.fst``
    (OpenFst binary header).  Empty if the model has no such table."""
    path = Path(model_dir) / "graph" / "Gr.fst"
    try:
        with open(path, "rb") as f:

            def i32() -> int:
                return struct.unpack("<i", f.read(4))[0]

            def text() -> str:
                return f.read(i32()).decode("utf-8", "replace")

            if i32() & 0xFFFFFFFF != 0x7EB2FDD6:
                return frozenset()
            text(), text()  # fst type, arc type
            _version, flags = i32(), i32()
            f.read(32)  # properties, start, states, arcs
            if not flags & 1:
                return frozenset()
            i32(), text()  # table magic, name
            f.read(8)  # available key
            (size,) = struct.unpack("<q", f.read(8))
            words = set()
            for _ in range(size):
                w = text()
                f.read(8)
                words.add(w)
            return frozenset(w for w in words if not w.startswith(("<", "#", "!", "[")))
    except (OSError, struct.error):
        return frozenset()


@dataclass
class Heard:
    text: str
    words: list[tuple[str, float]] = field(default_factory=list)
    restricted: bool = True

    @property
    def confidence(self) -> float:
        return sum(c for _w, c in self.words) / len(self.words) if self.words else 0.0


class VoiceModel:
    """The installed Vosk model, loaded on first use (about half a second, ~150-300 MB)."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._model = None
        self._words: frozenset[str] | None = None
        self._lock = threading.Lock()
        self.error: str | None = None

    def path(self) -> Path | None:
        return find_model_dir(self.folder)

    def available(self) -> bool:
        return self.error is None and self.path() is not None and backend_available()

    @property
    def words(self) -> frozenset[str]:
        if self._words is None:
            path = self.path()
            self._words = model_words(path) if path else frozenset()
        return self._words

    def model(self):
        with self._lock:
            if self._model is None:
                from vosk import Model, SetLogLevel

                SetLogLevel(-1)
                path = self.path()
                if path is None:
                    raise RuntimeError("no voice model installed")
                t = time.perf_counter()
                self._model = Model(str(path))
                log.info("voice: model %s loaded in %.1fs", path.name, time.perf_counter() - t)
            return self._model

    def recognizer(self, grammar: str | None = None):
        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(self.model(), RATE, grammar) if grammar else KaldiRecognizer(self.model(), RATE)
        rec.SetWords(True)
        return rec

    def transcribe(self, pcm: bytes, grammar: str | None = None) -> Heard:
        """16 kHz mono int16 audio -> what was heard (restricted when ``grammar`` is given)."""
        rec = self.recognizer(grammar)
        for i in range(0, len(pcm), 8000):
            rec.AcceptWaveform(pcm[i : i + 8000])
        return _heard(rec.FinalResult(), grammar is not None)

    def unload(self) -> None:
        with self._lock:
            self._model = None


def _heard(result_json: str, restricted: bool) -> Heard:
    res = json.loads(result_json or "{}")
    words = [(w["word"], float(w.get("conf", 1.0))) for w in res.get("result", []) if w.get("word") != "[unk]"]
    text = " ".join(w for w, _c in words) if words else res.get("text", "").replace("[unk]", "").strip()
    return Heard(" ".join(text.split()), words, restricted)


# --- the shop's vocabulary ------------------------------------------------------------------
@lru_cache(maxsize=1)
def question_words() -> frozenset[str]:
    """Every word of the Hindi and spoken templates, fillers, numbers and reply words."""
    words: set[str] = set(SPOKEN.values()) | set(NUMBER_WORDS.values()) | set(_EXTRA.split())
    for e in data.generate(per_template=4, seed=11):
        if e.style in ("hi", "sp"):
            words.update(_clean(t) for t in e.text.split() if not t.startswith("<"))
    return frozenset(w for w in words if w)


def _clean(token: str) -> str:
    return "".join(ch for ch in token if ch.isalnum() or "ऀ" <= ch <= "ॿ")


def shop_words(names: Iterable[str]) -> set[str]:
    """Devanagari words of the shop's Hindi names and details (villages)."""
    out: set[str] = set()
    for name in names:
        for tok in (name or "").split():
            tok = _clean(tok)
            if tok and all("ऀ" <= ch <= "ॿ" for ch in tok):
                out.add(tok)
    return out


def grammar(words: Iterable[str], known: frozenset[str] = frozenset()) -> str:
    """The restricted vocabulary as Vosk wants it: words the model knows, plus ``[unk]``."""
    chosen = sorted({w for w in words if not known or w in known})
    return json.dumps(chosen + ["[unk]"], ensure_ascii=False)


def voice_spellings(
    missing: Iterable[str],
    model: VoiceModel,
    synthesize: Callable[[str], bytes | None],
    cache_path: Path | None = None,
) -> dict[str, str]:
    """How the recogniser writes each word it does not know, by speaking it with the Windows
    Hindi voice and hearing it with the open vocabulary.  Cached per word in ``cache_path``."""
    cache: dict[str, str] = {}
    if cache_path is not None:
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
    changed = False
    for word in sorted(set(missing)):
        if word in cache:
            continue
        audio = synthesize(word)
        heard = model.transcribe(audio).text if audio else ""
        cache[word] = heard if heard and heard != word else ""
        changed = True
    if changed and cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        except OSError:
            log.exception("could not save voice spellings")
    return {w: s for w, s in cache.items() if s}


# --- the microphone -----------------------------------------------------------------------
Event = tuple[
    str, object
]  # ("level", 0..1) ("partial", text) ("final", (Heard, pcm)) ("error", text) ("timeout", None)


class Listener:
    """One spoken question: microphone -> restricted recogniser, in a worker thread.

    Stops by itself when the speaker pauses (the model's end-of-utterance rule), after
    ``max_seconds``, or when nothing was said for ``quiet_seconds``; ``stop()`` ends it early.
    """

    def __init__(
        self,
        model: VoiceModel,
        grammar_json: str | None,
        on_event: Callable[[Event], None],
        max_seconds: float = 15.0,
        quiet_seconds: float = 7.0,
        device=None,
        source: Iterable[bytes] | None = None,
    ):
        """``source``: audio chunks to use instead of the microphone (a voice note, tests)."""
        self.model, self.grammar_json, self.on_event = model, grammar_json, on_event
        self.max_seconds, self.quiet_seconds, self.device = max_seconds, quiet_seconds, device
        self.source = source
        self._chunks: queue.Queue[bytes | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="hth-voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        if self.source is None:
            try:
                import sounddevice as sd
            except Exception as exc:  # noqa: BLE001
                self.on_event(("error", f"microphone library missing: {exc}"))
                return
        try:
            rec = self.model.recognizer(self.grammar_json)
        except Exception as exc:  # noqa: BLE001
            log.exception("voice model failed")
            self.on_event(("error", str(exc)))
            return

        def callback(indata, _frames, _time, _status):
            self._chunks.put(bytes(indata))

        audio = bytearray()
        started = time.monotonic()
        spoke_at: float | None = None
        if self.source is not None:
            for chunk in self.source:
                self._chunks.put(chunk)
            self._chunks.put(bytes(2 * RATE))  # a second of silence: the end of the question
            self._chunks.put(None)
        try:
            stream = (
                contextlib.nullcontext()
                if self.source is not None
                else sd.RawInputStream(
                    samplerate=RATE,
                    blocksize=RATE // 10,
                    dtype="int16",
                    channels=1,
                    callback=callback,
                    device=self.device,
                )
            )
            with stream:
                while not self._stop.is_set():
                    try:
                        chunk = self._chunks.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if chunk is None:  # the end of a recorded source
                        break
                    audio += chunk
                    self.on_event(("level", _level(chunk)))
                    if rec.AcceptWaveform(chunk):
                        heard = _heard(rec.Result(), self.grammar_json is not None)
                        if heard.text:
                            self.on_event(("final", (heard, bytes(audio))))
                            return
                    else:
                        partial = json.loads(rec.PartialResult()).get("partial", "").replace("[unk]", "").strip()
                        if partial:
                            spoke_at = spoke_at or time.monotonic()
                            self.on_event(("partial", " ".join(partial.split())))
                    now = time.monotonic()
                    if now - started > self.max_seconds:
                        break
                    if spoke_at is None and now - started > self.quiet_seconds:
                        self.on_event(("timeout", None))
                        return
        except Exception as exc:  # noqa: BLE001 - no microphone, device busy, ...
            log.exception("microphone failed")
            self.on_event(("error", str(exc)))
            return
        heard = _heard(rec.FinalResult(), self.grammar_json is not None)
        self.on_event(("final", (heard, bytes(audio))) if heard.text else ("timeout", None))


def _level(chunk: bytes) -> float:
    """0..1 loudness of a chunk of int16 audio, for the level bar."""
    n = len(chunk) // 2
    if not n:
        return 0.0
    samples = struct.unpack(f"<{n}h", chunk[: n * 2])
    rms = (sum(s * s for s in samples[::4]) / max(1, len(samples[::4]))) ** 0.5
    return min(1.0, rms / 6000)


# --- installing ---------------------------------------------------------------------------
def install_zip(zip_path: Path, data_dir: Path) -> Path:
    """Unpack a Vosk model zip (as downloaded from alphacephei.com) into ``<data>/voice``.
    Members are written by their path inside the model folder only - nothing outside it."""
    dest = voice_dir(data_dir)
    tmp = dest.with_name("voice.new")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        marker = next((n for n in names if n.replace("\\", "/").endswith("am/final.mdl")), None)
        if marker is None or not any(n.replace("\\", "/").endswith("conf/model.conf") for n in names):
            raise ValueError("This zip is not a Vosk voice model (am/final.mdl and conf/model.conf are missing).")
        root = marker.replace("\\", "/")[: -len("am/final.mdl")]
        model_name = Path(root.rstrip("/")).name or "voice-model"
        target = tmp / model_name
        for n in names:
            rel = n.replace("\\", "/")
            if not rel.startswith(root):
                continue
            parts = [p for p in rel[len(root) :].split("/") if p not in ("", ".", "..")]
            if not parts:
                continue
            out = target.joinpath(*parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(n) as src, open(out, "wb") as f:
                shutil.copyfileobj(src, f, 1 << 20)
    if dest.exists():
        shutil.rmtree(dest.with_name("voice.old"), ignore_errors=True)
        dest.rename(dest.with_name("voice.old"))
    tmp.rename(dest)
    shutil.rmtree(dest.with_name("voice.old"), ignore_errors=True)
    found = find_model_dir(dest)
    if found is None:
        raise ValueError("The voice model could not be installed.")
    return found
