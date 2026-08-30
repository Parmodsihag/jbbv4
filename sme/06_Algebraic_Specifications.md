# Chapter 4 — Algebraic specifications (formal specification)

Each abstract data type is given as **sorts**, **operations** (signature) and
**axioms** (equations that hold for all values of the variables). Operations are split
into *constructors* (build values) and *observers/derived* (inspect values). Where the
implementation rounds, the axiom is stated on exact reals and rounding to 2 dp is a final
observer `round2`. Auxiliary sorts: `Real`, `Nat`, `Bool`, `Date` (totally ordered, with
`succ`, `daysBetween`, `fyEnd : Date → Date` giving the next 31 March on or after a date).

---

## 4.1 Interest

```
spec INTEREST
  uses  Real, Date, Bool
  consts
    r      : Real            -- daily rate = 0.24 / 365
  ops
    fyEnd  : Date → Date
    I      : Real × Date × Date → Real        -- I(principal, from, to)
  axioms  ∀ p : Real, d1 d2 : Date
    [I1] fyEnd(d) = (31 March of year(d))          if month(d) ≤ 3
    [I2] fyEnd(d) = (31 March of year(d) + 1)      if month(d) > 3
    [I3] I(p, d1, d2) = 0                          if ¬(d1 < d2)
    [I4] I(p, d1, d2) = p · daysBetween(d1, d2) · r
                                                   if d1 < d2 ∧ d2 ≤ fyEnd(d1)
    [I5] I(p, d1, d2) = p · daysBetween(d1, fyEnd(d1)) · r
                        + I(p + p · daysBetween(d1, fyEnd(d1)) · r,
                            succ(fyEnd(d1)), d2)   if d1 < d2 ∧ d2 > fyEnd(d1)
  observers
    interest(p, d1, d2) = round2(I(p, d1, d2))
end
```
Properties derivable from the axioms (checked in `tests/test_interest.py`):
`interest(1000, 2024-04-01, 2025-03-31) = 240.00` (one FY, simple);
`interest(p, d, d) = 0`; `I` is monotone in `d2`; compounding occurs only at `fyEnd`.

---

## 4.2 Ledger (customer account)

```
spec LEDGER
  uses  INTEREST, Real, Date, Bool, Nat
  sorts Ledger, Entry, Type = {P, M}, Tag = {0, 1, 2}
  ops
    -- constructors
    empty   : → Ledger
    add     : Ledger × Date × Real × Type × Tag → Ledger      -- append one row
    -- observers / derived
    sign    : Type → Real
    value   : Entry × Date → Real
    period  : Ledger → Ledger        -- rows after the last tag-0 row
    bal     : Ledger × Date → Real
    settle  : Ledger × Date × Real × Type → Ledger
    size    : Ledger → Nat
  axioms  ∀ L : Ledger, d t : Date, a b : Real, ty : Type, tg : Tag
    [L1] sign(P) = +1
    [L2] sign(M) = −1
    [L3] value(entry(d, a, ty, 1), t) = a + I(a, d, t)
    [L4] value(entry(d, a, ty, 2), t) = a
    [L5] value(entry(d, a, ty, 0), t) = 0
    [L6] period(empty) = empty
    [L7] period(add(L, d, a, ty, 0)) = empty                      -- settlement closes the period
    [L8] period(add(L, d, a, ty, tg)) = add(period(L), d, a, ty, tg)   if tg ≠ 0
    [L9] bal(empty, t) = 0
    [L10] bal(add(L, d, a, ty, tg), t) = bal(period(L), t) + sign(ty) · value(entry(d, a, ty, tg), t)
                                                                  if tg ≠ 0
    [L11] bal(add(L, d, a, ty, 0), t) = 0
    [L12] settle(L, d, a, P) = add(add(add(L, d, a, P, 0), d, bal(L, d), M, 0), d, bal(L, d) + a, M, 0)
    [L13] settle(L, d, a, M) = add(add(add(L, d, a, M, 0), d, bal(L, d), M, 0), d, bal(L, d) − a, M, 0)
    [L14] size(empty) = 0
    [L15] size(add(L, d, a, ty, tg)) = size(L) + 1
  observers
    balance(L, t) = round2(bal(L, t))
  invariants
    ∀ L d a ty : bal(settle(L, d, a, ty), d) = 0                  -- from L11
    ∀ L d a ty : size(settle(L, d, a, ty)) = size(L) + 3          -- three tag-0 rows
    a > 0 for every user-entered row; derived rows (Settled Amount, Discount) may be < 0
end
```
Note on ordering: rows are ordered by `(date, id)`; `add` appends with the next id, so
`period` is well defined even when several rows share a date.

