# Security

High Table Holdings keeps a shop's accounts, customers' names and phone numbers, and its
GST details on one PC. This page says what the program protects, what it does not, and how
to report a problem.

## Reporting a problem

Do **not** open a public issue for a security problem. Write to the maintainer through
GitHub's private vulnerability reporting on `Parmodsihag/jbbv4` (Security › Report a
vulnerability), with the version (Settings › About), what you did and what happened.
Expect an answer within a week. A fix is released as a patch version through the normal
update channel ([v5/docs/RELEASING.md](v5/docs/RELEASING.md#5-hotfixes)).

Supported: the latest 5.x on the `v5` branch. v4 and earlier get no fixes.

## What the program protects

| threat | protection | where |
|---|---|---|
| Someone at the counter uses the program without permission | sign-in; screen lock (`Ctrl+L`, idle auto-lock) | `services/auth.py`, `ui/app.py` |
| Password guessing | 5 failures, then a 30-second wait doubling with each further failure; failures written to the audit log | `services/auth.py` |
| Stolen password file | passwords stored as salted PBKDF2-HMAC-SHA256, 200,000 rounds; never logged | `services/auth.py` |
| Staff changing or deleting history | role → permission matrix; only admins edit or delete; checked by screens and services | `services/permissions.py` |
| Changes nobody owns up to | every write records its user; append-only audit log | `services/audit.py` |
| Default passwords left in place | the setup wizard refuses them; Today flags them until changed | `ui/views/setup.py`, `services/insights.py` |
| A tampered or broken update | each downloaded file is checked against GitHub's git hash; only plain paths inside the app folder are written; the old files are kept and put back on failure | `services/updates.py` |
| A malicious model or voice zip | installs take only the expected model files and stay inside their folder | `assistant/system2.py`, `assistant/voice.py` |
| Leaking the shop's data | no telemetry; the only network use is the update check and download (anonymous HTTPS to GitHub) and `pip`; the assistant and voice run offline; the audit log keeps the assistant's tool and arguments, not the question | |
| Losing the data | daily backups, backups before upgrades and restores, restore with checks | `services/backup.py` |

## What it does not protect

These are known limits. They are accepted for a single shop PC and listed so they can be
handled outside the program.

| limit | what to do |
|---|---|
| The data folder (`C:\JBB\v5`) and the backups are **not encrypted**. Anyone who can read the disk can read the books. | Use a Windows account with a password; BitLocker if available; keep off-PC backups somewhere locked. |
| Passwords need only 4 characters. | Choose longer ones; admins set them in Settings › Users. |
| The lockout counter lives in memory and resets when the program restarts. | Rely on the screen lock and Windows sign-in for an unattended PC. |
| Updates trust the `v5` branch of the repository. A compromised GitHub account could publish a bad version. | Two-factor authentication on the maintainer's GitHub account; branch protection on `v5`; *Undo last update*. |
| Updates may run `pip install` for new requirements from PyPI. | Requirements change rarely and are reviewed in the pull request. |
| WhatsApp reminders open `wa.me` links in the browser with the customer's number and balance in the text. | Only sent when someone clicks. |
| Anyone with admin rights can restore an old backup, replacing current data. | The current data is saved first as `hth_before_restore_<time>.db`; the restore is audited. |

## For developers

* Never log passwords, hashes or a customer's full details at INFO level.
* Check a `Permission` in the service, not only by hiding a button.
* Keep `services/updates.py` standard-library only and keep `_safe()` strict.
* Any new network call needs a decision record and a line in the table above.
