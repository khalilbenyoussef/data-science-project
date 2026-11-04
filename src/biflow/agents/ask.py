"""Ask Finova conversationnel : LLM avec outils sur les faits du tableau de bord.

Avec une cle LLM (``llm.routing.ask``), l'assistant converse librement et lit les
chiffres uniquement via des outils qui renvoient les faits des vues Finova
(aucun SQL, aucune autre source). Chaque nombre de la reponse doit figurer dans
les resultats d'outils du tour (controle de l'Auditor, ``audit_text.grounding``) :
sinon une seule regeneration, puis la reponse deterministe. Sans cle, un repli
deterministe gere salutations, remerciements, suggestions, relances simples
(« et en 2021 ? », « et le Maroc ? ») et quelques formulations FR / EN / darija.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections import OrderedDict
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from biflow.agents.analyst import (
    ASSOCIATION_CAVEAT, SCHEMA_VERSION, UNKNOWN_ANSWER, _strip, answer_question, detect_intent,
)
from biflow.llm import LLMConfigError, build_chat_model, key_format_ok, provider_env_var
from biflow.tools.audit_text import extract_numbers, grounding

logger = logging.getLogger(__name__)

ViewProvider = Callable[[str, int], Mapping[str, Any]]
ExplainReader = Callable[[str, str, int, str], str | None]

COUNTRY_NAMES = {"TUN": "Tunisie", "DZA": "Algérie", "EGY": "Égypte", "JOR": "Jordanie", "MAR": "Maroc"}
# formes francaises avec article : « en Tunisie », « au Maroc », « la Tunisie », « le Maroc »
COUNTRY_IN = {"TUN": "en Tunisie", "DZA": "en Algérie", "EGY": "en Égypte", "JOR": "en Jordanie",
              "MAR": "au Maroc"}
COUNTRY_THE = {"TUN": "la Tunisie", "DZA": "l'Algérie", "EGY": "l'Égypte", "JOR": "la Jordanie",
               "MAR": "le Maroc"}
COUNTRY_AR = {"TUN": "تونس", "DZA": "الجزائر", "EGY": "مصر", "JOR": "الأردن", "MAR": "المغرب"}
COUNTRY_EN = {"TUN": "Tunisia", "DZA": "Algeria", "EGY": "Egypt", "JOR": "Jordan", "MAR": "Morocco"}
COUNTRY_ALIASES = {
    "TUN": ("tunisie", "tunisia", "tounes", "tunis", "تونس"),
    "DZA": ("algerie", "algeria", "dzayer", "djazair", "الجزائر"),
    "EGY": ("egypte", "egypt", "masr", "مصر"),
    "JOR": ("jordanie", "jordan", "ordon", "الأردن", "الاردن"),
    "MAR": ("maroc", "morocco", "maghrib", "المغرب"),
}
# mots FR / EN / darija / arabe -> mot-cle du routeur deterministe (detect_intent)
INTENT_ALIASES = {
    "compte": ("bank account", "7sab", "hsab", "banka", "حساب", "بنك"),
    "femme": ("women", "woman", "nsa", "mra", "نساء", "المرأة", "المراة"),
    "epargne": ("tawfir", "ndakhar", "ادخار"),
    "emprunt": ("9ardh", "9redh", "kredi", "قرض"),
    "numerique": ("carta", "mobile money", "رقمي"),
    "atm": ("guichet", "صراف"),
    "rural": ("rif", "ريف"),
    "pauvrete": ("poor", "faqr", "فقر"),
    "smig": ("minimum wage",),
    "compar": ("neighbo", "jiran", "مقارنة", "versus", " vs "),
    "ecart": ("gap", "far9", "فرق"),
}
GREETINGS = ("bonjour", "bonsoir", "salut", "coucou", "hello", "hi", "hey", "salam", "aslema",
             "ahla", "marhba", "good morning", "السلام", "مرحبا", "اهلا", "أهلا")
THANKS = ("merci", "thanks", "thank you", "thx", "choukran", "chokran", "y3aychek", "yaatik",
          "شكرا", "يعطيك")
GOODBYES = ("au revoir", "bye", "a plus", "bslama", "beslema", "مع السلامة")
HELP = ("qui es-tu", "qui es tu", "tu fais quoi", "que sais-tu", "what can you do",
        "who are you", "help", "aide", "chnowa ta3mel", "chnowa najem", "شنوة تعمل")
CONCEPTS = {
    "inclusion": (("inclusion financiere", "financial inclusion", "الشمول المالي"), {
        "fr": ("L'inclusion financière désigne l'accès et l'usage, par les adultes, de "
               "services financiers formels : compte, paiements, épargne, crédit, assurance. "
               "Dans Finova, elle est suivie avec l'enquête Findex de la Banque mondiale "
               "(demande) et les données FAS du FMI (offre : agences, distributeurs, crédits)."),
        "en": ("Financial inclusion means that adults can access and use formal financial "
               "services: accounts, payments, savings, credit and insurance. Finova tracks it "
               "with the World Bank Findex survey (demand side) and IMF FAS data (supply side: "
               "branches, ATMs, credit)."),
    }),
    "findex": (("findex",), {
        "fr": ("Findex est l'enquête de la Banque mondiale sur l'inclusion financière, menée "
               "par vagues auprès d'adultes dans chaque pays. Entre deux vagues, Finova "
               "affiche la dernière enquête antérieure et le signale."),
        "en": ("Findex is the World Bank survey on financial inclusion, run in waves with "
               "adults in each country. Between waves, Finova shows the latest earlier survey "
               "and says so."),
    }),
    "fas": (("fas", "financial access survey"), {
        "fr": ("FAS (Financial Access Survey) est la base annuelle du FMI sur l'offre de "
               "services financiers : agences, distributeurs, déposants, emprunteurs, "
               "encours de crédits et de dépôts."),
        "en": ("FAS (Financial Access Survey) is the IMF annual database on the supply of "
               "financial services: branches, ATMs, depositors, borrowers, loans and deposits."),
    }),
}
DEFINITION_CUES = ("qu'est-ce", "qu est-ce", "c'est quoi", "cest quoi", "definition", "définition",
                   "what is", "what's", "explain", "explique", "chnowa", "chniya", "ما هو", "ما هي")
DIALECT_CUES = ("chnowa", "chniya", "9addech", "kadech", "kifech", "3lech", "barcha", "famma")
EN_CUES = ("what", "how", "which", "why", "the ", "is ", "are ", "does", "compare", "rate",
           "hello", "hi", "thanks", "thank you", "show", "tell me")
UNIT_WORDS = {"per_100k_adults": "pour 100 000 adultes (per 100,000 adults)",
              "per_1k_adults": "pour 1 000 adultes (per 1,000 adults)",
              "percentage_points": "points de pourcentage"}
ARABIC = re.compile(r"[؀-ۿ]")
YEAR = re.compile(r"\b(20[0-3]\d)\b")

SUGGESTIONS = {
    "fr": {
        "overview": ["Combien d'adultes ont un compte {en_pays} ?", "Comment se situe {le_pays} face à ses voisins ?",
                     "Quelle part utilise le paiement numérique ?", "Qu'est-ce que l'inclusion financière ?"],
        "inclusion": ["Quel est l'écart femmes-hommes {en_pays} ?", "Et l'écart entre riches et pauvres ?",
                      "Quelle part épargne ?", "Qu'est-ce que Findex ?"],
        "access": ["Combien de distributeurs pour 100 000 adultes ?", "Et le réseau d'agences ?",
                   "Quels crédits en % du PIB ?", "Les ATMs ont-ils augmenté depuis 2017 ?"],
        "exclusion": ["Quel est l'écart entre villes et zones rurales ?", "Pourquoi des adultes n'ont pas de compte ?",
                      "Combien d'adultes ont un compte {en_pays} ?"],
        "poverty": ["Quel est le SMIG ?", "Quel est le taux de pauvreté ?", "Et en zone rurale ?"],
        "pipeline": ["D'où viennent les données ?", "Qu'est-ce que Findex ?", "Qu'est-ce que FAS ?"],
    },
    "en": {
        "overview": ["How many adults have an account in {pays}?", "How does {pays} compare with its neighbours?",
                     "What share uses digital payments?", "What is financial inclusion?"],
        "inclusion": ["What is the gender gap in {pays}?", "And the gap between rich and poor?",
                      "What share saves?", "What is Findex?"],
        "access": ["How many ATMs per 100,000 adults?", "And the branch network?",
                   "What are loans as a share of GDP?"],
        "exclusion": ["What is the urban-rural gap?", "How many adults have an account in {pays}?"],
        "poverty": ["What is the minimum wage (SMIG)?", "What is the poverty rate?"],
        "pipeline": ["Where does the data come from?", "What is Findex?"],
    },
}
REPLIES = {
    "greeting": {
        "fr": "Bonjour ! Je suis Ask Finova. Posez-moi une question sur {le_pays} en {annee} : "
              "je ne réponds qu'avec les chiffres vérifiés du tableau de bord.",
        "en": "Hello! I'm Ask Finova. Ask me about {pays} in {annee}: I only answer with the "
              "verified figures of the dashboard.",
        "ar": "مرحبا! أنا Ask Finova. اسألني عن {ar_pays} في {annee}.",
    },
    "thanks": {
        "fr": "Avec plaisir ! Une autre question sur {le_pays} ?",
        "en": "You're welcome! Anything else about {pays}?",
        "ar": "على الرحب والسعة!",
    },
    "bye": {"fr": "Au revoir, à bientôt sur Finova !", "en": "Goodbye, see you soon on Finova!",
            "ar": "مع السلامة!"},
    "help": {
        "fr": "Je réponds aux questions sur la détention de compte, l'épargne, le crédit, les "
              "paiements numériques, les distributeurs, les écarts entre groupes et la "
              "comparaison avec les pays voisins, à partir des chiffres vérifiés du tableau de bord.",
        "en": "I answer questions on account ownership, savings, credit, digital payments, ATMs, "
              "gaps between groups and comparisons with neighbouring countries, using only the "
              "verified figures of the dashboard.",
    },
    "unknown": {
        "en": "I only answer from the dashboard's verified figures. Try one of the suggested "
              "questions below.",
    },
}
# Sources CSV de l'utilisateur (page « Mes données ») : jamais utilisees dans les reponses
USER_SOURCE_CUES = ("mes donnees", "source utilisateur", "sources utilisateur", "mon fichier",
                    "mon csv", "fichier importe", "fichier depose", "my data", "user source", "my file",
                    "uploaded file")
USER_SOURCE_REPLY = {
    "fr": "Cette source utilisateur n'est pas utilisée dans les réponses : Ask Finova ne cite que les "
          "chiffres officiels vérifiés du tableau de bord. Vos données restent consultables sur la page "
          "« Mes données ».",
    "en": "User sources are not used in the answers: Ask Finova only cites the dashboard's verified "
          "official figures. Your data stays available on the « Mes données » page.",
}
ARABIC_NOTE = ("Les réponses chiffrées sont en français ; une réponse complète en arabe "
               "nécessite le mode IA.")
SYSTEM_PROMPT = """Tu es Ask Finova, l'assistant du tableau de bord Finova sur l'inclusion financière.
Périmètre affiché : {pays} ({iso3}), année {annee}, page « {page} ».{vague}
Règles strictes :
- Converse naturellement (salutations, clarifications, questions de suivi, explications de concepts).
- Pour tout chiffre, appelle d'abord un outil. N'écris AUCUN nombre (valeur, année, pourcentage, rang)
  qui ne figure pas mot pour mot dans les résultats d'outils de ce tour ; ne calcule rien, n'arrondis pas.
