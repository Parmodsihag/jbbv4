"""Company profile (name, address, phone, GSTIN...) shown on statements and invoices."""

from __future__ import annotations

from dataclasses import dataclass, fields

from hth.db.connection import Database
from hth.services.settings import SettingsService

DEFAULTS = {
    "company.name": "JAAT BEEJ BHANDAR",
    "company.tagline": "Pesticides, fertilisers and certified seeds",
    "company.address": "Village Dhansu, Hisar (Haryana)",
    "company.phone": "8901254427",
    "company.gstin": "06AOIPR2828B1Z3",
    "company.licences": "Seed lic. 3418 · Pesticide 5169 · Fertilizer RL-2795",
    "company.footer": "Please check your statement and report any difference within 7 days.",
}


@dataclass(frozen=True)
class CompanyProfile:
    name: str
    tagline: str
    address: str
    phone: str
    gstin: str
    licences: str
    footer: str


class CompanyService:
    def __init__(self, db: Database):
        self.settings = SettingsService(db, DEFAULTS)

    def profile(self) -> CompanyProfile:
        return CompanyProfile(**{f.name: self.settings.get(f"company.{f.name}") for f in fields(CompanyProfile)})

    def update(self, **values: str) -> None:
        for key, value in values.items():
            if f"company.{key}" not in DEFAULTS:
                raise ValueError(f"Unknown company field {key}")
            self.settings.set(f"company.{key}", (value or "").strip())
