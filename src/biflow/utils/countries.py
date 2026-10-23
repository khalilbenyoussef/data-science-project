"""Utilitaires pays : codes ISO3, agregats et libelles."""

from __future__ import annotations

try:  # pycountry est optionnel : le pipeline doit rester executable sans lui
    import pycountry
except Exception:  # noqa: BLE001
    pycountry = None

# codes World Bank / Findex qui ne sont pas des pays
AGGREGATES = {
    "AFE", "AFW", "ARB", "CEB", "CHI", "CSS", "EAR", "EAP", "EAS", "ECA",
    "ECS", "EMU", "EUU", "FCS", "FCV", "HIC", "HPC", "IBD", "IBT", "IDA",
    "IDB", "IDX", "INX", "LAC", "LCN", "LDC", "LIC", "LMC", "LMY", "LTE",
    "MEA", "MIC", "MNA", "NAC", "OED", "OSS", "PRE", "PSS", "PST", "SAS",
    "SSA", "SSF", "SST", "TEA", "TEC", "TLA", "TMN", "TSA", "TSS", "UMC",
    "WLD",
}

SPECIAL = {"XKX": "Kosovo"}

ISO3_ALIASES = {"KOS": "XKX", "WBG": "PSE"}


def normalize_iso3(code: object) -> str | None:
    """Normalise un code texte sans convertir les valeurs manquantes en codes."""
    if not isinstance(code, str):
        return None
    code = code.upper().strip()
    if code in {"", "NAN", "<NA>", "NONE", "NULL", "NAT"}:
        return None
    return ISO3_ALIASES.get(code, code)


def is_aggregate(code: str | None) -> bool:
    return normalize_iso3(code) in AGGREGATES


def is_country(code: str | None) -> bool:
    code = normalize_iso3(code)
    if len(code or "") != 3 or code in AGGREGATES:
        return False
    if code in SPECIAL:
        return True
    if pycountry is None:
        return True
    return pycountry.countries.get(alpha_3=code) is not None


def country_name(code: str | None, fallback: str | None = None) -> str | None:
    code = normalize_iso3(code)
    if not code:
        return fallback
    if code in SPECIAL:
        return SPECIAL[code]
    if pycountry is not None:
        match = pycountry.countries.get(alpha_3=code)
        if match is not None:
            return match.name
    return fallback


def invalid_iso3(codes) -> list[str]:
    """Codes a 3 lettres qui ne correspondent ni a un pays ni a un agregat connu."""
    out = []
    for code in {normalize_iso3(c) for c in codes}:
        if code and len(code) == 3 and not is_country(code) and not is_aggregate(code):
            out.append(code)
    return sorted(out)


__all__ = [
    "AGGREGATES",
    "ISO3_ALIASES",
    "SPECIAL",
    "is_aggregate",
    "is_country",
    "country_name",
    "normalize_iso3",
    "invalid_iso3",
]
