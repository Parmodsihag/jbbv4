# Chapter 3 — Decision tables (formal specification)

Decision tables specify the branching business rules of the prototype. Each table is
complete (every combination of conditions is covered) and the rules are mutually
exclusive. `—` means *don't care*.

## 3.1 DT-1 Authorisation of an action

Conditions: the user's state and role; the action's required permission.

| Condition | R1 | R2 | R3 | R4 | R5 |
|-----------|----|----|----|----|----|
| User signed in | N | Y | Y | Y | Y |
| User is active | — | N | Y | Y | Y |
| Role | — | — | admin | employee | employee |
| Permission ∈ employee set* | — | — | — | Y | N |
| **Actions** | | | | | |
| Show login screen | X | X | | | |
| Allow action | | | X | X | |
| Hide / disable control, refuse service call | | | | | X |

\* employee set = {view_dashboard, record_sale, add_customer, add_item, manage_krar,
view_reports, export, billing, crop_trading, finance}. Admin holds every permission.

## 3.2 DT-2 Validating a Sales-screen entry

| Condition | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 |
|-----------|----|----|----|----|----|----|----|----|
| kind ∈ {P, M} | N | Y | Y | Y | Y | Y | Y | Y |
| date is `YYYY-MM-DD` | — | N | Y | Y | Y | Y | Y | Y |
| account exists | — | — | N | Y | Y | Y | Y | Y |
| item text non-empty | — | — | — | N | Y | Y | Y | Y |
| quantity > 0 | — | — | — | — | N | Y | Y | Y |
| tag ∈ {0,1,2} | — | — | — | — | — | N | Y | Y |
| entry unit compatible with item unit (or no item) | — | — | — | — | — | — | N | Y |
| **Actions** | | | | | | | | |
| Raise "Kind must be P or M" | X | | | | | | | |
| Raise "Invalid date" | | X | | | | | | |
| Raise "Select a valid account" | | | X | | | | | |
| Raise "Item is required" | | | | X | | | | |
| Raise "Quantity must be greater than zero" | | | | | X | | | |
| Raise "Tag must be 0, 1 or 2" | | | | | | X | | |
| Raise "Enter the quantity in <unit> or a compatible unit" | | | | | | | X | |
| Proceed to DT-3 | | | | | | | | X |

## 3.3 DT-3 What a valid Sales-screen entry writes

| Condition | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|-----------|----|----|----|----|----|----|----|
| Item is a crop (type C) | Y | Y | N | N | N | N | N |
| tag = 0 | Y | N | Y | Y | N | N | N |
| Item is a stock item | — | — | Y | N | Y | N | N |
| Money account chosen | — | — | — | — | — | Y | N |
| **Actions** | | | | | | | |
| Reject: crops cannot carry tag 0 | X | | | | | | |
| Crop purchase lot (M) or FIFO sale (P) → DT-4 | | X | | | | | |
| Write 3 tag-0 rows (entry, Settled Amount, Discount) | | | X | X | | | |
| Write 1 ledger row with given tag | | | | | X | X | X |
| Write stock movement (received if M, sale if P) with value; set last price | | | X | | X | | |
| Write cash-book row linked to the ledger row | | | | | | X | |
| Write audit row 03 (P) / 04 (M) | | X | X | X | X | X | X |
| Commit as one transaction | | X | X | X | X | X | X |

## 3.4 DT-4 Crop sale (Debit on a crop item)

| Condition | R1 | R2 | R3 |
|-----------|----|----|----|
| qty ≤ open-lot stock | Y | N | N |
| *Allow selling short* ticked | — | N | Y |
| **Actions** | | | |
| Reject: not enough stock | | X | |
| Allocate FIFO from oldest open lots; cost = Σ alloc × lot rate | X | | X |
| Uncovered part costed at last purchase rate; flag `short` | | | X |
| Store cost, margin = revenue − cost, margin % | X | | X |
| Debit buyer (or cash sale: no ledger row); reduce stock; audit 10 | X | | X |

## 3.5 DT-5 Contribution of a ledger row to the balance `bal(c, d)`

| Condition | R1 | R2 | R3 | R4 | R5 |
|-----------|----|----|----|----|----|
| Row is after the last tag-0 row (in current period) | N | Y | Y | Y | Y |
| tag | — | 1 | 1 | 2 | 2 |
| type | — | P | M | P | M |
| **Actions** | | | | | |
| Ignore row | X | | | | |
| Add `amount + I(amount, date, d)` | | X | | | |
| Subtract `amount + I(amount, date, d)` | | | X | | |
| Add `amount` | | | | X | |
| Subtract `amount` | | | | | X |

