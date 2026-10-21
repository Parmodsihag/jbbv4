"""Assistant: ask about the shop in Hindi, Hinglish or English - big text, few buttons.

The screen only draws; :mod:`hth.assistant.core` does the understanding and answering (the
same object a WhatsApp / Telegram bot or a voice loop will use later).  Answers are read-only.

Voice: 🎤 (or F2) listens with :mod:`hth.assistant.voice`; the words appear in the box as they
are heard and the question goes 1.2 s after he stops speaking, unless he taps the box to
correct it.  Answers to spoken questions are spoken back (:mod:`hth.assistant.speech`).
"""

from __future__ import annotations

import logging
import queue

import customtkinter as ctk

from hth import i18n
from hth.assistant import speech, voice
from hth.assistant.core import Assistant, Reply, Session
from hth.assistant.system2 import LocalModel, models_dir
from hth.i18n import Raw
from hth.ui import theme
from hth.ui.format import money, qty
from hth.ui.views.base import BaseView
from hth.ui.widgets.forms import primary_button, secondary_button

log = logging.getLogger(__name__)

MAX_BUBBLES = 60
MAX_ROWS = 12
AUTO_SEND_MS = 1200


def _t(en: str, hi: str) -> Raw:
    """Interface text for this screen, already in the interface language."""
    return Raw(hi if i18n.is_hindi() else en)


