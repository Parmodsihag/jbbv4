"""Shop-wide UI and security preferences, stored in the settings table."""

from __future__ import annotations

from hth.db.connection import Database
from hth.domain import numbers
from hth.services.settings import SettingsService

DEFAULTS = {
    "ui.theme": "dark",  # light | dark | system
    "ui.number_style": "indian",  # indian | international
    "ui.sidebar_compact": "0",
    "security.lock_minutes": "0",  # lock the screen after N idle minutes; 0 = never
    "ui.text_scale": "1.0",  # 0.9 | 1.0 | 1.15 | 1.3
    "ui.language": "en",  # en | hi
    "ui.layout": "new",  # new (six areas across the top, v5.5) | classic (the sidebar, as in v5.4)
    "assistant.speak": "voice",  # speak answers: voice (when the question was spoken) | always | never
    "assistant.mic": "",  # the recording device's name; "" = automatic (never a loopback like Stereo Mix)
    "update.repo": "Parmodsihag/jbbv4",  # where updates come from (GitHub owner/name)
    "update.branch": "v5",
    "update.folder": "v5",  # the app's folder inside the repository
    "update.last_check": "",  # ISO time of the last automatic check
    "update.result_seen": "",  # the last update result already shown
}
SPEAK_MODES = ("voice", "always", "never")
LANGUAGES = ("en", "hi")
LAYOUTS = ("classic", "new")
TEXT_SCALES = (0.9, 1.0, 1.15, 1.3)
THEMES = ("light", "dark", "system")


class Preferences:
    def __init__(self, db: Database):
        self.settings = SettingsService(db, DEFAULTS)

    def theme(self) -> str:
        v = self.settings.get("ui.theme").lower()
        return v if v in THEMES else "dark"

    def set_theme(self, mode: str) -> None:
        if mode not in THEMES:
            raise ValueError(f"Theme must be one of {', '.join(THEMES)}.")
        self.settings.set("ui.theme", mode)

    def number_style(self) -> str:
        v = self.settings.get("ui.number_style").lower()
        return v if v in numbers.STYLES else "indian"

    def set_number_style(self, style: str) -> None:
        if style not in numbers.STYLES:
            raise ValueError("Number style must be indian or international.")
        self.settings.set("ui.number_style", style)
        numbers.set_style(style)

    def apply_number_style(self) -> None:
        numbers.set_style(self.number_style())

    def text_scale(self) -> float:
        try:
            v = float(self.settings.get("ui.text_scale"))
        except ValueError:
            return 1.0
        return v if v in TEXT_SCALES else 1.0

    def set_text_scale(self, scale: float) -> None:
        if float(scale) not in TEXT_SCALES:
            raise ValueError("Text size must be 90%, 100%, 115% or 130%.")
        self.settings.set("ui.text_scale", f"{float(scale):g}")

    def assistant_speak(self) -> str:
        v = self.settings.get("assistant.speak").lower()
        return v if v in SPEAK_MODES else "voice"

    def set_assistant_speak(self, mode: str) -> None:
        if mode not in SPEAK_MODES:
            raise ValueError("Speak answers must be voice, always or never.")
        self.settings.set("assistant.speak", mode)

    def assistant_mic(self) -> str:
        return self.settings.get("assistant.mic")

    def set_assistant_mic(self, name: str) -> None:
        self.settings.set("assistant.mic", name or "")

    def update_source(self):
        from hth.services.updates import Source

        return Source(
            self.settings.get("update.repo").strip() or "Parmodsihag/jbbv4",
            self.settings.get("update.branch").strip() or "v5",
            self.settings.get("update.folder").strip().strip("/"),
        )

    def set_update_source(self, repo: str, branch: str) -> None:
        repo, branch = (repo or "").strip(), (branch or "").strip()
        if repo.count("/") != 1 or not all(repo.split("/")) or not branch or " " in repo + branch:
            raise ValueError("Repository must look like owner/name, and the branch must not be empty.")
        self.settings.set("update.repo", repo)
        self.settings.set("update.branch", branch)

    def language(self) -> str:
        v = self.settings.get("ui.language").lower()
        return v if v in LANGUAGES else "en"

    def set_language(self, lang: str) -> None:
        if lang not in LANGUAGES:
            raise ValueError("Language must be en or hi.")
        self.settings.set("ui.language", lang)

    def layout(self) -> str:
        """Which set of screens the whole shop uses: the classic sidebar or the new layout."""
        v = self.settings.get("ui.layout").lower()
        return v if v in LAYOUTS else "new"

    def set_layout(self, layout: str) -> None:
        if layout not in LAYOUTS:
            raise ValueError("Layout must be classic or new.")
        self.settings.set("ui.layout", layout)

    def sidebar_compact(self) -> bool:
        return self.settings.get_bool("ui.sidebar_compact")

    def set_sidebar_compact(self, on: bool) -> None:
        self.settings.set("ui.sidebar_compact", "1" if on else "0")

    def lock_minutes(self) -> int:
        try:
            return max(0, int(float(self.settings.get("security.lock_minutes"))))
        except ValueError:
            return 0

    def set_lock_minutes(self, minutes: int) -> None:
        minutes = int(minutes)
        if minutes < 0 or minutes > 24 * 60:
            raise ValueError("Auto-lock must be between 0 (off) and 1440 minutes.")
        self.settings.set("security.lock_minutes", str(minutes))
