"""Dictionnaire des indicateurs Findex / FAS / WDI utilises par BIFlow."""

from __future__ import annotations

FINDEX_LABELS = {
    "account_t_d": "Detention d'un compte (% adultes)",
    "fiaccount_t_d": "Compte aupres d'une institution financiere",
    "mobileaccount_t_d": "Compte mobile money",
    "inactive_t_d": "Compte inactif",
    "dig_acc": "Detention d'un compte permettant des paiements numeriques",
    "save_any_t_d": "Epargne, toute forme (12 mois)",
    "borrow_any_t_d": "Emprunt, toute source (12 mois)",
    "merchant_pay": "Paiement numerique chez un commercant",
    "g20_any": "Paiement numerique effectue ou recu dans l'annee",
    "fin17a": "Epargne aupres d'une banque ou institution financiere similaire (12 mois)",
    "fin22a": "Emprunt aupres d'une banque ou institution financiere similaire, carte de credit incluse (12 mois)",
    # Raisons de ne pas avoir de compte (part de tous les adultes 15+) : pas de KPI
    "fin11a": "Sans compte : institution financiere trop eloignee",
    "fin11b": "Sans compte : services financiers trop chers",
    "fin11c": "Sans compte : documents requis manquants",
    "fin11d": "Sans compte : fonds insuffisants",
    "fin11e": "Sans compte : un membre de la famille en possede deja un",
    "fin11f": "Sans compte : manque de confiance dans les institutions financieres",
    # Fonds d'urgence mobilisables en 30 jours (resilience), pas de paiement/epargne/emprunt
    "fin24aP": "Fonds d'urgence en 30 jours : possible",
    "fin24aN": "Fonds d'urgence en 30 jours : impossible (ne sait pas / refus inclus)",
    "fin24aSD_ND": "Fonds d'urgence en 30 jours : possible, pas ou peu difficile",
    "fin24sav": "Source principale des fonds d'urgence : epargne",
    "fin24fam": "Source principale des fonds d'urgence : famille ou amis",
    "fin24work": "Source principale des fonds d'urgence : travail",
    "fin24bor": "Source principale des fonds d'urgence : emprunt (banque, employeur, preteur prive)",
    "fin24sell": "Source principale des fonds d'urgence : vente d'actifs",
    "fin24other": "Source principale des fonds d'urgence : autre",
}

# Verification dans le glossaire officiel Global Findex 2025 (feuille Glossary,
# numero de ligne ; codes officiels avec points, CSV local avec underscores).
# Fichier telecharge le 2026-10-29, sha256 8eb99754e6e18d6831c133cc743d8207cc657baedc3447588a574fd3d935f923.
# dig_acc n'y figure pas : sources citees dans le README.
FINDEX_GLOSSARY_URL = (
    "https://thedocs.worldbank.org/en/doc/be6615202d1f08a25855c8ac2d615122-0050012025/"
    "related/GlobalFindex2025-glossary.xlsx"
)
FINDEX_GLOSSARY_ROWS = {
    "account_t_d": 2, "borrow_any_t_d": 3, "fiaccount_t_d": 5,
    "fin11a": 6, "fin11b": 7, "fin11c": 8, "fin11f": 9, "fin11d": 10, "fin11e": 11,
    "fin17a": 24, "fin22a": 31,
    "fin24sav": 34, "fin24fam": 35, "fin24work": 36, "fin24bor": 37, "fin24sell": 38,
    "fin24other": 39, "fin24aSD_ND": 43, "fin24aP": 44, "fin24aN": 45,
    "inactive_t_d": 109, "g20_any": 118, "merchant_pay": 119, "mobileaccount_t_d": 120,
    "save_any_t_d": 121,
}
# Codes non verifiables : libelle "unverified", jamais utilises par un KPI.
UNVERIFIED = "unverified"
FINDEX_UNVERIFIED: frozenset[str] = frozenset()

FAS_LABELS = {
    "branch_density": "Agences bancaires pour 100 000 adultes",
    "atm_density": "Distributeurs automatiques pour 100 000 adultes",
    "depositors_per_1k": "Deposants (banques commerciales) pour 1 000 adultes",
    "borrowers_per_1k": "Emprunteurs (banques commerciales) pour 1 000 adultes",
    "loan_accounts_per_1k": "Comptes de pret pour 1 000 adultes",
    "deposit_accounts_per_1k": "Comptes de depot pour 1 000 adultes",
    "deposits_pct_gdp": "Encours des depots (banques commerciales, % du PIB)",
    "loans_pct_gdp": "Encours des prets (banques commerciales, % du PIB)",
}

GDP_LABELS = {
    "NY.GDP.MKTP.CD": "PIB (USD courants)",
    "NY.GDP.PCAP.CD": "PIB par habitant (USD courants)",
    "NY.GDP.MKTP.KD.ZG": "Croissance du PIB (% annuel, prix constants)",
}

UNITS = {
    "account_t_d": "fraction",
    "fiaccount_t_d": "fraction",
    "mobileaccount_t_d": "fraction",
    "inactive_t_d": "fraction",
    "dig_acc": "fraction",
    "save_any_t_d": "fraction",
    "borrow_any_t_d": "fraction",
    "merchant_pay": "fraction",
    "g20_any": "fraction",
    "fin17a": "fraction",
    "fin22a": "fraction",
    "fin11a": "fraction",
    "fin11b": "fraction",
    "fin11c": "fraction",
    "fin11d": "fraction",
    "fin11e": "fraction",
    "fin11f": "fraction",
    "fin24aP": "fraction",
    "fin24aN": "fraction",
    "fin24aSD_ND": "fraction",
    "fin24sav": "fraction",
    "fin24fam": "fraction",
    "fin24work": "fraction",
    "fin24bor": "fraction",
    "fin24sell": "fraction",
    "fin24other": "fraction",
    "branch_density": "per_100k_adults",
    "atm_density": "per_100k_adults",
    "depositors_per_1k": "per_1k_adults",
    "borrowers_per_1k": "per_1k_adults",
    "loan_accounts_per_1k": "per_1k_adults",
    "deposit_accounts_per_1k": "per_1k_adults",
    "deposits_pct_gdp": "percent_of_gdp",
    "loans_pct_gdp": "percent_of_gdp",
    "NY.GDP.MKTP.CD": "usd_current",
    "NY.GDP.PCAP.CD": "usd_current_per_capita",
    "NY.GDP.MKTP.KD.ZG": "percent_annual_growth",
}

INDICATOR_SOURCE = {
    **{code: "findex" for code in FINDEX_LABELS},
    **{code: "fas" for code in FAS_LABELS},
    **{code: "gdp" for code in GDP_LABELS},
}

INDICATOR_LABELS = {**FINDEX_LABELS, **FAS_LABELS, **GDP_LABELS}


def label_for(code: str, fallback: str | None = None) -> str:
    if code in FINDEX_UNVERIFIED:
        return f"{INDICATOR_LABELS.get(code) or fallback or code} ({UNVERIFIED})"
    return INDICATOR_LABELS.get(code) or fallback or code


def unit_for(code: str, fallback: str = "") -> str:
    return UNITS.get(code, fallback)


__all__ = [
    "FINDEX_GLOSSARY_ROWS",
    "FINDEX_GLOSSARY_URL",
    "FINDEX_LABELS",
    "FINDEX_UNVERIFIED",
    "UNVERIFIED",
    "FAS_LABELS",
    "GDP_LABELS",
    "INDICATOR_LABELS",
    "INDICATOR_SOURCE",
    "UNITS",
    "label_for",
    "unit_for",
]
