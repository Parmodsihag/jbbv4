"""Things you do *to a customer*, shared by every screen of the new layout (Counter, Khata,
Today, Collections): new customer, promise, WhatsApp balance, statement.  Each one calls
the same services as the classic screens."""

from __future__ import annotations

import datetime as dt

from hth.domain.models import Customer
from hth.services.statements import financial_year_start
from hth.ui.format import open_path, today_str
from hth.ui.widgets.dialogs import Field, run_form

OWED_TO_US, OWED_BY_US = "Owed to us", "Owed by us"


def new_customer(parent, ctx, name: str = "") -> Customer | None:
    """The small "New customer" window; returns the account it made (or None)."""
    fields = [
        Field("name", "Name", default=name.strip().upper()),
        Field("details", "Village, father's name, phone"),
        Field("opening", "Opening balance (optional)"),
        Field("side", "It is", kind="option", default=OWED_TO_US, options=[OWED_TO_US, OWED_BY_US]),
    ]
    made: dict = {}

    def submit(v: dict) -> None:
        made["c"] = ctx.accounts.add_customer(
            v["name"],
            v["details"],
            v["opening"] or 0,
            today_str(),
            "NEW ACCOUNT",
            "P" if v["side"] == OWED_TO_US else "M",
            "1",
            ctx.username,
        )

    if run_form(parent, "New customer", fields, submit, "Create") and made:
        c = made["c"]
        ctx.toast(f"Account #{c.id} {c.name} created", "success")
        return c
    return None


def promise(parent, ctx, customer_id: int) -> bool:
    """Record or move the date this customer promised to pay (a krar)."""
    c = ctx.accounts.get_customer(customer_id)
    if c is None:
        return False
    dates = ctx.krar.unsettled_dates(c.id)
    current = f"  (now {max(dates)})" if dates else ""
    default = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    fields = [Field("date", f"Promised date{current}", default=default)]
    if run_form(
        parent,
        f"Promise from {c.name}",
        fields,
        lambda v: ctx.krar.add_or_update(c.id, v["date"], ctx.username),
        "Save promise",
    ):
        ctx.toast("Promise saved", "success")
        return True
    return False


def whatsapp_balance(parent, ctx, customer_id: int) -> None:
    """Balance message on the clipboard, and WhatsApp opened when there is a mobile number."""
    r = ctx.reminders.balance_message(customer_id)
    parent.clipboard_clear()
    parent.clipboard_append(r.text)
    if r.whatsapp_url:
        import webbrowser

        webbrowser.open(r.whatsapp_url)
        ctx.audit.log("07", f"whatsapp balance to customer {r.customer_id}", ctx.username)
        ctx.toast("WhatsApp opened - the message is also on the clipboard", "success")
    else:
        ctx.toast("No 10-digit mobile number in the account details - message copied instead", "warning")


def statement(parent, ctx, customer_id: int) -> None:
    c = ctx.accounts.get_customer(customer_id)
    if c is None:
        return
    fields = [Field("from", "From", default=financial_year_start()), Field("to", "To", default=today_str())]
    out: dict = {}

    def submit(v: dict) -> None:
        st = ctx.statements.build(c.id, v["from"], v["to"])
        out["path"] = ctx.statements.write(st, ctx.settings.export_dir)

    if run_form(parent, f"Statement for {c.name}", fields, submit, "Create") and out:
        ctx.toast(f"Statement saved: {out['path'].name}", "success")
        open_path(out["path"])


# Corrections (admin) -----------------------------------------------------------------------
def _lines(*parts: str) -> str:
    """A message box text with each line in the shop's language (message boxes are not
    translated by the widget hook)."""
    from hth import i18n

    return "\n".join(i18n.tr(p) if p else "" for p in parts)


def edit_customer(parent, ctx, customer_id: int) -> bool:
    c = ctx.accounts.get_customer(customer_id)
    if c is None:
        return False
    fields = [
        Field("name", "Name", default=c.name),
        Field("details", "Other details", default=c.other_details),
        Field("name_hi", "Name in Hindi  (blank = automatic)", default=c.name_hi if c.hi_manual else ""),
        Field("details_hi", "Details in Hindi", default=c.details_hi if c.hi_manual else ""),
    ]

    def submit(v: dict) -> None:
        ctx.accounts.update_customer(c.id, v["name"], v["details"], ctx.username)
        if v["name_hi"]:
            ctx.hindi.set_customer(c.id, v["name_hi"], v["details_hi"], ctx.username)
        elif c.hi_manual:
            ctx.hindi.reset("customer", c.id, ctx.username)

    if run_form(parent, f"Edit customer #{c.id}", fields, submit):
        ctx.app.refresh_names()
        return True
    return False


