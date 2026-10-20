"""Measure the assistant's intent recognition on questions it was never trained on.

    python tools/assistant/eval.py            # System 1 alone and with the assistant's routing
    python tools/assistant/eval.py --errors   # also print the questions it gets wrong

The test set holds out whole templates (not just reworded copies of training questions), so
the numbers say how well it copes with new phrasings.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hth.assistant import data  # noqa: E402
from hth.assistant.core import route  # noqa: E402
from hth.assistant.system1 import IntentClassifier, evaluate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--errors", action="store_true", help="print misclassified questions")
    ap.add_argument("--per-template", type=int, default=30)
    ap.add_argument("--folds", type=int, default=3, help="different held-out template sets to average over")
    args = ap.parse_args()

    examples = data.generate(per_template=args.per_template)
    folds = []
    for fold in range(args.folds):
        train, test = data.split(examples, seed=7 + fold)
        t = time.perf_counter()
        model = IntentClassifier.train(train)
        took = time.perf_counter() - t
        raw = evaluate(model, test)
        print(f"fold {fold + 1}: trained on {len(train)} in {took:.1f}s · System 1 alone {raw['accuracy']:.3f}")
        folds.append((model, test))
    today = dt.date(2026, 10, 20)
    right = total = 0
    by_style: Counter = Counter()
    n_style: Counter = Counter()
    by_intent: Counter = Counter()
    n_intent: Counter = Counter()
    confusions: Counter = Counter()
    errors = []
    t = time.perf_counter()
    for model, e in ((m, e) for m, test in folds for e in test):
        total += 1
        got = route(model, e.text, today)[0][0]
        ok = got == e.intent
        right += ok
        by_style[e.style] += ok
        n_style[e.style] += 1
        by_intent[e.intent] += ok
        n_intent[e.intent] += 1
        if not ok:
            confusions[(e.intent, got)] += 1
            errors.append((e.intent, got, e.text))
    per_question = (time.perf_counter() - t) / max(1, total) * 1000
    style = {s: by_style[s] / n_style[s] for s in n_style}
    print(f"with routing:  {right / total:.3f}  {_styles(style)}  ({total} questions, {per_question:.1f} ms each)")
    worst = sorted(n_intent, key=lambda i: by_intent[i] / n_intent[i])[:8]
    print("weakest:       " + ", ".join(f"{i} {by_intent[i] / n_intent[i]:.2f}" for i in worst))
    print("confusions:    " + ", ".join(f"{a}->{b} {n}" for (a, b), n in confusions.most_common(8)))
    if args.errors:
        for want, got, text in sorted(errors):
            print(f"  {want:18} got {got:18} {text}")
    return 0


def _styles(style: dict) -> str:
    names = {"en": "English", "hi": "Hindi", "hl": "Hinglish", "sp": "spoken"}
    return " · ".join(f"{names.get(s, s)} {v:.3f}" for s, v in sorted(style.items()))


if __name__ == "__main__":
    raise SystemExit(main())
