"""Finova analyst: deterministic facts, insights, XAI card and Ask answers.

The analyst never computes a number from raw tables. It reads the facts exported
from the dashboard spec (each fact is itself copied from the KPI catalog, the
read-only warehouse or a dated reference) and only writes sentences whose
numeric tokens already exist in those facts. ``verify_numbers`` is the guard:
any narration, templated or LLM-written, that introduces an unknown number is
rejected and replaced by the deterministic fallback.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from biflow.agents.base import BaseAgent
from biflow.config import path_of
from biflow.tools.kpi import load_catalog
from biflow.tools.warehouse_reader import FIN24AP_MISLABELED
from biflow.utils.io import save_json

SCHEMA_VERSION = "1.0"

ASSOCIATION_CAVEAT = (
    "Association, pas causalité : les écarts décrivent des sous-groupes observés "
    "et ne démontrent aucun effet causal."
)
UNKNOWN_ANSWER = (
    "Finova répond uniquement à partir des faits du dernier run. Posez une "
    "question sur la détention de compte, les paiements numériques, les ATMs, "
    "les écarts femmes-hommes, le milieu rural, la pauvreté ou le SMIG."
)
NO_DATA_ANSWER = (
    "Les données du dernier run ne contiennent pas d'observation permettant de "
    "répondre à cette question. Aucun chiffre n'est inventé ni estimé."
)

_NUMBER = re.compile(
    r"(?<![A-Za-z])\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?(?![A-Za-z])"
)


# ------------------------------------------------------------------ number guard
def _as_number(token: str) -> float:
    return float(token.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
                 .replace(",", "."))


def _tokens(text: str) -> list[str]:
    return [match.group(0) for match in _NUMBER.finditer(text or "")]


def allowed_numbers(facts: Iterable[Mapping[str, Any]]) -> set[float]:
    """Every numeric token the facts already contain: display, label, year, value."""
    allowed: set[float] = set()
    for fact in facts:
        for field in ("display", "label"):
            for token in _tokens(str(fact.get(field) or "")):
                allowed.add(_as_number(token))
        for field in ("year", "value"):
            value = fact.get(field)
            if isinstance(value, (int, float)):
                allowed.add(float(value))
        unit = fact.get("unit")
        if unit == "per_100k_adults":
            allowed.update({100.0, 1000.0})
        elif unit == "per_1k_adults":
            allowed.update({1.0, 1000.0})
    return allowed


def verify_numbers(text: str, facts: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return numeric tokens of ``text`` that no fact supports (empty = valid)."""
    allowed = allowed_numbers(facts)
    unknown: list[str] = []
    for token in _tokens(text):
        if _as_number(token) not in allowed:
            unknown.append(token)
    return unknown


