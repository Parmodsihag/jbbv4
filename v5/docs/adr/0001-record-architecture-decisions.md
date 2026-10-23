# 0001. Record architecture decisions

* Status: Accepted
* Date: 2026-10-23

## Context

The reasons behind the program's structure were spread over commit messages, the
CHANGELOG, module docstrings and two design documents written for review
([AI_CHAT_DESIGN.md](../AI_CHAT_DESIGN.md), [VOICE_DESIGN.md](../VOICE_DESIGN.md)). A new
contributor, or the course evaluator, could see *what* the code does but had to dig to
learn *why* it is shaped that way, and which constraints must not be broken.

## Decision

Keep architecture decision records in `v5/docs/adr/`, one short Markdown file per
decision, in the format of [README.md](README.md). Write one whenever a change:

* adds or removes a layer, a package or an external dependency;
* changes how data is stored, migrated, backed up or updated;
* changes a business rule or the way numbers are computed;
* is hard to undo once it ships to the shop.

The existing decisions are recorded retrospectively as 0002 – 0013.

## Consequences

* Reviewers can check a change against the decisions it touches.
* A decision is changed by writing a new record that supersedes the old one, so the
  history stays readable.
* Small cost: one page per significant change.

## Alternatives considered

* **Only the CHANGELOG.** It says what changed for the shop, not why the code is built a
  certain way, and it has no place for rejected options.
* **One long design document.** Harder to keep current and to reference from a review.
