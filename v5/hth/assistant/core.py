"""The assistant: question in, answer out - no Tk, so a chat screen, a WhatsApp / Telegram
bot or a voice loop can all use it.

    assistant = Assistant(db, user)
    session = Session()
    reply = assistant.ask("Ramesh ka last month ka hisab btao", session)
    reply.options  ->  "कौन से रमेश?" with three choices
    reply = assistant.ask("2", session)  ->  the ledger, and the question is settled

Pipeline: language -> entity linking (names become ``<C1>`` / ``<I1>``) -> System 1 intent ->
re-rank by what the question mentions -> slots (period, day, number, category) -> ask back
for anything missing or ambiguous -> run the read-only tool -> answer in the question's
language.  System 2 (a small language model) is consulted only when System 1 is unsure.
"""

from __future__ import annotations

import copy
import datetime as dt
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hth.assistant import normalize as norm
from hth.assistant.entities import Candidate, EntityIndex, resolve_choice
from hth.assistant.tools import TOOLS, L, Services, Tool
from hth.services.permissions import has_permission

if TYPE_CHECKING:
    # System 1 brings numpy, a quarter of a second at start-up: loaded on the first question
    from hth.assistant.system1 import IntentClassifier

log = logging.getLogger(__name__)

CONFIDENT = 0.55  # System 1 probability needed to answer without asking
FOLLOWUP_SECONDS = 120
_MADE_SENSE = ("answer", "help", "greeting", "cancelled")
_CANCEL = {norm.key(w) for w in "cancel chhodo chodo rehne rahne nahi no stop band bas".split()}
_ALSO = {norm.key(w) for w in "aur and bhi also phir about".split()}  # "aur pichle mahine?"
_PRONOUN = {norm.key(w) for w in "usi uska uski uske unka unki unke iska iski iske his her their same".split()}
_SINGLE_DAY_TWINS = {"period_sales": "day_summary"}  # a range question about one day
_RANGE_TWINS = {"day_summary": "period_sales"}
_CHAT_INTENTS = ("help", "greeting", "unsupported")  # answered without a tool


@dataclass
class Option:
    label: str
    reply: str  # what to send back when this option is tapped


@dataclass
class Reply:
    lang: str
    kind: str  # answer | ask | unsure | help | greeting | decline | error | cancelled
    text: str
    lines: list[str] = field(default_factory=list)
    columns: list[tuple[str, str]] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    actions: list[tuple[str, str, dict]] = field(default_factory=list)
    looked_up: str = ""
    tool: str | None = None
    args: dict = field(default_factory=dict)
    source: str = ""  # system1 | system2 | followup | clarified
    confidence: float = 0.0


@dataclass
class Pending:
    """The one open question: a tool waiting for one slot (and, if ambiguous, its options)."""

    tool: str
    args: dict
    slot: str
    lang: str
    options: list[Candidate] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)  # "did you mean" choices
    text: str = ""


@dataclass
class Session:
    pending: Pending | None = None
    last_tool: str | None = None
    last_args: dict = field(default_factory=dict)
    last_time: float = 0.0
    history: list[tuple[str, Reply]] = field(default_factory=list)

    def settle(self, reply: Reply) -> None:
        """An answered question leaves the context; only a quick follow-up may reuse it."""
        self.pending = None
        if reply.kind == "answer" and reply.tool:
            self.last_tool, self.last_args, self.last_time = reply.tool, dict(reply.args), time.monotonic()


