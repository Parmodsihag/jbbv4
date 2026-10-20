"""Voice: spoken Hinglish, the recogniser's vocabulary, voice spellings, spoken answers."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import struct
import zipfile
from pathlib import Path

import pytest

from hth.assistant import data, speech, voice
from hth.assistant import normalize as norm
from hth.assistant.core import Assistant, Option, Reply, Session
from hth.assistant.entities import EntityIndex
from hth.assistant.spoken import SPOKEN, to_spoken

TODAY = dt.date(2026, 10, 20)


# Spoken Hinglish -----------------------------------------------------------------------------
def test_every_hinglish_template_word_has_a_spoken_form():
    words = set()
    for _tid, _intent, style, t in data.templates():
        if style == "hl":
            words.update(w.lower() for w in re.findall(r"[A-Za-z']+", re.sub(r"\{[A-Z]+\}", " ", t)))
    for _v, phrases in data.PERIODS + data.DAYS:
        for t in phrases["hl"]:
            words.update(w.lower() for w in re.findall(r"[A-Za-z']+", t))
    assert sorted(words - set(SPOKEN)) == []


def test_to_spoken_writes_hinglish_as_a_recogniser_does():
    assert to_spoken("<C1> ka last month ka balance batao") == "<C1> का लास्ट मंथ का बैलेंस बताओ"
    assert to_spoken("top 10 bakayedar?") == "टॉप दस बकायेदार"


def test_spoken_style_is_held_out_with_its_hinglish_original():
    _train, test = data.split(data.generate(per_template=2))
    held_hl = {e.template_id for e in test if e.style == "hl"}
    held_sp = {e.template_id for e in test if e.style == "sp"}
    assert held_sp and held_sp == {t.replace("/hl/", "/sp/") for t in held_hl}


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("लास्ट मंथ की सेल", "last_month"),
        ("इस मंथ का प्रॉफिट", "this_month"),
        ("इस वीक", "this_week"),
        ("टुडे की सेल", "today"),
        ("यस्टरडे की एंट्री", "yesterday"),
        ("लास्ट ईयर का प्रॉफिट", "last_fy"),
        ("पिछले तीस दिन", "days:30"),
        ("लास्ट थर्टी डेज़", "days:30"),
        ("pichle do din ki bikri", "days:2"),
        ("पंद्रह तारीख का हिसाब", "dom:15"),
    ],
)
def test_spoken_periods(text, value):
    p = norm.find_period(text, TODAY)
    assert p is not None and p.value == value


def test_spoken_numbers_and_bata_do():
    assert norm.find_number("sabse bade bakayedar bata do") is None  # "tell me", not 2
    assert norm.find_number("sabse bade do bakayedar") == 2
    assert norm.find_number("टॉप टेन") == 10
    assert norm.find_number("top twenty five") == 25
    assert norm.find_number("पचास हज़ार से ऊपर") == 50_000


# The recogniser's vocabulary ------------------------------------------------------------------
def _fake_fst(path: Path, words: list[str]) -> None:
    """The OpenFst header + output symbol table Vosk's ``graph/Gr.fst`` starts with."""

    def s(x: str) -> bytes:
        b = x.encode("utf-8")
        return struct.pack("<i", len(b)) + b

    out = struct.pack("<i", 0x7EB2FDD6) + s("ngram") + s("standard") + struct.pack("<ii", 4, 3)
    out += struct.pack("<Qqqq", 0, 0, 1, 0)
    for _table in range(2):
        out += struct.pack("<i", 2125658996) + s("words.txt") + struct.pack("<qq", len(words), len(words))
        for k, w in enumerate(words):
            out += s(w) + struct.pack("<q", k)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


def _fake_model_dir(root: Path, words=("<eps>", "[unk]", "रमेश", "का", "बैलेंस", "#0")) -> Path:
    (root / "am").mkdir(parents=True)
    (root / "am" / "final.mdl").write_bytes(b"x")
    (root / "conf").mkdir()
    (root / "conf" / "model.conf").write_text("")
    _fake_fst(root / "graph" / "Gr.fst", list(words))
    return root


def test_model_words_reads_the_fst_symbol_table(tmp_path):
    folder = _fake_model_dir(tmp_path / "vosk-model-small-hi-0.22")
    assert voice.find_model_dir(tmp_path) == folder
    assert voice.model_words(folder) == {"रमेश", "का", "बैलेंस"}


def test_grammar_keeps_known_words_and_unk():
    g = json.loads(voice.grammar(["रमेश", "गोदारा", "का"], frozenset({"रमेश", "का"})))
    assert g == ["का", "रमेश", "[unk]"]
    assert "वाले" in voice.question_words() and "बैलेंस" in voice.question_words()
    assert voice.shop_words(["रमेश सैनी", "BHIWANI 98123", "भिवानी 98123"]) == {"रमेश", "सैनी", "भिवानी"}