# ------------------------------------------------------------------ fact lookup
def index_facts(facts: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        index.setdefault(str(fact.get("code")), []).append(dict(fact))
    return index


def pick(
    index: Mapping[str, Sequence[Mapping[str, Any]]], code: str, *,
    year: int | None = None,
) -> Mapping[str, Any] | None:
    """Prefer an exact year, otherwise the latest observed value for this code."""
    candidates = [fact for fact in index.get(code, ()) if fact.get("value") is not None]
    if not candidates:
        return None
    if year is not None:
        exact = [fact for fact in candidates if fact.get("year") == year]
        if exact:
            candidates = exact
    candidates.sort(key=lambda fact: fact.get("year") or 0)
    return candidates[-1]


def _strip(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _insight(
    insight_id: str, code: str, statement: str,
    *, severity: str, kind: str, cited: Iterable[Mapping[str, Any] | None],
    facts: Sequence[Mapping[str, Any]], warnings: list[str],
) -> dict[str, Any] | None:
    used = [fact for fact in cited if fact is not None and fact.get("value") is not None]
    if not used or not statement.strip():
        return None
    unknown = verify_numbers(statement, facts)
    if unknown:
        warnings.append(
            f"{insight_id}: nombres sans fait correspondant {unknown} — constat ignoré"
        )
        return None
    return {
        "id": insight_id,
        "code": code,
        "statement": statement,
        "severity": severity,
        "kind": kind,
        "evidence_ids": tuple(dict.fromkeys(fact["id"] for fact in used)),
    }


def _delta_sentence(delta: Mapping[str, Any] | None) -> str:
    return f" ({delta['display']})" if delta is not None else ""


def _is_provisional(kpi_id: str) -> bool:
    """Statut lu dans le catalogue : la mention « provisoire » suit le catalogue."""
    definition = (load_catalog().get("kpis") or {}).get(kpi_id) or {}
    return (definition.get("verification") or {}).get("status") == "provisional"


# -------------------------------------------------------------------- insights
def build_insights(
    facts: Sequence[Mapping[str, Any]], country: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Build page insights. Every statement is number-checked against facts."""
    index = index_facts(facts)
    warnings: list[str] = []
    pages: dict[str, list[dict[str, Any]]] = {key: [] for key in (
        "overview", "inclusion", "access", "exclusion", "poverty", "pipeline")}

    def add(page: str, item: dict[str, Any] | None) -> None:
        if item is not None:
            pages[page].append(item)

    # ------------------------------------------------------------------ overview
    account = pick(index, "account_ownership")
    if account is not None:
        statement = (
            f"En {account['year']}, {account['display']} des adultes en {country} "
            f"détiennent un compte.{_delta_sentence(pick(index, 'account_ownership_delta'))}"
        )
        add("overview", _insight(
            "INS-overview-account", "account_ownership", statement,
            severity="info", kind="auto",
            cited=(account, pick(index, "account_ownership_delta")),
            facts=facts, warnings=warnings,
        ))
    digital = pick(index, "digital_payment_rate")
    if digital is not None:
        statement = (
            f"Les paiements numériques concernent {digital['display']} des adultes "
            f"en {country} en {digital['year']} ; ce n'est pas une mesure de "
            "détention de compte."
        )
        add("overview", _insight(
            "INS-overview-digital", "digital_payment_rate", statement,
            severity="info", kind="auto", cited=(digital,),
            facts=facts, warnings=warnings,
        ))
    saving = pick(index, "saving_rate")
    if saving is not None:
        provisional = _is_provisional("saving_rate")
        statement = (
            f"L'épargne, toutes formes confondues, est estimée à {saving['display']} "
            f"en {saving['year']}"
            + (" ; cet indicateur du catalogue est provisoire." if provisional else ".")
        )
        add("overview", _insight(
            "INS-overview-saving", "saving_rate", statement,
            severity="review" if provisional else "info", kind="auto", cited=(saving,),
            facts=facts, warnings=warnings,
        ))
    emergency = pick(index, "emergency_money")
    if emergency is not None:
        # l'avertissement de libelle ne reste que si le dictionnaire garde l'ancien libelle
        statement = (
            f"{emergency['display']} des adultes déclarent pouvoir obtenir de "
            f"l'argent en urgence (fin24aP, {emergency['year']})"
            + (" ; le libellé du dictionnaire ne concorde pas avec la définition Findex "
               "attendue, la valeur brute reste à revoir." if FIN24AP_MISLABELED else ".")
        )
        add("overview", _insight(
            "INS-overview-emergency", "emergency_money", statement,
            severity="warning" if FIN24AP_MISLABELED else "info", kind="auto", cited=(emergency,),
            facts=facts, warnings=warnings,
        ))
    peers = [pick(index, f"account_peer_{code}") for code in
             ("TUN", "DZA", "EGY", "JOR", "MAR")]
    peers = [peer for peer in peers if peer is not None]
    if len(peers) == 5:
        lead = next(
            (peer for peer in peers if _strip(peer["label"]) == _strip(country)),
            peers[0],
        )
        listing = ", ".join(
            f"{peer['label']} {peer['display']}"
            for peer in peers if peer is not lead
        )
        statement = (
            f"Détention d'un compte en {lead['year']}: "
            f"{lead['label']} {lead['display']}, contre {listing}."
        )
        add("overview", _insight(
            "INS-overview-peers", "account_ownership_peers", statement,
            severity="info", kind="auto", cited=peers,
            facts=facts, warnings=warnings,
        ))

    # ----------------------------------------------------------------- inclusion
    formal_saving = pick(index, "formal_saving")
    formal_borrowing = pick(index, "formal_borrowing")
    if account is not None and digital is not None and formal_saving is not None:
        statement = (
            f"Les questions Findex sont distinctes : {account['display']} détiennent "
            f"un compte, {digital['display']} ont effectué un paiement numérique, "
            f"{formal_saving['display']} épargnent à une institution formelle"
        )
        cited = [account, digital, formal_saving, formal_borrowing]
        if formal_borrowing is not None:
            statement += f" et {formal_borrowing['display']} y empruntent"
        statement += "."
        add("inclusion", _insight(
            "INS-inclusion-funnel", "formal_usage", statement,
            severity="info", kind="auto", cited=cited,
            facts=facts, warnings=warnings,
        ))
    for dimension, title in (("gender", "femmes-hommes"),
                             ("income", "de revenu"),
                             ("education", "d'éducation")):
        gap = pick(index, f"gap_{dimension}")
        if gap is None:
            continue
        change = pick(index, f"gap_change_{dimension}")
        if dimension == "gender":
            left, right = (pick(index, "gender_femmes"), pick(index, "gender_hommes"))
        elif dimension == "income":
            left = pick(index, "income_40-les-plus-pauvres")
            right = pick(index, "income_60-les-plus-riches")
        else:
            left = pick(index, "education_primaire-ou-moins")
            right = pick(index, "education_secondaire-ou-plus")
        if left is None or right is None:
            continue
        statement = (
            f"Écart {title} en {gap['year']} : {left['display']} pour le premier "
            f"groupe contre {right['display']} pour le second, soit {gap['display']}."
        )
        if change is not None:
            statement += f" Variation depuis l'année antérieure observée : {change['display']}."
        add("inclusion", _insight(
            f"INS-inclusion-gap-{dimension}", f"gap_{dimension}", statement,
            severity="review", kind="auto",
            cited=(left, right, gap, change), facts=facts, warnings=warnings,
        ))

    # -------------------------------------------------------------------- access
    atm = pick(index, "atm_per_100k")
    if atm is not None:
        statement = (
            f"Le parc de distributeurs atteint {atm['display']} en {atm['year']}"
            f"{_delta_sentence(pick(index, 'atm_per_100k_delta'))}."
        )
        index_fact = pick(index, "index_atm_per_100k")
        if index_fact is not None:
            statement += f" Indice 2017 = 100 : {index_fact['display']}."
        add("access", _insight(
            "INS-access-atm", "atm_per_100k", statement,
            severity="info", kind="auto",
            cited=(atm, pick(index, "atm_per_100k_delta"), index_fact),
            facts=facts, warnings=warnings,
        ))
    branch = pick(index, "branch_density")
    if branch is not None:
        statement = (
            f"Le réseau d'agences est de {branch['display']} en {branch['year']}."
        )
        add("access", _insight(
            "INS-access-branch", "branch_density", statement,
            severity="info", kind="auto", cited=(branch,),
            facts=facts, warnings=warnings,
        ))
    depositors = pick(index, "depositors_per_1k")
    borrowers = pick(index, "borrowers_per_1k")
    if depositors is not None or borrowers is not None:
        parts = []
        cited = []
        for label, fact in (("Déposants", depositors), ("Emprunteurs", borrowers)):
            if fact is None:
                continue
            parts.append(f"{label} {fact['display']} en {fact['year']}")
            cited.append(fact)
        statement = "; ".join(parts) + "."
        add("access", _insight(
            "INS-access-outreach", "outreach", statement,
            severity="review", kind="auto", cited=cited,
            facts=facts, warnings=warnings,
        ))
    loans = pick(index, "loans_pct_gdp")
    deposits = pick(index, "deposits_pct_gdp")
    if loans is not None or deposits is not None:
        parts = []
        cited = []
        for label, fact in (("Encours de crédits", loans), ("Encours de dépôts", deposits)):
            if fact is None:
                continue
            parts.append(f"{label} {fact['display']} en {fact['year']}")
            cited.append(fact)
        add("access", _insight(
            "INS-access-balance", "banking_depth", "; ".join(parts) + ".",
            severity="review", kind="auto", cited=cited,
            facts=facts, warnings=warnings,
        ))

    # ------------------------------------------------------------------ poverty
    if country == "Tunisie" or pick(index, "smig_2025") is not None:
        smig_2025 = pick(index, "smig_2025")
        smig_2028 = pick(index, "smig_2028")
        if smig_2025 is not None and smig_2028 is not None:
            statement = (
                f"Le SMIG mensuel brut est de {smig_2025['display']} en "
                f"{smig_2025['year']} et le barème publié prévoit "
                f"{smig_2028['display']} en {smig_2028['year']} ; les "
                "revalorisations restent à confirmer au JORT."
            )
            add("poverty", _insight(
                "INS-poverty-smig", "smig", statement,
                severity="review", kind="auto",
                cited=(smig_2025, smig_2028), facts=facts, warnings=warnings,
            ))
        poverty = pick(index, "poverty_rate_2021")
        if poverty is not None:
            statement = (
                f"Le taux de pauvreté national était de {poverty['display']} en "
                f"{poverty['year']} (INS) : c'est un contexte socio-économique, "
                "pas une mesure d'exclusion financière."
            )
            add("poverty", _insight(
                "INS-poverty-rate", "poverty_rate", statement,
                severity="info", kind="auto", cited=(poverty,),
                facts=facts, warnings=warnings,
            ))

    return {page: items for page, items in pages.items()}, warnings


# ----------------------------------------------------------------------- XAI card
def build_xai(
    facts: Sequence[Mapping[str, Any]], country: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Evidence -> Interpretation -> Recommendation, all facts number-checked."""
    index = index_facts(facts)
    warnings: list[str] = []
    gap_gender = pick(index, "gap_gender")
    women = pick(index, "gender_femmes")
    men = pick(index, "gender_hommes")
    urban = pick(index, "urban_account")
    rural = pick(index, "rural_account")
    gap_place = pick(index, "gap_urbanicity")
    if gap_gender is None or women is None or men is None or urban is None or rural is None:
        warnings.append("carte XAI non produite : faits genre ou milieu manquants")
        return None, warnings

    def make(insight_id: str, statement: str, severity: str, kind: str,
             cited: Iterable[Mapping[str, Any] | None]) -> dict[str, Any] | None:
        return _insight(insight_id, kind, statement, severity=severity, kind=kind,
                        cited=cited, facts=facts, warnings=warnings)

    evidence_gender = make(
        "XAI-evidence-gender",
        f"En {gap_gender['year']}, {women['display']} des femmes détiennent un "
        f"compte contre {men['display']} des hommes, un écart de {gap_gender['display']}.",
        "review", "xai_evidence", (women, men, gap_gender),
    )
    evidence_place = make(
        "XAI-evidence-place",
        f"En {urban['year']}, {urban['display']} des adultes urbains détiennent un "
        f"compte contre {rural['display']} des adultes ruraux.",
        "review", "xai_evidence", (urban, rural),
    )
    cited_gap = (gap_gender, gap_place)
    interpretation = make(
        "XAI-interpretation-association",
        f"L'écart femmes-hommes ({gap_gender['display']}) et l'écart entre milieux "
        f"({gap_place['display'] if gap_place else 'non mesuré'}) sont des "
        "associations observées sur des sous-groupes distincts.",
        "info", "xai_interpretation", cited_gap,
    )
    # barrieres fin11 du pays (KPI barrier_*) : le texte suit leur presence dans les faits
    barriers = [fact for fact in facts if str(fact.get("code", "")).startswith("barrier_")
                and fact.get("iso3") not in (None, "PEERS") and fact.get("value") is not None]
    interpretation_barriers = make(
        "XAI-interpretation-barriers",
        "Findex mesure les raisons déclarées de ne pas avoir de compte : une même "
        "personne peut en citer plusieurs, et ces raisons décrivent l'exclusion sans "
        "en mesurer la cause."
        if barriers else
        "Les barrières déclarées ne sont pas chargées dans le warehouse : "
        "aucune explication par ces barrières n'est mesurée dans ce run.",
        "review", "xai_interpretation", barriers or cited_gap,
    )
    recommendation = make(
        "XAI-hypothesis",
        "Hypothèse à tester : des actions ciblant les femmes et les zones rurales "
        "pourraient réduire les écarts observés ; aucun effet causal n'est estimé ici.",
        "review", "hypothesis", cited_gap,
    )
    rows = [item for item in (evidence_gender, evidence_place, interpretation,
                              interpretation_barriers, recommendation) if item]
    if len(rows) != 5:
        warnings.append("carte XAI incomplète : un constat n'a pas passé le contrôle")
        return None, warnings
    card = {
        "title": f"Lecture XAI — {country}, {gap_gender['year']}",
        "evidence": (evidence_gender, evidence_place),
        "interpretation": (interpretation, interpretation_barriers),
        "recommendation": recommendation,
        "caveat": ASSOCIATION_CAVEAT,
    }
    return card, warnings


def build_analyst_payload(
    facts: Sequence[Mapping[str, Any]], country: str,
    *, pages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Insights plus XAI card, filtered to pages that actually exist."""
    insights, warnings = build_insights(facts, country)
    xai, xai_warnings = build_xai(facts, country)
    warnings.extend(xai_warnings)
    if pages is not None:
        known = {page.get("id") for page in pages}
        insights = {key: value for key, value in insights.items() if key in known}
    return {
        "schema_version": SCHEMA_VERSION,
        "country": country,
        "insights": insights,
        "xai": xai,
        "fact_count": len(list(facts)),
        "warnings": warnings,
    }


# ------------------------------------------------------------------------- Ask
class AskRequest(BaseModel):
    """Typed question accepted by ``POST /api/ask``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: StrictStr
    iso3: StrictStr | None = None
    year: int | None = None

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question cannot be empty")
        if len(value) > 500:
            raise ValueError("question is limited to 500 characters")
        return value


_INTENTS = (
    ("gender", ("femme", "homme", "genre", "gender", "ecart")),
    ("poverty", ("pauvrete", "pauvres", "poverty", "ins")),
    ("rural", ("rural", "urbain", "urban", "milieu", "campagne", "ville")),
    ("atm", ("atm", "distributeur", "dab", "automate")),
    ("branch", ("agence", "branch", "reseau")),
    ("peers", ("pair", "peer", "compar", "maroc", "egypte", "jordanie",
               "algerie", "region", "mena")),
    ("smig", ("smig", "salaire minimum", "salaire")),
    ("emergency", ("urgence", "emergency", "fin24")),
    ("loans", ("pib", "gdp", "depot", "depos", "credit", "pret")),
    ("borrowing", ("emprunt", "borrow", "loan")),
    ("saving", ("epargne", "saving", "economis")),
    ("digital", ("numerique", "digital", "paiement", "payment", "g20")),
    ("account", ("compte", "account", "bancaris", "detention", "inclusion")),
    ("index", ("augment", "evolu", "progres", "indice", "depuis 2017")),
)


def detect_intent(question: str) -> str | None:
    text = _strip(question)
    for intent, keywords in _INTENTS:
        if any(keyword in text for keyword in keywords):
            return intent
    return None


def _answer_peers(index: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[str, list[Mapping[str, Any]]]:
    peers = [pick(index, f"account_peer_{code}") for code in
             ("TUN", "DZA", "EGY", "JOR", "MAR")]
    peers = [peer for peer in peers if peer is not None]
    if not peers:
        return "", []
    listing = ", ".join(f"{peer['label']} {peer['display']}" for peer in peers)
    return (
        f"Détention d'un compte en {peers[0]['year']} : {listing}.",
        peers,
    )


def answer_question(
    question: str, facts: Sequence[Mapping[str, Any]], *,
    country: str = "Tunisie", year: int | None = None,
) -> dict[str, Any]:
    """Deterministic answer; unknowns stay explicit, no number is invented."""
    index = index_facts(facts)
    intent = detect_intent(question)
    used: list[Mapping[str, Any]] = []
    answer = ""
    fallback = False

    if intent == "account":
        fact = pick(index, "account_ownership")
        if fact is not None:
            answer = (
                f"En {fact['year']}, {fact['display']} des adultes en {country} "
                f"détiennent un compte.{_delta_sentence(pick(index, 'account_ownership_delta'))}"
            )
            used = [fact, pick(index, "account_ownership_delta")]
    elif intent == "digital":
        fact = pick(index, "digital_payment_rate")
        if fact is not None:
            answer = (
                f"En {fact['year']}, {fact['display']} des adultes en {country} ont "
                "effectué ou reçu un paiement numérique ; ce n'est pas la détention "
                "d'un compte."
            )
            used = [fact]
    elif intent == "saving":
        fact = pick(index, "saving_rate")
        if fact is not None:
            answer = (
                f"En {fact['year']}, {fact['display']} des adultes en {country} "
                "épargnent toutes formes confondues (définition provisoire)."
            )
            used = [fact, pick(index, "formal_saving")]
    elif intent == "borrowing":
        fact = pick(index, "borrowing_rate")
        if fact is not None:
            answer = (
                f"En {fact['year']}, {fact['display']} des adultes en {country} "
                "empruntent toutes formes confondues (définition provisoire)."
            )
            used = [fact, pick(index, "formal_borrowing")]
    elif intent == "atm":
        fact = pick(index, "atm_per_100k")
        if fact is not None:
            stale = year is not None and fact["year"] != year
            answer = (
                f"En {fact['year']}, le pays compte {fact['display']}"
                + (" (dernière année observée)" if stale else "")
                + f".{_delta_sentence(pick(index, 'atm_per_100k_delta'))}"
            )
            index_fact = pick(index, "index_atm_per_100k")
            if index_fact is not None:
                answer += f" Indice 2017 = 100 : {index_fact['display']}."
            used = [fact, pick(index, "atm_per_100k_delta"), index_fact]
    elif intent == "branch":
        fact = pick(index, "branch_density")
        if fact is not None:
            answer = f"En {fact['year']}, le réseau d'agences est de {fact['display']}."
            used = [fact]
    elif intent == "gender":
        gap = pick(index, "gap_gender")
        women = pick(index, "gender_femmes")
        men = pick(index, "gender_hommes")
        change = pick(index, "gap_change_gender")
        if gap is not None and women is not None and men is not None:
            answer = (
                f"En {gap['year']}, {women['display']} des femmes détiennent un "
                f"compte contre {men['display']} des hommes, soit un écart de "
                f"{gap['display']}."
            )
            if change is not None:
                answer += f" Variation de l'écart : {change['display']}."
            used = [women, men, gap, change]
    elif intent == "rural":
        urban = pick(index, "urban_account")
        rural = pick(index, "rural_account")
        gap = pick(index, "gap_urbanicity")
        if urban is not None and rural is not None:
            answer = (
                f"En {urban['year']}, {urban['display']} des adultes urbains "
                f"détiennent un compte contre {rural['display']} des adultes ruraux."
            )
            if gap is not None:
                answer += f" Écart : {gap['display']}."
            used = [urban, rural, gap]
    elif intent == "poverty":
        fact = pick(index, "poverty_rate_2021")
        extreme = pick(index, "poverty_rate_extreme_2021")
        if fact is not None:
            answer = (
                f"Le taux de pauvreté national était de {fact['display']} en "
                f"{fact['year']} (INS), un contexte, pas une mesure d'exclusion."
            )
            used = [fact]
            text = _strip(question)
            detail = pick(
                index,
                "poverty_rate_rural_2021" if "rural" in text else "poverty_rate_urban_2021",
            )
            if detail is not None and ("rural" in text or "urbain" in text or "urban" in text):
                answer += f" Milieu concerné : {detail['display']} en {detail['year']}."
                used.append(detail)
            if extreme is not None:
                answer += f" Pauvreté extrême : {extreme['display']}."
                used.append(extreme)
    elif intent == "smig":
        first = pick(index, "smig_2025")
        last = pick(index, "smig_2028")
        if first is not None and last is not None:
            answer = (
                f"Le SMIG mensuel brut est de {first['display']} en {first['year']} "
                f"et le barème publié prévoit {last['display']} en {last['year']} "
                "(revalorisations à confirmer au JORT)."
            )
            used = [first, last]
    elif intent == "emergency":
        fact = pick(index, "emergency_money")
        if fact is not None:
            answer = (
                f"En {fact['year']}, {fact['display']} des adultes déclarent pouvoir "
                "obtenir de l'argent en urgence (fin24aP), mais le libellé du "
                "dictionnaire ne concorde pas avec la définition Findex : valeur à revoir."
            )
            used = [fact]
    elif intent == "loans":
        parts = []
        cited = []
        for code, label in (("loans_pct_gdp", "Encours de crédits"),
                            ("deposits_pct_gdp", "Encours de dépôts"),
                            ("depositors_per_1k", "Déposants"),
                            ("borrowers_per_1k", "Emprunteurs")):
            fact = pick(index, code)
            if fact is not None:
                parts.append(f"{label} {fact['display']} en {fact['year']}")
                cited.append(fact)
        if parts:
            answer = "; ".join(parts) + "."
            used = cited
    elif intent == "peers":
        answer, used = _answer_peers(index)
    elif intent == "index":
        parts = []
        cited = []
        for code, label in (("index_atm_per_100k", "ATMs"),
                            ("index_digital_payment_rate", "Paiements numériques")):
            fact = pick(index, code)
            if fact is not None:
                parts.append(f"{label} : indice {fact['display']} en {fact['year']}")
                cited.append(fact)
        if parts:
            answer = "; ".join(parts) + " (2017 = 100)."
            used = cited

    if not answer:
        fallback = True
        answer = NO_DATA_ANSWER if intent is not None else UNKNOWN_ANSWER

    unknown = verify_numbers(answer, facts)
    if unknown:
        fallback = True
        answer = NO_DATA_ANSWER
        used = []

    return {
        "schema_version": SCHEMA_VERSION,
        "question": question,
        "intent": intent or "unknown",
        "answer": answer,
        "fallback": fallback,
        "fact_ids": tuple(distinct["id"] for distinct in used if distinct is not None),
        "facts": [dict(fact) for fact in used if fact is not None],
        "caveat": None if fallback else ASSOCIATION_CAVEAT,
        "number_check": {"passed": not unknown, "unknown": unknown},
    }


def narration_prompt(insight: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]) -> str:
    cited = set(insight.get("evidence_ids") or ())
    lines = [
        f"Constat: {insight['statement']}",
        "Faits autorisés (n'utilise que ces nombres, ne calcule rien):",
    ]
    for fact in facts:
        if fact.get("id") in cited:
            lines.append(
                f"- {fact['label']} = {fact['display']} (année {fact['year']}, "
                f"unité {fact['unit']})"
            )
    lines.append(
        "Réécris le constat en une phrase, sans introduire de nombre absent, "
        "sans causalité, en français."
    )
    return "\n".join(lines)


def narrate(
    agent: BaseAgent, insight: Mapping[str, Any], facts: Sequence[Mapping[str, Any]],
) -> str | None:
    """Optional LLM rewrite; rejected unless every number already exists."""
    text = agent.ask_text(
        narration_prompt(insight, facts),
        system=(
            "Tu es un analyste prudent. Tu ne calcules jamais, tu n'inventes aucun "
            "chiffre et tu ne présentes aucune association comme une causalité."
        ),
    )
    if not isinstance(text, str) or not text.strip():
        return None
    if verify_numbers(text, facts):
        return None
    return text.strip()


# ------------------------------------------------------------------------ agent
class FinovaAnalystAgent(BaseAgent):
    """Route 2 analyst: deterministic by default, optional checked narration."""

    name = "analyst"

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        facts = [dict(fact) for fact in ctx.get("facts") or []]
        if not facts:
            raise ValueError("analyst requires the dashboard facts")
        country = ctx.get("country_name") or ctx.get("iso3") or "Tunisie"
        pages = ctx.get("pages")
        payload = build_analyst_payload(facts, country, pages=pages)

        if ctx.get("narrate"):
            overview = payload["insights"].get("overview") or []
            for insight in overview:
                rewritten = narrate(self, insight, facts)
                if rewritten is None:
                    payload["warnings"].append(
                        f"{insight['id']}: narration LLM rejetée (nombre inconnu)"
                    )
                    break
                insight["statement"] = rewritten
                break

        report_path = path_of(self.cfg, "reports") / self.run_id / "finova_analyst.json"
        save_json(payload, report_path)
        return {
            "insights": payload["insights"],
            "xai": payload["xai"],
            "analyst_summary": {
                "country": country,
                "facts": payload["fact_count"],
                "insights": sum(len(items) for items in payload["insights"].values()),
                "xai": payload["xai"] is not None,
                "report": str(report_path),
            },
            "warnings": payload["warnings"],
        }


__all__ = [
    "AskRequest",
    "ASSOCIATION_CAVEAT",
    "FinovaAnalystAgent",
    "answer_question",
    "build_analyst_payload",
    "build_insights",
    "build_xai",
    "detect_intent",
    "index_facts",
    "narrate",
    "narration_prompt",
    "pick",
    "verify_numbers",
]