class AssistantView(BaseView):
    key = "assistant"
    title = "Assistant"
    permission = None  # every answer checks the permission of what it looks up

    def build(self) -> None:
        self.session = Session()
        self.assistant: Assistant | None = None
        self.system2: LocalModel | None = None
        self._ready = False
        self._busy = False
        self._queued: tuple[str, str] | None = None
        self._bubbles: list[ctk.CTkFrame] = []
        self._typing: ctk.CTkFrame | None = None
        self._row = 0
        # voice
        self.voice: voice.VoiceModel | None = None
        self.speaker = speech.Speaker()
        self._grammar: str | None = None
        self._listener: voice.Listener | None = None
        self._events: queue.Queue = queue.Queue()
        self._heard: tuple[voice.Heard, bytes] | None = None
        self._auto_send: str | None = None
        self._spoken = False
        self._mic_name = ""
        self._voice_state = "missing"  # preparing | ready | missing

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.chat = ctk.CTkScrollableFrame(self, fg_color=theme.color("surface"), corner_radius=12)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 8))
        self.chat.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        bottom.grid_columnconfigure(0, weight=1)
        self.chips = ctk.CTkFrame(bottom, fg_color="transparent")
        self.chips.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.entry = ctk.CTkEntry(
            bottom,
            height=48,
            font=theme.font(17),
            placeholder_text=_t("Ask… e.g. How much does Ramesh owe?", "पूछिए… जैसे: रमेश का कितना बकाया है?"),
        )
        self.entry.grid(row=1, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self.send())
        self.entry.bind("<F2>", lambda _e: self._voice())
        self.entry.bind("<Key>", self._typed, add="+")
        self.entry.bind("<Button-1>", self._typed, add="+")
        self.send_button = primary_button(
            bottom, _t("Ask", "पूछो"), self.send, height=48, width=110, font=theme.font(16, "bold")
        )
        self.send_button.grid(row=1, column=1, padx=(8, 0))
        self.mic_button = secondary_button(bottom, Raw("🎤"), self._voice, height=48, width=52, font=theme.font(18))
        self.mic_button.grid(row=1, column=2, padx=(8, 0))
        foot = ctk.CTkFrame(bottom, fg_color="transparent")
        foot.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        foot.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(foot, text="", font=theme.font(11), text_color=theme.color("muted"), anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        secondary_button(foot, _t("New chat", "नई बात"), self.new_chat, height=28, width=96, font=theme.font(12)).grid(
            row=0, column=1
        )

    # Life cycle ----------------------------------------------------------------------------
    def on_show(self, question: str | None = None, listen: bool = False, **kwargs) -> None:
        if self.assistant is None:
            self._start()
        self.entry.focus_set()
        if question:
            self.ask(question)
        elif listen:
            self.listen()

    def listen(self) -> None:
        """Start listening now, or as soon as the voice is ready (F2 / 🎤 from anywhere)."""
        if self._voice_state == "ready" or (self._ready and self._voice_state == "missing"):
            self._voice()  # listens - or says why it cannot (no voice model, no microphone)
        else:
            self._listen_when_ready = True

    def _start(self) -> None:
        data_dir = self.ctx.settings.data_dir
        self.voice = voice.VoiceModel(voice.voice_dir(data_dir))
        self.system2 = LocalModel(models_dir(data_dir))
        self.assistant = Assistant(self.ctx.db, self.ctx.user, model_dir=data_dir / "assistant", system2=self.system2)
        self._set_status(
            _t("Getting ready… (the first time takes up to a minute)", "तैयार हो रहा है… (पहली बार एक मिनट तक)")
        )
        self.send_button.configure(state="disabled")
        self.run_async(self.assistant.warm_up, self._on_ready, self._on_start_failed)

    def _on_ready(self, _result) -> None:
        self._ready = True
        self.send_button.configure(state="normal")
        self._show_status()
        self._reply_bubble(self.assistant.ask("help" if not i18n.is_hindi() else "मदद", Session()))
        self._fill_chips()
        if self._queued:
            text, shown = self._queued
            self._queued = None
            self._ask_now(text)
        if self.voice is not None and voice.backend_available():
            self._voice_state = "preparing"
            self.run_async(self._prepare_voice, self._voice_prepared, self._voice_failed)

    # Voice -------------------------------------------------------------------------------------
    def _prepare_voice(self) -> tuple[str, dict[str, str]] | None:
        """Unpack the bundled model if needed, load it and build the shop's vocabulary (background)."""
        if voice.ensure_model(self.ctx.settings.data_dir) is None:
            return None
        self.voice = voice.VoiceModel(voice.voice_dir(self.ctx.settings.data_dir))
        rows = self.ctx.db.fetchall("SELECT name_hi, details_hi FROM customers")
        names = [r["name_hi"] for r in rows] + [r["details_hi"] for r in rows]
        names += [r["name_hi"] for r in self.ctx.db.fetchall("SELECT name_hi FROM items")]
        shop = voice.shop_words(names)
        known = self.voice.words
        self.voice.model()
        cache = self.ctx.settings.data_dir / "assistant" / "voice_spellings.json"
        spellings = voice.voice_spellings(
            (w for w in shop if known and w not in known), self.voice, speech.synthesize, cache
        )
        heard_forms = voice.shop_words(spellings.values())
        return voice.grammar(voice.question_words() | shop | heard_forms, known), spellings

    def _voice_failed(self, exc: Exception) -> None:
        log.warning("voice: %s", exc)
        self._voice_state = "missing"

    def _voice_prepared(self, result) -> None:
        if result is None:
            self._voice_state = "missing"
            return
        self._voice_state = "ready"
        self._grammar, spellings = result
        if self.assistant is not None and spellings:
            self.assistant.set_voice_spellings(spellings)
        self._show_status()
        if getattr(self, "_listen_when_ready", False):
            self._listen_when_ready = False
            self._voice()

    def _voice(self) -> None:
        if self._listener is not None and self._listener.running:
            self._listener.stop()
            return
        if self._voice_state == "preparing":
            self.ctx.app.toast(_t("Getting the voice ready - a moment…", "आवाज़ तैयार हो रही है - एक पल…"))
            return
        if self.voice is None or not self.voice.available():
            self.ctx.app.toast(
                _t(
                    "Install the voice model first: Settings → Assistant → Install voice model…",
                    "पहले आवाज़ मॉडल लगाएँ: सेटिंग्स → सहायक → आवाज़ मॉडल लगाएँ…",
                ),
                "warning",
            )
            return
        if not self._ready or self._busy:
            return
        mic = voice.choose_device(self.ctx.prefs.assistant_mic())
        if mic is None:
            self.ctx.app.toast(_t("No microphone found on this PC.", "इस कंप्यूटर में कोई माइक नहीं मिला।"), "error")
            return
        self.speaker.stop()
        self._cancel_auto_send()
        self._heard = None
        self.entry.delete(0, "end") if self.entry.get() else None
        self._events = queue.Queue()
        self._mic_name = mic.name
        self._listener = voice.Listener(
            self.voice, self._grammar, self._events.put, device=mic.index, device_name=mic.name
        )
        self._listener.start()
        self.mic_button.configure(text=Raw("■"), fg_color=theme.color("danger"), text_color=theme.color("on_status"))
        self._set_status(_t("Listening… speak now", "सुन रहा हूँ… बोलिए"))
        self.after(50, self._poll_voice)

    def _poll_voice(self) -> None:
        if not self._alive:
            return
        done = False
        try:
            while True:
                kind, value = self._events.get_nowait()
                if kind == "level":
                    bars = int(value * 8 + 0.5)
                    self._set_status(_t("Listening… ", "सुन रहा हूँ… ") + "▮" * bars + "▯" * (8 - bars))
                elif kind == "partial":
                    self._show_heard(value)
                elif kind == "final":
                    heard, pcm, rate = value
                    if heard.text:
                        self._heard_ready(heard, pcm, rate)
                    else:  # there was speech, but none of the shop's words: try the whole dictionary
                        self._set_status(_t("Working out what was said…", "समझ रहा हूँ…"))
                        self.run_async(
                            lambda pcm=pcm, rate=rate: self.voice.transcribe(pcm, None, rate),
                            lambda h, pcm=pcm, rate=rate: self._heard_ready(h, pcm, rate),
                            lambda exc: self._show_status(),
                        )
                    done = True
                elif kind == "timeout":
                    self._set_status(self._nothing_heard(value or {}))
                    done = True
                elif kind == "error":
                    self.ctx.app.toast(_t(f"Microphone: {value}", f"माइक: {value}"), "error")
                    self._show_status()
                    done = True
        except queue.Empty:
            pass
        if done or self._listener is None or not self._listener.running and self._events.empty():
            self.mic_button.configure(text=Raw("🎤"), fg_color=theme.color("surface2"), text_color=theme.color("text"))
            return
        self.after(50, self._poll_voice)

    def _heard_ready(self, heard: voice.Heard, pcm: bytes, rate: int) -> None:
        if not heard.text:
            self._set_status(
                _t(
                    "I heard a voice but could not make out the words - speak a little closer to the microphone.",
                    "आवाज़ आई पर शब्द समझ नहीं आए - माइक के थोड़ा पास से साफ़ बोलिए।",
                )
            )
            return
        self._heard = (heard, pcm, rate)
        self._show_heard(heard.text)
        self._set_status(_t("Sending… tap the text to correct it", "भेज रहा हूँ… बदलना हो तो लिखे हुए पर दबाएँ"))
        self._auto_send = self.after(AUTO_SEND_MS, self._send_heard)

    def _nothing_heard(self, info: dict) -> str:
        if info.get("level", 0.0) < 0.01:  # not even room noise: the wrong device, muted, or blocked
            mic = info.get("device") or self._mic_name
            return _t(
                f"No sound is coming from “{mic}”. Choose your microphone in Settings → Assistant → "
                "Microphone, and check that it is not muted.",
                f"“{mic}” से कोई आवाज़ नहीं आ रही। सेटिंग्स → सहायक → माइक में अपना माइक चुनें, और देखें कि माइक बंद (mute) तो नहीं।",
            )
        return _t("I did not hear anything - tap 🎤 and speak.", "कुछ सुनाई नहीं दिया - 🎤 दबाकर बोलिए।")

    def _show_heard(self, text: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def _typed(self, _event=None) -> None:
        """He touched the box while a spoken question was about to go: let him correct it."""
        if self._auto_send is not None:
            self._cancel_auto_send()
            self._heard = None
            self._set_status(_t("Correct the text, then press Ask.", "सुधारकर 'पूछो' दबाएँ।"))

    def _cancel_auto_send(self) -> None:
        if self._auto_send is not None:
            self.after_cancel(self._auto_send)
            self._auto_send = None

    def _send_heard(self) -> None:
        self._auto_send = None
        if self._heard is None or self._busy:
            return
        heard, pcm, rate = self._heard
        self._heard = None
        self.entry.delete(0, "end")
        self._spoken = True
        label = self._user_bubble("🎤 " + heard.text)
        self._busy = True
        self.send_button.configure(state="disabled")
        self._typing = self._bubble("bot")
        ctk.CTkLabel(self._typing, text=Raw("…"), font=theme.font(18, "bold"), text_color=theme.color("muted")).pack(
            padx=16, pady=6
        )
        self._scroll_down()

        def work():
            return self.assistant.ask_heard(
                heard.text, self.session, alternative=lambda: self.voice.transcribe(pcm, None, rate).text
            )

        def done(result):
            used, reply = result
            if used != heard.text:  # the open-vocabulary hearing made more sense
                label.configure(text=Raw("🎤 " + used))
            self._answered(reply)

        self.run_async(work, done, self._ask_failed)

    def _on_start_failed(self, exc: Exception) -> None:
        self._set_status(_t(f"The assistant could not start: {exc}", f"सहायक शुरू नहीं हो पाया: {exc}"))

    def _show_status(self) -> None:
        parts = [_t("Ready", "तैयार")]
        if self.system2 is not None and self.system2.available():
            parts.append(_t("language model on", "भाषा मॉडल चालू"))
        if self.voice is not None and self.voice.available():
            parts.append(_t("🎤 or F2 to speak", "बोलने के लिए 🎤 या F2"))
        parts.append(_t("read-only: it only looks things up", "केवल देखता है, कुछ बदलता नहीं"))
        self._set_status(" · ".join(parts))

    def _set_status(self, text: str) -> None:
        self.status.configure(text=Raw(text))

    def _fill_chips(self) -> None:
        for w in self.chips.winfo_children():
            w.destroy()
        examples = (
            ["आज कितनी बिक्री हुई?", "किसके करार की तारीख निकल गई?", "क्या मँगवाना है?", "सबसे बड़े बकायेदार"]
            if i18n.is_hindi()
            else ["Sales today", "Overdue promises", "What should I reorder?", "Biggest debtors"]
        )
        for text in examples:
            secondary_button(
                self.chips, Raw(text), lambda t=text: self.ask(t), height=30, font=theme.font(12), corner_radius=15
            ).pack(side="left", padx=(0, 6))

    def new_chat(self) -> None:
        self.session = Session()
        for b in self._bubbles:
            b.destroy()
        self._bubbles.clear()
        self._typing = None
        if self._ready:
            self._reply_bubble(self.assistant.ask("help" if not i18n.is_hindi() else "मदद", Session()))
        self.entry.focus_set()

    # Asking ----------------------------------------------------------------------------------
    def send(self) -> None:
        if self._heard is not None:  # Ask pressed while a spoken question waits to go
            self._cancel_auto_send()
            self._send_heard()
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._spoken = False
        self.ask(text)

    def ask(self, text: str, shown: str | None = None) -> None:
        if self._busy:
            return
        self._user_bubble(shown or text)
        if not self._ready:
            self._queued = (text, shown or text)
            return
        self._ask_now(text)

    def _ask_now(self, text: str) -> None:
        self._busy = True
        self.send_button.configure(state="disabled")
        self._typing = self._bubble("bot")
        ctk.CTkLabel(self._typing, text=Raw("…"), font=theme.font(18, "bold"), text_color=theme.color("muted")).pack(
            padx=16, pady=6
        )
        self._scroll_down()
        self.run_async(lambda: self.assistant.ask(text, self.session), self._answered, self._ask_failed)

    def _answered(self, reply: Reply) -> None:
        self._drop_typing()
        self._busy = False
        self.send_button.configure(state="normal")
        self._reply_bubble(reply)
        self.entry.focus_set()
        if self._auto_send is None and not (self._listener is not None and self._listener.running):
            self._show_status()
        mode = self.ctx.prefs.assistant_speak()
        if mode == "always" or (mode == "voice" and self._spoken):
            self.speaker.say(speech.summary(reply), reply.lang)

    def destroy(self) -> None:
        if self._listener is not None:
            self._listener.stop()
        self.speaker.close()
        super().destroy()

    def _ask_failed(self, exc: Exception) -> None:
        self._drop_typing()
        self._busy = False
        self.send_button.configure(state="normal")
        bubble = self._bubble("bot")
        self._label(bubble, _t(f"Something went wrong: {exc}", f"कुछ गड़बड़ हो गई: {exc}"), 14, color="danger")

    def _drop_typing(self) -> None:
        if self._typing is not None:
            outer = self._typing.master
            if outer in self._bubbles:
                self._bubbles.remove(outer)
            outer.destroy()
            self._typing = None

    # Drawing -----------------------------------------------------------------------------------
    def _wrap(self) -> int:
        width = self.chat.winfo_width()
        return max(320, int((width if width > 50 else 900) * 0.68))

    def _bubble(self, side: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(self.chat, fg_color="transparent")
        outer.grid(row=self._row, column=0, sticky="ew", padx=8, pady=5)
        self._row += 1
        mine = side == "user"
        bubble = ctk.CTkFrame(outer, fg_color=theme.color("accent" if mine else "surface2"), corner_radius=14)
        bubble.pack(side="right" if mine else "left", padx=(60, 0) if mine else (0, 60))
        self._bubbles.append(outer)
        while len(self._bubbles) > MAX_BUBBLES:
            self._bubbles.pop(0).destroy()
        return bubble

    def _label(self, parent, text: str, size: int, weight: str = "normal", color: str = "text", **pack) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=Raw(text),
            font=theme.font(size, weight),
            text_color=theme.color(color),
            justify="left",
            anchor="w",
            wraplength=self._wrap(),
        )
        label.pack(fill="x", padx=14, pady=pack.get("pady", (2, 2)))
        return label

    def _user_bubble(self, text: str) -> ctk.CTkLabel:
        bubble = self._bubble("user")
        label = self._label(bubble, text, 16, color="accent_text", pady=(8, 8))
        self._scroll_down()
        return label

    def _pick(self, option) -> None:
        self.speaker.stop()
        self.ask(option.reply, shown=option.label)

    def _reply_bubble(self, reply: Reply) -> None:
        bubble = self._bubble("bot")
        self._label(bubble, reply.text, 16, "bold", pady=(10, 2))
        for line in reply.lines:
            self._label(bubble, line, 14)
        if reply.rows:
            self._table(bubble, reply)
        if reply.options:
            box = ctk.CTkFrame(bubble, fg_color="transparent")
            box.pack(fill="x", padx=10, pady=(6, 4))
            for opt in reply.options:
                ctk.CTkButton(
                    box,
                    text=Raw(opt.label),
                    font=theme.font(15),
                    height=40,
                    anchor="w",
                    fg_color=theme.color("surface"),
                    hover_color=theme.color("surface_hover"),
                    text_color=theme.color("text"),
                    border_width=1,
                    border_color=theme.color("surface3"),
                    command=lambda o=opt: self._pick(o),
                ).pack(fill="x", pady=3)
        if reply.actions:
            row = ctk.CTkFrame(bubble, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=(4, 2))
            for label, view, kwargs in reply.actions:
                secondary_button(
                    row,
                    Raw(label + " →"),
                    lambda v=view, k=kwargs: self.ctx.app.navigate(v, **k),
                    height=32,
                    font=theme.font(13),
                ).pack(side="left", padx=(0, 6))
        if reply.looked_up:
            self._label(bubble, "🔎 " + reply.looked_up, 11, color="muted", pady=(4, 8))
        else:
            ctk.CTkFrame(bubble, height=6, fg_color="transparent").pack()
        self._scroll_down()

    def _table(self, parent, reply: Reply) -> None:
        grid = ctk.CTkFrame(parent, fg_color=theme.color("surface"), corner_radius=8)
        grid.pack(fill="x", padx=12, pady=(6, 4))
        kinds = [k for _t, k in reply.columns]
        for c, (title, kind) in enumerate(reply.columns):
            grid.grid_columnconfigure(c, weight=1 if kind == "text" else 0)
            ctk.CTkLabel(
                grid,
                text=Raw(title),
                font=theme.font(12, "bold"),
                text_color=theme.color("muted"),
                anchor="w" if kind == "text" else "e",
            ).grid(row=0, column=c, sticky="ew", padx=8, pady=(4, 2))
        for r, row in enumerate(reply.rows[:MAX_ROWS], start=1):
            for c, value in enumerate(row[: len(kinds)]):
                kind = kinds[c]
                ctk.CTkLabel(
                    grid, text=Raw(_cell(value, kind)), font=theme.font(14), anchor="w" if kind == "text" else "e"
                ).grid(row=r, column=c, sticky="ew", padx=8, pady=1)
        more = len(reply.rows) - MAX_ROWS
        if more > 0:
            ctk.CTkLabel(
                grid,
                text=_t(f"… and {more} more", f"… और {more}"),
                font=theme.font(12),
                text_color=theme.color("muted"),
                anchor="w",
            ).grid(row=MAX_ROWS + 1, column=0, columnspan=len(kinds), sticky="ew", padx=8, pady=(0, 4))

    def _scroll_down(self) -> None:
        def go():
            try:
                self.chat._parent_canvas.yview_moveto(1.0)
            except Exception:  # noqa: BLE001 - cosmetic
                pass

        self.after(30, go)


def _cell(value, kind: str) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-" and value[:4].isdigit():
        return f"{value[8:]}-{value[5:7]}-{value[:4]}"  # ISO date -> the shop's dd-mm-yyyy
    if kind == "money":
        return money(value)
    if kind == "qty":
        return qty(value)
    if kind == "int":
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value)
    return str(value)
