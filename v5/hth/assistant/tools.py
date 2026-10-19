"""Read-only tools the assistant can run, and how their answers read in Hindi and English.

Every tool is a thin wrapper around a service method the reports already use, so a chat
answer and the matching report always agree.  A tool declares the permission it needs
and its slots; a missing required slot is asked for with the slot's own question.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field

from hth.assistant.normalize import Period, resolve
from hth.domain import numbers
from hth.services.permissions import Permission

# --- answers -------------------------------------------------------------------------------


@dataclass
class Answer:
    headline: str
    lines: list[str] = field(default_factory=list)
    columns: list[tuple[str, str]] = field(default_factory=list)  # (title, kind: text|money|qty|int)
    rows: list[tuple] = field(default_factory=list)
    actions: list[tuple[str, str, dict]] = field(default_factory=list)  # (label, view key, kwargs)
    looked_up: str = ""


def L(lang: str, en: str, hi: str) -> str:  # noqa: N802 - reads like a template marker
    return hi if lang == "hi" else en


def rs(value: float) -> str:
    return "₹" + numbers.amount(value)


def many(n: int, word: str) -> str:
    """'1 item', '3 items' (English only - Hindi counts read the same either way)."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def qty(value: float) -> str:
    return numbers.quantity(value)


_MONTHS_EN = "January February March April May June July August September October November December".split()
_MONTHS_HI = "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split()


def day_text(d: dt.date, lang: str) -> str:
    return f"{d.day} {(_MONTHS_HI if lang == 'hi' else _MONTHS_EN)[d.month - 1]} {d.year}"


def period_label(p: Period, lang: str) -> str:
    names = {
        "today": ("today", "आज"),
        "yesterday": ("yesterday", "कल"),
        "day_before": ("day before yesterday", "परसों"),
        "this_week": ("this week", "इस हफ्ते"),
        "last_week": ("last week", "पिछले हफ्ते"),
        "this_month": ("this month", "इस महीने"),
        "last_month": ("last month", "पिछले महीने"),
        "this_fy": ("this financial year", "इस वित्त वर्ष"),
        "last_fy": ("last financial year", "पिछले वित्त वर्ष"),
    }
    if p.value in names:
        base = names[p.value][1 if lang == "hi" else 0]
    elif p.value.startswith("month:"):
        base = (_MONTHS_HI if lang == "hi" else _MONTHS_EN)[p.start.month - 1] + f" {p.start.year}"
    elif p.value.startswith("days:"):
        n = p.value.split(":")[1]
        base = L(lang, f"last {n} days", f"पिछले {n} दिन")
    else:
        base = day_text(p.start, lang)
    if p.single_day:
        return base if p.value in names else day_text(p.start, lang)
    return f"{base} ({p.start:%d-%m-%Y} – {p.end:%d-%m-%Y})"


# --- the services a tool may use ----------------------------------------------------------


class Services:
    """What tools need - built from the database alone, so the assistant runs in any front end."""

    def __init__(self, db):
        from hth.services.accounts import AccountsService
        from hth.services.categories import CategoryService
        from hth.services.inventory import InventoryService
        from hth.services.krar import KrarService
        from hth.services.reports import ReportsService

        self.db = db
        self.accounts = AccountsService(db)
        self.inventory = InventoryService(db)
        self.krar = KrarService(db)
        self.reports = ReportsService(db)
        self.categories = CategoryService(db)

    def finance(self):
        from hth.services.sales import money_flow_handler

        return money_flow_handler(self.db)


# --- tools ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    name: str  # customer | item | period | day | number | category
    required: bool
    ask_en: str = ""
    ask_hi: str = ""


@dataclass(frozen=True)
class Tool:
    name: str
    run: Callable
    slots: tuple[Slot, ...] = ()
    permission: Permission | None = None
    default_period: str | None = None
    title_en: str = ""
    title_hi: str = ""


_CUSTOMER = Slot("customer", True, "Whose account?", "किसका खाता?")
_ITEM = Slot("item", True, "Which item?", "कौन सा सामान?")


def _customer(svc, cid):
    return svc.accounts.get_customer(cid)


def _cname(c, lang) -> str:
    return (c.name_hi or c.name) if lang == "hi" else c.name.title()


