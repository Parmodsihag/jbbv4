"""System 2: an optional small language model for the questions System 1 is unsure about.

Off until a trained model is installed (Settings -> Assistant -> Install model: the zip the
Kaggle cell produces) and ``llama-cpp-python`` is present.  Without either the assistant
simply asks "did you mean ..." instead - nothing else changes.

Sized for the shop PC (Celeron, 4 GB): a ~200-300 MB GGUF file, memory-mapped, loaded only
when first needed and dropped again after 10 idle minutes.  The model sees the question with
names already replaced by ``<C1>`` / ``<I1>`` and must answer with one ``call:tool{...}``; only
the tool name is used - periods, names and numbers always come from the deterministic parser.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hth.assistant import data

log = logging.getLogger(__name__)

IDLE_UNLOAD_SECONDS = 600
MANIFEST = "manifest.json"
_PREFERRED = ("q4_k_m", "q5_k_m", "q8_0", "f16")


@dataclass(frozen=True)
class ModelInfo:
    path: Path
    manifest: dict

    @property
    def size_mb(self) -> float:
        try:
            return self.path.stat().st_size / 1e6
        except OSError:
            return 0.0


def models_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "models"


def find_model(folder: Path) -> ModelInfo | None:
    """The best installed GGUF file (smallest good quantisation first) and its manifest."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    if manifest.get("prompt_version", data.PROMPT_VERSION) != data.PROMPT_VERSION:
        return None
    files = sorted(folder.glob("*.gguf"))
    for kind in _PREFERRED:
        for f in files:
            if kind in f.name.lower():
                return ModelInfo(f, manifest)
    return ModelInfo(files[0], manifest) if files else None


def backend_available() -> bool:
    try:
        import llama_cpp  # noqa: F401
    except Exception:  # noqa: BLE001 - ImportError, or a DLL that will not load on this CPU
        return False
    return True


Runner = Callable[[str], str]


def _llama_loader(path: Path, threads: int, ctx: int) -> Runner:
    from llama_cpp import Llama

    llm = Llama(model_path=str(path), n_ctx=ctx, n_threads=threads, n_batch=128, use_mmap=True, verbose=False)

    def run(prompt: str) -> str:
        out = llm(prompt, max_tokens=48, temperature=0.0, stop=["<end_function_call>", "<end_of_turn>"])
        return out["choices"][0]["text"] + "<end_function_call>"

    return run


class LocalModel:
    """``available()`` / ``call(masked_text) -> (intent, args) | None`` - what the assistant needs."""

    def __init__(
        self,
        folder: Path,
        threads: int | None = None,
        ctx: int = 512,
        idle_seconds: float = IDLE_UNLOAD_SECONDS,
        loader: Callable[[Path, int, int], Runner] | None = None,
    ):
        self.folder = Path(folder)
        self.threads = threads or min(4, os.cpu_count() or 2)
        self.ctx = ctx
        self.idle_seconds = idle_seconds
        self._loader = loader or _llama_loader
        self._run: Runner | None = None
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self.error: str | None = None
        self.last_ms: float = 0.0

    @property
    def loaded(self) -> bool:
        return self._run is not None

    def info(self) -> ModelInfo | None:
        return find_model(self.folder)

    def available(self) -> bool:
        if self.error is not None or self.info() is None:
            return False
        return self._loader is not _llama_loader or backend_available()

    def call(self, masked_text: str) -> tuple[str, dict] | None:
        with self._lock:
            try:
                if self._run is None:
                    info = self.info()
                    if info is None:
                        return None
                    t = time.perf_counter()
                    self._run = self._loader(info.path, self.threads, self.ctx)
                    log.info("assistant: System 2 loaded %s in %.1fs", info.path.name, time.perf_counter() - t)
                t = time.perf_counter()
                text = self._run(data.prompt(masked_text))
                self.last_ms = (time.perf_counter() - t) * 1000
            except Exception as exc:  # noqa: BLE001 - a broken model must not break the chat
                log.exception("System 2 failed")
                self.error = str(exc)
                self._run = None
                return None
            self._schedule_unload()
        return data.parse_call(text)

    def unload(self) -> None:
        with self._lock:
            self._run = None
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _schedule_unload(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self.idle_seconds, self.unload)
        self._timer.daemon = True
        self._timer.start()


def install_zip(zip_path: Path, data_dir: Path) -> ModelInfo:
    """Unpack the Kaggle cell's zip into ``<data>/models``: only ``*.gguf`` files and the
    manifest, by their base names (nothing can be written outside that folder)."""
    dest = models_dir(data_dir)
    with zipfile.ZipFile(zip_path) as z:
        members = {Path(n).name: n for n in z.namelist() if not n.endswith("/")}
        if MANIFEST not in members or not any(n.endswith(".gguf") for n in members):
            raise ValueError("This zip has no assistant model (manifest.json and a .gguf file).")
        manifest = json.loads(z.read(members[MANIFEST]).decode("utf-8"))
        if manifest.get("prompt_version") != data.PROMPT_VERSION:
            raise ValueError("This model was trained for a different app version - train it again with the new cell.")
        tmp = dest.with_name("models.new")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for name, member in members.items():
            if name == MANIFEST or name.endswith(".gguf"):
                with z.open(member) as src, open(tmp / name, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
    if dest.exists():
        shutil.rmtree(dest.with_name("models.old"), ignore_errors=True)
        dest.rename(dest.with_name("models.old"))
    tmp.rename(dest)
    shutil.rmtree(dest.with_name("models.old"), ignore_errors=True)
    info = find_model(dest)
    if info is None:
        raise ValueError("The model could not be installed.")
    return info
