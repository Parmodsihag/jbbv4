# Feature modules

`bills` and `crop_trading` from v3 are **not** part of the v4 core. They will be rebuilt
here as independent modules so they can be worked on, tested and released separately.

## Adding a module

Create a package and export a `MODULE` spec:

```
hth/modules/bills/
    __init__.py      # exports MODULE
    service.py       # business logic, talks to hth.db.Database only
    views.py         # a BaseView subclass
    schema.py        # optional: extra tables, applied via hth.db.schema.MIGRATIONS
tests/modules/test_bills.py
```

```python
# hth/modules/bills/__init__.py
from hth.modules import ModuleSpec
from hth.services.permissions import Permission
from .views import BillsView

MODULE = ModuleSpec(
    key="bills",
    label="Bills",
    view_factory=BillsView,  # (master, ctx) -> BaseView
    permission=Permission.RECORD_SALE,
    shortcut="b",
    order=10,
)
```

Rules that keep modules independent:

* Use the shared `AppContext` (`ctx.db`, `ctx.accounts`, `ctx.inventory`, `ctx.user`,
  `ctx.toast`, `ctx.navigate`) - never import UI classes from other modules.
* Keep tables in the single `hth.db` database; add a migration entry rather than opening
  a second SQLite file.
* Gate every screen and every destructive action with a `Permission`.
* Write to the audit log through `ctx.audit.log(code, message, ctx.username)`.

## Modules

| module         | status  | v3 source            | notes                                                        |
|----------------|---------|----------------------|--------------------------------------------------------------|
| bills          | done    | `bills/`             | GST invoices from the v3 DOCX template, PDF conversion & merge, month batch. |
| finance        | done    | –                    | money accounts, cash book, expenses, recurring, cash flow, P&L; receives Sales-screen money entries via `register_money_flow_handler`. |
| crop_trading   | done    | `database/crop_database.py`, `gui/crop_trading.py` | lots from farmers (gross/kaat/net, quality), FIFO-costed sales with margin, ledger + stock integration, market rates with a provider interface, valuation, reports. |

`bills/` is the reference implementation: `service.py` (pure rules + storage, fully tested
in `tests/modules/test_bills.py`), `views.py` (one `BaseView` with tab panels), a schema
migration in `hth/db/schema.py`, and `MODULE = ModuleSpec(...)` in `__init__.py`.
