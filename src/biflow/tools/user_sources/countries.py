"""Noms de pays -> ISO3 pour les sources utilisateur (correspondance exacte).

Index construit a partir de pycountry (noms anglais, officiels, usuels et leurs
traductions francaises et arabes), des alias ISO3 du projet, de la config
`countries.name_to_iso3` et des alias confirmes dans le mapping. La
comparaison ignore casse, accents et ponctuation ; aucune correspondance
approchee : un nom inconnu ou ambigu est liste, jamais devine.
"""
from __future__ import annotations

import gettext
import re
import unicodedata
from functools import lru_cache
from typing import Iterable, Mapping

from biflow.utils.countries import ISO3_ALIASES, SPECIAL, is_aggregate, is_country, normalize_iso3

try:
    import pycountry
except Exception:  # noqa: BLE001 - pycountry optionnel
    pycountry = None


def normalize_name(text: object) -> str:
    """Cle de comparaison : minuscules, sans accents ni ponctuation, espaces reduits."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^\w]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _base_index() -> dict[str, frozenset[str]]:
    index: dict[str, set[str]] = {}

    def add(name, code):
        key = normalize_name(name)
        if key:
            index.setdefault(key, set()).add(code)

    for code, name in SPECIAL.items():
        add(name, code)
    if pycountry is not None:
        translations = []
        for lang in ("fr", "ar"):
            try:
                translations.append(gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=[lang]))
            except OSError:
                continue
        for country in pycountry.countries:
            names = {country.name, getattr(country, "official_name", None), getattr(country, "common_name", None)}
            for name in [n for n in names if n]:
                add(name, country.alpha_3)
                for translation in translations:
                    add(translation.gettext(name), country.alpha_3)
    return {key: frozenset(codes) for key, codes in index.items()}


class CountryResolver:
    """Resout codes ISO3 et noms de pays ; garde la trace des echecs."""

    def __init__(self, aliases: Mapping[str, str] | None = None):
        self.aliases = {normalize_name(name): normalize_iso3(code) for name, code in (aliases or {}).items()}

    def resolve(self, value: object, kind: str = "auto") -> tuple[str | None, str | None]:
        """(iso3, None) si reconnu ; (None, raison) sinon. kind : iso3 | name | auto."""
        if not isinstance(value, str) or not value.strip():
            return None, "pays manquant"
        text = value.strip()
        if kind in ("iso3", "auto") and re.fullmatch(r"[A-Za-z]{3}", text):
            code = normalize_iso3(text)
            if is_country(code) or code in ISO3_ALIASES.values():
                return code, None
            if is_aggregate(code):
                return None, f"agregat {code} (pas un pays)"
            if kind == "iso3":
                return None, f"code ISO3 inconnu {text!r}"
        if kind == "iso3":
            return None, f"code ISO3 attendu, recu {text!r}"
        key = normalize_name(text)
        if key in self.aliases:
            return self.aliases[key], None
        codes = _base_index().get(key)
        if not codes:
            return None, f"nom de pays inconnu {text!r}"
        if len(codes) > 1:
            return None, f"nom ambigu {text!r} ({', '.join(sorted(codes))})"
        return next(iter(codes)), None

    def resolve_all(self, values: Iterable[object], kind: str = "auto") -> tuple[dict[str, str], dict[str, str]]:
        """({valeur: iso3}, {valeur: raison}) pour les valeurs distinctes."""
        resolved, unresolved = {}, {}
        for value in dict.fromkeys(v for v in values if isinstance(v, str) and v.strip()):
            code, reason = self.resolve(value, kind)
            if code:
                resolved[value] = code
            else:
                unresolved[value] = reason
        return resolved, unresolved


__all__ = ["CountryResolver", "normalize_name"]