(Tag-0 rows are by definition not after the last tag-0 row, so they never contribute.)

## 3.6 DT-6 Settlement discount row

| Condition | R1 | R2 |
|-----------|----|----|
| Settlement entry type | P | M |
| **Actions** | | |
| Discount = balance_before + amount | X | |
| Discount = balance_before − amount | | X |
| Write *Settled Amount* = balance_before (M, tag 0) | X | X |
| Write *Discount* (M, tag 0), negative allowed | X | X |

## 3.7 DT-7 Interest accrual over a period `[start, end)`

| Condition | R1 | R2 | R3 |
|-----------|----|----|----|
| start < end | N | Y | Y |
| a 31 March lies in `[start, end)` | — | N | Y |
| **Actions** | | | |
| Interest = 0 | X | | |
| Interest = principal × days × 0.24/365 | | X | |
| Interest to 31 March added to principal; recurse from 1 April | | | X |
| Round result to 2 dp | X | X | X |

## 3.8 DT-8 Krar bucket (latest promised date `L`, today `T`)

| Condition | R1 | R2 | R3 | R4 |
|-----------|----|----|----|----|
| krar settled (`is_nill = 1`) | Y | N | N | N |
| L < T | — | Y | N | N |
| L = T | — | — | Y | N |
| **Actions** | | | | |
| Not listed | X | | | |
| Bucket *Overdue* | | X | | |
| Bucket *Today* | | | X | |
| Bucket *Upcoming* | | | | X |

## 3.9 DT-9 Unit conversion of an entered quantity

| Condition | R1 | R2 | R3 | R4 |
|-----------|----|----|----|----|
| Entry unit given | N | Y | Y | Y |
| Entry unit = stock unit | — | Y | N | N |
| Same family (mass / volume) | — | — | Y | N |
| **Actions** | | | | |
| Use quantity as is | X | X | | |
| Multiply by family factor (G→KG ÷1000, QTL→KG ×100, ML→LTR ÷1000) | | | X | |
| Reject: incompatible unit | | | | X |

## 3.10 DT-10 Changing an item's unit (admin)

| Condition | R1 | R2 | R3 | R4 |
|-----------|----|----|----|----|
| New unit same family as old | Y | N | N | N |
| Factor supplied by user | — | Y | N | N |
| "Relabel only" chosen | — | — | Y | N |
| **Actions** | | | | |
| Factor = family factor | X | | | |
| Factor = user's | | X | | |
| Factor = 1 (labels change, numbers don't) | | | X | |
| Ask "how many <new> is 1 <old>?" | | | | X |
| Multiply quantities, divide per-unit prices, leave money unchanged (movements, lots, sales, allocations, rates) | X | X | X | |

## 3.11 DT-11 Customer re-scoring to a category

Thresholds `t1 < t2 < t3` from Settings; `s` = account score ∈ [0, 1].

| Condition | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|-----------|----|----|----|----|----|----|----|
| Category is E | Y | N | N | N | N | N | N |
| Category locked (set by hand) | — | Y | N | N | N | N | N |
| Nothing outstanding (balance ≤ 0) | — | — | Y | N | N | N | N |
| s < t1 | — | — | — | Y | N | N | N |
| s < t2 | — | — | — | — | Y | N | N |
| s < t3 | — | — | — | — | — | Y | N |
| **Actions** | | | | | | | |
| Skip (unchanged) | X | X | | | | | |
| Set A | | | X | X | | | |
| Set B | | | | | X | | |
| Set C | | | | | | X | |
| Set D | | | | | | | X |

## 3.12 DT-12 GST on an invoice line (Bills module)

| Condition | R1 | R2 | R3 |
|-----------|----|----|----|
| Item type | P | F | S or O |
| **Actions** | | | |
| CGST = SGST = 9 % of taxable | X | | |
| CGST = SGST = 2.5 % of taxable | | X | |
| CGST = SGST = 0 | | | X |
| Round each tax to 2 dp; total = taxable + CGST + SGST | X | X | X |

## 3.13 DT-13 Month-batch invoice rendering (admin)

| Condition | R1 | R2 |
|-----------|----|----|
| Bill total ≥ ₹20 000 | Y | N |
| **Actions** | | |
| Create bill row, flag, do **not** render | X | |
| Create bill row and render DOCX | | X |

## 3.14 DT-14 Automatic daily backup at start-up

| Condition | R1 | R2 | R3 |
|-----------|----|----|----|
| Auto-backup enabled | N | Y | Y |
| A backup `hth_auto_<today>.db` already exists | — | Y | N |
| **Actions** | | | |
| Do nothing | X | X | |
| Write `hth_auto_YYYYMMDD.db`; delete oldest beyond N | | | X |