class _FakeModel:
    """Hears what was 'said' from the bytes (a test's stand-in for Vosk)."""

    def __init__(self, hearing: dict[bytes, str] | None = None):
        self.hearing = hearing or {}

    def transcribe(self, pcm, grammar=None):
        return voice.Heard(self.hearing.get(pcm, ""), [], grammar is not None)


def test_voice_spellings_are_heard_once_and_cached(tmp_path):
    said = []

    def synth(word):
        said.append(word)
        return word.encode("utf-8")

    model = _FakeModel({"क्लोर्पाइरिफ़ोस".encode(): "क्लोरोपायरीफास", "धुल्ल".encode(): "धुल्ल"})
    cache = tmp_path / "spell.json"
    got = voice.voice_spellings(["क्लोर्पाइरिफ़ोस", "धुल्ल"], model, synth, cache)
    assert got == {"क्लोर्पाइरिफ़ोस": "क्लोरोपायरीफास"}  # heard as itself: nothing to add
    assert voice.voice_spellings(["क्लोर्पाइरिफ़ोस"], model, synth, cache) == got
    assert said == ["क्लोर्पाइरिफ़ोस", "धुल्ल"]  # the second call used the cache


def test_heard_spelling_finds_the_record(db, inventory):
    item = inventory.add_item("CHLORPYRIFOS", 310, 360, unit="LTR", opening_quantity=5)
    db.execute("UPDATE items SET name_hi = 'क्लोर्पाइरिफ़ोस' WHERE id = ?", (item.id,))
    index = EntityIndex.from_db(db, TODAY)
    assert index.link("क्लोरोपायरीफास कितना बचा है", ("item",)).first("item") is None
    index.add_spellings({"क्लोर्पाइरिफ़ोस": "क्लोरोपायरीफास"})
    assert index.link("क्लोरोपायरीफास कितना बचा है", ("item",)).first("item").best.id == item.id


def test_install_voice_zip_is_confined_to_the_voice_folder(tmp_path):
    src = tmp_path / "v.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("vosk-model-small-hi-0.22/am/final.mdl", b"m")
        z.writestr("vosk-model-small-hi-0.22/conf/model.conf", b"c")
        z.writestr("vosk-model-small-hi-0.22/graph/Gr.fst", b"g")
        z.writestr("vosk-model-small-hi-0.22/../../evil.txt", b"x")
        z.writestr("other/readme.txt", b"x")
    data_dir = tmp_path / "data"
    folder = voice.install_zip(src, data_dir)
    assert folder == data_dir / "voice" / "vosk-model-small-hi-0.22"
    assert (folder / "graph" / "Gr.fst").exists()
    assert not (tmp_path / "evil.txt").exists() and not (data_dir / "evil.txt").exists()
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("readme.txt", b"x")
    with pytest.raises(ValueError):
        voice.install_zip(bad, data_dir)
    assert voice.find_model_dir(data_dir / "voice") == folder  # a bad zip leaves the old model


# The microphone loop, with a recorded source and a fake recogniser ---------------------------
class _FakeRecognizer:
    def __init__(self, words):
        self.words, self.n = words, 0

    def AcceptWaveform(self, chunk):  # noqa: N802 - Vosk's API
        self.n += 1
        return False

    def PartialResult(self):  # noqa: N802
        return json.dumps({"partial": " ".join(self.words[: self.n])})

    def Result(self):  # noqa: N802
        return self.FinalResult()

    def FinalResult(self):  # noqa: N802
        return json.dumps({"result": [{"word": w, "conf": 0.9} for w in self.words], "text": " ".join(self.words)})


def test_listener_reports_partials_then_the_final_hearing():
    class Model:
        def recognizer(self, grammar):
            return _FakeRecognizer(["रमेश", "का", "बैलेंस"])

    events = []
    listener = voice.Listener(Model(), "[]", events.append, source=[b"\1\0" * 1600] * 3)
    listener.start()
    listener._thread.join(5)
    kinds = [k for k, _v in events]
    assert "level" in kinds and "partial" in kinds and kinds[-1] == "final"
    heard, pcm = events[-1][1]
    assert heard.text == "रमेश का बैलेंस" and heard.restricted and len(pcm) >= 3 * 3200


# Spoken answers -------------------------------------------------------------------------------
def test_answers_are_spoken_in_hindi_words():
    text = speech.speakable("रमेश कुमार · शेष ₹6,597.92 (हमें लेना है) · वादा 10-10-2026", "hi")
    assert "छः हज़ार पाँच सौ अट्ठानवे रुपये" in text and "दस अक्टूबर" in text
    assert not re.search(r"\d", text)
    assert speech.speakable("यूरिया · स्टॉक में 24 BAG", "hi") == "यूरिया, स्टॉक में चौबीस बोरी"
    assert speech.speakable("total ₹2,40,512.50 (01-09-2026 – 30-09-2026)", "en") == "total 240512 rupees"


