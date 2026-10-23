# 0006. Feature modules discovered through `ModuleSpec`

* Status: Accepted
* Date: 2026-08-29 (4.1.0)

## Context

v3's bills and crop-trading code was tangled into the core. The v4 rewrite shipped the core
first; GST bills, crop trading and a cash book were to come back as separate pieces that
could be built, tested and released on their own, without the core depending on them.

## Decision

* A feature module is a package under `hth/modules/` that exports
  `MODULE = ModuleSpec(key, label, view_factory, permission, shortcut, order, area, tab, reports)`.
* `hth.modules.discover()` imports every package at start-up and collects the specs; a
  module that fails to import is logged and skipped.
* **Core never imports a module.** Where the core must call into one (a counter entry on a
  crop item, or a money entry that belongs in the cash book) the module registers a handler
  with the sales service (`register_crop_handler`, `register_money_flow_handler`).
* A module keeps its tables in `hth.db` through the shared migration list, gates its screens
  and destructive actions with a `Permission`, and writes to the audit log.
* Since 5.5 a module names where it appears in the New layout (`area`, `tab`) and which
  reports it offers to the catalogue (`reports`).

## Consequences

* bills, crop_trading and finance were added without touching the core's screens, and each
  has its own tests (`tests/modules/`).
* The counter behaves the same with or without a module installed.
* Schema changes for modules still go through the one migration list, so module order in
  that list matters.

## Alternatives considered

* **Entry-point plugins (`importlib.metadata`).** Needs installing each module as a
  package; the shop copies a folder.
* **Everything in the core.** Simpler at first, but v3 showed where that leads.
