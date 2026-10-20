"""Updates from GitHub (with a fake GitHub) and the voice model shipped with the app."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from hth.services import updates
from hth.services.updates import Source, UpdateError, Updater, blob_sha


class FakeGitHub:
    """The three things the updater asks GitHub: the branch's commit, its file tree, raw files."""

    def __init__(self, files: dict[str, bytes], repo="me/shop", branch="v5", folder="v5"):
        self.files, self.repo, self.branch, self.folder = files, repo, branch, folder
        self.commit = "c0ffee"
        self.asked: list[str] = []
        self.tamper: set[str] = set()

    def __call__(self, url: str) -> bytes:
        self.asked.append(url)
        api = f"https://api.github.com/repos/{self.repo}/"
        raw = f"https://raw.githubusercontent.com/{self.repo}/{self.commit}/{self.folder}/"
        if url == api + f"commits/{self.branch}":
            return json.dumps({"sha": self.commit}).encode()
        if url == api + f"git/trees/{self.commit}?recursive=1":
            tree = [
                {"path": f"{self.folder}/{p}", "type": "blob", "sha": blob_sha(d), "size": len(d)}
                for p, d in self.files.items()
            ]
            tree.append({"path": "other/readme.md", "type": "blob", "sha": "x", "size": 1})
            return json.dumps({"tree": tree, "truncated": False}).encode()
        if url.startswith(raw):
            rel = url[len(raw) :]
            return b"tampered" if rel in self.tamper else self.files[rel]
        raise OSError(f"404 {url}")


def _app(root: Path, version: str, extra: dict[str, bytes] | None = None) -> Path:
    files = {
        "hth/__init__.py": f'__version__ = "{version}"\n'.encode(),
        "hth/core.py": b"OLD = 1\n",
        "run.py": b"print('run')\n",
        "CHANGELOG.md": b"# Changelog\n\n## 5.3.1\n- old\n",
    }
    files.update(extra or {})
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    return root


def _remote(version="5.4.0") -> dict[str, bytes]:
    return {
        "hth/__init__.py": f'__version__ = "{version}"\n'.encode(),
        "hth/core.py": b"NEW = 2\n",
        "hth/added.py": b"ADDED = 3\n",
        "run.py": b"print('run')\n",
        "CHANGELOG.md": b"# Changelog\n\n## 5.4.0 - today\n- voice ships with the app\n\n## 5.3.1\n- old\n",
    }


@pytest.fixture
def setup(tmp_path):
    root = _app(tmp_path / "app", "5.3.1")
    data = tmp_path / "data"
    gh = FakeGitHub(_remote())
    return root, data, gh, Updater(data, Source("me/shop", "v5", "v5"), gh, root)


def test_versions_compare_as_numbers():
    assert updates.parse_version("5.10.0") > updates.parse_version("5.9.3")
    assert updates.version_in('__version__ = "5.4.0"\n') == "5.4.0"
    assert updates.blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"  # git hash-object


def test_check_lists_only_changed_files_and_the_notes(setup):
    root, _data, gh, up = setup
    found = up.check()
    assert found.mode == "copy" and found.newer and found.version == "5.4.0"
    assert sorted(p for p, _s, _z in found.changed) == [
        "CHANGELOG.md",
        "hth/__init__.py",
        "hth/added.py",
        "hth/core.py",
    ]
    assert "voice ships with the app" in found.notes and "old" not in found.notes
    assert "other/readme.md" not in found.every  # only the app's folder


def test_crlf_copies_are_not_downloaded_again(setup):
    root, _data, _gh, up = setup
    (root / "run.py").write_bytes(b"print('run')\r\n")  # copied from a Windows git checkout
    assert "run.py" not in [p for p, _s, _z in up.check().changed]


def test_nothing_newer_means_nothing_to_do(tmp_path):
    root = _app(tmp_path / "app", "5.4.0")
    found = Updater(tmp_path / "d", Source("me/shop"), FakeGitHub(_remote("5.4.0")), root).check()
    assert not found.newer and found.changed == []


def test_stage_then_apply_at_the_next_start(setup):
    root, data, gh, up = setup
    staging = up.stage(up.check())
    assert (staging / "manifest.json").exists()
    assert (root / "hth" / "core.py").read_bytes() == b"OLD = 1\n"  # nothing changes before the restart
    result = updates.apply_pending(data, root)
    assert result["ok"] and result["from"] == "5.3.1" and result["to"] == "5.4.0"
    assert (root / "hth" / "core.py").read_bytes() == b"NEW = 2\n"
    assert (root / "hth" / "added.py").exists()
    assert updates.current_version(root) == "5.4.0"
    assert updates.pending(data) is None and updates.last_result(data)["ok"]
    assert json.loads((root / updates.MANIFEST).read_text())  # the file list for next time
    assert updates.apply_pending(data, root) is None


def test_a_bad_download_stages_nothing(setup):
    root, data, gh, up = setup
    gh.tamper.add("hth/core.py")
    with pytest.raises(UpdateError):
        up.stage(up.check())
    assert updates.pending(data) is None and not up.staging.exists()


