"""Synthetic training data for the assistant - one source for System 1 and System 2.

**Self-contained on purpose** (standard library only, no ``hth`` imports): the Kaggle
training cell embeds this file verbatim, so the model is trained on exactly the
phrasings the app's own System 1 learns from.

Each intent has templates in three styles - English (``en``), Hindi in Devanagari
(``hi``) and Hinglish / Roman Hindi (``hl``).  Placeholders:

* ``{C}`` a customer, ``{I}`` an item - always replaced by ``<C1>`` / ``<I1>`` (the app's
  entity linker substitutes real names the same way before any model sees the text);
* ``{P}`` a period phrase, ``{D}`` a day phrase, ``{N}`` a number, ``{CAT}`` a category.

``generate()`` returns examples ``(text, intent, args, style, template_id)``; the split
is *by template*, so held-out examples are phrasings never seen in training.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field

CORPUS_VERSION = "2026-10-20.5"
_PLACEHOLDER = re.compile(r"<[A-Za-z]\d>")

# --- slot fillers: (style -> phrases) and the canonical value they mean ----------------
PERIODS: list[tuple[str, dict[str, list[str]]]] = [
    ("today", {"en": ["today", "for today"], "hi": ["आज", "आज का"], "hl": ["aaj", "aaj ka", "aj"]}),
    ("yesterday", {"en": ["yesterday"], "hi": ["कल", "कल का"], "hl": ["kal", "kal ka", "kl"]}),
    ("this_week", {"en": ["this week"], "hi": ["इस हफ्ते", "इस सप्ताह"], "hl": ["is hafte", "is week", "es hafte"]}),
    (
        "last_week",
        {
            "en": ["last week", "previous week"],
            "hi": ["पिछले हफ्ते"],
            "hl": ["pichle hafte", "pichhle hafte", "last week"],
        },
    ),
    (
        "this_month",
        {"en": ["this month"], "hi": ["इस महीने"], "hl": ["is mahine", "is mahine ka", "es mahine", "is month"]},
    ),
    (
        "last_month",
        {
            "en": ["last month", "previous month"],
            "hi": ["पिछले महीने", "पिछला महीना"],
            "hl": ["pichle mahine", "pichhle mahine", "pichla mahina", "last month", "pichle month"],
        },
    ),
    (
        "this_fy",
        {
            "en": ["this year", "this financial year"],
            "hi": ["इस साल", "इस वर्ष"],
            "hl": ["is saal", "is sal", "es saal"],
        },
    ),
    ("last_fy", {"en": ["last year"], "hi": ["पिछले साल"], "hl": ["pichle saal", "pichhle sal", "pichla saal"]}),
    ("month:3", {"en": ["in march"], "hi": ["मार्च में"], "hl": ["march mein", "march me"]}),
    ("month:10", {"en": ["in october"], "hi": ["अक्टूबर में"], "hl": ["october mein", "oct me"]}),
    ("days:7", {"en": ["last 7 days", "past week"], "hi": ["पिछले 7 दिन"], "hl": ["pichle 7 din", "last 7 din"]}),
    ("days:30", {"en": ["last 30 days"], "hi": ["पिछले 30 दिन"], "hl": ["pichle 30 din"]}),
]
DAYS: list[tuple[str, dict[str, list[str]]]] = [
    ("today", {"en": ["today"], "hi": ["आज"], "hl": ["aaj", "aj"]}),
    ("yesterday", {"en": ["yesterday"], "hi": ["कल"], "hl": ["kal"]}),
    ("dom:15", {"en": ["on the 15th"], "hi": ["15 तारीख"], "hl": ["15 tarikh", "15 tareekh"]}),
    ("dom:1", {"en": ["on the 1st"], "hi": ["1 तारीख"], "hl": ["1 tarikh"]}),
]
NUMBERS = [3, 5, 10, 15, 20]
CATEGORIES = ["A", "B", "C", "D"]

# --- intents --------------------------------------------------------------------------
# name -> (slots, {style: [templates]})
INTENTS: dict[str, tuple[list[str], dict[str, list[str]]]] = {
    "customer_balance": (
        ["customer"],
        {
            "en": [
                "how much does {C} owe",
                "what is {C}'s balance",
                "balance of {C}",
                "{C} balance",
                "how much is due from {C}",
                "tell me {C}'s dues",
                "what does {C} have to pay",
                "{C} outstanding",
                "is {C} still owing money",
                "pending amount of {C}",
                "{C} dues please",
                "what is left for {C} to pay",
                "what is {C}'s balance",
                "how much is pending from {C}",
            ],
            "hi": [
                "{C} का कितना बकाया है",
                "{C} का बकाया",
                "{C} पर कितने पैसे बाकी हैं",
                "{C} को कितना देना है",
                "{C} का शेष बताओ",
                "{C} की बाकी रकम",
                "{C} को कितने पैसे देने हैं",
                "{C} पर कितना निकलता है",
            ],
            "hl": [
                "{C} ka kitna baaki hai",
                "{C} ka kitna baki h",
                "{C} ka balance kitna hai",
                "{C} pe kitna udhaar hai",
                "{C} ke kitne paise baaki hai",
                "{C} ka bakaya batao",
                "{C} ka kitna lena hai",
                "{C} se kitna lena h",
                "{C} ka baki",
                "{C} kitna dega",
                "{C} pe kitna nikalta hai",
                "{C} ko kitne paise dene hain",
                "{C} ka kitna lena hai",
            ],
        },
    ),
    "customer_ledger": (
        ["customer", "period?"],
        {
            "en": [
                "show {C}'s account",
                "{C} ledger {P}",
                "statement of {C} {P}",
                "show entries of {C} {P}",
                "what did {C} buy {P}",
                "{C}'s transactions {P}",
                "{C} history",
                "full account of {C}",
                "what happened in {C}'s account {P}",
            ],
            "hi": [
                "{C} का हिसाब बताओ",
                "{C} का {P} का हिसाब",
                "{C} का खाता दिखाओ",
                "{C} की {P} की एंट्री",
                "{C} ने {P} क्या लिया",
            ],
            "hl": [
                "{C} ka hisab batao",
                "{C} ka {P} ka hisab btao",
                "{C} ka khata dikhao",
                "{C} ki entry dikhao {P}",
                "{C} ne {P} kya liya",
                "{C} ka hisaab",
                "{C} ka {P} ka hisaab batao",
                "{C} ka khata",
            ],
        },
    ),
    "customer_contact": (
        ["customer"],
        {
            "en": [
                "what is {C}'s phone number",
                "{C} mobile number",
                "contact of {C}",
                "number of {C}",
                "give me {C}'s number",
                "{C} phone",
                "how do I call {C}",
                "contact details of {C}",
            ],
            "hi": ["{C} का नंबर", "{C} का मोबाइल नंबर बताओ", "{C} का फ़ोन नंबर क्या है"],
            "hl": [
                "{C} ka number",
                "{C} ka mobile number batao",
                "{C} ka phone no",
                "{C} ka no do",
                "{C} ka contact",
                "{C} ka phone number kya hai",
            ],
        },
    ),
    "customer_interest": (
        ["customer"],
        {
            "en": ["how much interest on {C}", "interest of {C}", "{C} interest amount"],
            "hi": ["{C} का ब्याज कितना हुआ", "{C} पर कितना ब्याज लगा"],
            "hl": ["{C} ka byaj kitna hua", "{C} ka interest kitna", "{C} pe kitna byaaj laga"],
        },
    ),
    "customer_krar": (
        ["customer"],
        {
            "en": [
                "when did {C} promise to pay",
                "{C} promise date",
                "{C}'s krar",
                "when will {C} pay",
                "what date did {C} give",
                "{C} payment promise",
                "has {C} promised a date",
                "what date did {C} promise",
                "{C} promise date",
            ],
            "hi": [
                "{C} ने कब देने का वादा किया",
                "{C} का करार कब का है",
                "{C} की वादे की तारीख",
                "{C} कब पैसे देगा",
                "{C} ने कौन सी तारीख दी",
            ],
            "hl": [
                "{C} ne kab dene ka vada kiya",
                "{C} ka karar kab ka hai",
                "{C} ka krar",
                "{C} kab paise dega",
                "{C} kab paise dega",
                "{C} ne kya tarikh di",
                "{C} ka vada kab ka hai",
            ],
        },
    ),
    "krar_overdue": (
        [],
        {
            "en": [
                "whose promises are overdue",
                "overdue promises",
                "who missed their payment date",
                "late payers",
                "show overdue krar",
                "who has not paid on the promised date",
                "missed promises",
                "promises past due",
                "who broke their promise",
                "promises not kept",
                "overdue payments",
            ],
            "hi": ["किसके करार की तारीख निकल गई", "जिनका वादा निकल गया", "किसने वादा तोड़ा", "देर वाले करार दिखाओ"],
            "hl": [
                "kiske karar ki tarikh nikal gayi",
                "kiska vada nikal gaya",
                "overdue karar dikhao",
                "kisne time pe paisa nahi diya",
                "jinka krar nikal gaya",
                "late wale karar",
                "kaun time par nahi aaya",
                "jinhone vada toda",
                "vade ki date nikal gayi kiski",
                "kisne vade pe paisa nahi diya",
                "jinki tarikh nikal gayi",
            ],
        },
    ),
    "krar_today": (
        [],
        {
            "en": [
                "who promised to pay today",
                "today's promises",
                "whose krar is today",
                "who will pay today",
                "payments promised for today",
                "whose promise is today",
                "who promised to pay today",
            ],
            "hi": ["आज किसका करार है", "आज किसने पैसे देने का वादा किया", "आज के वादे"],
            "hl": [
                "aaj kiska karar hai",
                "aaj kisne paise dene the",
                "aaj ke vade",
                "aaj kiska krar h",
                "aaj kiska vada hai",
                "aaj kaun paise dega",
            ],
        },
    ),
    "krar_upcoming": (
        ["period?"],
        {
            "en": [
                "upcoming promises",
                "who will pay {P}",
                "money expected {P}",
                "promised payments coming",
                "who is going to pay {P}",
                "promises due {P}",
                "expected payments {P}",
                "coming promises",
                "who will pay soon",
                "next promised payments",
            ],
            "hi": ["{P} किसका पैसा आना है", "आने वाले करार", "{P} कौन पैसे देगा", "आने वाले वादे", "आगे कौन कौन पैसे देगा"],
            "hl": [
                "{P} kiska paisa aana hai",
                "aane wale karar",
                "{P} kaun paise dega",
                "agle karar dikhao",
                "aane wale vade",
                "agle karar kiske hain",
                "aage kaun kaun paise dega",
            ],
        },
    ),
    "top_debtors": (
        ["number?", "category?"],
        {
            "en": [
                "top {N} debtors",
                "who owes the most",
                "biggest dues",
                "top debtors in category {CAT}",
                "largest balances",
                "who has the highest balance",
                "top {N} dues",
                "list the biggest debtors",
                "highest outstanding customers",
            ],
            "hi": ["सबसे ज़्यादा किसका बकाया है", "सबसे बड़े {N} देनदार", "सबसे ज़्यादा उधार किस पर है"],
            "hl": [
                "sabse jyada kiska baaki hai",
                "top {N} udhaar wale",
                "sabse bade bakayedar",
                "sabse zyada kiska baki h",
                "category {CAT} ke top bakayedar",
                "sabse bade {N} bakayedar dikhao",
                "kiska sabse jyada udhaar hai",
            ],
        },
    ),
    "collections": (
        [],
        {
            "en": [
                "who should I collect money from",
                "collection list",
                "whom to call for payment",
                "debtors who have not paid for long",
                "who do I need to call for payments",
                "list of people to collect from",
                "pending collections",
                "who has not paid for a long time",
            ],
            "hi": ["किससे पैसे लेने हैं", "वसूली सूची", "किसको फ़ोन करना है पैसों के लिए", "लंबे समय से किसने पैसे नहीं दिए"],
            "hl": [
                "kisse paise lene hain",
                "vasooli list dikhao",
                "kisko phone karna hai paise ke liye",
                "kisne bahut time se paise nahi diye",
                "kis kis se paisa lena hai",
                "kis kis ko phone karna hai",
                "vasooli wale log",
            ],
        },
    ),
    "total_receivable": (
        [],
        {
            "en": [
                "total receivable",
                "how much is due in the market",
                "total money to collect",
                "total outstanding",
                "how much money is stuck in the market",
                "total dues of all customers",
                "overall receivable",
                "sum of all balances",
                "how much do customers owe in total",
                "total balance of everyone",
                "all customers together owe how much",
                "money stuck with customers",
                "total money to collect from everyone",
            ],
            "hi": [
                "बाज़ार में कुल कितना बकाया है",
                "कुल लेनदारी कितनी है",
                "कुल कितना पैसा लेना है",
                "सबका मिलाकर कितना बाकी है",
                "बाज़ार से कुल कितना लेना है",
                "कुल लेनदारी कितनी है",
                "बाज़ार में कितना पैसा फँसा है",
            ],
            "hl": [
                "market me kul kitna baaki hai",
                "kul lena kitna hai",
                "total udhaar kitna hai",
                "bazar me kitna paisa phasa hai",
                "sab ka milake kitna baaki hai",
                "kul udhaar kitna hai",
                "bazar ka total lena",
                "sabka milake kitna baaki",
                "sab grahakon ka kul baaki",
                "market se total kitna lena hai",
                "kul lendari kitni hai",
                "bazar me kitna paisa fasa hai",
            ],
        },
    ),
    "total_payable": (
        [],
        {
            "en": [
                "how much do we owe",
                "total payable",
                "how much do I have to pay farmers",
                "what do we owe in total",
                "total amount we have to pay",
                "how much do we owe customers",
                "money we owe farmers",
                "how much do we have to pay",
                "amount we need to pay others",
                "how much we owe in total",
                "what do we have to give to people",
            ],
            "hi": ["हमें कुल कितना देना है", "कुल देनदारी कितनी है", "हमारी कुल देनदारी", "हमें कुल कितना चुकाना है"],
            "hl": [
                "hume kitna dena hai",
                "kul dena kitna hai",
                "kisano ko kitna dena hai",
                "hamein kul kitna dena hai",
                "kisan ko kitna dena baki hai",
                "hamein kitna chukana hai",
                "humein kul kitna dena baki hai",
                "hamari kul dendari",
            ],
        },
    ),
    "day_summary": (
        ["day?"],
        {
            "en": [
                "how much did we sell {D}",
                "sales {D}",
                "{D} summary",
                "how was business {D}",
                "how much business {D}",
                "what came in {D}",
                "{D} total",
                "sales and receipts {D}",
                "{D}'s collection",
            ],
            "hi": ["{D} कितनी बिक्री हुई", "{D} का हिसाब", "{D} कितना पैसा आया"],
            "hl": [
                "{D} kitni bikri hui",
                "{D} ka hisab",
                "{D} kitna paisa aaya",
                "{D} kitna becha",
                "{D} ki sale",
                "{D} kitna kaam hua",
                "{D} ka total batao",
            ],
        },
    ),
    "period_sales": (
        ["period"],
        {
            "en": [
                "sales {P}",
                "how much did we sell {P}",
                "total sales {P}",
                "business {P}",
                "what was the turnover {P}",
                "how much business {P}",
                "{P} sales total",
                "total sold {P}",
            ],
            "hi": [
                "{P} कितनी बिक्री हुई",
                "{P} की बिक्री",
                "{P} कुल कितना बिका",
                "{P} कुल कितना बिका",
                "{P} कुल बिक्री",
                "{P} कितना माल बिका",
            ],
            "hl": [
                "{P} kitni bikri hui",
                "{P} ki sale kitni hai",
                "{P} kitna becha",
                "{P} ka total sale",
                "{P} kitna dhandha hua",
                "{P} kul bikri",
                "{P} kul kitna bika",
                "{P} kitna maal bika",
            ],
        },
    ),
    "day_book": (
        ["day?"],
        {
            "en": [
                "show entries of {D}",
                "day book {D}",
                "list {D}'s entries",
                "what was entered {D}",
                "what entries were made {D}",
                "all transactions {D}",
                "{D} entries",
                "what was written {D}",
                "entries made {D}",
                "list of entries {D}",
            ],
            "hi": ["{D} की एंट्री दिखाओ", "{D} का रोज़नामचा", "{D} क्या क्या लिखा गया"],
            "hl": ["{D} ki entries dikhao", "{D} ki entry", "{D} ka rojnamcha", "{D} kya kya likha"],
        },
    ),
    "item_stock": (
        ["item"],
        {
            "en": [
                "how much {I} is left",
                "{I} stock",
                "stock of {I}",
                "do we have {I}",
                "{I} in stock",
                "is {I} available",
                "how many {I} are left",
                "{I} quantity in stock",
                "check stock of {I}",
                "how much {I} do we have",
                "how much {I} remaining",
                "{I} left?",
                "how many bags of {I} left",
            ],
            "hi": ["{I} कितना बचा है", "{I} का स्टॉक", "{I} है क्या", "{I} कितने बचे", "{I} कितने बचे हैं", "{I} स्टॉक में है क्या"],
            "hl": [
                "{I} kitna bacha hai",
                "{I} ka stock",
                "{I} hai kya",
                "{I} kitne bache",
                "{I} kitna pada hai",
                "{I} kitne bache hain",
                "{I} stock me hai kya",
                "{I} kitni bori padi hai",
            ],
        },
    ),
    "item_price": (
        ["item"],
        {
            "en": [
                "price of {I}",
                "{I} rate",
                "what is the rate of {I}",
                "how much does {I} cost",
                "what do we sell {I} for",
                "selling price of {I}",
                "{I} price please",
                "rate of {I}",
                "how much is {I}",
                "what's the rate for {I}",
                "cost of one {I}",
                "{I} mrp",
                "how much for {I}",
                "how much does {I} cost",
                "what does one {I} cost",
            ],
            "hi": [
                "{I} का रेट क्या है",
                "{I} का भाव",
                "{I} कितने का है",
                "{I} का रेट बताओ",
                "{I} कितने का है",
                "{I} की कीमत",
                "एक {I} कितने का",
            ],
            "hl": [
                "{I} ka rate kya hai",
                "{I} ka bhav",
                "{I} kitne ka hai",
                "{I} ka rate",
                "{I} kitne ka hai",
                "{I} ka rate batao",
                "{I} ki keemat",
                "ek {I} kitne ka",
            ],
        },
    ),
    "item_sales": (
        ["item", "period?"],
        {
            "en": [
                "how much {I} sold {P}",
                "{I} sales {P}",
                "sale of {I} {P}",
                "how many {I} did we sell {P}",
                "{I} sold {P}",
                "quantity of {I} sold {P}",
            ],
            "hi": ["{P} {I} कितना बिका", "{I} की बिक्री {P}"],
            "hl": ["{P} {I} kitna bika", "{I} kitna bika {P}", "{I} ki sale {P}"],
        },
    ),
    "low_stock": (
        [],
        {
            "en": [
                "which items are running out",
                "low stock",
                "what is out of stock",
                "items finishing",
                "what is about to finish",
                "items with little stock",
                "which items are almost over",
                "stock running low",
                "what has finished",
                "which items are nearly finished",
                "short items",
            ],
            "hi": [
                "कौन सा सामान ख़त्म होने वाला है",
                "कम स्टॉक",
                "क्या ख़त्म हो गया",
                "कौन सा माल कम बचा है",
                "किसका स्टॉक कम है",
                "कौन सा सामान नहीं बचा",
            ],
            "hl": [
                "kaun sa saman khatam hone wala hai",
                "kam stock wala saman",
                "kya khatam ho gaya",
                "stock kam hai kiska",
                "kaunsa maal kam bacha hai",
                "kiska stock khatam hone wala hai",
                "kya kya khatam ho gaya",
                "kaunsa saman nahi bacha",
            ],
        },
    ),
    "reorder": (
        [],
        {
            "en": [
                "what should I reorder",
                "what to order",
                "reorder list",
                "what do I need to buy",
                "what should we order",
                "items to purchase",
            ],
            "hi": ["क्या मँगवाना है", "क्या ऑर्डर करना है"],
            "hl": ["kya mangwana hai", "kya order karna hai", "kya maal mangana hai"],
        },
    ),
    "expiring": (
        [],
        {
            "en": [
                "what is expiring",
                "expiring items",
                "which medicine expires soon",
                "which products will expire",
                "what expires soon",
                "items near expiry",
                "expiry list",
                "which batches expire soon",
                "anything going to expire",
                "expired items",
                "medicines near expiry date",
            ],
            "hi": [
                "कौन सी दवाई एक्सपायर होने वाली है",
                "एक्सपायर होने वाला सामान",
                "एक्सपायरी वाला सामान",
                "कौन सा माल एक्सपायर हो गया",
                "एक्सपायरी लिस्ट",
                "किस दवाई की एक्सपायरी पास है",
            ],
            "hl": [
                "kaunsi dawai expire hone wali hai",
                "expiry wala saman",
                "kya expire ho raha hai",
                "expiry list dikhao",
                "kaunsa maal expire ho gaya",
                "expiry date wali dawai",
                "kiski expiry paas hai",
            ],
        },
    ),
    "profit": (
        ["period?"],
        {
            "en": [
                "profit {P}",
                "how much profit {P}",
                "did we make money {P}",
                "what is the profit {P}",
                "how much did we earn {P}",
                "earnings {P}",
                "net profit {P}",
                "did we make a profit {P}",
                "profit or loss {P}",
                "were we in profit {P}",
                "how much money did the shop make {P}",
                "how much did we gain {P}",
            ],
            "hi": [
                "{P} कितना मुनाफ़ा हुआ",
                "{P} का फ़ायदा",
                "{P} कितनी कमाई हुई",
                "{P} मुनाफ़ा कितना रहा",
                "{P} नफ़ा नुकसान",
                "{P} कितना कमाया",
            ],
            "hl": [
                "{P} kitna munafa hua",
                "{P} ka profit",
                "{P} kitna fayda hua",
                "{P} kitni kamai hui",
                "{P} kitna kamaya",
                "{P} nafa nuksan",
                "{P} munafa kitna raha",
                "{P} profit hua ya loss",
                "{P} kitna bacha munafa",
            ],
        },
    ),
    "expenses": (
        ["period?"],
        {
            "en": [
                "expenses {P}",
                "how much did we spend {P}",
                "total expenses {P}",
                "what did we spend {P}",
                "spending {P}",
                "where did the money go {P}",
                "what were the expenses {P}",
                "money spent {P}",
                "how much went in expenses {P}",
                "costs {P}",
            ],
            "hi": ["{P} कितना ख़र्चा हुआ", "{P} का ख़र्च", "{P} कितना पैसा ख़र्च हुआ", "{P} ख़र्चे कितने हुए"],
            "hl": [
                "{P} kitna kharcha hua",
                "{P} ka kharch",
                "{P} kitna kharch hua",
                "{P} kharche kitne hue",
                "{P} paisa kahan kharch hua",
                "{P} ke kharche",
            ],
        },
    ),
    "cash_balance": (
        [],
        {
            "en": [
                "how much cash do we have",
                "cash in hand",
                "bank balance",
                "money in the accounts",
                "how much money is in the bank",
                "balance in cash box",
                "cash and bank balance",
                "money in hand",
            ],
            "hi": ["गल्ले में कितना पैसा है", "नकद कितना है", "बैंक में कितना है"],
            "hl": ["galle me kitna paisa hai", "cash kitna hai", "bank me kitna hai", "hath me kitna cash h"],
        },
    ),
    "attention": (
        [],
        {
            "en": [
                "what needs attention",
                "anything important today",
                "any problems",
                "what should I know",
                "anything urgent",
                "what is important today",
                "show me problems",
                "what should I check today",
                "any issues in the shop",
                "alerts",
                "what should I look at today",
                "any alerts today",
                "is everything ok",
                "what needs to be done today",
                "anything wrong",
            ],
            "hi": [
                "आज किस पर ध्यान देना है",
                "कोई ज़रूरी बात",
                "कोई दिक्कत है क्या",
                "आज क्या देखना है",
                "सब ठीक है क्या",
                "कोई अलर्ट",
            ],
            "hl": [
                "aaj kya dhyan dena hai",
                "koi zaruri baat",
                "koi problem hai kya",
                "aaj kya karna hai",
                "kuch zaruri hai kya",
                "aaj kya dekhna hai",
                "koi dikkat to nahi",
                "sab theek hai kya",
                "aaj ka kaam kya hai",
                "koi alert",
                "aaj kis kis ko dekhna hai",
            ],
        },
    ),
    "help": (
        [],
        {
            "en": [
                "what can you do",
                "help",
                "how to use this",
                "what can I ask",
                "how do I use you",
                "what questions can I ask",
                "show examples",
                "what do you know",
                "what kind of questions do you answer",
                "give me some examples",
                "how does this work",
                "what can you tell me",
                "i need help",
                "how can you help me",
            ],
            "hi": [
                "तुम क्या कर सकते हो",
                "मदद",
                "क्या पूछ सकता हूँ",
                "क्या क्या पूछ सकते हैं",
                "कैसे इस्तेमाल करूँ",
                "उदाहरण दिखाओ",
                "तुम्हें क्या पता है",
                "कैसे पूछूँ",
                "पूछने का तरीका बताओ",
            ],
            "hl": [
                "tum kya kar sakte ho",
                "madad karo",
                "kya puch sakta hu",
                "help karo",
                "kya kya puch sakte hain",
                "kaise use karu",
                "kuch example batao",
                "ye kaise chalta hai",
                "tum kya kya batate ho",
                "kya puchu",
                "kaise puchna hai",
                "kaise puchu",
                "kya puchna hai",
                "puchne ka tarika batao",
            ],
        },
    ),
    "greeting": (
        [],
        {
            "en": [
                "hello",
                "hi",
                "good morning",
                "thanks",
                "hey",
                "good evening",
                "thank you",
                "ok thanks",
                "how are you",
                "good night",
            ],
            "hi": ["नमस्ते", "राम राम", "धन्यवाद", "कैसे हो", "क्या हाल है"],
            "hl": [
                "namaste",
                "ram ram",
                "dhanyawad",
                "shukriya",
                "kaise ho",
                "ram ram ji",
                "theek hai dhanyawad",
                "shukriya ji",
                "kya haal hai",
                "kaise ho bhai",
                "sab badhiya",
                "haal chaal",
            ],
        },
    ),
    "unsupported": (
        [],
        {
            "en": [
                "what is the weather",
                "tell me a joke",
                "who won the match",
                "play a song",
                "what is the news",
                "what is the price of gold",
                "who is the prime minister",
                "write a poem",
                "tell me a story",
                "who won the match",
                "play a song",
                "what is the news today",
                "tell me a joke",
                "how is the weather tomorrow",
                "book a train ticket",
            ],
            "hi": [
                "मौसम कैसा है",
                "चुटकुला सुनाओ",
                "मैच किसने जीता",
                "गाना चलाओ",
                "मैच किसने जीता",
                "गाना सुनाओ",
                "आज की खबर",
                "मौसम कैसा है",
            ],
            "hl": [
                "mausam kaisa hai",
                "joke sunao",
                "match kisne jeeta",
                "gana chalao",
                "aaj ki khabar",
                "sone ka bhav kya hai",
                "kahani sunao",
                "cricket score",
                "match kisne jeeta",
                "gana chalao",
                "aaj ki khabar sunao",
                "mausam kaisa rahega",
                "ticket book karo",
            ],
        },
    ),
}

POLITE = {
    "en": ["", "", "please ", "can you tell me ", "tell me "],
    "hi": ["", "", "ज़रा ", "भाई "],
    "hl": ["", "", "zara ", "bhai ", "please "],
}
POLITE_END = {
    "en": ["", "", "?", " please"],
    "hi": ["", "", "?", " जी", " बताओ"],
    "hl": ["", "", "?", " ji", " btao", " bata do"],
}


@dataclass(frozen=True)
class Example:
    text: str
    intent: str
    args: dict = field(default_factory=dict)
    style: str = "hl"
    template_id: str = ""


def _typo(text: str, rng: random.Random) -> str:
    """One realistic slip: a dropped vowel, a doubled letter, or a swapped pair (Latin only)."""
    protected = {j for m in _PLACEHOLDER.finditer(text) for j in range(m.start(), m.end())}
    letters = [i for i, ch in enumerate(text) if ch.isascii() and ch.isalpha() and i not in protected]
    if len(letters) < 4:
        return text
    i = rng.choice(letters[1:-1])
    kind = rng.random()
    if kind < 0.4 and text[i] in "aeiou":
        return text[:i] + text[i + 1 :]
    if kind < 0.7:
        return text[:i] + text[i] + text[i:]
    if i + 1 < len(text) and text[i + 1].isalpha():
        return text[:i] + text[i + 1] + text[i] + text[i + 2 :]
    return text


_FUTURE = ("this_week", "this_month", "days:7", "days:30")


def _fill(template: str, style: str, rng: random.Random, intent: str = "") -> tuple[str, dict]:
    args: dict = {}
    text = template
    if "{C}" in text:
        text = text.replace("{C}", "<C1>")
        args["customer"] = "C1"
    if "{I}" in text:
        text = text.replace("{I}", "<I1>")
        args["item"] = "I1"
    if "{P}" in text:
        choices = [p for p in PERIODS if p[0] in _FUTURE] if intent == "krar_upcoming" else PERIODS
        value, phrases = rng.choice(choices)
        text = text.replace("{P}", rng.choice(phrases[style]))
        args["period"] = value
    if "{D}" in text:
        value, phrases = rng.choice(DAYS)
        text = text.replace("{D}", rng.choice(phrases[style]))
        args["day"] = value
    if "{N}" in text:
        n = rng.choice(NUMBERS)
        text = text.replace("{N}", str(n))
        args["number"] = n
    if "{CAT}" in text:
        cat = rng.choice(CATEGORIES)
        text = text.replace("{CAT}", cat)
        args["category"] = cat
    return " ".join(text.split()), args


def templates() -> list[tuple[str, str, str, str]]:
    """(template_id, intent, style, template)."""
    out = []
    for intent, (_slots, by_style) in INTENTS.items():
        for style, items in by_style.items():
            for k, t in enumerate(items):
                out.append((f"{intent}/{style}/{k}", intent, style, t))
    return out


def generate(per_template: int = 30, seed: int = 7, noise: float = 0.25) -> list[Example]:
    rng = random.Random(seed)
    out: list[Example] = []
    for tid, intent, style, template in templates():
        seen = set()
        for _ in range(per_template):
            text, args = _fill(template, style, rng, intent)
            label = intent
            if intent == "period_sales" and args.get("period") in ("today", "yesterday"):
                label, args = "day_summary", {"day": args["period"]}
            text = rng.choice(POLITE[style]) + text + rng.choice(POLITE_END[style])
            if style != "hi" and rng.random() < noise:
                text = _typo(text, rng)
            if style != "hi" and rng.random() < 0.3:
                text = _PLACEHOLDER.sub(lambda m: m.group(0).upper(), text.lower())
            if text in seen:
                continue
            seen.add(text)
            out.append(Example(text, label, args, style, tid))
    return out


def split(examples: list[Example], test_share: float = 0.15, seed: int = 7) -> tuple[list[Example], list[Example]]:
    """Hold out whole templates (per intent and style), so test phrasings are unseen."""
    rng = random.Random(seed)
    by_group: dict[tuple[str, str], list[str]] = {}
    for tid, intent, style, _t in templates():
        by_group.setdefault((intent, style), []).append(tid)
    held: set[str] = set()
    for tids in by_group.values():
        if len(tids) >= 3:
            k = max(1, round(len(tids) * test_share))
            held.update(rng.sample(tids, k))
    train = [e for e in examples if e.template_id not in held]
    test = [e for e in examples if e.template_id in held]
    return train, test


# --- System 2 (language model) prompt format: shared by the Kaggle cell and the app -----
def tool_lines() -> str:
    """One compact line per tool - identical on every call, so llama.cpp can cache it."""
    lines = []
    for intent, (slots, _t) in INTENTS.items():
        lines.append(f"{intent}({', '.join(slots)})")
    return "\n".join(lines)


PROMPT_VERSION = 2  # bump when the prompt layout changes - a model trained on another layout is not used

INSTRUCTION = (
    "Map the shop owner's question (English, Hindi or Hinglish) to one tool call. "
    "<C1> is a customer, <I1> an item. Reply only with call:tool{args}."
)


def prompt(question: str) -> str:
    """The prompt System 2 sees: short (the fine-tuned model knows the tools), so a Celeron
    reads it in well under a second and training on Kaggle stays quick."""
    return (
        f"<start_of_turn>developer\n{INSTRUCTION}<end_of_turn>\n"
        f"<start_of_turn>user\n{question}<end_of_turn>\n<start_of_turn>model\n"
    )


def target(intent: str, args: dict) -> str:
    return f"<start_function_call>call:{intent}{json.dumps(args, ensure_ascii=False, separators=(',', ':'))}<end_function_call>"


def parse_call(text: str) -> tuple[str, dict] | None:
    """``<start_function_call>call:name{...}`` -> (name, args), or None."""
    start = text.find("call:")
    if start < 0:
        return None
    body = text[start + 5 :]
    brace = body.find("{")
    if brace < 0:
        return None
    name = body[:brace].strip()
    depth, end = 0, -1
    for i, ch in enumerate(body[brace:], start=brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0 or name not in INTENTS:
        return None
    try:
        args = json.loads(body[brace : end + 1])
    except ValueError:
        return None
    return (name, args) if isinstance(args, dict) else None
