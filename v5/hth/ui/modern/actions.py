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