def _state(balance: float, lang: str) -> str:
    if balance > 0:
        return L(lang, "owes us", "हमें लेना है")
    if balance < 0:
        return L(lang, "we owe them", "हमें देना है")
    return L(lang, "settled", "हिसाब बराबर")


def _last_payment(svc, cid):
    row = svc.db.fetchone(
        "SELECT date, amount FROM transactions WHERE customer_id = ? AND type = 'M' "
        "AND NOT (tag = '0' AND description IN ('Settled Amount', 'Discount')) ORDER BY date DESC, id DESC LIMIT 1",
        (cid,),
    )
    return (row["date"], float(row["amount"])) if row else None


def customer_balance(svc, a, lang, today) -> Answer:
    c = _customer(svc, a["customer"])
    bal = svc.accounts.get_balance(c.id)
    ans = Answer(
        f"{_cname(c, lang)} · {L(lang, 'balance', 'शेष')} {rs(abs(bal))} ({_state(bal, lang)})",
        actions=[(L(lang, "Open ledger", "खाता खोलें"), "customers", {"customer_id": c.id})],
        looked_up=L(lang, "balance", "बकाया") + f" · {_cname(c, lang)}",
    )
    dates = svc.krar.unsettled_dates(c.id)
    if dates:
        d = dt.date.fromisoformat(max(dates))
        late = (today - d).days
        when = (
            L(lang, f"{late} days late", f"{late} दिन देर")
            if late > 0
            else (L(lang, "today", "आज") if late == 0 else L(lang, f"in {-late} days", f"{-late} दिन में"))
        )
        ans.lines.append(L(lang, f"Promised {d:%d-%m-%Y} ({when})", f"वादा {d:%d-%m-%Y} ({when})"))
    lp = _last_payment(svc, c.id)
    if lp:
        ans.lines.append(
            L(
                lang,
                f"Last payment {lp[0]} · {rs(lp[1])}",
                f"पिछला भुगतान {dt.date.fromisoformat(lp[0]):%d-%m-%Y} · {rs(lp[1])}",
            )
        )
    elif bal > 0:
        ans.lines.append(L(lang, "No payment recorded yet", "अभी तक कोई भुगतान दर्ज नहीं"))
    return ans


def customer_ledger(svc, a, lang, today) -> Answer:
    c = _customer(svc, a["customer"])
    rows = svc.accounts.ledger(c.id)
    p: Period | None = a.get("period")
    if p is not None:
        shown = [r for r in rows if p.start.isoformat() <= r.date <= p.end.isoformat()]
        span = period_label(p, lang)
    else:
        shown = rows[-10:]
        span = L(lang, "last 10 entries", "पिछली 10 एंट्री")
    deb = sum(r.debit or 0 for r in shown if r.particulars not in ("Settled Amount", "Discount"))
    cred = sum(r.credit or 0 for r in shown if r.particulars not in ("Settled Amount", "Discount"))
    bal = svc.accounts.get_balance(c.id)
    ans = Answer(
        f"{_cname(c, lang)} · {span}",
        columns=[
            (L(lang, "Date", "तारीख"), "text"),
            (L(lang, "Particulars", "विवरण"), "text"),
            (L(lang, "Debit", "नामे"), "money"),
            (L(lang, "Credit", "जमा"), "money"),
            (L(lang, "Balance", "शेष"), "money"),
        ],
        rows=[(r.date, r.particulars, r.debit, r.credit, r.balance) for r in shown],
        actions=[(L(lang, "Open ledger", "खाता खोलें"), "customers", {"customer_id": c.id})],
        looked_up=L(lang, "account", "हिसाब") + f" · {_cname(c, lang)} · {span}",
    )
    if shown:
        ans.lines.append(
            L(
                lang,
                f"{len(shown)} entries · debit {rs(deb)} · credit {rs(cred)}",
                f"{len(shown)} एंट्री · नामे {rs(deb)} · जमा {rs(cred)}",
            )
        )
    else:
        ans.lines.append(L(lang, "No entries in this period.", "इस अवधि में कोई एंट्री नहीं।"))
    ans.lines.append(
        L(lang, f"Balance today {rs(abs(bal))} ({_state(bal, lang)})", f"आज का शेष {rs(abs(bal))} ({_state(bal, lang)})")
    )
    return ans


