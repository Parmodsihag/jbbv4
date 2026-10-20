"""System 2: an optional small language model for the questions System 1 is unsure about.

Off until a trained model is installed (Settings -> Assistant -> Install model: the zip the
Kaggle cell produces) and ``llama-cpp-python`` is present.  Without either the assistant
simply asks "did you mean ..." instead - nothing else changes.

Sized for the shop PC (Celeron, 4 GB): a ~250 MB GGUF file, memory-mapped in a separate
process (so a crash there cannot close the program), started only when first needed and
stopped again after 10 idle minutes.  The model sees the question with names already replaced
by ``<C1>`` / ``<I1>`` and must answer with one ``call:tool{...}``; only the tool name is used,
and only when it is one of System 1's own three best guesses - periods, names and numbers
always come from the deterministic parser.
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
LOAD_TIMEOUT = 180  # a Celeron reading 250 MB from a slow disk
ANSWER_TIMEOUT = 60


def _llama_factory(path: str, threads: int, ctx: int) -> Runner:
    """Runs inside the model process."""
    from llama_cpp import Llama

    llm = Llama(model_path=path, n_ctx=ctx, n_threads=threads, n_batch=128, use_mmap=True, verbose=False)

    def run(prompt: str) -> str:
        out = llm(prompt, max_tokens=48, temperature=0.0, stop=["<end_function_call>", "<end_of_turn>"])
        return out["choices"][0]["text"] + "<end_function_call>"

    return run


def _worker(path: str, threads: int, ctx: int, conn, factory) -> None:
    try:
        run = factory(path, threads, ctx)
    except Exception as exc:  # noqa: BLE001 - reported to the app, which switches System 2 off
        conn.send(f"could not load the model: {exc}")
        return
    conn.send("ready")
    while True:
        try:
            prompt = conn.recv()
        except (EOFError, OSError):
            return
        try:
            conn.send(run(prompt))
        except Exception as exc:  # noqa: BLE001
            conn.send(("error", str(exc)))


class ProcessRunner:
    """The model in its own process.  Many Celerons lack the AVX instructions a llama.cpp build
    may use; there that ends in an "illegal instruction" no Python code can catch.  In a separate
    process it only ends that process - the shop program stays open and System 2 turns itself
    off.  Closing the process also frees the model's memory at once."""

    def __init__(self, path: Path, threads: int, ctx: int, factory=_llama_factory, timeout: float = ANSWER_TIMEOUT):
        import multiprocessing

        mp = multiprocessing.get_context("spawn")
        self._conn, child = mp.Pipe()
        self._proc = mp.Process(target=_worker, args=(str(path), threads, ctx, child, factory), daemon=True)
        self._proc.start()
        child.close()
        self.timeout = timeout
        status = self._receive(LOAD_TIMEOUT)
        if status != "ready":
            self.close()
            raise RuntimeError(status)

    def __call__(self, prompt: str) -> str:
        try:
            self._conn.send(prompt)
        except OSError as exc:
            self.close()
            raise RuntimeError("the model process has stopped") from exc
        reply = self._receive(self.timeout)
        if isinstance(reply, tuple):
            raise RuntimeError(reply[1])
        return reply

    def _receive(self, timeout: float):
        try:
            if not self._conn.poll(timeout):
                self.close()
                raise RuntimeError("the model did not answer in time")
            return self._conn.recv()
        except (EOFError, OSError) as exc:
            self._proc.join(2)
            code = self._proc.exitcode
            self.close()
            raise RuntimeError(f"the model process stopped (exit code {code}) - this PC may not support it") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except OSError:
            pass
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(5)


def _llama_loader(path: Path, threads: int, ctx: int) -> Runner:
    return ProcessRunner(path, threads, ctx)


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
                self._close_runner()
                return None
            self._schedule_unload()
        return data.parse_call(text)

    def unload(self) -> None:
        with self._lock:
            self._close_runner()
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _close_runner(self) -> None:
        run, self._run = self._run, None
        close = getattr(run, "close", None)
        if close is not None:
            close()

    def _schedule_unload(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self.idle_seconds, self.unload)
        self._timer.daemon = True
        self._timer.start()


def _best_gguf(names) -> str | None:
    ggufs = sorted(n for n in names if n.lower().endswith(".gguf"))
    for kind in _PREFERRED:
        for n in ggufs:
            if kind in n.lower():
                return n
    return ggufs[0] if ggufs else None


def install_zip(zip_path: Path, data_dir: Path) -> ModelInfo:
    """Unpack the Kaggle cell's zip into ``<data>/models``: the manifest and the one model file
    the app would use (the smallest good quantisation), by their base names - nothing can be
    written outside that folder."""
    dest = models_dir(data_dir)
    with zipfile.ZipFile(zip_path) as z:
        members = {Path(n).name: n for n in z.namelist() if not n.endswith("/")}
        model = _best_gguf(members)
        if MANIFEST not in members or model is None:
            raise ValueError("This zip has no assistant model (manifest.json and a .gguf file).")
        manifest = json.loads(z.read(members[MANIFEST]).decode("utf-8"))
        if manifest.get("prompt_version") != data.PROMPT_VERSION:
            raise ValueError("This model was trained for a different app version - train it again with the new cell.")
        tmp = dest.with_name("models.new")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for name in (MANIFEST, model):
            with z.open(members[name]) as src, open(tmp / name, "wb") as out:
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
