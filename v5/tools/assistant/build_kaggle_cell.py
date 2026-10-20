"""Write ``tools/assistant/kaggle_train_cell.py``: the training cell with the app's question
generator and System 1 (``hth/assistant/spoken.py``, ``data.py``, ``normalize.py``, ``system1.py``) embedded, so
Kaggle trains on exactly the questions the app learns from and can compare the model with System 1.

    python tools/assistant/build_kaggle_cell.py

Run it again whenever those files change (a test checks the cell is up to date).
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = HERE / "kaggle_cell_template.py"
SOURCES = [ROOT / "hth" / "assistant" / name for name in ("spoken.py", "data.py", "normalize.py", "system1.py")]
CELL = HERE / "kaggle_train_cell.py"
MARKER = "FILES = None  # @@FILES@@"


def build() -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    assert MARKER in template, "marker missing from the template"
    parts = []
    for path in SOURCES:
        lines = "\n".join(f"            {line!r}," for line in path.read_text(encoding="utf-8").split("\n"))
        parts.append(f"    {path.name!r}: '\\n'.join(\n        [\n{lines}\n        ]\n    ),")
    embedded = "FILES = {  # hth/assistant/*, verbatim\n" + "\n".join(parts) + "\n}"
    return template.replace(MARKER, embedded)


def main() -> int:
    CELL.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {CELL.relative_to(ROOT)} ({CELL.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
