# Voice model shipped with the app

`vosk-model-small-hi-0.22.zip` is Vosk's small Hindi speech-recognition model, unchanged.

* Source: <https://alphacephei.com/vosk/models> (`vosk-model-small-hi-0.22`, 42 MB zip, 79 MB unpacked)
* License: Apache 2.0 (Alpha Cephei Inc.)
* SHA-256: `7c50a10866889f0ac21d912c20537a055a597ed09fc1d3e5bcd798f9f0017e48`

The app unpacks it into `<data>/voice` the first time the Assistant opens
(`hth.assistant.voice.ensure_model`). Put a different Vosk model zip here instead and the
app installs that one on its next start; a model installed by hand in Settings → Assistant
is left alone. Packaged builds must include this folder (see README → Packaging).