- Une explication de concept sans outil ne contient aucun nombre.
- Si un outil dit « indisponible », dis-le simplement : aucune valeur n'est estimée.
- Cite l'année de chaque chiffre. Une association n'est jamais une causalité.
- Les sources CSV ajoutées par l'utilisateur (page « Mes données ») ne sont jamais utilisées : si on
  t'interroge à leur sujet, dis que cette source utilisateur n'est pas utilisée dans les réponses ;
  n'en parle jamais si la question ne les mentionne pas.
- Réponds dans la langue de l'utilisateur (français, anglais ou arabe), en trois phrases au plus,
  en texte simple (pas de markdown)."""
TOOLS = [
    {"type": "function", "function": {
        "name": "current_scope", "description": "Pays, année et page affichés dans le tableau de bord.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_kpis", "description": "Indicateurs disponibles dans la vue actuelle (identifiant et libellé).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_kpi", "description": "Valeur vérifiée d'un indicateur pour un pays et une année.",
        "parameters": {"type": "object", "properties": {
            "kpi_id": {"type": "string"}, "iso3": {"type": "string"}, "year": {"type": "integer"}},
            "required": ["kpi_id"]}}},
    {"type": "function", "function": {
        "name": "compare_countries", "description": "Même indicateur pour plusieurs pays, même année.",
        "parameters": {"type": "object", "properties": {
            "kpi_id": {"type": "string"}, "iso3": {"type": "array", "items": {"type": "string"}},
            "year": {"type": "integer"}}, "required": ["kpi_id", "iso3"]}}},
    {"type": "function", "function": {
        "name": "compare_years", "description": "Même indicateur pour un pays sur plusieurs années.",
        "parameters": {"type": "object", "properties": {
            "kpi_id": {"type": "string"}, "iso3": {"type": "string"},
            "years": {"type": "array", "items": {"type": "integer"}}}, "required": ["kpi_id", "years"]}}},
    {"type": "function", "function": {
        "name": "explain", "description": "Explication de l'Auditor : source, formule et statut d'une valeur.",
        "parameters": {"type": "object", "properties": {
            "kpi_id": {"type": "string"}, "iso3": {"type": "string"}, "year": {"type": "integer"}},
            "required": ["kpi_id"]}}},
]


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["user", "assistant"]
    text: StrictStr = Field(max_length=2000)


class ChatRequest(BaseModel):
    """Question de ``POST /api/ask`` avec l'historique de la session du navigateur."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: StrictStr
    iso3: StrictStr | None = None
    year: int | None = None
    page: StrictStr | None = None
    session_id: StrictStr | None = Field(default=None, max_length=64)
    history: tuple[ChatTurn, ...] = Field(default=(), max_length=40)

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question cannot be empty")
        if len(value) > 500:
            raise ValueError("question is limited to 500 characters")
        return value


