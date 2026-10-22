"""Dictionnaire des indicateurs Findex / FAS / WDI utilises par BIFlow."""

from __future__ import annotations

FINDEX_LABELS = {
    "account_t_d": "Detention d'un compte (% adultes)",
    "fiaccount_t_d": "Compte aupres d'une institution financiere",
    "mobileaccount_t_d": "Compte mobile money",
    "inactive_t_d": "Compte inactif",
    "dig_acc": "Paiement numerique",
    "save_any_t_d": "Epargne",
    "borrow_any_t_d": "Emprunt",
    "merchant_pay": "Paiement chez un commercant",
    "g20_any": "Envoi ou reception de fonds",
    "fin17a": "Epargne formelle",
    "fin22a": "Emprunt formel",
    "fin24aP": "Paiement numerique (vague 2024)",
    "fin24sav": "Epargne (vague 2024)",
    "fin24bor": "Emprunt (vague 2024)",
}

FAS_LABELS = {
    "branch_density": "Agences bancaires pour 100 000 adultes",
    "atm_density": "Distributeurs automatiques pour 100 000 adultes",
    "depositors_per_1k": "Deposants (banques commerciales) pour 1 000 adultes",
    "borrowers_per_1k": "Emprunteurs (banques commerciales) pour 1 000 adultes",
    "loan_accounts_per_1k": "Comptes de pret pour 1 000 adultes",
    "deposit_accounts_per_1k": "Comptes de depot pour 1 000 adultes",
}

GDP_LABELS = {
    "NY.GDP.MKTP.CD": "PIB (USD courants)",
    "NY.GDP.PCAP.CD": "PIB par habitant (USD courants)",
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
    "fin24aP": "fraction",
    "fin24sav": "fraction",
    "fin24bor": "fraction",
    "branch_density": "per_100k_adults",
    "atm_density": "per_100k_adults",
    "depositors_per_1k": "per_1k_adults",
    "borrowers_per_1k": "per_1k_adults",
    "loan_accounts_per_1k": "per_1k_adults",
    "deposit_accounts_per_1k": "per_1k_adults",
    "NY.GDP.MKTP.CD": "usd_current",
    "NY.GDP.PCAP.CD": "usd_current_per_capita",
}

INDICATOR_SOURCE = {
    **{code: "findex" for code in FINDEX_LABELS},
    **{code: "fas" for code in FAS_LABELS},
    **{code: "gdp" for code in GDP_LABELS},
}

INDICATOR_LABELS = {**FINDEX_LABELS, **FAS_LABELS, **GDP_LABELS}


def label_for(code: str, fallback: str | None = None) -> str:
    return INDICATOR_LABELS.get(code) or fallback or code


def unit_for(code: str, fallback: str = "") -> str:
    return UNITS.get(code, fallback)


__all__ = [
    "FINDEX_LABELS",
    "FAS_LABELS",
    "GDP_LABELS",
    "INDICATOR_LABELS",
    "INDICATOR_SOURCE",
    "UNITS",
    "label_for",
    "unit_for",
]