class Assistant:
    def __init__(self, db, user=None, model_dir=None, today=None, system2=None, classifier=None):
        self.db = db
        self.user = user
        self.services = Services(db)
        self._today = today
        self._index: EntityIndex | None = None
        self._index_time = 0.0
        self._classifier: IntentClassifier | None = classifier
        self.model_dir = model_dir
        self.system2 = system2  # object with .available() and .call(text) -> (intent, args) | None
        self.voice_spellings: dict[str, str] = {}  # stored Hindi word -> how the recogniser writes it
        self._dry = False  # trying a hearing out: no audit lines
        self._s2_cache: dict[str, tuple[str, dict] | None] = {}

    # Lazy parts ------------------------------------------------------------------------------
    @property
    def today(self) -> dt.date:
        return self._today or dt.date.today()

    @property
    def classifier(self) -> IntentClassifier:
        if self._classifier is None:
            from hth.assistant.system1 import IntentClassifier

            self._classifier = IntentClassifier.cached(self.model_dir)
        return self._classifier

    def index(self) -> EntityIndex:
        if self._index is None or time.monotonic() - self._index_time > 60:  # new customers appear
            self._index = EntityIndex.from_db(self.db, self.today)
            if self.voice_spellings:
                self._index.add_spellings(self.voice_spellings)
            self._index_time = time.monotonic()
        return self._index

    def set_voice_spellings(self, spellings: dict[str, str]) -> None:
        self.voice_spellings = dict(spellings)
        self._index = None

    def warm_up(self) -> None:
        """Train / load System 1 and index names (call from a background thread)."""
        _ = self.classifier
        self.index()

    # Main entry --------------------------------------------------------------------------------
    def ask(self, text: str, session: Session) -> Reply:
        text = (text or "").strip()
        lang = norm.answer_language(text) if text else "hi"
        if not text:
            return self._help(lang)
        try:
            if session.pending is not None:
                reply = self._continue(text, session)
                if reply is not None:
                    session.history.append((text, reply))
                    return reply
            reply = self._new(text, session, lang)
        except Exception as exc:  # noqa: BLE001 - never crash the chat
            log.exception("assistant failed on %r", text)
            reply = Reply(lang, "error", L(lang, f"Something went wrong: {exc}", f"कुछ गड़बड़ हो गई: {exc}"))
        session.history.append((text, reply))
        if reply.kind in ("answer", "help", "greeting", "decline", "error", "cancelled"):
            session.settle(reply)
        return reply

    def ask_heard(self, heard: str, session: Session, alternative=None) -> tuple[str, Reply]:
        """A spoken question.  ``heard`` is System 1 voice's (restricted) hearing; when it does not
        make sense, ``alternative()`` - the open-vocabulary hearing of the same audio, computed only
        then - is tried.  Returns the text that was used and its reply."""
        if alternative is None or session.pending is not None:  # a short reply to a question asked
            return heard, self.ask(heard, session)
        if self._try(heard, session).kind in _MADE_SENSE:
            return heard, self.ask(heard, session)
        other = (alternative() or "").strip()
        if other and other != heard and self._try(other, session).kind in _MADE_SENSE:
            return other, self.ask(other, session)
        return heard, self.ask(heard, session)

    def _try(self, text: str, session: Session) -> Reply:
        """What ``text`` would get, without touching ``session`` or the audit log."""
        trial = Session(copy.deepcopy(session.pending), session.last_tool, dict(session.last_args), session.last_time)
        self._dry = True
        try:
            return self.ask(text, trial)
        finally:
            self._dry = False

    # A reply to an open question ------------------------------------------------------------
    def _continue(self, text: str, session: Session) -> Reply | None:
        p = session.pending
        lang = p.lang if norm.language(text) != "hi" else "hi"
        words = set(norm.keys(text))
        if words & _CANCEL and len(words) <= 3:
            session.pending = None
            return Reply(lang, "cancelled", L(lang, "OK, left it.", "ठीक है, छोड़ दिया।"))
        if p.intents:  # "did you mean" - by number or by name of the choice
            pick = _pick_index(text, len(p.intents))
            if pick is not None:
                session.pending = None
                intent = p.intents[pick]
                return self._run_intent(intent, p.text, session, p.lang, source="clarified", prob=1.0)
            return None
        if p.options:
            choice = resolve_choice(text, p.options)
            if choice is None:
                linked = self.index().link(text, (p.slot,)).first(p.slot)
                if linked and not linked.ambiguous:
                    choice = linked.best
            if choice is None:
                if len(norm.tokens(text)) <= 3:  # a short reply that fits nothing: ask again
                    return self._ask_options(p.tool, p.args, p.slot, p.options, p.lang, session, again=True)
                session.pending = None
                return None  # a new question
            args = dict(p.args, **{p.slot: choice.id})
            session.pending = None
            return self._complete(p.tool, args, p.lang, session, text=p.text, source="clarified")
        # a missing slot: the reply should name it
        mention = self.index().link(text, (p.slot,)).first(p.slot)
        if mention is None:
            if len(norm.tokens(text)) <= 3:
                return self._ask_slot(p.tool, p.args, p.slot, p.lang, session, again=True)
            session.pending = None
            return None
        if mention.ambiguous:
            return self._ask_options(p.tool, p.args, p.slot, mention.candidates, p.lang, session)
        session.pending = None
        return self._complete(
            p.tool, dict(p.args, **{p.slot: mention.best.id}), p.lang, session, text=p.text, source="clarified"
        )

    # A new question ---------------------------------------------------------------------------
    def _new(self, text: str, session: Session, lang: str) -> Reply:
        link = self.index().link(text)
        masked = link.placeholder_text()
        ranked = route(self.classifier, masked, self.today)
        intent, prob = ranked[0]
        # follow-ups right after an answer: "aur pichle mahine?" repeats the last question with
        # what changed; "uska phone number" asks something new about the same customer / item
        words = set(norm.keys(text))
        recent = session.last_tool and time.monotonic() - session.last_time < FOLLOWUP_SECONDS
        carry: dict = {}
        if recent and words & _ALSO and len(_content_words(masked)) <= 1:
            reply = self._followup(text, link, session, lang)
            if reply is not None:
                return reply
        if recent and words & _PRONOUN:
            carry = {k: v for k, v in session.last_args.items() if k in ("customer", "item")}
            if carry:
                ranked = route(self.classifier, masked + "".join(f" <{k[0].upper()}1>" for k in carry), self.today)
                intent, prob = ranked[0]
        source = "system1"
        if prob < CONFIDENT and self.system2 is not None and self.system2.available():
            if masked not in self._s2_cache:  # a spoken question may be tried, then asked
                self._s2_cache = {masked: self.system2.call(masked)} | dict(list(self._s2_cache.items())[:20])
            call = self._s2_cache[masked]  # only its choice of tool is used; slots stay ours
            # it only settles a tie among System 1's own three best guesses; anything else is asked
            # back (measured on Kaggle: 11 wrong answers instead of 19 per 113 unsure questions)
            top = {i for i, _p in ranked[:3]}
            if call is not None and call[0] in top and (call[0] in TOOLS or call[0] in _CHAT_INTENTS):
                intent, prob, source = call[0], max(prob, CONFIDENT), "system2"
        if prob < CONFIDENT:
            choices = [i for i, _p in ranked[:3] if i in TOOLS]
            if choices:
                session.pending = Pending(choices[0], {}, "", lang, intents=choices, text=text)
                return Reply(
                    lang,
                    "unsure",
                    L(lang, "I am not sure what you mean. Did you mean:", "मैं ठीक से समझ नहीं पाया। क्या आपका मतलब है:"),
                    options=[Option(f"{k + 1} · {_title(c, lang)}", str(k + 1)) for k, c in enumerate(choices)],
                    confidence=prob,
                )
        return self._run_intent(intent, text, session, lang, source=source, prob=prob, link=link, carry=carry)

    def _run_intent(self, intent, text, session, lang, source="system1", prob=1.0, link=None, carry=None) -> Reply:
        if intent == "help":
            return self._help(lang)
        if intent == "greeting":
            return Reply(
                lang,
                "greeting",
                L(
                    lang,
                    "Namaste! Ask me about balances, karar, stock or sales.",
                    "नमस्ते! बकाया, करार, स्टॉक या बिक्री के बारे में पूछिए।",
                ),
                source=source,
            )
        if intent == "unsupported" or intent not in TOOLS:
            return Reply(
                lang,
                "decline",
                L(
                    lang,
                    "I can only answer about the shop's accounts and stock.",
                    "मैं केवल दुकान के हिसाब और स्टॉक के बारे में बता सकता हूँ।",
                ),
                source=source,
            )
        link = link or self.index().link(text)
        masked = link.placeholder_text()
        tool = TOOLS[intent]
        args: dict = {}
        period = norm.find_period(masked, self.today)
        day = norm.find_day(masked, self.today)
        if intent in _SINGLE_DAY_TWINS and period is not None and period.single_day:
            intent, tool = _SINGLE_DAY_TWINS[intent], TOOLS[_SINGLE_DAY_TWINS[intent]]
        elif intent in _RANGE_TWINS and period is not None and not period.single_day:
            intent, tool = _RANGE_TWINS[intent], TOOLS[_RANGE_TWINS[intent]]
        for slot in tool.slots:
            if slot.name == "period" and period is not None:
                args["period"] = period
            elif slot.name == "day" and day is not None:
                args["day"] = day
            elif slot.name == "number":
                n = norm.find_number(masked)
                if n is not None and 0 < n <= 100:
                    args["number"] = int(n)
            elif slot.name == "category":
                c = norm.find_category(masked)
                if c:
                    args["category"] = c
        for slot in tool.slots:
            if slot.name not in ("customer", "item"):
                continue
            mention = link.first(slot.name)
            if mention is None and carry and slot.name in carry:
                args[slot.name] = carry[slot.name]
                continue
            if mention is None:
                if slot.required:
                    return self._ask_slot(intent, args, slot.name, lang, session, text=text)
                continue
            if mention.ambiguous:
                return self._ask_options(intent, args, slot.name, mention.candidates, lang, session, text=text)
            args[slot.name] = mention.best.id
        return self._complete(intent, args, lang, session, text=text, source=source, prob=prob)

    def _complete(self, intent, args, lang, session, text="", source="system1", prob=1.0) -> Reply:
        tool = TOOLS[intent]
        for slot in tool.slots:  # still something required and missing?
            if slot.required and slot.name not in args:
                return self._ask_slot(intent, args, slot.name, lang, session, text=text)
        if self.user is not None and tool.permission is not None and not has_permission(self.user, tool.permission):
            return Reply(lang, "decline", L(lang, "You do not have access to this.", "यह जानकारी आपके लिए नहीं है।"))
        ans = tool.run(self.services, args, lang, self.today)
        self._audit(intent, args)
        return Reply(
            lang,
            "answer",
            ans.headline,
            ans.lines,
            ans.columns,
            ans.rows,
            [],
            ans.actions,
            ans.looked_up,
            intent,
            args,
            source,
            prob,
        )

    def _followup(self, text, link, session, lang) -> Reply | None:
        tool = TOOLS[session.last_tool]
        args = dict(session.last_args)
        masked = link.placeholder_text()
        period = norm.find_period(masked, self.today)
        names = {s.name for s in tool.slots}
        named = {m.kind for m in link.mentions}
        if named - names or (period is None and not named):
            return None  # "aur dap?" after a reorder list is a new question about DAP
        for slot in tool.slots:
            if slot.name in ("period", "day") and period is not None:
                args[slot.name] = period
            elif slot.name in ("customer", "item"):
                m = link.first(slot.name)
                if m is not None:
                    if m.ambiguous:
                        return self._ask_options(tool.name, args, slot.name, m.candidates, lang, session, text=text)
                    args[slot.name] = m.best.id
        return self._complete(tool.name, args, lang, session, text=text, source="followup")

    # Asking back -------------------------------------------------------------------------------
    def _ask_slot(self, intent, args, slot, lang, session, text="", again=False) -> Reply:
        tool_slot = next(s for s in TOOLS[intent].slots if s.name == slot)
        session.pending = Pending(intent, dict(args), slot, lang, text=text)
        question = tool_slot.ask_hi if lang == "hi" else tool_slot.ask_en
        if again:
            question = L(lang, "I could not find that. ", "यह नाम नहीं मिला। ") + question
        return Reply(lang, "ask", question, lines=[L(lang, "Type the name (or 'cancel').", "नाम लिखें (या 'छोड़ो')।")])

    def _ask_options(self, intent, args, slot, candidates, lang, session, text="", again=False) -> Reply:
        options = list(candidates)[:6]
        session.pending = Pending(intent, dict(args), slot, lang, options=options, text=text)
        if slot == "customer":
            q = L(lang, "Which one?", "कौन से?")
            first = options[0].name_hi or options[0].name if lang == "hi" else options[0].name.title()
            first_word = first.split()[0] if first else ""
            q = L(lang, f"Which {first_word}?", f"कौन से {first_word}?")
        else:
            q = L(lang, "Which item?", "कौन सा सामान?")
        if again:
            q = L(lang, "Please pick one: ", "इनमें से एक चुनें: ") + q
        return Reply(
            lang,
            "ask",
            q,
            lines=[L(lang, "Reply with the number, or a word like the village.", "नंबर लिखें, या गाँव जैसा कोई शब्द।")],
            options=[Option(f"{k + 1} · {c.label(lang)}", str(k + 1)) for k, c in enumerate(options)],
        )

    def _help(self, lang) -> Reply:
        examples = {
            "hi": [
                "रमेश का कितना बकाया है?",
                "किसके करार की तारीख निकल गई?",
                "यूरिया कितना बचा है?",
                "पिछले महीने कितनी बिक्री हुई?",
                "कल की एंट्री दिखाओ",
                "क्या मँगवाना है?",
                "इस साल कितना मुनाफ़ा हुआ?",
            ],
            "en": [
                "How much does Ramesh owe?",
                "Whose promises are overdue?",
                "How much urea is left?",
                "Sales last month",
                "Show yesterday's entries",
                "What should I reorder?",
                "Profit this year",
            ],
        }[lang]
        return Reply(
            lang,
            "help",
            L(lang, "You can ask me things like:", "आप ऐसे पूछ सकते हैं:"),
            options=[Option(e, e) for e in examples],
        )

    def _audit(self, intent, args) -> None:
        if self._dry:
            return
        try:
            from hth.domain.constants import AuditCode
            from hth.services.audit import AuditService

            shown = {k: (v.value if hasattr(v, "value") else v) for k, v in args.items()}
            AuditService(self.db).log(
                AuditCode.ASSISTANT, f"assistant {intent} {shown}", self.user.username if self.user else "system"
            )
        except Exception:  # noqa: BLE001 - logging must not break an answer
            log.exception("assistant audit failed")


