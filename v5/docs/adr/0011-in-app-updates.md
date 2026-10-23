# 0011. In-app updates from GitHub, staged and undoable

* Status: Accepted
* Date: 2026-10-21 (5.4.0)

## Context

Fixes and features were reaching the shop PC by hand: copying files or running git
commands, which the owner cannot do alone. A half-copied update can leave a program that
will not start, and then there is no screen left to fix it from. The data must never be
touched by an update.

## Decision

* **Settings › Updates** checks the app's folder on a GitHub branch (default
  `Parmodsihag/jbbv4`, branch `v5`, folder `v5`; changeable) and shows the version and the
  CHANGELOG notes since the installed one. Admins also get a message after sign-in, checked
  at most once a day.
* **Install** downloads only files whose git blob hash differs from the local copy, each
  checked against GitHub's hash, into `<data>/updates/staged`, and installs new Python
  packages from `requirements.txt`. A broken download stages nothing.
* Nothing in the app changes until the **next start**. Then, before the rest of the program
  is imported, every file about to be replaced is saved to
  `<data>/updates/before-<to>-from-<from>-<time>.zip`, the new files go in, files dropped
  upstream are removed, and on any error the old files are put back.
* **Undo last update** stages that zip the same way.
* Only plain relative paths inside the app folder are ever written. The data folder is
  never touched; database changes come from the new version's migrations
  ([ADR 0005](0005-forward-only-migrations.md)).
* `services/updates.py` uses the standard library only.
* A git checkout updates with `git pull --ff-only` (refused with local changes); a packaged
  build cannot update itself.
* Every step goes to `logs/updates.log` and the audit log (code 14).

## Consequences

* The developer publishes by pushing to the `v5` branch; the release checklist
  ([RELEASING.md](../RELEASING.md)) is what protects the shop from a bad push.
* Tested against a fake GitHub (`tests/test_updates.py`): staging, applying, rollback on
  failure, undo, unsafe paths, unreachable GitHub.
* Uses GitHub's anonymous API, which is rate-limited; one check a day is well within it.

## Alternatives considered

* **Replace files while running.** Python has already imported them; a crash mid-copy
  leaves no way back.
* **An installer per release.** The owner would have to download and run it; no undo.
* **pip / a package index.** The app is not a published package, and its folder carries
  data files (the voice model, the bill template).