# ----------------------------------------------------------------- comprehension
def _has(text: str, words: Iterable[str]) -> bool:
    padded = f" {text} "
    return any((f" {word} " in padded) if word.isascii() and len(word) <= 4 else word in text
               for word in words)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[?!.,;:¿؟]", " ", _strip(text)).split())


def detect_language(text: str) -> str:
    if ARABIC.search(text or ""):
        return "ar"
    norm = f" {_norm(text)} "
    if _has(norm, DIALECT_CUES):
        return "fr"
    english = sum(cue in norm for cue in (f" {c.strip()} " for c in EN_CUES))
    french = sum(cue in norm for cue in (" le ", " la ", " les ", " des ", " est ", " quel", " combien",
                                         " et ", " en ", " pour ", " bonjour", " merci", " pourquoi"))
    return "en" if english > french else "fr"


def mentioned_countries(text: str) -> list[str]:
    norm = _norm(text)
    raw = text or ""
    return [code for code, names in COUNTRY_ALIASES.items()
            if any((name in raw) if not name.isascii() else re.search(rf"\b{name}\b", norm)
                   for name in names)]


def mentioned_year(text: str) -> int | None:
    match = YEAR.search(text or "")
    return int(match.group(1)) if match else None


def routed_text(text: str) -> str:
    """Question enrichie des mots-cles du routeur, pays retires (« et le Maroc ? »
    n'est pas une question de comparaison)."""
    norm = _norm(text)
    for names in COUNTRY_ALIASES.values():
        for name in names:
            norm = re.sub(rf"\b{re.escape(_strip(name))}\b", " ", norm) if name.isascii() else norm
    extra = [target for target, words in INTENT_ALIASES.items()
             if any(word in norm or word in (text or "") for word in words)]
    return " ".join([norm, *extra])