def test_undo_puts_the_old_files_back(setup):
    root, data, gh, up = setup
    up.stage(up.check())
    updates.apply_pending(data, root)
    backup = updates.backups(data)[0]
    updates.stage_undo(data, backup)
    result = updates.apply_pending(data, root)
    assert result["ok"] and result["kind"] == "undo"
    assert (root / "hth" / "core.py").read_bytes() == b"OLD = 1\n"
    assert not (root / "hth" / "added.py").exists()  # created by the update: removed again
    assert updates.current_version(root) == "5.3.1"


def test_a_failure_while_applying_rolls_everything_back(setup, monkeypatch):
    root, data, gh, up = setup
    up.stage(up.check())
    real = updates.os.replace
    calls = []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 3:
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(updates.os, "replace", flaky)
    result = updates.apply_pending(data, root)
    assert not result["ok"] and "disk full" in result["error"]
    assert (root / "hth" / "core.py").read_bytes() == b"OLD = 1\n"
    assert updates.current_version(root) == "5.3.1" and not (root / "hth" / "added.py").exists()


def test_files_dropped_upstream_are_removed_on_the_next_update(tmp_path):
    root = _app(tmp_path / "app", "5.3.1", {"hth/gone.py": b"x"})
    (root / updates.MANIFEST).write_text(json.dumps(["hth/__init__.py", "hth/gone.py", "run.py"]))
    (root / "my_notes.txt").write_text("mine")  # never part of the app: never touched
    data = tmp_path / "data"
    up = Updater(data, Source("me/shop"), FakeGitHub(_remote()), root)
    found = up.check()
    assert found.removed == ["hth/gone.py"]
    up.stage(found)
    updates.apply_pending(data, root)
    assert not (root / "hth" / "gone.py").exists() and (root / "my_notes.txt").exists()


def test_unsafe_paths_are_never_written(tmp_path):
    for bad in ("../evil.py", "/abs.py", "C:/x.py", "a/../../b.py", ".git/config"):
        assert not updates._safe(bad)
    assert updates._safe("hth/core.py")


def test_a_git_checkout_is_updated_with_git(tmp_path):
    (tmp_path / ".git").mkdir()
    root = _app(tmp_path / "v5", "5.3.1")
    up = Updater(tmp_path / "data", Source("me/shop"), FakeGitHub(_remote()), root)
    assert up.mode == "git"
    with pytest.raises(UpdateError):
        up.stage(updates.Available("5.3.1", "5.4.0", "git"))


def test_github_unreachable_is_a_clear_error(tmp_path):
    root = _app(tmp_path / "app", "5.3.1")

    def offline(url):
        raise OSError("no internet")

    with pytest.raises(UpdateError, match="Could not reach GitHub"):
        Updater(tmp_path / "d", Source("me/shop"), offline, root).check()


def test_update_source_preference(db):
    from hth.services.preferences import Preferences

    prefs = Preferences(db)
    assert prefs.update_source() == Source("Parmodsihag/jbbv4", "v5", "v5")
    prefs.set_update_source("someone/fork", "main")
    assert prefs.update_source().repo == "someone/fork" and prefs.update_source().branch == "main"
    with pytest.raises(ValueError):
        prefs.set_update_source("no-slash", "main")


# The voice model shipped with the app ---------------------------------------------------------
def _model_zip(path: Path, name="vosk-model-small-hi-0.22", extra=b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{name}/am/final.mdl", b"m" + extra)
        z.writestr(f"{name}/conf/model.conf", b"c")
    return path


def test_the_bundled_voice_model_is_set_up_once_and_refreshed_when_it_changes(tmp_path, monkeypatch):
    from hth.assistant import voice

    bundle = tmp_path / "bundled" / "voice"
    monkeypatch.setattr(voice, "bundled_dir", lambda: bundle)
    data = tmp_path / "data"
    assert voice.ensure_model(data) is None  # nothing shipped, nothing installed
    _model_zip(bundle / "vosk-model-small-hi-0.22.zip")
    folder = voice.ensure_model(data)
    assert folder == data / "voice" / "vosk-model-small-hi-0.22"
    assert voice.model_source(data)["from"] == "bundled"
    marker = folder / "am" / "final.mdl"
    marker.write_bytes(b"touched")
    assert voice.ensure_model(data) == folder and marker.read_bytes() == b"touched"  # same zip: kept
    _model_zip(bundle / "vosk-model-small-hi-0.22.zip", extra=b"-newer")  # an update ships a new zip
    voice.ensure_model(data)
    assert marker.read_bytes() == b"m-newer"


def test_a_model_installed_in_settings_is_left_alone(tmp_path, monkeypatch):
    from hth.assistant import voice

    bundle = tmp_path / "bundled" / "voice"
    _model_zip(bundle / "vosk-model-small-hi-0.22.zip")
    monkeypatch.setattr(voice, "bundled_dir", lambda: bundle)
    data = tmp_path / "data"
    voice.install_zip(_model_zip(tmp_path / "other.zip", name="vosk-model-hi-other"), data)
    assert voice.ensure_model(data).name == "vosk-model-hi-other"


def test_the_repository_ships_the_voice_model():
    from hth.assistant import voice

    shipped = voice.bundled_zip()
    assert shipped is not None and shipped.name == "vosk-model-small-hi-0.22.zip"
    assert shipped.stat().st_size > 40_000_000
