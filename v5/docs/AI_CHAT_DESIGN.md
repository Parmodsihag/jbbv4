# AI chat assistant — design (for review)

Status: **draft for review, nothing implemented yet.** Version target: 5.2.
Owner decisions needed are collected in [§14 Open questions](#14-open-questions).

---

## 1. What we are building

A **chat screen** (सहायक / *Assistant*) where the shop owner or an employee types a
question in **English, Hindi (देवनागरी) or Hinglish** and gets the answer from the shop's
own data, instantly and offline:

(figures below are illustrative)

| asked | answered with |
|---|---|
| `ramesh sihag ka kitna baaki hai` | रमेश सिहाग · शेष ₹12,500.00 (हमें देना है) · वादा 03-07-2026, 108 दिन देर · [खाता खोलें] |
| `किसके करार की तारीख निकल गई?` | 40 accounts, ₹6,00,000 at stake — table, biggest first · [करार खोलें] |
| `how much urea is left` | UREA 45KG IFFCO · 34 BAG in stock · sold 18 in the last 30 days · ~57 days left |
| `pichle mahine kitni bikri hui` | September 2026: debits ₹3,00,000 · credits ₹2,50,000 · 400 entries |
| `top 5 debtors in category D` | table of 5 · [वसूली सूची खोलें] |
| `kal ke entries dikhao` | yesterday's day book |
| `profit this year` | FY 2026-27 P&L summary · [लाभ-हानि खोलें] |

The assistant **finds and shows** data the app already computes. It never invents a number.

### Goals
1. Answer the ~30 everyday question types in under 1.5 s on the shop PC, fully offline.
2. Understand English, Hindi and Hinglish, misspellings, and names typed either way
   (`ramesh` / `रमेश`), relative dates (`aaj`, `kal`, `pichle hafte`, `is saal`) and amounts
   (`pachas hazaar`, `50k`, `५०,०००`).
3. Every figure comes from the same service method as the matching report, so the chat
   and the report can never disagree.
4. Respect roles: an employee cannot get the audit log or staff report through chat.
5. Work **without** the language model too (smaller install, older PCs) — the model adds
   coverage for unusual phrasing, it is not a single point of failure.

### Non-goals (first release)
- No free-form "chat about anything", no advice, no internet, no cloud API.
- No writing to the books from chat in v5.2 (record payment, add krar…) — designed in §9,
  shipped later behind a confirmation card.
- No voice input yet (see §12, phase 4).

---

## 2. Architecture: two systems

The request mentioned a small LM with LoRA *plus* a "system one" model. This design reads
that as Kahneman's **System 1 / System 2** split (please confirm in §14):

```
                ┌──────────────────────────── Assistant screen ────────────────────────────┐
 question ──▶  │ 1 Normalise   2 Link entities   3 System 1 (fast)  ──conf≥τ──▶ 5 Execute │──▶ answer card
               │  script, nums,   names, items,      intent + slots      │          tool     │    + table
               │  dates           money accts        <10 ms, no model    │ conf<τ   (service │    + "open report"
               │                                                         ▼          methods)│
               │                                    4 System 2 (deliberate)                 │
               │                                      small LM + LoRA → tool call (JSON,    │
               │                                      grammar-constrained), ~0.5–1.5 s      │
               └────────────────────────────────────────────────────────────────────────────┘
```

* **System 1 — fast, intuitive, tiny.** Recognises the intent of common questions from
  learned patterns in a shared embedding space (in the spirit of a JEPA-style encoder:
  it predicts *in representation space*, it never generates text). Handles the large
  majority of real questions in milliseconds and needs no model download.
* **System 2 — slow, deliberate, small LM.** Only consulted when System 1 is unsure, or
  the question combines conditions (“farmers who sold wheat last month and still owe us”).
  It translates the question into **one structured tool call** — it does not answer.
* **Executor** runs the tool against the existing services (`ReportsService`,
  `AccountsService`, `InsightsService`, `FinanceService`, …). **Composer** renders a
  templated answer in the UI language, plus a table and a link to the full report.

Why this split: accounting answers must be exact, so the model's job is reduced to
*choosing a query*. Getting a query wrong is visible and recoverable (the card shows what
was looked up: “बकाया · रमेश सिहाग”); a model that writes numbers can be silently wrong.

---

## 3. The pipeline in detail

### 3.1 Normalise (deterministic)
* Unicode NFC; strip punctuation noise; lower-case Latin.
* **Script bridge:** Devanagari is also romanised (`बकाया` → `bakaya`) with a small
  reverse of `hth/i18n/translit.py`, so System 1 features are shared across scripts.
* **Numbers:** digits in either script (`५०` → 50), `50k`, `1.5 lakh`, `do hazaar`,
  `पचास हज़ार`.
* **Dates:** `aaj/आज`, `kal/कल` (yesterday by default; “kal tak” = until tomorrow is a
  known ambiguity → ask), `parso`, `pichle hafte`, `is mahine`, `pichle mahine`,
  `15 tarikh`, `March`, `is saal / FY`, explicit `2026-10-20`, `20/10`.
* **Units:** `kg kilo quintal qtl bag katta bori litre packet`.

### 3.2 Link entities (deterministic, the most important step)
Customers, items, money accounts, expense heads, crops, users and categories are found in
the question by fuzzy matching against the database — both the English name and the
stored Hindi copy (`name_hi`, added in 5.1):
* candidate spans of 1–4 tokens; scoring = token-set similarity on romanised forms, with
  bonus for exact id (`#349`), village/phone in details, and recency of activity;
* ambiguity (two RAMESH SIHAGs) → the answer card asks “कौन से?” with the options;
* linked entities are replaced by typed placeholders before any model sees the text:
  `ramesh sihag ka kitna baaki hai` → `<C1> ka kitna baaki hai` with `C1 = customer #349`.

Placeholders make the model's task smaller (it never has to learn 663 names), keep real
customer names out of training data, and let a model trained on synthetic names work on
the real shop.

### 3.3 System 1 — intent + slots in milliseconds
* **Encoder:** hashed character 3–5-grams + word 1–2-grams of the normalised,
  placeholder-substituted text → 2¹⁸-dim sparse vector → linear projection to a 128-dim
  embedding. **Head:** cosine similarity to per-intent prototypes, plus a small
  multinomial logistic layer. Pure NumPy, < 2 MB on disk, no new dependency.
* **Training:** on the synthetic corpus (§6), seconds on the shop PC; retrained whenever
  the template set grows.
* **Slots** come from the deterministic steps (entities, dates, numbers) plus a few
  intent-specific rules (`top 5` → `n=5`, `category D`, `more than 10,000`).
* **Confidence:** margin between the best and second-best intent; below threshold τ
  (tuned on the eval set, start 0.35) → System 2. If System 2 is not installed, the
  card shows the top-3 interpretations as buttons (“क्या आपका मतलब…”).
* Optional upgrade if the n-gram encoder plateaus: a small multilingual sentence encoder
  (≈100 M params) used only as a frozen feature extractor — same head, same prototypes.

### 3.4 System 2 — small LM that writes one tool call
Input (≈40–120 tokens): a fixed short instruction + the compact tool list + the
placeholder text + today's date. Output: exactly one call, e.g.

```
<start_function_call>call:customer_balance{customer:"C1"}<end_function_call>
<start_function_call>call:collections{min_balance:10000,status:"overdue",category:"D",limit:5}<end_function_call>
```

* **Grammar-constrained decoding** (llama.cpp GBNF built from the tool schemas): the model
  can only emit a valid tool name and correctly typed arguments, so parsing never fails
  and enum values (`status`, `period`, `category`) cannot be invented. The executor still
  validates every argument.
* **Short prompts on CPU:** prompt processing dominates small-model latency on CPU, so tool
  declarations are compressed to one line each and the instruction+tool block is
  identical on every call — llama.cpp's prompt cache then makes it free after the first
  question. After LoRA tuning, the declaration block can be shortened further.
* Output is checked: unknown placeholder, missing required argument, or a permission the
  user lacks → the card says so instead of guessing.

### 3.5 Execute
Each tool is a thin, typed, **read-only** wrapper around a method that already exists and
is already tested (table in §4). The tool declares the permission it needs; the executor
checks `ctx.can(...)` before running it — the same matrix as the screens.

### 3.6 Compose the answer
* Templated sentences per tool, in Hindi or English (follows the UI language; §14 asks
  whether to follow the question's language instead), using `hth.i18n`, Hindi names and
  Indian digit grouping.
* A compact `DataTable` for list answers (top 20 rows; “और दिखाएँ” opens the report).
* A chip showing **what was looked up** (“बकाया · रमेश सिहाग · आज तक”) — tap to edit the
  slots (change person, period) without retyping.
* Buttons: open the ledger / item / report with the same parameters; copy; WhatsApp
  (where the answer is about one customer).
* Follow-ups: the last tool call is kept, so “aur pichle mahine?” / “and for DAP?” re-runs
  it with one slot changed (System 1 has explicit `followup_*` intents).

---

## 4. Tool catalogue (v5.2 scope: 28 read-only tools)

All map onto existing, tested code. P = permission (`—` = any signed-in user).

| tool | arguments | backed by | P |
|---|---|---|---|
| `customer_balance` | customer | `AccountsService.get_balance`, krar, last payment | ADD_CUSTOMER |
| `customer_ledger` | customer, period? | `AccountsService.ledger` (+ period filter) | ADD_CUSTOMER |
| `customer_lookup` | text | `SearchService.search` | ADD_CUSTOMER |
| `collections` | status?, category?, min_balance?, limit? | `ReportsService.collections` | VIEW_REPORTS |
| `top_debtors` | n, category? | `ReportsService.top_debtors` | VIEW_REPORTS |
| `receivables_aging` | category? | `ReportsService.aging` | VIEW_REPORTS |
| `totals` | — | `ReportsService.kpis` (receivable, payable, stock, cash) | VIEW_DASHBOARD |
| `krar_list` | bucket (overdue/today/upcoming/all), customer? | `KrarService.entries` | MANAGE_KRAR |
| `krar_forecast` | days | `ReportsService.krar_forecast` | VIEW_REPORTS |
| `day_book` | date | `ReportsService.day_book` / `day_totals` | VIEW_REPORTS |
| `period_flow` | period | `ReportsService.monthly_flow` / `day_totals` | VIEW_REPORTS |
| `customer_activity` | period, customer? | `ReportsService.customer_activity` | VIEW_REPORTS |
| `interest` | customer?, by_fy? | `interest_summary` / `interest_by_fy` | VIEW_REPORTS |
| `item_stock` | item | `InventoryService.quantity` + last price, 30-day sales | ADD_ITEM |
| `item_movement` | item?, period | `ReportsService.item_movement` / item history | VIEW_REPORTS |
| `low_stock` | threshold? | `InventoryService.low_stock` | VIEW_REPORTS |
| `reorder` | window_days? | `InsightsService.reorder_suggestions` | VIEW_REPORTS |
| `expiring` | days? | `InventoryService.expiring` | VIEW_REPORTS |
| `dead_stock` | days? | `ReportsService.dead_stock` | VIEW_REPORTS |
| `item_profit` | period, item? | `ReportsService.item_profit` | VIEW_REPORTS |
| `cash_balance` | account? | `FinanceService.balances` | FINANCE |
| `expenses` | period, head? | `FinanceService.expenses_by_head` | FINANCE |
| `profit_loss` | period | `FinanceService.profit_and_loss` | FINANCE_REPORTS |
| `crop_stock` | crop? | crop valuation | CROP_TRADING |
| `crop_margin` | period, crop?, by (crop/buyer/farmer) | crop reports | CROP_TRADING |
| `gst_summary` | period | `ReportsService.gst_summary` | BILLING |
| `attention` | — | `InsightsService.collect` | VIEW_DASHBOARD |
| `staff_activity` | period | `ReportsService.staff_activity` | VIEW_AUDIT |

`period` is one typed value: `{kind: day|week|month|fy|range, from, to}` resolved by the
normaliser, so the model only says `"last_month"` / `"this_fy"` / `"D1"` (a date slot).

Adding a tool = one entry in `hth/assistant/tools.py` (schema, permission, executor,
templates) + its templates in the data generator. Nothing else changes.

---

## 5. Model choice for System 2

Constraint from the request: **≤ 500 M parameters**, offline, CPU (shop PC; this dev
machine is a Ryzen 7 4700U, 8 cores, 7.4 GB RAM, no CUDA GPU).

| candidate | params | why consider | concerns |
|---|---|---|---|
| **FunctionGemma 270M** (Google, Gemma 3 base) | 270 M | Purpose-built for *fine-tuned* function calling; documented call format; runs in ≈550 MB RAM at full precision; GGUF builds and LoRA recipes exist. Gemma 3's 262k-token vocabulary is reported among the most efficient open tokenizers for Indic scripts — Hindi costs few tokens. | Gemma licence terms (not Apache) — read before shipping; quality on Hindi/Hinglish untested — our eval decides. |
| **Qwen2.5-0.5B-Instruct** | ≈494 M | Strong at structured/JSON output for its size; Apache-2.0. | Weaker Hindi tokenization (more tokens per word → slower prompts); right at the size limit. |
| SmolLM2-360M | 360 M | Apache-2.0, fast. | English-centric training; poor fit for Hindi. |
| Qwen3-0.6B | ≈600 M | Good small reasoner, Apache-2.0. | Over the 500 M limit. |

**Recommendation:** build the pipeline model-agnostic, run the same eval on
FunctionGemma-270M and Qwen2.5-0.5B (zero-shot, then LoRA), and ship the one that wins on
accuracy within the latency budget. Expectation: FunctionGemma-270M wins on Hindi/Hinglish
and speed; Qwen2.5-0.5B may win on long compositional questions.

**Runtime:** `llama-cpp-python` (llama.cpp) with a GGUF file — CPU-only, runs on Windows,
supports GBNF grammars and prompt caching. Quantisation: Q8_0 first (≈300 MB for 270 M);
try Q5/Q4 only if latency needs it (quality drops sharply below 4-bit at this size).
The model is an **optional extra**: `pip install high-table-holdings[assistant]` plus a
model file in `C:\JBB\v5\models\`; without them the assistant runs System 1 only.

**Latency budget (shop PC, to be measured with `llama-bench`):** normalise + link
< 30 ms · System 1 < 10 ms · System 2 ≤ 1.2 s (≈100 prompt tokens cached + ≤ 40 generated)
· execute + compose < 200 ms · **p95 end-to-end ≤ 1.5 s**.

---

## 6. Training data (synthetic, generated from the app's own vocabulary)

There are no chat logs to learn from, so the corpus is generated:

* **Templates per intent** in three styles — English, Hindi (Devanagari), Hinglish —
  e.g. `customer_balance`: “how much does {C} owe”, “{C} ka kitna baaki hai”,
  “{C} का कितना बकाया है”, “{C} ka hisab batao”, “balance of {C}”, …
  (20–60 templates per intent, written once, reviewed by the shop).
* **Slot fillers:** placeholders (`<C1>`, `<I1>`, `<D1>`), period words, numbers in all
  forms, categories, statuses.
* **Noise:** common misspellings (`baki/baaki/bakaya`), dropped vowels (`kitna/ktna`),
  code-switching mid-sentence, extra politeness (`bhai`, `ji`, `zara`, `please`).
* **Negatives:** out-of-scope questions (“weather”, “who are you”) → `unsupported` tool,
  so the model learns to abstain.
* **Compositions:** filters combined (status + category + amount), for System 2.
* Size: ≈30–50 k examples, 80/10/10 split **by template** (so the test set contains
  phrasings the model never saw).

Real customer names never enter the corpus (placeholders), so training data can be shared
or trained in the cloud without exposing the shop's books. Optionally, the shop owner
dictates 50–100 real questions — the single most valuable addition to the **eval** set.

---

## 7. Fine-tuning (LoRA)

* Format: the chosen model's own chat/function-calling format (for FunctionGemma: the
  developer message, function declarations, `<start_function_call>` output).
* LoRA on attention + MLP projections, rank 16, alpha 32, dropout 0.05, lr 2e-4 cosine,
  2–3 epochs, max length 256, loss on the output only. Typical public recipes for 270 M
  use exactly this size of adapter.
* Where: a free cloud GPU notebook (≈30–60 min for 270 M) — or this laptop's CPU overnight
  if cloud is not wanted. Only the synthetic corpus is uploaded.
* Export: merge adapter → convert to GGUF → Q8_0 → checksum; ships as one file.
* Reproducible: `tools/assistant/make_data.py`, `train_lora.py`, `export_gguf.py`,
  `eval.py` with fixed seeds; training needs `transformers`, `peft`, `trl` — dev-only,
  never installed on the shop PC.

---

## 8. Evaluation and acceptance

`tools/assistant/eval.py` runs every question through the full pipeline and reports:

| metric | target for release |
|---|---|
| tool + arguments exactly right (held-out templates, all 3 styles) | ≥ 95 % |
| entity linking top-1 on real names (generated from the live DB, read-only) | ≥ 97 % |
| wrong answer (confident and wrong) | ≤ 1 % |
| abstain / ask back | ≤ 5 % |
| answer numbers identical to the matching report | 100 % (unit tests) |
| p95 latency on the shop PC | ≤ 1.5 s |

Reported per style (English / Hindi / Hinglish), per intent, System 1 vs System 2, so a
regression is visible before it ships. The current System-1-only score is the baseline the
LM has to beat to be worth installing.

---

## 9. Later: actions with confirmation (not in 5.2)

Write intents (`record_receipt`, `add_krar`, `send_reminder`, `add_expense`) will **never
execute from the model's output**. The assistant fills the existing form (Sales screen,
krar dialog) or shows a confirmation card with every field visible — account, amount,
money account, date, tag — and nothing happens until the user presses the normal button.
Same permissions, same audit entries, same undo as doing it by hand.

---

## 10. User interface

* New sidebar entry **सहायक / Assistant** (`Alt+H`), plus `Ctrl+J` from any screen opens
  a compact chat panel on the right.
* Message list with question bubbles and **answer cards** (headline figure, one-line
  explanation, small table, buttons). Hindi or English follows Settings.
* Under the input: suggestion chips that change with the screen and the data
  (“आज की बिक्री”, “करार जिनकी तारीख निकली”, “कम स्टॉक”).
* The "looked up" chip on every answer makes the interpretation visible and editable.
* History of the session in memory only (not stored), cleared on sign-out/lock.
* Settings → Assistant: on/off, model file status (installed / missing / speed test),
  “answers in question's language” toggle (if chosen in §14).

---

## 11. Privacy, safety, logging

* 100 % offline: no network calls; the model file is local.
* Read-only tools in 5.2; permissions enforced per tool; locked screen = no chat.
* The model sees only placeholder text (`<C1> ka kitna baaki hai`), never balances or
  ledger rows.
* Audit log: one line per question with the **tool and arguments**
  (`assistant: customer_balance #349`), not the free text — so supervision works without
  storing what people typed.
* Failure is always explicit: unknown → “समझ नहीं आया — क्या आपका मतलब…?” with options.

---

## 12. Delivery plan

| phase | delivers | depends on |
|---|---|---|
| **1 · Assistant without a model** | chat screen, normaliser (scripts, numbers, dates), entity linker, 28 tools, answer cards in Hindi/English, System 1 trained on the synthetic corpus, follow-ups, audit lines | nothing new to install |
| **2 · Data + eval** | template corpus (3 styles), generator, eval harness + report, owner's real questions | §14 answers |
| **3 · System 2** | zero-shot baseline for both candidates with GBNF; LoRA training + GGUF export; optional `llama-cpp-python` integration with router thresholds; `llama-bench` on the shop PC; ship the winner if it beats System 1 alone | model licence check; a GPU notebook or an overnight CPU run |
| **4 · Actions & voice** (later) | confirmation-card actions (§9); optional offline speech input | phases 1–3 in use |

Phase 1 alone should answer most everyday questions; phases 2–3 widen phrasing coverage
and handle combined conditions.

---

## 13. Risks

| risk | mitigation |
|---|---|
| Hinglish spelling variety beats System 1 | noise generation, char n-grams, System 2 fallback, "did you mean" buttons, owner's real questions in eval |
| Name ambiguity (same name, two villages) | linker uses details/phone/recency; asks when close |
| 270 M model too weak for compositions | grammar constraint, placeholders, LoRA on our tools only; Qwen2.5-0.5B as alternative; abstain rather than guess |
| Shop PC too slow | System 1 path needs no model; Q5/Q4; prompt cache; model optional |
| `llama-cpp-python` install on Windows | prebuilt CPU wheel or bundle in the PyInstaller build; feature degrades gracefully if missing |
| Licence (Gemma terms) | review before shipping; Qwen2.5-0.5B (Apache-2.0) as the fallback choice |

---

## 14. Open questions

1. **“jev like system one model”** — this design assumes *System 1 / System 2* (fast
   classifier + deliberate small LM), with System 1 as a JEPA-style embedding predictor.
   If you meant something else (a JARVIS-style voice assistant? a specific model?), say
   which and §2–3 change accordingly.
2. **Shop PC hardware** — CPU model and RAM decide quantisation and whether System 2 is on
   by default.
3. **Training location** — OK to fine-tune on a free cloud GPU with the synthetic
   (placeholder-only) corpus, or must everything stay on local machines (overnight CPU)?
4. **Answer language** — always the UI language, or the language the question was asked in?
5. **Real questions** — can you (or the shop) list 50–100 questions actually asked at the
   counter, in the words used? They become the evaluation set.
6. **Actions** — confirm that 5.2 is read-only and actions come later with confirmation.
7. **Employees** — same assistant for employees (with their permissions), or admin only?

---

### Sources consulted (October 2026)
- FunctionGemma 270M — run & fine-tune guide (Unsloth): https://unsloth.ai/docs/models/tutorials/functiongemma
- FunctionGemma model listing (LM Studio): https://lmstudio.ai/models/google/functiongemma-270m
- Function calling with FunctionGemma (NVIDIA NeMo AutoModel): https://docs.nvidia.com/nemo/automodel/recipes-e2e-examples/function-calling
- Community LoRA adapter on FunctionGemma (r=16, α=32): https://huggingface.co/sumitagrawal/functiongemma-270m-tool-agent/blob/main/README.md
- Indic tokenizer comparison (Gemma 3, 262k vocab): https://huggingface.co/vivekvar/indictok-256k
- Sarvam AI on Gemma 3 tokenization for Indian languages: https://deepmind.google/models/gemma/gemmaverse/sarvam-ai/
- BrahmicTokenizer paper (cites Gemma 3 vocab size): https://arxiv.org/pdf/2605.29379
- llama-cpp-python grammars → JSON: https://til.simonwillison.net/llms/llama-cpp-python-grammars
- llama.cpp grammars: https://www.mintlify.com/ggml-org/llama.cpp/advanced/grammars
- Small-model CPU latency notes: https://wandb.ai/c-metrics/model-latency-benchmarking/reports/Inference-Speed-Benchmarking-GPU-CPU-LlamaCPP-ONNX--VmlldzoxMDQwMzIwNA
- Small language model round-ups: https://www.turingpost.com/p/slmslist , https://www.siliconflow.com/articles/best-small-llms-for-personal-projects
