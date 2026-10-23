# 0012. Two layouts over one core

* Status: Accepted
* Date: 2026-10-20 (5.5.0)

## Context

The sidebar layout of v4–v5.4 grew to twelve screens organised around how the program was
built (Sales, Accounts, Karar, Items, Finance …) and spoke accounting (Debit / Credit). The
staff think in shop words: a sale, a purchase, a payment in, a payment out, and "what needs
doing today". The owner was used to the old screens, and a forced switch on a working shop
is a risk.

## Decision

* Add a **New** layout (`hth/ui/modern/`): six areas across the top (Today, Counter, Khata,
  Stock, Money, Reports) with Settings behind a gear and an Ask box on every screen.
* Keep **Classic** unchanged. An admin switches the whole shop in Settings, either way, at
  any time; New is the default since 5.5, and a shop that chose Classic keeps it.
* Both layouts call the **same services**; business rules, numbers and the database are not
  touched by the layout. One service method was added for the new Counter
  (`SalesService.record_sale_with_payment`).
* `hth/ui/modern/registry.py` maps every classic screen key to its area and tab, so
  `navigate(key)` and every Alt-letter shortcut work in both.
* Built in phases (0 – 6), one area per commit, each with its UI tests.

## Consequences

* The switch is reversible for the shop; tests check both directions
  (`test_switch_both_ways_while_signed_in`) and that New holds every classic screen
  (`test_new_layout_areas_hold_every_classic_screen`).
* Two sets of screens to maintain. Classic is kept for fixes only; new work goes to New.

## Alternatives considered

* **Rework the sidebar in place.** No way back for a user who preferred it.
* **A separate program.** Two codebases for the same books.