def test_ask_back_is_spoken_with_villages_not_phone_numbers():
    reply = Reply(
        "hi",
        "ask",
        "कौन से रमेश?",
        options=[Option("1 · रमेश सैनी  (भिवानी 9812345678)", "1"), Option("2 · रमेश कुमार  (रोहतक)", "2")],
    )
    said = speech.summary(reply)
    assert said == "कौन से रमेश. रमेश सैनी, भिवानी वाले या रमेश कुमार, रोहतक वाले"


def test_ledger_dates_are_not_read_out_as_names():
    reply = Reply("hi", "answer", "रमेश कुमार · पिछले महीने", ["2 एंट्री"], [("तारीख", "text")], [("2026-09-03", "x")])
    assert "सबसे ऊपर" not in speech.summary(reply)


# Spoken questions through the assistant -------------------------------------------------------
@pytest.fixture(scope="module")
def classifier():
    from hth.assistant.system1 import IntentClassifier

    return IntentClassifier.train(data.split(data.generate(per_template=30))[0])


@pytest.fixture
def shop(db, accounts, inventory):
    r1 = accounts.add_customer("RAMESH KUMAR", "ROHTAK", 5000, "2026-09-01")
    r2 = accounts.add_customer("RAMESH SAINI", "BHIWANI", 1200, "2026-09-03")
    urea = inventory.add_item("UREA", 266, 280, unit="BAG", opening_quantity=40)
    return {"r1": r1, "r2": r2, "urea": urea}


@pytest.mark.parametrize(
    ("heard", "tool"),
    [
        ("<C1> का बैलेंस कितना है", "customer_balance"),
        ("<C1> का लास्ट मंथ का हिसाब", "customer_ledger"),
        ("लास्ट मंथ की सेल कितनी हुई", "period_sales"),
        ("<I1> का स्टॉक कितना है", "item_stock"),
        ("<I1> का रेट क्या है", "item_price"),
        ("मार्केट में टोटल कितना उधार है", "total_receivable"),
        ("टॉप टेन डिफॉल्टर दिखाओ", "top_debtors"),
        ("कौन सा माल ऑर्डर करना है", "reorder"),
        ("इस मंथ का प्रॉफिट", "profit"),
        ("कैश कितना है", "cash_balance"),
    ],
)
def test_spoken_hinglish_intents(classifier, heard, tool):
    from hth.assistant.core import route

    assert route(classifier, heard, TODAY)[0][0] == tool


def test_restricted_hearing_falls_back_to_the_open_one(db, shop, classifier):
    bot = Assistant(db, today=TODAY, classifier=classifier)
    session = Session()
    asked = []

    def alternative():
        asked.append(1)
        return "यूरिया का स्टॉक कितना है"

    used, reply = bot.ask_heard("रिपोर्ट रिपोर्ट रिपोर्ट", session, alternative)
    assert asked and used == "यूरिया का स्टॉक कितना है" and reply.tool == "item_stock"
    used, reply = bot.ask_heard("रमेश सैनी का बैलेंस बताओ", session, lambda: asked.append(2) or "x")
    assert used == "रमेश सैनी का बैलेंस बताओ" and reply.tool == "customer_balance"
    assert asked == [1]  # a hearing that made sense needs no second opinion
    logged = db.fetchall("SELECT message FROM audit_log WHERE code = '13'")
    assert len(logged) == 2  # the trial runs did not write audit lines


def test_a_spoken_reply_to_an_ask_back_is_used_as_heard(db, shop, classifier):
    bot = Assistant(db, today=TODAY, classifier=classifier)
    session = Session()
    _used, reply = bot.ask_heard("रमेश का बैलेंस बताओ", session, lambda: "")
    assert reply.kind == "ask"
    used, reply = bot.ask_heard("रोहतक वाले", session, lambda: pytest.fail("not needed"))
    assert reply.kind == "answer" and reply.args["customer"] == shop["r1"].id


def test_speak_preference(db):
    from hth.services.preferences import Preferences

    prefs = Preferences(db)
    assert prefs.assistant_speak() == "voice"
    prefs.set_assistant_speak("never")
    assert prefs.assistant_speak() == "never"
    with pytest.raises(ValueError):
        prefs.set_assistant_speak("loud")


# Real recogniser and Windows voice (only where they are installed) ----------------------------
REAL_MODEL = os.environ.get("HTH_VOICE_MODEL")


@pytest.mark.skipif(not REAL_MODEL, reason="set HTH_VOICE_MODEL=<folder with a Vosk model> to run")
def test_real_voice_round_trip():
    if "hi" not in speech.voice_names():
        pytest.skip("no Windows Hindi voice")
    model = voice.VoiceModel(Path(REAL_MODEL))
    pcm = speech.synthesize("रमेश का लास्ट मंथ का बैलेंस बताओ")
    words = voice.question_words() | {"रमेश"}
    heard = model.transcribe(pcm, voice.grammar(words, model.words))
    assert heard.text == "रमेश का लास्ट मंथ का बैलेंस बताओ"