def set_category(parent, ctx, customer_id: int) -> bool:
    c = ctx.accounts.get_customer(customer_id)
    if c is None:
        return False
    fields = [
        Field(
            "category",
            "Category (E = defaulter, kept out of reports and scoring)",
            "option",
            c.category,
            ["A", "B", "C", "D", "E"],
        ),
        Field("mode", "After saving", "option", "Keep (locked)", ["Keep (locked)", "Let re-score change it"]),
    ]

    def submit(v: dict) -> None:
        if v["mode"].startswith("Keep"):
            ctx.categories.set_customer_category(c.id, v["category"], ctx.username)
        else:
            ctx.accounts.set_category(c.id, v["category"], ctx.username, locked=False)

    if run_form(parent, f"Category of {c.name}", fields, submit):
        ctx.toast("Category updated", "success")
        return True
    return False


def add_entry(parent, ctx, customer_id: int) -> bool:
    """A plain ledger line typed by an admin (no stock, no cash book) - as on the classic ledger."""
    fields = [
        Field("date", "Date", default=today_str()),
        Field("description", "Particulars"),
        Field("amount", "Amount"),
        Field("type", "Debit (P) or credit (M)", "option", "P", ["P", "M"]),
        Field("tag", "Tag  (1 interest, 2 no interest, 0 settlement)", "option", "1", ["1", "2", "0"]),
    ]
    return bool(
        run_form(
            parent,
            "Add ledger entry",
            fields,
            lambda v: ctx.accounts.add_transaction(
                customer_id, v["date"], v["description"], v["amount"], v["type"], v["tag"], ctx.username
            ),
        )
    )


def correct_entry(parent, ctx, tx_id: int) -> bool:
    tx = ctx.accounts.get_transaction(tx_id)
    if tx is None:
        return False
    fields = [
        Field("date", "Date", default=tx.date),
        Field("description", "Particulars", default=tx.description),
        Field("amount", "Amount", default=f"{tx.amount:g}"),
        Field("type", "Debit (P) or credit (M)", "option", tx.type, ["P", "M"]),
        Field("tag", "Tag  (1 interest, 2 no interest, 0 settlement)", "option", tx.tag, ["1", "2", "0"]),
    ]
    saved = run_form(
        parent,
        f"Correct entry #{tx.id}",
        fields,
        lambda v: ctx.accounts.update_transaction(
            tx.id, v["date"], v["description"], v["amount"], v["type"], v["tag"], ctx.username
        ),
    )
    if saved:
        ctx.toast("Entry corrected - a receipt's cash-book line follows the change", "success")
    return bool(saved)


def delete_entry(parent, ctx, tx_id: int, balance_note: str = "") -> bool:
    """Delete one ledger line after saying plainly what changes - and what does not."""
    from hth.services.accounts import ValidationError
    from hth.ui.modern.widgets import rupees
    from hth.ui.widgets.dialogs import confirm

    tx = ctx.accounts.get_transaction(tx_id)
    if tx is None:
        return False
    text = _lines(
        f"{tx.date}  ·  {tx.description}  ·  {rupees(tx.amount)}",
        "",
        balance_note,
        "If it went into the cash book, that line is removed too.",
        "Stock is not changed by deleting a ledger entry.",
        "",
        "This cannot be undone. It is written in the audit log with your name.",
    )
    if not confirm(parent, f"Delete entry #{tx.id}?", text):
        return False
    try:
        ctx.accounts.delete_transaction(tx.id, ctx.username)
    except ValidationError as exc:
        ctx.toast(str(exc), "error")
        return False
    ctx.toast("Entry deleted", "success")
    return True


def delete_customer(parent, ctx, customer_id: int) -> bool:
    from hth.services.accounts import ValidationError
    from hth.ui.widgets.dialogs import confirm

    c = ctx.accounts.get_customer(customer_id)
    if c is None:
        return False
    if not confirm(
        parent,
        "Delete customer",
        _lines(f"Delete #{c.id} {c.name} and ALL its ledger entries?", "This cannot be undone."),
    ):
        return False
    try:
        ctx.accounts.delete_customer(c.id, ctx.username)
    except ValidationError as exc:
        ctx.toast(str(exc), "error")
        return False
    ctx.toast(f"Customer {c.name} deleted", "success")
    return True


def mark_kept(parent, ctx, customer_id: int) -> bool:
    from hth.ui.widgets.dialogs import confirm

    c = ctx.accounts.get_customer(customer_id)
    if c is None or not ctx.krar.unsettled_dates(c.id):
        return False
    if not confirm(parent, "Promise kept", _lines(f"Mark the open promise of {c.name} as kept?")):
        return False
    ctx.krar.settle(c.id, ctx.username)
    ctx.toast("Promise marked kept", "success")
    return True
