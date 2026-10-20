"""How well spoken questions are heard and answered - System 1 voice end to end.

    python tools/assistant/eval_voice.py                        # synthetic: Windows Hindi voices speak
    python tools/assistant/eval_voice.py --noise 15             #   ... with shop-like noise (dB SNR)
    python tools/assistant/eval_voice.py --recordings D:/rec    # real recordings (stay on this PC)

Synthetic mode speaks held-out spoken-style questions (with made-up customer and item names in a
throw-away in-memory shop - no shop data) and compares three ways of hearing them: the open
vocabulary, the shop's restricted vocabulary, and restricted with the open one as fallback (what
the app does).  Recordings mode reads ``*.wav`` (16 kHz mono) and, when present, a ``.txt`` with
the same name holding what was said, and prints what was heard and answered.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hth.assistant import data, speech, voice  # noqa: E402
from hth.assistant.core import Assistant, Session  # noqa: E402
from hth.assistant.normalize import keys  # noqa: E402
from hth.config import default_data_dir  # noqa: E402

PEOPLE = [
    ("RAMESH KUMAR", "ROHTAK"), ("RAMESH SAINI", "BHIWANI"), ("RAMESH GODARA", "HISAR"), ("SURESH JAKHAR", "SIRSA"),
    ("MAHAVIR SINGH", "JIND"), ("RAJBIR DHULL", "KAITHAL"), ("SATBIR MALIK", "SONIPAT"), ("KRISHAN LAL", "FATEHABAD"),
    ("OMPRAKASH", "HANSI"), ("JAGDISH CHANDER", "TOHANA"), ("BALWAN SINGH", "UKLANA"), ("DHARAMPAL", "BARWALA"),
]  # fmt: skip
ITEMS = [("UREA", "BAG"), ("DAP", "BAG"), ("ZINC SULPHATE", "KG"), ("NPK 12-32-16", "BAG"), ("CHLORPYRIFOS", "LTR")]
_MADE_SENSE = ("answer", "help", "greeting")


def demo_shop():
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.services.accounts import AccountsService
    from hth.services.inventory import InventoryService

    db = Database(":memory:")
    initialize(db)
    acc, inv = AccountsService(db), InventoryService(db)
    for name, place in PEOPLE:
        acc.add_customer(name, place, 1000, "2026-09-01")
    for name, unit in ITEMS:
        inv.add_item(name, 100, 120, unit=unit, opening_quantity=20)
    return db


def word_errors(ref: str, hyp: str) -> tuple[int, int]:
    r, h = keys(ref), keys(hyp)  # phonetic keys: ज़रा and जरा are the same word
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)], len(r)


def add_noise(pcm: bytes, snr_db: float | None, seed: int) -> bytes:
    if snr_db is None:
        return pcm
    import numpy as np

    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    noise = np.convolve(np.random.default_rng(seed).normal(size=x.size), np.ones(8) / 8, mode="same")
    x = x + noise * np.sqrt(np.mean(x**2) / (np.mean(noise**2) * 10 ** (snr_db / 10)))
    return np.clip(x, -32768, 32767).astype(np.int16).tobytes()


def shop_grammar(db, model: voice.VoiceModel) -> tuple[str, dict[str, str]]:
    rows = db.fetchall("SELECT name_hi, details_hi FROM customers")
    names = [r["name_hi"] for r in rows] + [r["details_hi"] for r in rows]
    names += [r["name_hi"] for r in db.fetchall("SELECT name_hi FROM items")]
    shop = voice.shop_words(names)
    spellings = voice.voice_spellings((w for w in shop if w not in model.words), model, speech.synthesize)
    return voice.grammar(voice.question_words() | shop | voice.shop_words(spellings.values()), model.words), spellings


def synthetic(args, model: voice.VoiceModel) -> None:
    db = demo_shop()
    bot = Assistant(db, today=dt.date(2026, 10, 20))
    bot._dry = True
    bot.warm_up()
    gram, spellings = shop_grammar(db, model)
    bot.set_voice_spellings(spellings)
    customers = db.fetchall("SELECT id, name_hi FROM customers")
    items = db.fetchall("SELECT id, name_hi FROM items")
    rng = random.Random(3)
    _train, test = data.split(data.generate(per_template=6))
    test = rng.sample([e for e in test if e.style == "sp" and e.intent != "unsupported"], args.n)
    modes = ("open", "restricted", "app")
    stats = {m: {"err": 0, "words": 0, "right": 0, "asked": 0, "secs": 0.0} for m in modes}
    for k, e in enumerate(test):
        c, i = rng.choice(customers), rng.choice(items)
        said = " ".join(e.text.replace("<C1>", c["name_hi"]).replace("<I1>", i["name_hi"]).split())
        pcm = add_noise(speech.synthesize(said, rate=[-1, 0, 1, 2][k % 4]) or b"", args.noise, k)
        for mode in modes:
            t = time.perf_counter()
            if mode == "app":
                heard = model.transcribe(pcm, gram).text
                heard, reply = bot.ask_heard(heard, Session(), lambda pcm=pcm: model.transcribe(pcm).text)
            else:
                heard = model.transcribe(pcm, gram if mode == "restricted" else None).text
                reply = bot.ask(heard, Session())
            s = stats[mode]
            s["secs"] += time.perf_counter() - t
            err, n = word_errors(said, heard)
            s["err"], s["words"] = s["err"] + err, s["words"] + n
            ok = (reply.kind == "answer" and reply.tool == e.intent) or reply.kind == e.intent
            ok = ok and ("customer" not in e.args or reply.args.get("customer") == c["id"])
            ok = ok and ("item" not in e.args or reply.args.get("item") == i["id"])
            s["right"] += ok
            s["asked"] += reply.kind in ("ask", "unsure")
            if mode == "app" and not ok and args.errors:
                print(f"  {e.intent:17} said {said!r}\n{'':19}heard {heard!r} -> {reply.kind} {reply.tool or ''}")
    noise = "clean" if args.noise is None else f"{args.noise:g} dB noise"
    print(f"{args.n} held-out spoken questions, Windows Hindi voices, {noise}, {len(spellings)} voice spellings")
    for mode in modes:
        s = stats[mode]
        print(
            f"  {mode:10} word errors {s['err'] / max(1, s['words']):6.1%}   answered right {s['right'] / args.n:6.1%}"
            f"   asked back {s['asked'] / args.n:5.1%}   {s['secs'] / args.n * 1000:5.0f} ms each"
        )


def recordings(args, model: voice.VoiceModel) -> None:
    from hth.db.connection import Database

    db = Database(str(args.db)) if args.db else demo_shop()
    bot = Assistant(db)
    bot._dry = True  # never writes: no audit lines
    gram, spellings = shop_grammar(db, model)
    bot.set_voice_spellings(spellings)
    total_err = total_words = 0
    for wav in sorted(Path(args.recordings).glob("*.wav")):
        with wave.open(str(wav), "rb") as w:
            if w.getframerate() != voice.RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
                print(f"{wav.name}: skipped (needs 16 kHz mono 16-bit)")
                continue
            pcm = w.readframes(w.getnframes())
        heard = model.transcribe(pcm, gram).text
        used, reply = bot.ask_heard(heard, Session(), lambda pcm=pcm: model.transcribe(pcm).text)
        line = f"{wav.name}: heard {used!r} -> {reply.kind} {reply.tool or ''}"
        ref = wav.with_suffix(".txt")
        if ref.exists():
            err, n = word_errors(ref.read_text(encoding="utf-8").strip(), used)
            total_err, total_words = total_err + err, total_words + n
            line += f"  ({err}/{n} words wrong)"
        print(line)
    if total_words:
        print(f"word errors overall: {total_err / total_words:.1%}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=voice.voice_dir(default_data_dir()), help="Vosk model folder")
    ap.add_argument("--n", type=int, default=150, help="synthetic questions")
    ap.add_argument("--noise", type=float, default=None, help="add noise at this SNR in dB (e.g. 15)")
    ap.add_argument("--errors", action="store_true", help="print the questions answered wrongly")
    ap.add_argument("--recordings", type=Path, help="folder of 16 kHz mono .wav recordings (+ optional .txt)")
    ap.add_argument("--db", type=Path, help="with --recordings: a shop database to look names up in")
    args = ap.parse_args()
    model = voice.VoiceModel(args.model)
    if not model.available():
        print(f"no voice model at {args.model} (or vosk is not installed)")
        return 1
    if args.recordings:
        recordings(args, model)
    elif "hi" not in speech.voice_names():
        print("synthetic mode needs a Windows Hindi voice (Settings -> Time & language -> Speech)")
        return 1
    else:
        synthetic(args, model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
