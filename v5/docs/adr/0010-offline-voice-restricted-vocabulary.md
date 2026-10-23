# 0010. Offline voice with a vocabulary limited to the shop's words

* Status: Accepted
* Date: 2026-10-21 (5.3.0)

Full design and measurements: [VOICE_DESIGN.md](../VOICE_DESIGN.md).

## Context

The owner asks questions mostly in spoken Hinglish. A Hindi recogniser writes that as
Devanagari with English words in Devanagari spelling ("लास्ट मंथ का बैलेंस"). General Hindi
recognisers that fit a 4 GB Celeron have a 20–25 % word error rate. Windows has no offline
Hindi recogniser. The internet is not reliable.

## Decision

* Use **Vosk's small Hindi model** (`vosk-model-small-hi-0.22`, 42 MB, Apache 2.0, no AVX
  needed), offline. Since 5.4 it ships in `bundled/voice/` and is unpacked on first use.
* Decode with a **grammar limited to the shop's words**: the question words of the
  assistant's corpus as spoken, numbers and periods, and the Hindi copies of every customer,
  village and item name. When that hearing does not make sense, decode the same audio with
  the model's full dictionary.
* Teach System 1 the spoken form: a fourth corpus style, `sp`, generated from the Hinglish
  templates by a hand-made table of ~300 words (`hth/assistant/spoken.py`).
* Speak answers back in Hindi with Windows' own voices through SAPI (`pywin32`).
* Never record from a loopback device such as Stereo Mix (it records the speakers).

## Consequences

* Measured on 150 held-out spoken questions: 99.3 % answered right clean, 95.3 % with
  shop-like noise, about 0.1–0.2 s per question. Real recordings will be lower;
  `tools/assistant/eval_voice.py --recordings` measures them on the PC.
* Names missing from the model's dictionary get a *voice spelling* once and are cached.
* Adds `vosk`, `sounddevice`, `pywin32` and a 42 MB file to the app.

## Alternatives considered

* **Cloud speech-to-text.** Needs internet and sends audio out.
* **Vosk's large Hindi model (1.5 GB) or Whisper.** Too heavy for the PC; Whisper kept as a
  possible optional System 2 voice later.
* **Windows speech recognition.** No offline Hindi.
