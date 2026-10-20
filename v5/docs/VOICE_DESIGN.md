# Voice for the assistant — design (for review)

Status: **V1 shipped in 5.3.0 (2026-10-21)** — microphone, Vosk small Hindi with the shop's
vocabulary, open-vocabulary fallback, voice spellings, the `sp` corpus style, period / number
fixes, spoken answers. Measured results in [§12](#12-v1-as-built-and-measured). Decisions:
go ahead with V1 (2026-10-20); speak answers by default only when the question was spoken
(Settings can make it always / never); a recorded test set is still to come.

Who it is for: the same one user as the chat — the shop owner, who would rather speak than
type. He asks mostly in **Hinglish**; the answer appears on screen and is **spoken in Hindi**.
Offline, on the shop PC (Celeron, 4 GB). The same pipeline later serves WhatsApp voice notes.

---

## 1. The key point: spoken Hinglish is Hindi speech with English words

"Hinglish" is a way of *writing*. Spoken, *"Ramesh ka last month ka balance batao"* is Hindi
speech with a few English words, and a Hindi speech recogniser writes it in Devanagari:
**"रमेश का लास्ट मंथ का बैलेंस बताओ"**. So the voice model does not have to produce Roman
Hinglish. System 1 just has to understand Hinglish written in Devanagari.

Probe on 16 such questions (2026-10-20, current System 1, text only):

* **14 / 16 intents right** already. "बैलेंस", "स्टॉक", "रेट", "मार्केट … टोटल" work through the
  phonetic keys.
* Missed: "टोटल बैलेंस" (→ ledger) and "पेमेंट ओवरड्यू" (→ collection list).
* **Real bug:** the period parser does not read **"लास्ट मंथ" / "इस मंथ"**, so a spoken "last
  month" would fall back to a default period. The answer card shows its period, so the user
  would see it, but it must be fixed before voice ships. Typed Devanagari has the same gap.

## 2. Architecture: System 1 voice, System 2 voice

Mirrors the text side: a small, fast, specialised model always on, and a bigger model only when
the first one is unsure.

```
🎤 → voice-activity detection (starts on speech, stops after ~1 s of silence)
   → SYSTEM 1 VOICE: Vosk small Hindi (42 MB), streaming - words appear in the box as he speaks
        decoding limited to the shop's own words (question words, periods, numbers,
        Hindi copies of customer and item names)
   → transcript (Devanagari) → normalise → entity linking → System 1 intent → answer
   → unsure, or [unk] where a name should be, or the name is not found?
        → SYSTEM 2 VOICE (optional): Whisper fine-tuned for Hindi, int8, on the same audio,
          prompted with the likely names and words → run the pipeline again
        → still unsure → the usual ask-back ("कौन से रमेश?"), which he can answer by voice
   → answer card on screen + a short spoken summary (Windows Hindi voice)
```

### 2.1 System 1 voice — Vosk small Hindi with the shop's vocabulary

* [`vosk-model-small-hi-0.22`](https://alphacephei.com/vosk/models): 42 MB, Apache 2.0,
  listed word error rate 20.9 % (IITM challenge set) / 24.7 % (MUCS). It is Kaldi based and
  streams, giving partial words while he speaks. It runs comfortably on small CPUs and needs no
  AVX, which suits the Celeron.
* **What makes it "System 1": it is limited to what the shop says.** Vosk's small models accept
  a word list at runtime ("most small models allow dynamic vocabulary reconfiguration" — still
  to be confirmed on the Hindi one). The list holds:
  * the corpus question words, as spoken (§3);
  * period and number words;
  * the **Hindi copies of every customer and item name**, which the app already stores.

  A general 20–25 % error rate becomes much lower when the recogniser can only choose among a
  few thousand words that make sense here.
* Limits:
  * A name missing from the model's own dictionary cannot be added at runtime; it comes out as
    `[unk]`, and the assistant asks back or hands over to System 2 voice.
  * Two recognisers can share the one loaded model: a restricted one and an open one. The open
  one catches anything outside the list, such as an off-topic question.
* Not chosen:
  * Windows speech recognition: no offline Hindi recogniser. This laptop has only en-US and
    en-IN.
  * The big Vosk Hindi model: 1.5 GB, too heavy for 4 GB.
  * Cloud speech-to-text: possible later through the cloud router, never required.

### 2.2 System 2 voice — Whisper fine-tuned for Hindi (optional, later)

* Candidate: [`vasista22/whisper-hindi-small`](https://huggingface.co/vasista22/whisper-hindi-small)
  (Whisper small fine-tuned on GramVaani, Shrutilipi, FLEURS and others; its large-v2 sibling
  reports 6.8 % WER on FLEURS). It would be converted to CTranslate2 int8, about 250 MB, and run
  with `faster-whisper`, which is already installed on this laptop. For comparison,
  [Collabora's Hindi small fine-tune](https://www.collabora.com/news-and-blog/news-and-events/breaking-language-barriers-fine-tuning-whisper-for-hindi.html)
  reports 10–17 % on FLEURS.
* It gets the domain words and the most likely names as its initial prompt, which biases
  spelling towards the shop's vocabulary.
* Cost on the Celeron: probably several seconds per question. That is why it runs only when
  System 1 voice fails, in its own process like System 2 text, and is stopped when idle.
  **Measure on the shop PC before deciding.**
* Alternative to evaluate: AI4Bharat IndicConformer as a Hindi-only int8 ONNX pack
  ([~131 MB per language](https://huggingface.co/nmukthap/vertexvoice-indic); the full
  multilingual int8 model is [0.62 GB, ~1.1 GB RAM](https://huggingface.co/yashwork-byte/indic-conformer-600m-int8-onnx)).
  Strong on Hindi, but these are community repackagings.

## 3. Teaching System 1 spoken Hinglish (no audio needed)

* A fourth corpus style, **`sp` (spoken)**, is generated automatically from the Hinglish
  templates. It writes them the way a recogniser does:
  * English words in Devanagari, from a loanword table: बैलेंस, स्टॉक, रेट, पेमेंट, टोटल,
    लास्ट मंथ, वीक, एंट्री, ऑर्डर, प्रॉफिट, कैश;
  * Hindi words via the existing transliterator;
  * no punctuation, numbers as words (दस, पाँच सौ);
  * recogniser-like slips: dropped का / की, vowel length, words run together.
* Period and number parser: add the Devanagari loanword forms (लास्ट / पिछला मंथ, इस वीक, टुडे,
  लास्ट थर्टी डेज़, टेन, ट्वेंटी) and more Hindi number words.
* Concept lexicon: bailens, pement, ovardyu, kaish, difoltar, … (built from the loanword table,
  so nothing is listed twice).
* `eval.py` reports the `sp` style separately, with the same ≥ 95 % target.

## 4. Speaking the answer

* **Windows' own Hindi voices, Kalpana and Hemant** (offline "OneCore" voices). They are
  installed on this laptop. On the shop PC: Settings → Time & language → Speech → add the Hindi
  voice if it is missing.
* Only a short summary is spoken: the headline and the first line. Amounts are said in rupees
  in Hindi ("छह हज़ार पाँच सौ अट्ठानवे रुपये"), names from their Hindi copies, and tables are
  not read out.
* Ask-back is spoken too: "कौन से रमेश? रोहतक वाले, भिवानी वाले या हिसार वाले?". He answers
  "रोहतक वाले" or "दूसरे", which the choice resolver already understands.
* A mute button, and Settings → Assistant → Speak answers (on or off).
* Fallback if a PC has no Hindi voice: Piper neural voices. Hindi ones exist as community
  conversions (e.g. [`hi_IN` rohan](https://huggingface.co/pronoobie/piper-voices-hindi)), but
  their upstream status is unclear, so this is not the default.

## 5. How it looks

* One big 🎤 button:
  * tap, a short beep, and the button turns red with a level bar while listening;
  * the words appear in the box live;
  * it stops on silence or a second tap;
  * the question is sent 1.5 s later unless he taps the text to correct it.
* Options stay as buttons, so a tap still works.
* Push-to-talk key (F2) for the laptop keyboard.

## 6. Shop PC budget (Celeron, 4 GB)

| part | memory | time per question |
|---|---|---|
| Vosk small Hindi | ~150–300 MB | streaming: text ready when he stops talking |
| System 1 text (existing) | ~30 MB | < 20 ms |
| Windows Hindi voice | system | ~0.3 s to start speaking |
| System 2 voice (optional) | ~500 MB, own process | seconds; only on demand |
| System 2 text (optional, existing) | ~250 MB, own process | ~1 s; only on demand |

All the parts together fit in 4 GB next to the app (≈ 200 MB).

## 7. Getting better at *his* voice (later, Kaggle)

* Step 1 needs no training: restricting the vocabulary and adding the `sp` style do it.
* Step 2 is a test set: 50–100 questions recorded by him, stored only on the PC. It measures
  word errors and end-to-end answer accuracy on his accent (Haryanvi Hindi) and the shop's
  noise.
* Step 3 is fine-tuning Whisper small/base Hindi in a single Kaggle cell, like the text one.
  Training data:
  * synthetic speech of the corpus questions (Windows Hindi voices and others);
  * optionally some of his recordings.

  **Privacy:** recordings that contain real customer names would leave the PC, so record those
  with made-up names, or keep the recordings out of training.

## 8. Packages and downloads (nothing is downloaded without your OK)

* `pip install vosk` (a small wheel). `sounddevice` for the microphone is already on this
  laptop and would be added to requirements.
* `vosk-model-small-hi-0.22` (42 MB). It is installed from Settings → Assistant → *Install voice
  model…*, the same way as the text model; the app never downloads by itself.
* System 2 voice: a Hindi Whisper converted to CTranslate2 (~250 MB). The conversion can be a
  Kaggle cell.

## 9. Phases

| phase | delivers |
|---|---|
| **V1** | microphone + Vosk small Hindi + vocabulary from the shop + `sp` corpus style + period / number fixes + spoken answers with the Windows Hindi voice |
| **V2** | System 2 voice (Whisper Hindi) for unsure questions; the recorded test set and a voice eval |
| **V3** | WhatsApp / Telegram voice notes through the same pipeline (audio file in, voice note out) |
| **V4** | fine-tuning on his voice (Kaggle cell) |

The period-parser bug (§1) is fixed at the start of V1, since it affects typed Devanagari too.

## 10. Decisions needed

1. Go ahead with **V1**?
2. OK to download **`vosk`** and the **42 MB Hindi model** to test on this laptop? I would test
   with questions spoken by the Windows Hindi voice, since I cannot speak into the microphone.
3. **Speak answers aloud by default**, or only when turned on?
4. Will you record a **test set in his voice** (kept on the PC), so the real accuracy is known
   before he relies on it?

## 11. Risks

* Vosk small Hindi is at 21–25 % WER on general speech. The restricted vocabulary should help a
  lot, but his accent is unknown until measured (§7).
* A name outside the model's dictionary comes out as `[unk]`. This is handled by ask-back and
  by System 2 voice.
* Shop noise and laptop microphones: a ₹300–500 USB or headset microphone helps more than any
  model. The silence threshold calibrates itself from the first half second.
* A misheard question can look like a good one. Every answer shows what was heard and the
  period and name it used, so a wrong hearing is visible and can be corrected with one tap.

## 12. V1 as built and measured

* `hth/assistant/voice.py` - model, vocabulary, `Listener` (microphone or a recorded source),
  `voice_spellings`, `install_zip`; `hth/assistant/speech.py` - Windows voices through SAPI
  (OneCore token list, no extra download), `summary()` of a reply card;
  `hth/assistant/spoken.py` - the Hinglish → Devanagari table and `to_spoken`.
* The model's whole dictionary (178,957 words) is read straight from the symbol table in
  `graph/Gr.fst`, so the app knows exactly which shop words the recogniser can hear.
  Vosk's dynamic vocabulary works on the small Hindi model (it has `HCLr.fst` + `Gr.fst`).
* `Assistant.ask_heard(heard, session, alternative)`: the restricted hearing is tried first; if
  it does not make sense, the open-vocabulary hearing of the same audio (computed only then).
  Trials write no audit lines; System 2 answers are cached so a trial and the real ask do not
  run the model twice. A reply to an ask-back ("रोहतक वाले") is used as heard.
* Results (`tools/assistant/eval_voice.py`, 150 held-out spoken questions, Windows Hindi
  voices at four speeds, made-up names, this laptop):

  | | word errors | answered right | per question |
  |---|---|---|---|
  | open vocabulary, clean | 11.6 % | 96.7 % | 887 ms |
  | restricted, clean | 7.7 % | 98.7 % | 98 ms |
  | **app (restricted → open), clean** | 7.4 % | **99.3 %** | 110 ms |
  | open vocabulary, 15 dB noise | 31.4 % | 84.0 % | 1180 ms |
  | **app, 15 dB noise** | 18.5 % | **95.3 %** | 171 ms |

  Synthetic speech is cleaner than a person in a shop; the recorded test set (§7) is the real
  measure.
* Since 5.4.0 the model zip ships with the app (`bundled/voice/`) and is unpacked on first use
  (`voice.ensure_model`); the microphone is chosen by `voice.choose_device` (never a loopback
  such as "Stereo Mix", which can be Windows' default recording device - found on the first
  real test, where every question came back as "nothing heard").
* Not done in V1: System 2 voice (Whisper), WhatsApp voice notes (the `Listener` already takes a
  recorded source), fine-tuning on his voice.