def customer_contact(svc, a, lang, today) -> Answer:
    from hth.services.reminders import extract_phone

    c = _customer(svc, a["customer"])
    phone = extract_phone(c.other_details)
    details = c.details_hi if lang == "hi" and c.details_hi else c.other_details
    if phone:
        head = f"{_cname(c, lang)} · {L(lang, 'phone', 'फ़ोन')} {phone}"
    else:
        head = f"{_cname(c, lang)} · " + L(lang, "no mobile number saved", "कोई मोबाइल नंबर दर्ज नहीं")
    ans = Answer(head, looked_up=L(lang, "phone", "फ़ोन") + f" · {_cname(c, lang)}")
    if details and details.upper() != "NA":
        ans.lines.append(L(lang, f"Details: {details}", f"विवरण: {details}"))
    ans.actions.append((L(lang, "Open ledger", "खाता खोलें"), "customers", {"customer_id": c.id}))
    return ans


def customer_interest(svc, a, lang, today) -> Answer:
    c = _customer(svc, a["customer"])
    t = svc.accounts.period_totals(customer_ids=[c.id])[c.id]
    return Answer(
        f"{_cname(c, lang)} · {L(lang, 'interest', 'ब्याज')} {rs(t.interest)}",
        [
            L(
                lang,
                f"Principal {rs(t.principal)} + interest {rs(t.interest)} = {rs(t.total)}",
                f"मूल {rs(t.principal)} + ब्याज {rs(t.interest)} = {rs(t.total)}",
            ),
            L(
                lang,
                "Since the last settlement, 24% a year, added each 31 March.",
                "पिछले हिसाब-बराबर से, 24% सालाना, हर 31 मार्च को जुड़ता है।",
            ),
        ],
        actions=[(L(lang, "Open ledger", "खाता खोलें"), "customers", {"customer_id": c.id})],
        looked_up=L(lang, "interest", "ब्याज") + f" · {_cname(c, lang)}",
    )


def customer_krar(svc, a, lang, today) -> Answer:
    c = _customer(svc, a["customer"])
    dates = svc.krar.unsettled_dates(c.id)
    if not dates:
        return Answer(
            f"{_cname(c, lang)} · " + L(lang, "no open promise", "कोई खुला वादा नहीं"),
            looked_up=L(lang, "promise", "करार") + f" · {_cname(c, lang)}",
        )
    d = dt.date.fromisoformat(max(dates))
    bal = svc.accounts.get_balance(c.id)
    history = ", ".join(dt.date.fromisoformat(x).strftime("%d-%m-%Y") for x in sorted(dates))
    return Answer(
        f"{_cname(c, lang)} · " + L(lang, f"promised {d:%d-%m-%Y}", f"वादा {d:%d-%m-%Y}"),
        [
            L(lang, f"Owes {rs(max(bal, 0))}", f"बकाया {rs(max(bal, 0))}"),
            L(lang, f"Dates given: {history}", f"दी गई तारीखें: {history}"),
        ],
        actions=[(L(lang, "Open Karar", "करार खोलें"), "karar", {})],
        looked_up=L(lang, "promise", "करार") + f" · {_cname(c, lang)}",
    )


def _krar_table(svc, entries, lang, today, title_en, title_hi) -> Answer:
    balances = svc.accounts.balances(customer_ids=[e.customer_id for e in entries])
    cust = {c.id: c for c in svc.accounts.list_customers()}
    rows = []
    for e in entries:
        c = cust.get(e.customer_id)
        d = dt.date.fromisoformat(e.last_date)
        rows.append(
            (
                _cname(c, lang) if c else e.customer_name,
                d.strftime("%d-%m-%Y"),
                (today - d).days,
                balances.get(e.customer_id, 0.0),
            )
        )
    rows.sort(key=lambda r: -r[3])
    total = sum(max(r[3], 0) for r in rows)
    return Answer(
        L(lang, f"{title_en}: {len(rows)} · {rs(total)} outstanding", f"{title_hi}: {len(rows)} · {rs(total)} बकाया"),
        columns=[
            (L(lang, "Customer", "ग्राहक"), "text"),
            (L(lang, "Promised", "वादा"), "text"),
            (L(lang, "Days late", "दिन देर"), "int"),
            (L(lang, "Balance", "शेष"), "money"),
        ],
        rows=rows,
        actions=[(L(lang, "Open Karar", "करार खोलें"), "karar", {})],
    )


