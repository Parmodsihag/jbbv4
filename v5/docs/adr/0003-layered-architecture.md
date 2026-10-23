# 0003. Layers: ui → services → db / domain

* Status: Accepted
* Date: 2026-08-29 (4.0.0)

## Context

In v3 the screens ran SQL directly, business rules were repeated in several screens
(interest was computed in more than one place), and nothing could be tested without
opening a window.

## Decision

Four layers with one-way dependencies:

| layer | package | may use | must not |
|---|---|---|---|
| presentation | `hth/ui` | services, i18n | run SQL |
| business logic | `hth/services` (and module services) | db, domain, i18n | import `tkinter` / `customtkinter` |
| data access | `hth/db` | `sqlite3` | know business rules |
| rules | `hth/domain` | the standard library | do I/O |

Views get services through one `AppContext`. Services raise `ValidationError` /
`AuthError` with a message for the user; views show it.

## Consequences

* Business rules are tested on an in-memory database in seconds, without a display.
* The same services serve both layouts ([ADR 0012](0012-two-layouts-one-core.md)), the
  assistant ([ADR 0009](0009-assistant-two-systems-read-only.md)), the tools in `tools/` and
  the v3 importer.
* A screen that needs new data needs a service method first. That is a little more code,
  and the point.
* The rule is checked in review; there is no import linter yet.

## Alternatives considered

* **Model–view–controller inside the UI.** Still ties the rules to the toolkit.
* **Repository classes per table under the services.** More layers than a program of
  this size needs; services use `Database` directly.