def _title(intent: str, lang: str) -> str:
    titles = {
        "customer_balance": ("a customer's balance", "किसी का बकाया"),
        "customer_ledger": ("a customer's account", "किसी का हिसाब"),
        "customer_contact": ("a phone number", "फ़ोन नंबर"),
        "customer_interest": ("interest on an account", "खाते पर ब्याज"),
        "customer_krar": ("a customer's promise", "किसी का करार"),
        "krar_overdue": ("overdue promises", "तारीख निकले करार"),
        "krar_today": ("today's promises", "आज के करार"),
        "krar_upcoming": ("coming promises", "आने वाले करार"),
        "top_debtors": ("biggest debtors", "सबसे बड़े बकायेदार"),
        "collections": ("collection list", "वसूली सूची"),
        "total_receivable": ("total receivable", "कुल लेनदारी"),
        "total_payable": ("what we owe", "कुल देनदारी"),
        "day_summary": ("one day's sales", "एक दिन की बिक्री"),
        "period_sales": ("sales in a period", "अवधि की बिक्री"),
        "day_book": ("a day's entries", "दिन की एंट्री"),
        "item_stock": ("stock of an item", "सामान का स्टॉक"),
        "item_price": ("price of an item", "सामान का भाव"),
        "item_sales": ("sales of an item", "सामान की बिक्री"),
        "low_stock": ("low stock", "कम स्टॉक"),
        "reorder": ("what to reorder", "क्या मँगवाना है"),
        "expiring": ("expiring items", "एक्सपायर होने वाला सामान"),
        "profit": ("profit", "मुनाफ़ा"),
        "expenses": ("expenses", "खर्च"),
        "cash_balance": ("cash and bank", "नकद और बैंक"),
        "attention": ("what needs attention", "ध्यान देने वाली बातें"),
    }
    en, hi = titles.get(intent, (intent, intent))
    return hi if lang == "hi" else en


