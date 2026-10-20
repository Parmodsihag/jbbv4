"""Updates: find a newer version of the app on GitHub and install it from inside the app.

Two kinds of installation:

* **A plain copy of the app folder** (the shop PC).  Every file is compared with the GitHub
  branch by its git blob hash, so only the files that changed are downloaded - each one
  checked against GitHub's hash - into ``<data>/updates/staged``.  Nothing in the app
  changes until the next start: then, before the app loads, every file about to be replaced
  is saved to a backup zip, the new files go in, and if anything fails the backup is put
  back.  "Undo last update" stages that backup the same way.  New Python packages named in
  ``requirements.txt`` are installed while downloading, before anything is staged.
* **A git checkout** (a developer's PC): ``git pull --ff-only``, refused when there are local
  changes.  A packaged (PyInstaller) build cannot update itself.

Standard library only: ``apply_pending`` runs at start-up before the rest of the app is
imported.  The data folder (``C:\\JBB\\v5``) is never touched; database changes in a new
version are made by its own migrations, which back the database up first.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_REPO = "Parmodsihag/jbbv4"
DEFAULT_BRANCH = "v5"
DEFAULT_FOLDER = "v5"  # the app's folder inside the repository
MANIFEST = ".hth-files.json"  # in the app folder: the files the last update installed
_SKIP = ("__pycache__/", ".pytest_cache/", ".ruff_cache/", ".git/")
_VERSION = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")

Fetch = Callable[[str], bytes]


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Source:
    repo: str = DEFAULT_REPO
    branch: str = DEFAULT_BRANCH
    folder: str = DEFAULT_FOLDER

    @property
    def web(self) -> str:
        return f"github.com/{self.repo} ({self.branch})"


@dataclass
class Available:
    current: str
    version: str
    mode: str  # copy | git
    commit: str = ""
    notes: str = ""
    changed: list[tuple[str, str, int]] = field(default_factory=list)  # (path, blob sha, size)
    removed: list[str] = field(default_factory=list)
    every: list[str] = field(default_factory=list)  # every file of the new version
    requirements_changed: bool = False
    behind: int = 0  # git: commits to pull

    @property
    def newer(self) -> bool:
        return parse_version(self.version) > parse_version(self.current)

    @property
    def download_mb(self) -> float:
        return sum(size for _p, _s, size in self.changed) / 1e6


# --- small helpers -----------------------------------------------------------------------------
def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", text or "")[:4]) or (0,)


def version_in(init_py: str) -> str | None:
    m = _VERSION.search(init_py or "")
    return m.group(1) if m else None


def blob_sha(data: bytes) -> str:
    """Git's hash of a file's content (what GitHub's tree lists for it)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def app_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def current_version(root: Path | None = None) -> str:
    try:
        return version_in(((root or app_dir()) / "hth" / "__init__.py").read_text(encoding="utf-8")) or "0"
    except OSError:
        return "0"


def git_root(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return None


def http_get(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "HighTableHoldings-updater", "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https to GitHub only
        return resp.read()


def changelog_since(changelog: str, current: str) -> str:
    """The CHANGELOG sections newer than ``current`` ("## 5.4.0 — date" headings)."""
    out, keep = [], False
    for line in changelog.splitlines():
        m = re.match(r"##\s+(\d+(?:\.\d+)+)", line)
        if m:
            keep = parse_version(m.group(1)) > parse_version(current)
        if keep:
            out.append(line)
    return "\n".join(out).strip()


def _no_window() -> dict:
    return {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}  # CREATE_NO_WINDOW


# --- checking and downloading ----------------------------------------------------------------
class Updater:
    def __init__(self, data_dir: Path, source: Source | None = None, fetch: Fetch = http_get, root: Path | None = None):
        self.data_dir = Path(data_dir)
        self.source = source or Source()
        self.fetch = fetch
        self.root = Path(root) if root else app_dir()
        self._git = git_root(self.root)

    @property
    def mode(self) -> str:
        if getattr(sys, "frozen", False):
            return "frozen"
        return "git" if self._git is not None else "copy"

    @property
    def staging(self) -> Path:
        return self.data_dir / "updates" / "staged"

    def _api(self, path: str):
        return json.loads(self.fetch(f"https://api.github.com/repos/{self.source.repo}/{path}").decode("utf-8"))

    def _raw(self, commit: str, rel: str) -> bytes:
        return self.fetch(f"https://raw.githubusercontent.com/{self.source.repo}/{commit}/{self._remote(rel)}")

    def _remote(self, rel: str) -> str:
        return f"{self.source.folder}/{rel}" if self.source.folder else rel

    def check(self) -> Available:
        if self.mode == "frozen":
            raise UpdateError("This packaged copy cannot update itself - install the new version.")
        if self.mode == "git":
            return self._check_git()
        current = current_version(self.root)
        try:
            commit = self._api(f"commits/{self.source.branch}")["sha"]
            tree = self._api(f"git/trees/{commit}?recursive=1")
        except Exception as exc:  # noqa: BLE001 - offline, wrong name, GitHub limits
            raise UpdateError(f"Could not reach GitHub ({self.source.web}): {exc}") from exc
        if tree.get("truncated"):
            raise UpdateError("GitHub sent only part of the file list - try again later.")
        prefix = self.source.folder.rstrip("/") + "/" if self.source.folder else ""
        remote = {
            e["path"][len(prefix) :]: (e["sha"], int(e.get("size", 0)))
            for e in tree.get("tree", [])
            if e.get("type") == "blob" and e["path"].startswith(prefix)
        }
        if "hth/__init__.py" not in remote:
            raise UpdateError(f"{self.source.web} has no app in folder '{self.source.folder}'.")
        version = version_in(self._raw(commit, "hth/__init__.py").decode("utf-8")) or "0"
        avail = Available(current, version, "copy", commit, every=sorted(remote))
        if not avail.newer:
            return avail
        for rel, (sha, size) in sorted(remote.items()):
            if not self._same(rel, sha):
                avail.changed.append((rel, sha, size))
        old = self._manifest()
        avail.removed = sorted(p for p in old if p not in remote and (self.root / p).is_file())
        avail.requirements_changed = any(p == "requirements.txt" for p, _s, _z in avail.changed)
        try:
            avail.notes = changelog_since(self._raw(commit, "CHANGELOG.md").decode("utf-8"), current)
        except Exception:  # noqa: BLE001 - notes are a nicety
            avail.notes = ""
        return avail

    def _same(self, rel: str, sha: str) -> bool:
        path = self.root / rel
        try:
            data = path.read_bytes()
        except OSError:
            return False
        if blob_sha(data) == sha:
            return True
        # a copy made from a Windows git checkout has CRLF line ends; the repository has LF
        return b"\r\n" in data and blob_sha(data.replace(b"\r\n", b"\n")) == sha

    def _manifest(self) -> list[str]:
        try:
            return list(json.loads((self.root / MANIFEST).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return []

    def stage(self, avail: Available, progress: Callable[[int, int, str], None] | None = None) -> Path:
        """Download the changed files, check each one, install new packages, and leave the update
        ready for the next start.  Raises ``UpdateError``; on failure nothing is staged."""
        if avail.mode != "copy":
            raise UpdateError("Only a plain copy of the app is updated this way.")
        staging = self.staging
        shutil.rmtree(staging, ignore_errors=True)
        files = staging / "files"
        files.mkdir(parents=True)
        try:
            for k, (rel, sha, _size) in enumerate(avail.changed, start=1):
                if progress:
                    progress(k, len(avail.changed), rel)
                data = self._raw(avail.commit, rel)
                if blob_sha(data) != sha:
                    raise UpdateError(f"{rel} did not download correctly - nothing was changed.")
                out = files / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
            if avail.requirements_changed:
                install_packages(files / "requirements.txt")
            manifest = {
                "kind": "update",
                "from": avail.current,
                "to": avail.version,
                "commit": avail.commit,
                "files": [p for p, _s, _z in avail.changed],
                "removed": avail.removed,
                "every": avail.every,
                "staged": dt.datetime.now().isoformat(timespec="seconds"),
            }
            tmp = staging / "manifest.tmp"
            tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
            os.replace(tmp, staging / "manifest.json")  # its presence means: complete
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return staging

    # git checkouts --------------------------------------------------------------------------
    def _git_cmd(self, *args: str, timeout: float = 120) -> str:
        try:
            done = subprocess.run(
                ["git", "-C", str(self._git), *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                **_no_window(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpdateError(f"git: {exc}") from exc
        if done.returncode != 0:
            raise UpdateError(f"git {' '.join(args)}: {(done.stderr or done.stdout).strip()[-300:]}")
        return done.stdout

    def _folder_in_repo(self) -> str:
        return self.root.relative_to(self._git).as_posix()

    def _check_git(self) -> Available:
        current = current_version(self.root)
        branch = self.source.branch
        self._git_cmd("fetch", "origin", branch)
        behind = int(self._git_cmd("rev-list", "--count", f"HEAD..origin/{branch}").strip() or 0)
        folder = self._folder_in_repo()
        prefix = "" if folder == "." else folder + "/"
        remote_init = self._git_cmd("show", f"origin/{branch}:{prefix}hth/__init__.py")
        avail = Available(current, version_in(remote_init) or "0", "git", behind=behind)
        if avail.newer:
            try:
                avail.notes = changelog_since(self._git_cmd("show", f"origin/{branch}:{prefix}CHANGELOG.md"), current)
            except UpdateError:
                pass
        return avail

    def pull(self) -> str:
        if self._git_cmd("status", "--porcelain", "--untracked-files=no").strip():
            raise UpdateError("This copy has changes that are not committed - commit or put them aside first.")
        return self._git_cmd("pull", "--ff-only", "origin", self.source.branch)


def install_packages(requirements: Path) -> None:
    """``pip install -r`` for an update's new requirements (before anything is staged)."""
    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe" and (python.parent / "python.exe").exists():
        python = python.parent / "python.exe"
    try:
        done = subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(requirements)],
            capture_output=True,
            text=True,
            timeout=1800,
            **_no_window(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"Could not install the new packages: {exc}") from exc
    if done.returncode != 0:
        raise UpdateError("Could not install the new packages:\n" + (done.stderr or done.stdout).strip()[-600:])


# --- applying at start-up ------------------------------------------------------------------
def pending(data_dir: Path) -> dict | None:
    try:
        return json.loads((Path(data_dir) / "updates" / "staged" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def last_result(data_dir: Path) -> dict | None:
    try:
        return json.loads((Path(data_dir) / "updates" / "last.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def backups(data_dir: Path) -> list[Path]:
    return sorted((Path(data_dir) / "updates").glob("before-*.zip"), reverse=True)


def _wait_for(pid: int, timeout: float = 30.0) -> None:
    """Wait until the copy that asked for the restart has closed (its files and database)."""
    if sys.platform.startswith("win"):
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if handle:
            ctypes.windll.kernel32.WaitForSingleObject(handle, int(timeout * 1000))
            ctypes.windll.kernel32.CloseHandle(handle)
        return
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)


def wait_for_previous() -> None:
    """Started by "Restart now": wait for the old copy to close before going on."""
    wait = os.environ.pop("HTH_WAIT_PID", "")
    if wait.isdigit():
        _wait_for(int(wait))


def apply_pending(data_dir: Path, root: Path | None = None) -> dict | None:
    """Put a staged update (or undo) into the app folder.  Runs at start-up before the app is
    imported; returns the result (also saved as ``updates/last.json``) or None if nothing was staged."""
    data_dir, root = Path(data_dir), Path(root) if root else app_dir()
    manifest = pending(data_dir)
    if manifest is None:
        return None
    wait_for_previous()
    staging = data_dir / "updates" / "staged"
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = data_dir / "updates" / f"before-{manifest.get('to', 'x')}-from-{current_version(root)}-{stamp}.zip"
    touched = [p for p in manifest.get("files", []) + manifest.get("removed", []) if _safe(p)]
    created: list[str] = []
    result = {"ok": False, "from": current_version(root), "to": manifest.get("to"), "kind": manifest.get("kind")}
    try:
        with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in touched:
                if (root / rel).is_file():
                    z.write(root / rel, rel)
                else:
                    created.append(rel)
            old_manifest = root / MANIFEST
            z.writestr("_update.json", json.dumps({"created": created, "had_manifest": old_manifest.exists()}))
            if old_manifest.exists():
                z.write(old_manifest, MANIFEST)
        for rel in manifest.get("files", []):
            if not _safe(rel):
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".hth-new")
            shutil.copyfile(staging / "files" / rel, tmp)
            os.replace(tmp, target)
        for rel in manifest.get("removed", []):
            if _safe(rel) and (root / rel).is_file():
                (root / rel).unlink()
        if manifest.get("every"):
            (root / MANIFEST).write_text(json.dumps(manifest["every"]), encoding="utf-8")
        result.update(ok=True, backup=str(backup))
    except Exception as exc:  # noqa: BLE001 - put everything back
        result["error"] = str(exc)
        _restore(backup, root)
    result["when"] = dt.datetime.now().isoformat(timespec="seconds")
    shutil.rmtree(staging, ignore_errors=True)
    (data_dir / "updates" / "last.json").write_text(json.dumps(result), encoding="utf-8")
    _log(data_dir, result)
    return result


def _safe(rel: str) -> bool:
    """Only plain relative paths inside the app folder: no .., no root ("/x" is the drive's root on
    Windows), no drive, no backslashes, nothing in git's or Python's own folders."""
    from pathlib import PurePosixPath, PureWindowsPath

    if not rel or "\\" in rel or ":" in rel or rel.startswith("/") or PureWindowsPath(rel).anchor:
        return False
    parts = PurePosixPath(rel).parts
    return ".." not in parts and not rel.startswith(_SKIP) and "__pycache__" not in parts


def _restore(backup: Path, root: Path) -> None:
    try:
        with zipfile.ZipFile(backup) as z:
            info = json.loads(z.read("_update.json"))
            for name in z.namelist():
                if name != "_update.json" and _safe(name):
                    (root / name).parent.mkdir(parents=True, exist_ok=True)
                    (root / name).write_bytes(z.read(name))
            for rel in info.get("created", []):
                if _safe(rel) and (root / rel).is_file():
                    (root / rel).unlink()
            if not info.get("had_manifest") and (root / MANIFEST).exists():
                (root / MANIFEST).unlink()
    except Exception:  # noqa: BLE001
        log.exception("could not restore %s", backup)


def stage_undo(data_dir: Path, backup: Path) -> None:
    """Stage the files saved before an update, so the next start puts them back."""
    staging = Path(data_dir) / "updates" / "staged"
    shutil.rmtree(staging, ignore_errors=True)
    (staging / "files").mkdir(parents=True)
    with zipfile.ZipFile(backup) as z:
        info = json.loads(z.read("_update.json"))
        files = [n for n in z.namelist() if n != "_update.json" and _safe(n)]
        for name in files:
            out = staging / "files" / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(z.read(name))
    manifest = {"kind": "undo", "to": "previous", "files": files, "removed": info.get("created", []), "every": []}
    (staging / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _log(data_dir: Path, result: dict) -> None:
    try:
        logs = data_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / "updates.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
    except OSError:
        pass


def relaunch(root: Path | None = None, wait_for_me: bool = True) -> None:
    """Start the app again (``run.py``), detached; the new copy waits for this one to close."""
    root = root or app_dir()
    env = dict(os.environ)
    if wait_for_me:
        env["HTH_WAIT_PID"] = str(os.getpid())
    else:
        env.pop("HTH_WAIT_PID", None)
    flags = 0x00000008 | 0x00000200 if sys.platform.startswith("win") else 0  # DETACHED, NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, str(root / "run.py")], cwd=str(root), env=env, creationflags=flags)  # noqa: S603
