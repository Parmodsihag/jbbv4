"""Write ``tools/assistant/kaggle_train_cell.py``: the training cell with ``hth/assistant/data.py``
embedded, so Kaggle trains on exactly the questions the app's System 1 learns from.

    python tools/assistant/build_kaggle_cell.py

Run it again whenever ``data.py`` changes (a test checks the cell is up to date).
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = HERE / "kaggle_cell_template.py"
DATA = ROOT / "hth" / "assistant" / "data.py"
CELL = HERE / "kaggle_train_cell.py"
MARKER = "DATA_PY = None  # @@DATA_PY@@"


def build() -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    source = DATA.read_text(encoding="utf-8")
    lines = "\n".join(f"    {line!r}," for line in source.split("\n"))
    embedded = f"DATA_PY = '\\n'.join([  # hth/assistant/data.py\n{lines}\n])"
    assert MARKER in template, "marker missing from the template"
    return template.replace(MARKER, embedded)


def main() -> int:
    CELL.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {CELL.relative_to(ROOT)} ({CELL.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