def krar_overdue(svc, a, lang, today) -> Answer:
    ans = _krar_table(svc, svc.krar.entries("past", today), lang, today, "Overdue promises", "तारीख निकल चुके वादे")
    ans.looked_up = L(lang, "promises · overdue", "करार · तारीख निकली")
    ans.actions = [(L(lang, "Open Karar", "करार खोलें"), "karar", {"bucket": "Overdue"})]
    return ans


def krar_today(svc, a, lang, today) -> Answer:
    ans = _krar_table(svc, svc.krar.entries("today", today), lang, today, "Promised for today", "आज के वादे")
    ans.looked_up = L(lang, "promises · today", "करार · आज")
    ans.actions = [(L(lang, "Open Karar", "करार खोलें"), "karar", {"bucket": "Today"})]
    return ans


def krar_upcoming(svc, a, lang, today) -> Answer:
    p: Period | None = a.get("period")
    if p is None:
        end = today + dt.timedelta(days=30)
    elif p.value == "this_week":
        end = p.start + dt.timedelta(days=6)
    elif p.value == "this_month":
        nxt = (p.start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        end = nxt - dt.timedelta(days=1)
    elif p.value.startswith("days:"):
        end = today + (p.end - p.start)
    else:
        end = max(p.end, today)
    entries = [e for e in svc.krar.entries("future", today) if e.last_date <= end.isoformat()]
    ans = _krar_table(svc, entries, lang, today, "Coming promises", "आने वाले वादे")
    ans.headline += L(lang, f" (until {end:%d-%m-%Y})", f" ({end:%d-%m-%Y} तक)")
    ans.looked_up = L(lang, "promises · coming", "करार · आने वाले")
    return ans


def top_debtors(svc, a, lang, today) -> Answer:
    n = int(a.get("number") or 10)
    cat = a.get("category")
    summaries = svc.categories.customer_summaries(scope="all" if cat else "settings")
    if cat:
        summaries = [s for s in summaries if s.category == cat]
    top = svc.reports.top_debtors(min(max(n, 1), 50), summaries)
    cust = {c.id: c for c in svc.accounts.list_customers()}
    rows = [(_cname(cust[s.id], lang), s.balance, s.days) for s in top]
    head = L(lang, f"Top {len(rows)} debtors", f"सबसे बड़े {len(rows)} बकायेदार") + (
        f" · {L(lang, 'category', 'श्रेणी')} {cat}" if cat else ""
    )
    return Answer(
        head,
        [L(lang, f"Together {rs(sum(r[1] for r in rows))}", f"कुल {rs(sum(r[1] for r in rows))}")],
        columns=[
            (L(lang, "Customer", "ग्राहक"), "text"),
            (L(lang, "Balance", "शेष"), "money"),
            (L(lang, "Idle days", "खाली दिन"), "int"),
        ],
        rows=rows,
        actions=[(L(lang, "Open report", "रिपोर्ट खोलें"), "reports", {"report": "top"})],
        looked_up=head,
    )


def collections(svc, a, lang, today) -> Answer:
    rows_all = svc.reports.collections(today)
    cust = {c.id: c for c in svc.accounts.list_customers()}
    rows = [
        (
            _cname(cust[r.id], lang),
            r.phone,
            r.balance,
            r.last_payment if r.last_payment != "never" else L(lang, "never", "कभी नहीं"),
        )
        for r in rows_all[:15]
    ]
    return Answer(
        L(
            lang,
            f"{len(rows_all)} people owe us · {rs(sum(r.balance for r in rows_all))}",
            f"{len(rows_all)} लोगों पर बकाया · {rs(sum(r.balance for r in rows_all))}",
        ),
        [L(lang, "Biggest first, with phone and last payment:", "सबसे बड़ा पहले, फ़ोन और पिछले भुगतान के साथ:")],
        columns=[
            (L(lang, "Customer", "ग्राहक"), "text"),
            (L(lang, "Phone", "फ़ोन"), "text"),
            (L(lang, "Balance", "शेष"), "money"),
            (L(lang, "Last paid", "पिछला भुगतान"), "text"),
        ],
        rows=rows,
        actions=[(L(lang, "Open collections list", "वसूली सूची खोलें"), "reports", {"report": "collections"})],
        looked_up=L(lang, "collections", "वसूली"),
    )


def total_receivable(svc, a, lang, today) -> Answer:
    k = svc.reports.kpis()
    return Answer(
        L(lang, f"Receivable {rs(k.receivable)}", f"कुल लेनदारी {rs(k.receivable)}"),
        [
            L(lang, f"{many(k.debtors, 'customer')} owe us", f"{k.debtors} ग्राहकों पर बकाया"),
            L(lang, f"We owe {rs(k.payable)}", f"हम पर देनदारी {rs(k.payable)}"),
        ],
        actions=[(L(lang, "Open dashboard", "डैशबोर्ड खोलें"), "dashboard", {})],
        looked_up=L(lang, "receivable", "लेनदारी"),
    )


def total_payable(svc, a, lang, today) -> Answer:
    k = svc.reports.kpis()
    return Answer(
        L(lang, f"We owe {rs(k.payable)}", f"हम पर कुल देनदारी {rs(k.payable)}"),
        [L(lang, f"Receivable {rs(k.receivable)}", f"लेनदारी {rs(k.receivable)}")],
        actions=[(L(lang, "Open dashboard", "डैशबोर्ड खोलें"), "dashboard", {})],
        looked_up=L(lang, "payable", "देनदारी"),
    )


def day_summary(svc, a, lang, today) -> Answer:
    p: Period = a.get("day") or resolve("today", today)
    t = svc.reports.day_totals(p.start.isoformat())
    label = period_label(p, lang)
    if not t.entries:
        return Answer(L(lang, f"{label}: nothing entered", f"{label}: कुछ दर्ज नहीं"), looked_up=label)
    return Answer(
        L(lang, f"{label}: sales / debits {rs(t.debit)}", f"{label}: बिक्री / नामे {rs(t.debit)}"),
        [
            L(lang, f"Received / credits {rs(t.credit)}", f"जमा {rs(t.credit)}"),
            L(lang, f"{t.entries} entries", f"{t.entries} एंट्री"),
        ],
        actions=[(L(lang, "Open day book", "रोज़नामचा खोलें"), "reports", {"report": "daybook"})],
        looked_up=L(lang, "day", "दिन") + f" · {label}",
    )


def period_sales(svc, a, lang, today) -> Answer:
    p: Period = a.get("period") or resolve("this_month", today)
    t = svc.reports.range_totals(p.start.isoformat(), p.end.isoformat())
    label = period_label(p, lang)
    return Answer(
        L(lang, f"{label}: sales / debits {rs(t.debit)}", f"{label}: बिक्री / नामे {rs(t.debit)}"),
        [
            L(lang, f"Received / credits {rs(t.credit)}", f"जमा {rs(t.credit)}"),
            L(lang, f"{t.entries} entries", f"{t.entries} एंट्री"),
        ],
        actions=[(L(lang, "Open monthly report", "मासिक रिपोर्ट खोलें"), "reports", {"report": "monthly"})],
        looked_up=L(lang, "sales", "बिक्री") + f" · {label}",
    )


def day_book(svc, a, lang, today) -> Answer:
    p: Period = a.get("day") or resolve("today", today)
    rows = svc.reports.day_book(p.start.isoformat())
    cust = {c.name: c for c in svc.accounts.list_customers()}
    label = period_label(p, lang)
    table = []
    for _id, name, desc, amount, tx_type, tag, _user in rows:
        if tag == "0" and desc in ("Settled Amount", "Discount"):
            continue
        c = cust.get(name)
        table.append(
            (
                _cname(c, lang) if c else name,
                desc,
                amount if tx_type == "P" else None,
                amount if tx_type == "M" else None,
            )
        )
    return Answer(
        L(lang, f"{label}: {len(table)} entries", f"{label}: {len(table)} एंट्री"),
        columns=[
            (L(lang, "Customer", "ग्राहक"), "text"),
            (L(lang, "Particulars", "विवरण"), "text"),
            (L(lang, "Debit", "नामे"), "money"),
            (L(lang, "Credit", "जमा"), "money"),
        ],
        rows=table,
        actions=[(L(lang, "Open day book", "रोज़नामचा खोलें"), "reports", {"report": "daybook"})],
        looked_up=L(lang, "day book", "रोज़नामचा") + f" · {label}",
    )


def _iname(i, lang) -> str:
    return (i.name_hi or i.name) if lang == "hi" else i.name


def item_stock(svc, a, lang, today) -> Answer:
    i = svc.inventory.get_item(a["item"])
    q = svc.inventory.quantity(i.id)
    since = (today - dt.timedelta(days=29)).isoformat()
    sold, _value, _n = svc.inventory.sales_between(i.id, since, today.isoformat())
    ans = Answer(
        f"{_iname(i, lang)} · " + L(lang, f"{qty(q)} {i.unit} in stock", f"स्टॉक में {qty(q)} {i.unit}"),
        actions=[(L(lang, "Open item", "सामान खोलें"), "items", {"item_id": i.id})],
        looked_up=L(lang, "stock", "स्टॉक") + f" · {_iname(i, lang)}",
    )
    if sold > 0:
        ans.lines.append(
            L(lang, f"Sold {qty(sold)} {i.unit} in the last 30 days", f"पिछले 30 दिन में {qty(sold)} {i.unit} बिका")
        )
        if q > 0:
            days = q / (sold / 30)
            ans.lines.append(
                L(lang, f"Lasts about {days:.0f} days at this rate", f"इस रफ़्तार से लगभग {days:.0f} दिन चलेगा")
            )
    if q <= 0:
        ans.lines.append(L(lang, "Out of stock", "स्टॉक ख़त्म"))
    return ans


def item_price(svc, a, lang, today) -> Answer:
    i = svc.inventory.get_item(a["item"])
    return Answer(
        f"{_iname(i, lang)} · "
        + L(lang, f"price {rs(i.last_value)} per {i.unit}", f"भाव {rs(i.last_value)} प्रति {i.unit}"),
        [L(lang, f"Cost {rs(i.stock_value)} per {i.unit}", f"लागत {rs(i.stock_value)} प्रति {i.unit}")],
        actions=[(L(lang, "Open item", "सामान खोलें"), "items", {"item_id": i.id})],
        looked_up=L(lang, "price", "भाव") + f" · {_iname(i, lang)}",
    )


def item_sales(svc, a, lang, today) -> Answer:
    i = svc.inventory.get_item(a["item"])
    p: Period = a.get("period") or resolve("this_month", today)
    sold, value, n = svc.inventory.sales_between(i.id, p.start.isoformat(), p.end.isoformat())
    label = period_label(p, lang)
    ans = Answer(
        f"{_iname(i, lang)} · {label}: " + L(lang, f"{qty(sold)} {i.unit} sold", f"{qty(sold)} {i.unit} बिका"),
        actions=[(L(lang, "Open item", "सामान खोलें"), "items", {"item_id": i.id})],
        looked_up=L(lang, "sales", "बिक्री") + f" · {_iname(i, lang)} · {label}",
    )
    if n:
        ans.lines.append(
            L(
                lang,
                f"{many(n, 'sale')}" + (f" · value {rs(value)}" if value else ""),
                f"{n} बार" + (f" · मूल्य {rs(value)}" if value else ""),
            )
        )
    return ans


_MONEY_ITEMS = {"CASH", "UPI", "BANK"}


def low_stock(svc, a, lang, today) -> Answer:
    items = [
        s
        for s in svc.inventory.low_stock(5)
        if s.item.category != "E"
        and s.item.name.strip().upper() not in _MONEY_ITEMS
        and s.item.unit.upper() not in ("INR", "RS")
    ]
    rows = [(_iname(s.item, lang), s.in_stock, s.item.unit) for s in sorted(items, key=lambda s: s.in_stock)][:30]
    return Answer(
        L(lang, f"{len(items)} items at 5 or less", f"{len(items)} सामान 5 या कम"),
        columns=[
            (L(lang, "Item", "सामान"), "text"),
            (L(lang, "In stock", "स्टॉक"), "qty"),
            (L(lang, "Unit", "इकाई"), "text"),
        ],
        rows=rows,
        actions=[(L(lang, "Open report", "रिपोर्ट खोलें"), "reports", {"report": "low"})],
        looked_up=L(lang, "low stock", "कम स्टॉक"),
    )


def reorder(svc, a, lang, today) -> Answer:
    from hth.services.insights import InsightsService

    lines = InsightsService(svc.db).reorder_suggestions(today=today)
    items = {i.id: i for i in svc.inventory.list_items()}
    rows = [(_iname(items[r.item_id], lang), r.in_stock, r.sold_window, r.days_left) for r in lines]
    return Answer(
        L(lang, f"{many(len(rows), 'item')} to reorder", f"{len(rows)} सामान मँगवाने हैं")
        if rows
        else L(lang, "Nothing to reorder right now", "अभी कुछ मँगवाने की ज़रूरत नहीं"),
        columns=[
            (L(lang, "Item", "सामान"), "text"),
            (L(lang, "In stock", "स्टॉक"), "qty"),
            (L(lang, "Sold in 30 days", "30 दिन में बिका"), "qty"),
            (L(lang, "Days left", "बचे दिन"), "qty"),
        ],
        rows=rows,
        actions=[(L(lang, "Open report", "रिपोर्ट खोलें"), "reports", {"report": "reorder"})],
        looked_up=L(lang, "reorder", "मँगवाना"),
    )


def expiring(svc, a, lang, today) -> Answer:
    found = [(s, d) for s, d in svc.inventory.expiring(60, today) if s.in_stock > 0]
    rows = [(_iname(s.item, lang), s.item.expiry_date, d, s.in_stock) for s, d in found]
    return Answer(
        L(lang, f"{many(len(rows), 'item')} expiring within 60 days", f"{len(rows)} सामान 60 दिन में एक्सपायर")
        if rows
        else L(lang, "Nothing expires in the next 60 days", "अगले 60 दिन में कुछ एक्सपायर नहीं"),
        columns=[
            (L(lang, "Item", "सामान"), "text"),
            (L(lang, "Expiry", "एक्सपायरी"), "text"),
            (L(lang, "Days left", "बचे दिन"), "int"),
            (L(lang, "In stock", "स्टॉक"), "qty"),
        ],
        rows=rows,
        actions=[(L(lang, "Open report", "रिपोर्ट खोलें"), "reports", {"report": "expiring"})],
        looked_up=L(lang, "expiring", "एक्सपायरी"),
    )


def _no_finance(lang) -> Answer:
    return Answer(L(lang, "The finance module is not set up", "वित्त मॉड्यूल चालू नहीं है"))


def profit(svc, a, lang, today) -> Answer:
    fin = svc.finance()
    if fin is None:
        return _no_finance(lang)
    p: Period = a.get("period") or resolve("this_fy", today)
    pl = fin.profit_and_loss(p.start.isoformat(), p.end.isoformat())
    label = period_label(p, lang)
    return Answer(
        L(lang, f"{label}: net profit {rs(pl.net_profit)}", f"{label}: शुद्ध लाभ {rs(pl.net_profit)}"),
        [
            L(
                lang,
                f"Margin on goods {rs(pl.gross_margin)} + other income {rs(pl.other_income)}"
                f" − expenses {rs(pl.total_expenses)}",
                f"सामान पर मुनाफ़ा {rs(pl.gross_margin)} + अन्य आय {rs(pl.other_income)} − खर्च {rs(pl.total_expenses)}",
            ),
            L(
                lang,
                "Interest on customer balances is not counted (not received yet).",
                "ग्राहकों पर चढ़ा ब्याज शामिल नहीं (अभी मिला नहीं)।",
            ),
        ],
        actions=[(L(lang, "Open Finance", "वित्त खोलें"), "finance", {})],
        looked_up=L(lang, "profit", "मुनाफ़ा") + f" · {label}",
    )


def expenses(svc, a, lang, today) -> Answer:
    fin = svc.finance()
    if fin is None:
        return _no_finance(lang)
    p: Period = a.get("period") or resolve("this_month", today)
    heads = fin.expenses_by_head(p.start.isoformat(), p.end.isoformat())
    label = period_label(p, lang)
    total = sum(v for _h, v in heads)
    return Answer(
        L(lang, f"{label}: expenses {rs(total)}", f"{label}: खर्च {rs(total)}"),
        columns=[(L(lang, "Head", "मद"), "text"), (L(lang, "Amount", "रकम"), "money")],
        rows=heads,
        actions=[(L(lang, "Open Finance", "वित्त खोलें"), "finance", {})],
        looked_up=L(lang, "expenses", "खर्च") + f" · {label}",
    )


def cash_balance(svc, a, lang, today) -> Answer:
    fin = svc.finance()
    if fin is None:
        return _no_finance(lang)
    balances = fin.balances()
    total = sum(b for _a, b in balances)
    return Answer(
        L(lang, f"Cash & bank {rs(total)}", f"नकद और बैंक {rs(total)}"),
        columns=[(L(lang, "Account", "खाता"), "text"), (L(lang, "Balance", "शेष"), "money")],
        rows=[(acc.name, b) for acc, b in balances],
        actions=[(L(lang, "Open Finance", "वित्त खोलें"), "finance", {})],
        looked_up=L(lang, "cash", "नकद"),
    )


def attention(svc, a, lang, today) -> Answer:
    from hth import i18n
    from hth.services.insights import InsightsService

    found = InsightsService(svc.db).collect(svc.categories.customer_summaries(), today)
    previous = i18n.language()
    i18n.set_language("hi" if lang == "hi" else "en")  # insight texts are English phrases in the table
    try:
        rows = [(i18n.tr(f.title), i18n.tr(f.detail)) for f in found]
    finally:
        i18n.set_language(previous)
    return Answer(
        L(lang, "Things to look at", "इन पर ध्यान दें"),
        columns=[(L(lang, "What", "क्या"), "text"), (L(lang, "Detail", "विवरण"), "text")],
        rows=rows,
        actions=[(L(lang, "Open dashboard", "डैशबोर्ड खोलें"), "dashboard", {})],
        looked_up=L(lang, "needs attention", "ध्यान दें"),
    )


_P = Slot("period", False)
_D = Slot("day", False)
TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool("customer_balance", customer_balance, (_CUSTOMER,), Permission.ADD_CUSTOMER),
        Tool("customer_ledger", customer_ledger, (_CUSTOMER, _P), Permission.ADD_CUSTOMER),
        Tool("customer_contact", customer_contact, (_CUSTOMER,), Permission.ADD_CUSTOMER),
        Tool("customer_interest", customer_interest, (_CUSTOMER,), Permission.ADD_CUSTOMER),
        Tool("customer_krar", customer_krar, (_CUSTOMER,), Permission.MANAGE_KRAR),
        Tool("krar_overdue", krar_overdue, (), Permission.MANAGE_KRAR),
        Tool("krar_today", krar_today, (), Permission.MANAGE_KRAR),
        Tool("krar_upcoming", krar_upcoming, (_P,), Permission.MANAGE_KRAR),
        Tool("top_debtors", top_debtors, (Slot("number", False), Slot("category", False)), Permission.VIEW_REPORTS),
        Tool("collections", collections, (), Permission.VIEW_REPORTS),
        Tool("total_receivable", total_receivable, (), Permission.VIEW_DASHBOARD),
        Tool("total_payable", total_payable, (), Permission.VIEW_DASHBOARD),
        Tool("day_summary", day_summary, (_D,), Permission.VIEW_REPORTS),
        Tool("period_sales", period_sales, (Slot("period", False),), Permission.VIEW_REPORTS),
        Tool("day_book", day_book, (_D,), Permission.VIEW_REPORTS),
        Tool("item_stock", item_stock, (_ITEM,), Permission.ADD_ITEM),
        Tool("item_price", item_price, (_ITEM,), Permission.ADD_ITEM),
        Tool("item_sales", item_sales, (_ITEM, _P), Permission.VIEW_REPORTS),
        Tool("low_stock", low_stock, (), Permission.VIEW_REPORTS),
        Tool("reorder", reorder, (), Permission.VIEW_REPORTS),
        Tool("expiring", expiring, (), Permission.VIEW_REPORTS),
        Tool("profit", profit, (_P,), Permission.FINANCE_REPORTS),
        Tool("expenses", expenses, (_P,), Permission.FINANCE),
        Tool("cash_balance", cash_balance, (), Permission.FINANCE),
        Tool("attention", attention, (), Permission.VIEW_DASHBOARD),
    )
}