---

## 4.3 Stock (inventory of one item)

```
spec STOCK
  uses  Real, Date, Bool
  sorts Stock, Unit, Family = {mass, volume, count}
  ops
    new      : Real × Unit → Stock              -- opening quantity in stock unit
    receive  : Stock × Date × Real × Unit → Stock
    sell     : Stock × Date × Real × Unit → Stock
    qty      : Stock → Real
    unit     : Stock → Unit
    lastPrice: Stock → Real
    setPrice : Stock × Real → Stock
    fam      : Unit → Family
    factor   : Unit × Unit → Real               -- partial: defined iff fam(u) = fam(v) ∧ fam ≠ count or u = v
    conv     : Real × Unit × Unit → Real
  axioms  ∀ S : Stock, q p : Real, u v : Unit, d : Date
    [S1] factor(u, u) = 1
    [S2] factor(G, KG) = 1/1000;  factor(KG, QTL) = 1/100;  factor(ML, LTR) = 1/1000
    [S3] factor(u, v) = 1 / factor(v, u)
    [S4] factor(u, w) = factor(u, v) · factor(v, w)            (same family)
    [S5] conv(q, u, v) = q · factor(u, v)                      if defined(factor(u, v))
    [S6] conv(q, u, v) = ⊥ (UnitError)                          otherwise
    [S7] unit(new(q, u)) = u
    [S8] unit(receive(S, d, q, u)) = unit(S);   unit(sell(S, d, q, u)) = unit(S)
    [S9] qty(new(q, u)) = q
    [S10] qty(receive(S, d, q, u)) = qty(S) + conv(q, u, unit(S))
    [S11] qty(sell(S, d, q, u)) = qty(S) − conv(q, u, unit(S))
    [S12] lastPrice(setPrice(S, p)) = p
    [S13] qty(setPrice(S, p)) = qty(S)
  invariant
    qty(S) = Σ received − Σ sold (all expressed in unit(S)); no truncation to integers.
end
```

**Unit change** (admin): `rescale(S, v, f)` with factor `f = factor(unit(S), v)` (or user
supplied) satisfies `qty(rescale(S, v, f)) = qty(S) · f`, `lastPrice(rescale(S, v, f)) =
lastPrice(S) / f` and `value = qty · price` is preserved.

---

## 4.4 Crop lots and FIFO costing

```
spec CROPFIFO
  uses  Real, Date, Bool, list
  sorts Lot, Lots, Sale
  ops
    lot       : Date × Real × Real × Real → Lot       -- (date, gross, kaat, rate); net = gross − kaat
    remaining : Lot → Real
    none      : → Lots
    push      : Lots × Lot → Lots                     -- lots kept in date order (oldest first)
    open      : Lots → Real                            -- Σ remaining
    alloc     : Lots × Real → (Lots × Real)            -- (lots after allocation, cost)
    sale      : Lots × Real × Real × Bool → Sale       -- (lots, qty, sellRate, allowShort)
    lastRate  : Lots → Real
  axioms  ∀ Ls : Lots, l : Lot, q r : Real, short : Bool
    [F1] remaining(lot(d, g, k, r)) = g − k
    [F2] open(none) = 0
    [F3] open(push(Ls, l)) = open(Ls) + remaining(l)
    [F4] alloc(Ls, 0) = (Ls, 0)
    [F5] alloc(push(Ls, l), q) with l the OLDEST open lot:
           if q ≤ remaining(l):  (lots with remaining(l) − q,  q · rate(l))
           else:                 let (Ls', c) = alloc(Ls without l, q − remaining(l))
                                 in (Ls', remaining(l) · rate(l) + c)
    [F6] sale(Ls, q, r, short) = ⊥ (rejected)                 if q > open(Ls) ∧ ¬short
    [F7] cost(sale(Ls, q, r, short)) = snd(alloc(Ls, min(q, open(Ls))))
                                        + max(0, q − open(Ls)) · lastRate(Ls)
    [F8] margin(sale(Ls, q, r, _)) = q · r − cost(sale(Ls, q, r, _))
    [F9] flagged(sale(Ls, q, r, true)) = (q > open(Ls))
    [F10] open(after(sale(Ls, q, r, _))) = max(0, open(Ls) − q)
  invariant   Σ_lots remaining ≥ 0;  every allocation row references an existing lot.
end
```

---

## 4.5 Krar (promise to pay)