_GRAMMAR = {
    norm.key(w)
    for w in (
        "ka ki ke hai h hain kya batao btao bata dikhao dikha bolo se ko ne me mein ji bhai zara to toh ab abhi "
        "the a an of for is are was what how please tell show me give do does did can you it its"
    ).split()
}


def _content_words(masked: str) -> list[str]:
    """Words left once names, periods, follow-up markers and grammar are removed - none (or
    one, after "aur") means the question only changes something about the previous one."""
    rest = norm.strip_period_words(masked)
    return [t for t in norm.keys(rest) if t not in _GRAMMAR and t not in _ALSO and not t.startswith("<")]


def _pick_index(text: str, n: int) -> int | None:
    from hth.assistant.entities import _ORDINALS

    for t in norm.keys(text):
        if t in _ORDINALS and _ORDINALS[t] < n:
            return _ORDINALS[t]
    return None


def route(classifier: IntentClassifier, masked: str, today: dt.date) -> list[tuple[str, float]]:
    """System 1's ranking, corrected by what the question plainly contains."""
    if not _content_words(masked) and norm.find_period(masked, today) is None:
        if "<I1>" in masked and "<C1>" not in masked:  # just "urea?" - the stock
            return [("item_stock", 1.0)]
        if "<C1>" in masked and "<I1>" not in masked:  # just "Ramesh?" - the balance
            return [("customer_balance", 1.0)]
    ranked = _rerank(classifier.predict(masked, top=6).ranked, masked, _unknown_words(classifier, masked))
    period = norm.find_period(masked, today)
    if period is not None:  # one day vs a range decides between the two sales summaries
        twins = _SINGLE_DAY_TWINS if period.single_day else _RANGE_TWINS
        merged: dict[str, float] = {}
        for intent, p in ranked:
            target = twins.get(intent, intent)
            merged[target] = merged.get(target, 0.0) + p
        ranked = sorted(merged.items(), key=lambda t: -t[1])
    return ranked