def intent_of(text: str) -> str | None:
    return detect_intent(routed_text(text))


def small_talk(text: str) -> str | None:
    norm = _norm(text)
    if intent_of(text) is not None or mentioned_year(text) or mentioned_countries(text):
        return None
    for kind, words in (("help", HELP), ("thanks", THANKS), ("bye", GOODBYES), ("greeting", GREETINGS)):
        if _has(norm, [_strip(word) for word in words]) or any(w in (text or "") for w in words if not w.isascii()):
            if len(norm.split()) <= 8:
                return kind
    return None


def concept_of(text: str) -> str | None:
    norm = _norm(text)
    if not (_has(norm, [_strip(c) for c in DEFINITION_CUES]) or any(c in (text or "") for c in DEFINITION_CUES)):
        return None
    for concept, (keywords, _) in CONCEPTS.items():
        if any(_strip(word) in norm or word in (text or "") for word in keywords):
            return concept
    return None


def resolve_followup(question: str, history: Sequence[ChatTurn], iso3: str,
                     year: int) -> tuple[str, str, int, bool]:
    """(question effective, iso3, annee, relance ?) : « et en 2021 ? » reprend la
    derniere question de l'utilisateur avec la nouvelle annee ou le nouveau pays."""
    countries = mentioned_countries(question)
    wanted_year = mentioned_year(question) or year
    wanted_iso = countries[0] if len(countries) == 1 else iso3
    if intent_of(question) is not None or not (countries or mentioned_year(question)):
        return question, wanted_iso, wanted_year, False
    for turn in reversed(history):
        if turn.role == "user" and intent_of(turn.text) is not None:
            return turn.text, wanted_iso, wanted_year, True
    return question, wanted_iso, wanted_year, False


def suggestions_for(page: str | None, iso3: str, lang: str) -> list[str]:
    table = SUGGESTIONS["en" if lang == "en" else "fr"]
    names = {"pays": {"TUN": "Tunisia", "DZA": "Algeria", "EGY": "Egypt", "JOR": "Jordan",
                      "MAR": "Morocco"}.get(iso3, iso3) if lang == "en" else COUNTRY_NAMES.get(iso3, iso3),
             "en_pays": COUNTRY_IN.get(iso3, iso3), "le_pays": COUNTRY_THE.get(iso3, iso3)}
    return [item.format(**names) for item in table.get(page or "overview", table["overview"])][:4]


