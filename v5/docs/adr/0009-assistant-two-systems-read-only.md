# 0009. Assistant: System 1 always, System 2 optional, read-only

* Status: Accepted
* Date: 2026-10-20 (5.2.0)

Full design: [AI_CHAT_DESIGN.md](../AI_CHAT_DESIGN.md).

## Context

The owner wanted to ask about the shop in plain words (Hindi, Hinglish or English) and get
exact answers. The shop PC is a Celeron with 4 GB and often no internet. Names are where a
wrong answer hurts most (three customers called Ramesh). An answer that is wrong but
plausible is worse than no answer.

## Decision

* The assistant **chooses a query; it never writes numbers**. Every answer comes from a
  read-only *tool* that wraps a service method the reports already use, so the chat and the
  matching report always agree. Each tool checks the user's permission.
* A deterministic pipeline: normalise (language, periods, numbers) → link names to the
  shop's own customers and items (replaced by `<C1>` / `<I1>`; ambiguous names are asked
  back, never guessed) → **System 1**, a small NumPy softmax classifier trained on a
  synthetic corpus of question templates, picks the intent in under a millisecond.
* **System 2**, an optional fine-tuned small language model (GGUF through
  `llama-cpp-python`), is consulted only when System 1 is unsure. It runs in its own process
  (a crash there only switches it off) and is trusted only when it agrees with one of
  System 1's three best guesses; otherwise the assistant asks "did you mean …?".
* Training data is generated, never taken from the shop. The audit log records the tool and
  its arguments, not the question text. Nothing leaves the PC.

## Consequences

* Works with nothing to install; System 1 alone answered 95–96 % of unseen phrasings
  correctly (see the CHANGELOG for 5.2 and 5.3).
* New kinds of question need new templates in `hth/assistant/data.py` and, for System 2, a
  rebuilt Kaggle cell (`test_kaggle_cell_is_up_to_date` checks it).
* The core (`Assistant.ask(text, session) → Reply`) has no Tk, so a bot or voice loop can
  reuse it.

## Alternatives considered

* **A language model writing the answer.** Can be silently wrong with numbers; too heavy
  for the PC.
* **A cloud model.** Needs internet and sends the shop's data out; kept as a possible later
  option for hard questions, never required.
* **Rules only.** Brittle across three languages and spelling variants.