```
spec KRAR
  uses  Date, Bool, set
  sorts Krar, Bucket = {overdue, today, upcoming, none}
  ops
    open      : Date → Krar
    promise   : Krar × Date → Krar        -- reschedule = add a date
    settleK   : Krar → Krar
    latest    : Krar → Date
    isOpen    : Krar → Bool
    bucket    : Krar × Date → Bucket      -- (krar, today)
  axioms  ∀ K : Krar, d t : Date
    [K1] isOpen(open(d)) = true
    [K2] isOpen(promise(K, d)) = isOpen(K)
    [K3] isOpen(settleK(K)) = false
    [K4] latest(open(d)) = d
    [K5] latest(promise(K, d)) = max(latest(K), d)
    [K6] bucket(K, t) = none        if ¬isOpen(K)
    [K7] bucket(K, t) = overdue     if isOpen(K) ∧ latest(K) < t
    [K8] bucket(K, t) = today       if isOpen(K) ∧ latest(K) = t
    [K9] bucket(K, t) = upcoming    if isOpen(K) ∧ latest(K) > t
  invariant   a customer has at most one K with isOpen(K) = true.
end
```

---

## 4.6 Permissions

```
spec PERMISSIONS
  uses  Bool, set
  sorts Role = {admin, employee}, Perm, User
  ops
    perms   : Role → Set(Perm)
    allowed : User × Perm → Bool
    role, active : User → Role, Bool
  axioms  ∀ u : User, p : Perm
    [P1] perms(admin) = ALL
    [P2] perms(employee) = {view_dashboard, record_sale, add_customer, add_item, manage_krar,
                            view_reports, export, billing, crop_trading, finance}
    [P3] perms(employee) ⊂ perms(admin)
    [P4] allowed(u, p) = active(u) ∧ p ∈ perms(role(u))
end
```

---

## 4.7 Audit log

```
spec AUDIT
  uses  Nat, Date, string, list
  sorts Log, Code = {01..12}
  ops
    emptyLog : → Log
    log      : Log × Code × string × string × Date → Log      -- (log, code, detail, user, at)
    count    : Log → Nat
    byUser   : Log × string → Log
  axioms
    [A1] count(emptyLog) = 0
    [A2] count(log(G, c, s, u, t)) = count(G) + 1
    [A3] byUser(emptyLog, u) = emptyLog
    [A4] byUser(log(G, c, s, u', t), u) = if u = u' then log(byUser(G, u), c, s, u, t) else byUser(G, u)
  invariant   Log is append-only: no operation removes an entry.
end
```

---

## 4.8 Money accounts (Finance module)

```
spec CASHBOOK
  uses  Real, Date
  sorts Book, Kind = {receipt, payment, expense, income, transfer_in, transfer_out, capital, drawings}
  ops
    openBook : Real → Book                    -- opening balance
    post     : Book × Date × Kind × Real → Book
    balance  : Book → Real
    inflow   : Kind → Bool
  axioms  ∀ B : Book, o a : Real, d : Date, k : Kind
    [C1] inflow(k) = k ∈ {receipt, income, transfer_in, capital}
    [C2] balance(openBook(o)) = o
    [C3] balance(post(B, d, k, a)) = balance(B) + a       if inflow(k)
    [C4] balance(post(B, d, k, a)) = balance(B) − a       if ¬inflow(k)
    [C5] transfer(B1, B2, a) = (post(B1, d, transfer_out, a), post(B2, d, transfer_in, a))
  invariant   Σ over all books of balance = Σ opening + Σ inflows − Σ outflows
              (transfers cancel); balances are never stored, always derived.
end
```

## 4.9 Consistency with the implementation

| Spec | Implementation | Pinning test |
|------|----------------|--------------|
| INTEREST | `hth/domain/interest.py` | `tests/test_interest.py` |
| LEDGER | `AccountsService.get_balance / ledger / record_settlement` | `tests/test_accounts.py` |
| STOCK | `InventoryService`, `hth/domain/units.py` | `tests/test_inventory_sales.py`, `tests/test_units.py`, `tests/test_unit_change.py` |
| CROPFIFO | `hth/modules/crop_trading/service.py` | `tests/modules/test_crops.py`, `tests/test_sales_crops.py` |
| KRAR | `KrarService` | `tests/test_krar_reports_auth.py` |
| PERMISSIONS | `hth/services/permissions.py` | `tests/test_krar_reports_auth.py::test_permissions` |
| AUDIT | `AuditService` | asserted throughout |
| CASHBOOK | `hth/modules/finance/service.py` | `tests/modules/test_finance.py` |