# ----------------------------------------------------------------------- outils
def _kpi_of(fact: Mapping[str, Any]) -> str:
    for evidence in fact.get("evidence_ids") or ():
        match = re.match(r"EV-(.+)-([A-Z]{3}|PEERS)-(\d{4}|NA)$", str(evidence))
        if match:
            return match.group(1)
    return str(fact.get("code"))


def _public(fact: Mapping[str, Any], country: str | None = None,
            wave: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item = {"kpi_id": _kpi_of(fact), "label": fact.get("label"), "display": fact.get("display"),
            "year": fact.get("year"), "iso3": fact.get("iso3"), "fact_id": fact.get("id")}
    if fact.get("unit") in UNIT_WORDS:
        item["unit_text"] = UNIT_WORDS[fact["unit"]]
    if country:
        item["country"] = country
    # seule une valeur lue a la vague anterieure (annee sans enquete) porte la note
    used, requested = (wave or {}).get("year_used"), (wave or {}).get("year_requested")
    if used and requested and used != requested and fact.get("year") == used:
        item["note"] = f"pas d'enquête Findex en {requested} : valeur de l'enquête {used}"
    return item


class FactTools:
    """Outils de lecture des faits Finova ; consignent les faits renvoyes au tour."""

    def __init__(self, view: ViewProvider, *, iso3: str, year: int, page: str | None,
                 explain_reader: ExplainReader | None = None, lang: str = "fr") -> None:
        self.view = view
        self.iso3 = iso3
        self.year = year
        self.page = page
        self.explain_reader = explain_reader
        self.lang = lang
        self.returned: list[dict[str, Any]] = []
        self.texts: list[str] = []

    def _spec(self, iso3: str, year: int) -> Mapping[str, Any]:
        return self.view(iso3, year)

    def _facts(self, kpi_id: str, iso3: str, year: int) -> list[dict[str, Any]]:
        try:
            spec = self._spec(iso3, year)
        except Exception as exc:  # noqa: BLE001 - une vue absente devient « indisponible »
            logger.info("vue indisponible %s %s : %s", iso3, year, exc)
            return []
        country = (spec.get("country") or {}).get("name") or COUNTRY_NAMES.get(iso3, iso3)
        wanted = kpi_id.strip().lower()
        facts = [fact for fact in spec.get("facts") or []
                 if fact.get("value") is not None and fact.get("iso3") == iso3]
        found = [fact for fact in facts
                 if wanted in (str(fact.get("code")).lower(), _kpi_of(fact).lower())]
        if not found:  # identifiant approche (« account_ownership_rate ») : prefixe commun
            found = [fact for fact in facts if _kpi_of(fact).lower() != "fact" and (
                wanted.startswith(_kpi_of(fact).lower()) or _kpi_of(fact).lower().startswith(wanted))]
        found.sort(key=lambda fact: (fact.get("year") != (fact.get("year_requested") or year),
                                     -(fact.get("year") or 0)))
        return [_public(fact, country, spec.get("findex_wave")) for fact in found[:2]]

    def _record(self, payload: Any) -> Any:
        text = json.dumps(payload, ensure_ascii=False)
        self.texts.append(text)
        stack = [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if item.get("fact_id"):
                    self.returned.append(item)
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
        return payload

    def current_scope(self) -> dict[str, Any]:
        spec = self._spec(self.iso3, self.year)
        wave = spec.get("findex_wave") or {}
        return self._record({
            "iso3": self.iso3, "country": (spec.get("country") or {}).get("name"),
            "year": self.year, "page": self.page,
            "findex_survey_used": wave.get("year_used"),
        })

    def list_kpis(self) -> dict[str, Any]:
        spec = self._spec(self.iso3, self.year)
        seen: dict[str, str] = {}
        for fact in spec.get("facts") or []:
            if fact.get("provider") in ("semantic", "warehouse") and fact.get("iso3") == self.iso3:
                seen.setdefault(_kpi_of(fact), str(fact.get("label")))
        # liste d'identifiants seulement : aucun chiffre a citer
        return {"kpis": [{"kpi_id": key, "label": label} for key, label in list(seen.items())[:40]]}

    def get_kpi(self, kpi_id: str, iso3: str | None = None, year: int | None = None) -> dict[str, Any]:
        code = (iso3 or self.iso3).upper()
        wanted = int(year or self.year)
        facts = self._facts(kpi_id, code, wanted)
        payload = {"kpi_id": kpi_id, "iso3": code, "year_requested": wanted,
                   "status": "available" if facts else "indisponible", "values": facts}
        if not facts:
            payload["kpi_ids_valides"] = [item["kpi_id"] for item in self.list_kpis()["kpis"]]
        return self._record(payload)

    def compare_countries(self, kpi_id: str, iso3: Sequence[str], year: int | None = None) -> dict[str, Any]:
        wanted = int(year or self.year)
        rows = [{"iso3": code.upper(), "values": self._facts(kpi_id, code.upper(), wanted)}
                for code in list(iso3)[:5]]
        return self._record({"kpi_id": kpi_id, "year_requested": wanted, "countries": rows})

    def compare_years(self, kpi_id: str, years: Sequence[int], iso3: str | None = None) -> dict[str, Any]:
        code = (iso3 or self.iso3).upper()
        rows = [{"year_requested": int(item), "values": self._facts(kpi_id, code, int(item))}
                for item in list(years)[:6]]
        return self._record({"kpi_id": kpi_id, "iso3": code, "years": rows})

    def explain(self, kpi_id: str, iso3: str | None = None, year: int | None = None) -> dict[str, Any]:
        code = (iso3 or self.iso3).upper()
        wanted = int(year or self.year)
        text = self.explain_reader(kpi_id, code, wanted, self.lang) if self.explain_reader else None
        return self._record({"kpi_id": kpi_id, "iso3": code, "year": wanted,
                             "explanation": text or "indisponible"})

    def call(self, name: str, args: Mapping[str, Any]) -> Any:
        method = getattr(self, name, None) if name in {tool["function"]["name"] for tool in TOOLS} else None
        if method is None:
            return {"error": f"outil inconnu : {name}"}
        try:
            return method(**dict(args or {}))
        except TypeError as exc:
            return {"error": f"arguments invalides : {exc}"}


# --------------------------------------------------------------------- sessions
class SessionBudget:
    """Appels LLM par session de navigateur (memoire du processus, LRU)."""

    def __init__(self, max_calls: int, max_sessions: int = 512) -> None:
        self.max_calls = max_calls
        self.max_sessions = max_sessions
        self._calls: OrderedDict[str, int] = OrderedDict()
        self._lock = threading.Lock()

    def take(self, session: str) -> bool:
        with self._lock:
            used = self._calls.pop(session, 0)
            self._calls[session] = used
            while len(self._calls) > self.max_sessions:
                self._calls.popitem(last=False)
            if used >= self.max_calls:
                return False
            self._calls[session] = used + 1
            return True

    def left(self, session: str) -> int:
        with self._lock:
            return max(0, self.max_calls - self._calls.get(session, 0))


def ask_settings(cfg: Mapping[str, Any]) -> dict[str, Any]:
    ask = ((cfg.get("llm") or {}).get("ask") or {})
    return {"temperature": float(ask.get("temperature", 0.2)),
            "max_calls_per_session": int(ask.get("max_calls_per_session", 30)),
            "max_tool_steps": int(ask.get("max_tool_steps", 4)),
            "history_turns": int(ask.get("history_turns", 10))}


def build_ask_llm(cfg: Mapping[str, Any]) -> Any | None:
    """Modeles de ``llm.routing.ask`` avec outils lies (primaire + replis) ; None
    sans cle valide, sans appel reseau."""
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("enabled", True):
        return None
    providers = llm_cfg.get("providers") or {}
    temperature = ask_settings(cfg)["temperature"]
    built = []
    for name in (llm_cfg.get("routing") or {}).get("ask") or []:
        spec = providers.get(name)
        if not spec:
            continue
        try:
            key = os.getenv(provider_env_var(name, spec), "")
            if not key or not key_format_ok(name, spec, key):
                continue
            built.append(build_chat_model(name, {**spec, "temperature": temperature}, temperature)
                         .bind_tools(TOOLS))
        except (LLMConfigError, ImportError, ValueError) as exc:
            logger.info("ask : provider %s ignore (%s)", name, exc)
    if not built:
        return None
    primary, *fallbacks = built
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


# ------------------------------------------------------------------- reponses
def _base(question: str, answer: str, *, lang: str, mode: str, intent: str,
          facts: Sequence[Mapping[str, Any]] = (), fallback: bool = False,
          caveat: str | None = None, unknown: Sequence[str] = ()) -> dict[str, Any]:
    chips = [{"id": fact.get("fact_id") or fact.get("id"), "label": fact.get("label"),
              "display": fact.get("display"), "year": fact.get("year"),
              "iso3": fact.get("iso3"), "unit": fact.get("unit")} for fact in facts]
    return {"schema_version": SCHEMA_VERSION, "question": question, "intent": intent,
            "answer": answer, "fallback": fallback, "mode": mode, "lang": lang,
            "fact_ids": tuple(chip["id"] for chip in chips if chip["id"]), "facts": chips,
            "caveat": caveat, "number_check": {"passed": not unknown, "unknown": list(unknown)}}


def deterministic_answer(request: ChatRequest, view: ViewProvider, *, iso3: str, year: int,
                         lang: str, note: str | None = None) -> dict[str, Any]:
    country = COUNTRY_NAMES.get(iso3, iso3)
    kind = small_talk(request.question)
    if kind is not None:
        replies = REPLIES[kind]
        text = replies.get(lang) or replies.get("fr") or ""
        if lang == "ar" and kind == "help":
            text = f"{REPLIES['greeting']['ar']} {replies['fr']}"
        if lang == "ar" and kind in ("greeting", "help"):
            text = f"{text} {ARABIC_NOTE}"
        names = {"pays": COUNTRY_EN.get(iso3, country) if lang == "en" else country,
                 "le_pays": COUNTRY_THE.get(iso3, country), "ar_pays": COUNTRY_AR.get(iso3, country)}
        return _base(request.question, text.format(annee=year, **names), lang=lang,
                     mode="deterministic", intent=f"small_talk:{kind}")
    concept = concept_of(request.question)
    if concept is not None:
        texts = CONCEPTS[concept][1]
        text = texts["en"] if lang == "en" else texts["fr"]
        if lang == "ar":
            text = f"{text} {ARABIC_NOTE}"
        return _base(request.question, text, lang=lang, mode="deterministic", intent=f"concept:{concept}")

    question, wanted_iso, wanted_year, followup = resolve_followup(
        request.question, request.history, iso3, year)
    try:
        spec = view(wanted_iso, wanted_year)
    except Exception as exc:  # noqa: BLE001
        logger.info("ask : vue %s %s indisponible (%s)", wanted_iso, wanted_year, exc)
        spec = {"facts": [], "country": {"name": COUNTRY_NAMES.get(wanted_iso, wanted_iso)}}
    name = (spec.get("country") or {}).get("name") or COUNTRY_NAMES.get(wanted_iso, wanted_iso)
    result = answer_question(routed_text(question), spec.get("facts") or [], country=name,
                             year=wanted_year)
    answer = result["answer"]
    if result["intent"] == "unknown" and lang == "en":
        answer = REPLIES["unknown"]["en"]
    elif lang == "en" and not result["fallback"] and result["facts"]:
        answer = f"Verified figures for {name} ({wanted_year}): " + "; ".join(
            f"{fact['label']}: {fact['display']} ({fact['year']})" for fact in result["facts"]) + "."
    if lang == "ar":
        answer = f"{answer} {ARABIC_NOTE}"
    if note:
        answer = f"{answer} {note}"
    # gabarits « des adultes en {pays} » : « au Maroc »
    answer = answer.replace(f"en {name}", COUNTRY_IN.get(wanted_iso, f"en {name}"))
    unknown = result["number_check"]["unknown"]
    out = _base(request.question, answer, lang=lang, mode="deterministic", intent=result["intent"],
                facts=[{**fact, "fact_id": fact.get("id")} for fact in result["facts"]],
                fallback=result["fallback"], caveat=result["caveat"], unknown=unknown)
    out["resolved"] = {"iso3": wanted_iso, "year": wanted_year, "followup": followup,
                       "question": question if followup else None}
    return out


def _content(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        content = " ".join(str(part.get("text", "")) if isinstance(part, dict) else str(part)
                           for part in content)
    # le panneau affiche du texte brut : l'emphase markdown est retiree
    return re.sub(r"(\*\*|__)(.+?)\1", r"\2", str(content or "")).strip()


def llm_answer(request: ChatRequest, llm: Any, tools: FactTools, *, lang: str,
               budget: Callable[[], bool], settings: Mapping[str, Any]) -> dict[str, Any] | None:
    """Tour LLM avec outils ; None si le budget est epuise ou si la reponse reste
    non fondee apres une regeneration (l'appelant repasse en deterministe)."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    spec = tools._spec(tools.iso3, tools.year)
    scope = tools.current_scope()  # resultat d'outil du tour : l'annee affichee est citable
    wave = spec.get("findex_wave") or {}
    wave_text = (f" Pas d'enquête Findex en {tools.year} : la vue utilise l'enquête {wave['year_used']}."
                 if wave.get("year_used") and wave.get("year_used") != tools.year else "")
    messages: list[Any] = [SystemMessage(SYSTEM_PROMPT.format(
        pays=(spec.get("country") or {}).get("name") or tools.iso3, iso3=tools.iso3,
        annee=tools.year, page=request.page or "overview", vague=wave_text)
        + " Résultat de l'outil current_scope : " + json.dumps(scope, ensure_ascii=False)
        + " Identifiants kpi_id utilisables (libellés, sans valeurs) : "
        + "; ".join(f"{item['kpi_id']} = {item['label']}" for item in tools.list_kpis()["kpis"]))]
    for turn in list(request.history)[-int(settings["history_turns"]):]:
        messages.append(HumanMessage(turn.text) if turn.role == "user" else AIMessage(turn.text))
    messages.append(HumanMessage(request.question))

    def run(steps: int) -> str | None:
        for _ in range(steps):
            if not budget():
                return None
            reply = llm.invoke(messages)
            messages.append(reply)
            calls = getattr(reply, "tool_calls", None) or []
            if not calls:
                return _content(reply)
            for call in calls:
                result = tools.call(call.get("name", ""), call.get("args") or {})
                messages.append(ToolMessage(json.dumps(result, ensure_ascii=False),
                                            tool_call_id=call.get("id") or call.get("name", "tool")))
        return None

    answer = run(int(settings["max_tool_steps"]))
    if answer is None:
        return None
    accepted, unsupported = grounding(answer, "\n".join(tools.texts))
    if not accepted:
        messages.append(HumanMessage(
            "Ta réponse contient des nombres absents des résultats d'outils de ce tour : "
            f"{', '.join(unsupported)}. Réécris-la sans ces nombres, ou appelle un outil."))
        answer = run(2)
        if answer is None:
            return None
        accepted, unsupported = grounding(answer, "\n".join(tools.texts))
        if not accepted:
            logger.info("ask : reponse LLM non fondee (%s), repli deterministe", unsupported)
            return None
    numbers = set(extract_numbers(answer))
    used, seen = [], set()
    for fact in tools.returned:
        if fact["fact_id"] in seen:
            continue
        if numbers & set(extract_numbers(str(fact.get("display")))):
            used.append(fact)
            seen.add(fact["fact_id"])
    result = _base(request.question, answer, lang=lang, mode="llm", intent="conversation",
                   facts=used, caveat=ASSOCIATION_CAVEAT if used else None)
    # badge du perimetre reellement repondu (comme en mode simple) : un seul pays et une
    # seule annee cites -> ce perimetre, s'il differe de celui du tableau de bord
    scopes = {(fact.get("iso3"), fact.get("year")) for fact in used}
    if len(scopes) == 1:
        iso3, year = next(iter(scopes))
        if iso3 and year and (iso3, year) != (tools.iso3, tools.year):
            result["resolved"] = {"iso3": iso3, "year": int(year), "followup": True, "question": None}
    return result


def answer_chat(request: ChatRequest, view: ViewProvider, *, iso3: str, year: int,
                llm: Any | None = None, budget: SessionBudget | None = None,
                settings: Mapping[str, Any] | None = None,
                explain_reader: ExplainReader | None = None) -> dict[str, Any]:
    """Reponse d'un tour : LLM avec outils si disponible, sinon deterministe."""
    settings = settings or ask_settings({})
    lang = detect_language(request.question)
    if any(cue in _norm(request.question) for cue in USER_SOURCE_CUES):
        result = _base(request.question, USER_SOURCE_REPLY["en" if lang == "en" else "fr"], lang=lang,
                       mode="deterministic", intent="user_source")
        result["suggestions"] = suggestions_for(request.page, iso3, lang)
        return result
    session = request.session_id or "anonymous"
    result = None
    note = None
    if llm is not None:
        tools = FactTools(view, iso3=iso3, year=year, page=request.page,
                          explain_reader=explain_reader, lang="en" if lang == "en" else "fr")
        take = (lambda: budget.take(session)) if budget is not None else (lambda: True)
        if budget is not None and budget.left(session) == 0:
            note = ("(Budget de la session atteint : réponse en mode simple.)" if lang != "en"
                    else "(Session budget reached: simple mode.)")
        else:
            try:
                result = llm_answer(request, llm, tools, lang=lang, budget=take, settings=settings)
            except Exception:  # noqa: BLE001 - un incident LLM ne casse jamais le chat
                logger.warning("ask : appel LLM en echec, repli deterministe", exc_info=True)
                result = None
    if result is None:
        result = deterministic_answer(request, view, iso3=iso3, year=year, lang=lang, note=note)
        result["llm_available"] = llm is not None
    result["suggestions"] = suggestions_for(request.page, iso3, lang)
    if budget is not None:
        result["budget_left"] = budget.left(session)
    return result


__all__ = [
    "ChatRequest", "ChatTurn", "FactTools", "SessionBudget", "TOOLS", "answer_chat", "ask_settings",
    "build_ask_llm", "detect_language", "deterministic_answer", "llm_answer", "mentioned_countries",
    "resolve_followup", "small_talk", "suggestions_for",
]