def _unknown_words(classifier: IntentClassifier, masked: str) -> bool:
    """Is there a word the assistant has never seen - most likely a name it could not find?"""
    from hth.assistant.system1 import concept

    return any(f"w:{t}" not in classifier.vocab and concept(t) is None for t in _content_words(masked))


def _rerank(ranked: list[tuple[str, float]], masked: str, unknown: bool = True) -> list[tuple[str, float]]:
    """Prefer intents that use what the question names: a customer named -> a customer
    question; an item named -> an item question; nothing named -> not a per-customer tool."""
    has_c, has_i = "<C1>" in masked, "<I1>" in masked
    out = []
    for intent, p in ranked:
        tool: Tool | None = TOOLS.get(intent)
        names = {s.name for s in tool.slots} if tool else set()
        factor = 1.0
        if has_c and "customer" not in names:
            factor *= 0.1
        if has_i and "item" not in names:
            factor *= 0.1
        # nothing named: "kal ka hisab" is the day, not a customer - unless an unknown word
        # (a name not in the shop's list) suggests one was meant, then we ask which
        if not has_c and "customer" in names:
            factor *= 0.6 if unknown else 0.15
        if not has_i and "item" in names:
            factor *= 0.6 if unknown else 0.15
        out.append((intent, p * factor))
    total = sum(p for _i, p in out) or 1.0
    out = [(i, p / total) for i, p in out]
    return sorted(out, key=lambda t: -t[1])
