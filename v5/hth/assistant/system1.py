"""System 1: the fast intent classifier - no language model, NumPy only.

Text (names already replaced by ``<C1>`` / ``<I1>``) -> phonetic word tokens -> sparse
features (words, word pairs, character 3-5-grams inside words) -> softmax regression over
the intents of :mod:`hth.assistant.data`.  Trained on the synthetic corpus in a few seconds
and cached as one small ``.npz`` (keyed by the corpus version), so the shop PC trains once.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from hth.assistant import data
from hth.assistant.normalize import key, keys

log = logging.getLogger(__name__)


# Concepts shared by English, Hindi and Hinglish - the representation in which "owe",
# "baaki", "बकाया" and "udhaar" are the same thing.  Matched on phonetic keys.
_CONCEPTS: dict[str, str] = {}
for concept, words in {
    "bal": "stuck fasa fansa phasa atka owe owes owed due dues outstanding balance baki baaki bakaya udhaar udhar udhari lena baqi pending remaining shesh",
    "phone": "phone number mobile contact no fon nambar mobail",
    "krar": "promise promised promises krar karar vada vaada wada commitment",
    "late": "past broke broken kept late overdue missed nikal nikla nikli gaya gayi toda broke expired_promise delay der",
    "sale": "turnover sell sold sale sales selling bikri bika bike bechi becha beche bikri bechna business dhandha",
    "stock": "stock left bacha bache bachi pada padi remaining inventory available hai_kya",
    "price": "ret reit keemat kimat price rate cost bhav bhaav dam daam kimat keemat mrp",
    "profit": "gain loss nafa nuksan nuksaan kamaya kamaia kamaye profit munafa fayda faida kamai earning earned margin",
    "exp": "kharche kharchey costs expense expenses kharcha kharch spend spent spending lagat",
    "cash": "cash bank galla galle money_in_hand nakad nakd account_balance",
    "order": "reorder order mangwana mangana mangvana purchase_order",
    "expire": "eksapairi eksapaiar expire expiry expiring expired",
    "low": "finish finished nearly almost low running finishing khatam kam short",
    "interest": "interest byaj byaaj sood",
    "entries": "entered enter written book entries entry rojnamcha daybook likha written transactions list",
    "top": "top biggest most largest sabse jyada zyada maximum bade",
    "collect": "collect collection vasooli vasuli call recover recovery",
    "total": "lendari lenadari milake milakar sabka everyone together total kul market bazar sab overall",
    "payable": "dendari denadari chukana chukani payable hume humein hamein dena farmers kisano kisan",
    "greet": "haal hal chaal badhiya night hello hi namaste ram_ram dhanyawad thanks shukriya morning",
    "help": "puch puchna puchu pucho poochna puchne tarika example examples udaharan know works istemal chalta batate help madad sakte use samjhao kya_puch",
    "attn": "alert alerts theek thik wrong issue issues attention dhyan zaruri important problem dikkat",
    "off": "jeeta jita jeeti won maich ticket poem kavita kahani story weather mausam joke chutkula song gana match news khabar movie",
    "when": "when kab date tarikh",
    "ledger": "ledger statement account khata hisab hisaab history",
    "who": "who whom kiska kiske kisne kisse kaun kisko",
    "today": "today aaj",
    "coming": "aage soon upcoming coming aane agle next will dega denge aayega",
    "much": "much kitna kitni kitne",
}.items():
    for w in words.split():
        for part in w.split("_"):
            _CONCEPTS.setdefault(key(part) if not part.startswith("<") else part, concept)


# Typos in a concept word ("prfoit", "sotck", "nubmer") still name the concept: one letter
# dropped, added, swapped or changed.  Common words never take part ("this" is not "thik").
_COMMON = {
    key(w)
    for w in (
        "this that these those what when where which with from have has had will would should could shall "
        "week month year last next first day days time there their they them then than your yours about into "
        "over under some much many more most kya kaun kaise kitna kitni kitne hain wala wali wale mein karo "
        "batao dikhao please"
    ).split()
}
_DELETES: dict[str, str] = {}
for _w, _c in _CONCEPTS.items():
    if len(_w) >= 5 and not _w.startswith("<"):
        for _i in range(len(_w)):
            _DELETES.setdefault(_w[:_i] + _w[_i + 1 :], _c)


@lru_cache(maxsize=8192)
def concept(token: str) -> str | None:
    found = _CONCEPTS.get(token)
    if found or len(token) < 4 or token.startswith("<") or token in _COMMON:
        return found
    if token in _DELETES:  # a letter missing: "prfit"
        return _DELETES[token]
    for i in range(len(token)):
        shorter = token[:i] + token[i + 1 :]
        if len(shorter) >= 4 and shorter in _CONCEPTS:  # a letter too many: "phonee"
            return _CONCEPTS[shorter]
        if len(token) >= 5 and shorter in _DELETES:  # a letter changed: "stoxk"
            return _DELETES[shorter]
    for i in range(len(token) - 1):  # two letters swapped: "prfoit"
        swapped = token[:i] + token[i + 1] + token[i] + token[i + 2 :]
        if swapped in _CONCEPTS:
            return _CONCEPTS[swapped]
    return None


def features(text: str) -> list[str]:
    toks = keys(text)
    concepts = [c for c in map(concept, toks) if c]
    out = [f"k:{c}" for c in concepts]
    out += [f"kk:{a}_{b}" for a, b in zip(concepts, concepts[1:], strict=False)]
    out += ["has:" + t for t in toks if t.startswith("<")]
    for i, t in enumerate(toks):
        out.append("w:" + t)
        if i + 1 < len(toks):
            out.append("b:" + t + "_" + toks[i + 1])
        if not t.startswith("<"):
            padded = f"^{t}$"
            for n in (3, 4, 5):
                out.extend("c:" + padded[j : j + n] for j in range(max(1, len(padded) - n + 1)))
    return out


_SYNONYMS: dict[str, list[str]] = {}
for _w, _c in _CONCEPTS.items():
    if not _w.startswith("<"):
        _SYNONYMS.setdefault(_c, []).append(_w)


def augment(examples: list[data.Example], seed: int = 7, share: float = 0.6) -> list[data.Example]:
    """Copies with concept words swapped for synonyms (owe -> baaki -> dues), so the model
    learns to lean on concepts rather than one exact word."""
    import random

    rng = random.Random(seed)
    out = []
    for e in examples:
        if rng.random() > share:
            continue
        toks = e.text.split()
        changed = False
        for i, t in enumerate(toks):
            c = _CONCEPTS.get(key(t.strip("?.,!")))
            if c and c not in ("when", "who", "much", "today") and rng.random() < 0.7:
                toks[i] = rng.choice(_SYNONYMS[c])
                changed = True
        if changed:
            out.append(data.Example(" ".join(toks), e.intent, e.args, e.style, e.template_id + "+aug"))
    return out


@dataclass(frozen=True)
class Prediction:
    intent: str
    confidence: float  # softmax probability of the best intent
    margin: float  # best minus second best probability
    ranked: list[tuple[str, float]]


class IntentClassifier:
    def __init__(self, vocab: dict[str, int], intents: list[str], weights: np.ndarray, bias: np.ndarray):
        self.vocab, self.intents, self.W, self.b = vocab, intents, weights, bias

    # Training --------------------------------------------------------------------------------
    @classmethod
    def train(
        cls,
        examples: list[data.Example] | None = None,
        epochs: int = 12,
        seed: int = 7,
        lr: float = 0.5,
        l2: float = 1e-5,
    ) -> IntentClassifier:
        examples = examples if examples is not None else data.split(data.generate(per_template=30))[0]
        examples = list(examples) + augment(examples, seed=seed)
        intents = sorted({e.intent for e in examples})
        label = {name: i for i, name in enumerate(intents)}
        rows = [features(e.text) for e in examples]
        vocab: dict[str, int] = {}
        for feats in rows:
            for f in feats:
                vocab.setdefault(f, len(vocab))
        idx = [np.fromiter({vocab[f] for f in feats}, dtype=np.int64) for feats in rows]
        y = np.array([label[e.intent] for e in examples])
        d, k = len(vocab), len(intents)
        W = np.zeros((d, k), dtype=np.float32)
        b = np.zeros(k, dtype=np.float32)
        G = np.full((d, k), 1e-6, dtype=np.float32)  # AdaGrad accumulators
        Gb = np.full(k, 1e-6, dtype=np.float32)
        rng = np.random.default_rng(seed)
        order = np.arange(len(idx))
        batch = 128
        for _epoch in range(epochs):
            rng.shuffle(order)
            for start in range(0, len(order), batch):
                sel = order[start : start + batch]
                feats = [idx[i] for i in sel]
                scale = [1.0 / np.sqrt(max(1, len(f))) for f in feats]
                logits = np.stack([W[f].sum(axis=0) * s for f, s in zip(feats, scale, strict=True)]) + b
                logits -= logits.max(axis=1, keepdims=True)
                p = np.exp(logits)
                p /= p.sum(axis=1, keepdims=True)
                p[np.arange(len(sel)), y[sel]] -= 1.0  # gradient of cross-entropy w.r.t. logits
                p /= len(sel)
                flat = np.concatenate(feats)
                grads = np.repeat(p * np.array(scale, dtype=np.float32)[:, None], [len(f) for f in feats], axis=0)
                gW = np.zeros((len(flat), k), dtype=np.float32)
                gW[:] = grads
                uniq, inverse = np.unique(flat, return_inverse=True)
                agg = np.zeros((len(uniq), k), dtype=np.float32)
                np.add.at(agg, inverse, gW)
                agg += l2 * W[uniq]
                G[uniq] += agg * agg
                W[uniq] -= lr * agg / np.sqrt(G[uniq])
                gb = p.sum(axis=0)
                Gb += gb * gb
                b -= lr * gb / np.sqrt(Gb)
        return cls(vocab, intents, W, b)

    # Use ----------------------------------------------------------------------------------
    def predict(self, text: str, top: int = 3) -> Prediction:
        ids = sorted({self.vocab[f] for f in features(text) if f in self.vocab})
        if not ids:
            logits = self.b.copy()
        else:
            logits = self.W[ids].sum(axis=0) / np.sqrt(len(ids)) + self.b
        logits = logits - logits.max()
        p = np.exp(logits)
        p /= p.sum()
        order = np.argsort(-p)
        ranked = [(self.intents[i], float(p[i])) for i in order[:top]]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        return Prediction(ranked[0][0], ranked[0][1], ranked[0][1] - second, ranked)

    # Cache ---------------------------------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        vocab = np.array(sorted(self.vocab, key=self.vocab.get), dtype=object)
        np.savez_compressed(
            path,
            W=self.W,
            b=self.b,
            vocab=vocab,
            intents=np.array(self.intents, dtype=object),
            version=np.array(data.CORPUS_VERSION),
        )

    @classmethod
    def load(cls, path: Path) -> IntentClassifier | None:
        try:
            z = np.load(path, allow_pickle=True)
            if str(z["version"]) != data.CORPUS_VERSION:
                return None
            vocab = {f: i for i, f in enumerate(z["vocab"].tolist())}
            return cls(vocab, z["intents"].tolist(), z["W"], z["b"])
        except (OSError, KeyError, ValueError):
            return None

    @classmethod
    def cached(cls, folder: Path | None) -> IntentClassifier:
        """Load the cached model for this corpus version, or train and cache it."""
        path = folder / f"system1-{data.CORPUS_VERSION}.npz" if folder else None
        if path is not None and path.exists():
            model = cls.load(path)
            if model is not None:
                return model
        t = time.perf_counter()
        model = cls.train()
        log.info("assistant: System 1 trained in %.1fs (%d features)", time.perf_counter() - t, len(model.vocab))
        if path is not None:
            try:
                model.save(path)
            except OSError:
                log.exception("could not cache the System 1 model")
        return model


def evaluate(model: IntentClassifier, examples: list[data.Example]) -> dict:
    """Accuracy overall, per style and per intent (for tools/assistant/eval.py and tests)."""
    total = right = 0
    by_style: dict[str, list[int]] = {}
    by_intent: dict[str, list[int]] = {}
    for e in examples:
        ok = int(model.predict(e.text).intent == e.intent)
        total += 1
        right += ok
        by_style.setdefault(e.style, [0, 0])
        by_style[e.style][0] += ok
        by_style[e.style][1] += 1
        by_intent.setdefault(e.intent, [0, 0])
        by_intent[e.intent][0] += ok
        by_intent[e.intent][1] += 1
    return {
        "accuracy": right / max(1, total),
        "n": total,
        "style": {s: r / n for s, (r, n) in by_style.items()},
        "intent": {i: r / n for i, (r, n) in by_intent.items()},
    }
