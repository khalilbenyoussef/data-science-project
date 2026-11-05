"""Couche texte de l'Auditor : gabarits FR/EN et reformulation LLM verifiee.

Les gabarits sont construits uniquement a partir des enregistrements
d'explication (toujours disponibles, seuls utilises avec --no-llm). Un LLM peut
seulement reformuler un gabarit : chaque nombre de sa reponse doit figurer, a
l'identique (meme arrondi), dans le gabarit ; sinon la reponse est ecartee.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

# Nombre d'un texte : format francais (37,8 ; milliers groupes par une espace fine
# insecable U+202F ou insecable U+00A0 : « 1\u202f063,3 ») ou point decimal (37.8).
# Une espace ordinaire ne groupe jamais : « en 2024 37,8 » reste deux nombres.
THOUSANDS = "\u202f\u00a0"
NUMBER = re.compile(
    r"(?<![\w.,\u202f\u00a0])[-+−]?(?:\d{1,3}(?:[\u202f\u00a0]\d{3})+|\d+)(?:[.,]\d+)?(?!\w)")
UNIT_LABELS = {
    "fr": {"percent": "%", "percentage_points": "pts", "per_100k_adults": "pour 100 000 adultes"},
    "en": {"percent": "%", "percentage_points": "pts", "per_100k_adults": "per 100 000 adults"},
}
STATUS_LABELS = {
    "fr": {"approved": "approuvé", "approved_with_review_note": "approuvé avec note de revue",
           "blocked": "bloqué", "not_evaluated": "non évalué"},
    "en": {"approved": "approved", "approved_with_review_note": "approved with review note",
           "blocked": "blocked", "not_evaluated": "not evaluated"},
}


# --------------------------------------------------------------------------- controles
# Nom court en francais de chaque controle de l'Auditor (l'identifiant technique reste
# affiche a cote, en petit). Un controle inconnu garde son identifiant.
CHECK_NAMES = {
    "A1_recomputed_values": "Valeurs recalculées",
    "A2_unavailable_rows_are_null": "Valeurs indisponibles vides",
    "A3_peers_recomputed": "Moyennes des pairs recalculées",
    "A4_row_completeness": "Lignes attendues présentes",
    "A5_raw_to_fact": "Fichiers bruts fidèles à l'entrepôt",
    "A6_user_source_facts": "Sources utilisateur fidèles au fichier",
    "B1_one_unit_per_kpi": "Une unité par indicateur",
    "B2_value_ranges": "Valeurs dans les bornes",
    "B3_country_entities_only": "Pays uniquement, sans agrégat",
    "B4_peers_are_configured_peers": "Pairs conformes à la configuration",
    "B5_snapshot_and_run_ids": "Version et run cohérents",
    "B6_source_hashes": "Empreintes des sources",
    "B7_warehouse_content_digest": "Empreinte de l'entrepôt",
    "B8_catalog_definitions": "Définitions du catalogue",
    "B9_quality_gate": "Contrôle qualité réussi",
    "C1_partial_survey_wave": "Vagues d'enquête partielles",
    "C2_partial_peer_coverage": "Moyennes de pairs incomplètes",
    "C3_input_quality_findings": "Constats qualité sur les entrées",
    "C4_within_survey_noise": "Variations dans le bruit d'enquête",
    "F1_insights_grounded": "Constats fondés sur les chiffres",
}
VERDICTS_FR = {"pass": "conforme", "pass_with_warnings": "conforme avec avertissements", "fail": "non conforme"}


def check_name(check_id: str | None) -> str:
    """« A2 – Valeurs indisponibles vides » ; identifiant seul si le controle est inconnu."""
    code = str(check_id or "")
    name = CHECK_NAMES.get(code)
    return f"{code.split('_')[0]} – {name}" if name else code


def insight_faults_note(faults: list[dict[str, Any]]) -> str | None:
    """Ligne sous le tableau d'injection de fautes : les fautes portant sur les constats
    (controle F*) sont arretees par le rejet du constat, pas par le verdict des donnees."""
    numbers = [i for i, fault in enumerate(faults, 1) if str(fault.get("expected_check") or "").startswith("F")]
    if not numbers:
        return None
    verdicts = {VERDICTS_FR.get(f.get("verdict"), f.get("verdict")) for f in faults
                if str(f.get("expected_check") or "").startswith("F")}
    label = f"{numbers[0]}–{numbers[-1]}" if len(numbers) > 1 else str(numbers[0])
    verdict = next(iter(verdicts)) if len(verdicts) == 1 else "inchangé"
    return (f"Fautes {label} (constats) : elles sont détectées par le rejet du constat concerné ; les données "
            f"restent exactes, donc le verdict des données reste « {verdict} ».")


# --------------------------------------------------------------------------- nombres
def fr_number(value: float | int, decimals: int = 1, signed: bool = False, thousands: str = "\u202f") -> str:
    """Nombre au format francais : virgule decimale, milliers separes par ``thousands``
    (U+202F dans l'application et l'API, U+00A0 dans les PDF). Affichage seulement."""
    text = f"{value:+,.{decimals}f}" if signed else f"{value:,.{decimals}f}"
    return text.replace(",", "|").replace(".", ",").replace("|", thousands)


def number_value(token: str) -> float:
    """Valeur d'un nombre lu par NUMBER (signe, groupes de milliers et virgule acceptes)."""
    text = token.replace("−", "-")
    for sep in THOUSANDS:
        text = text.replace(sep, "")
    return float(text.replace(",", "."))


def fmt(value: float | None, lang: str, decimals: int = 1, signed: bool = False) -> str:
    if value is None:
        return "n/d" if lang == "fr" else "n/a"
    if lang == "fr":
        return fr_number(value, decimals, signed)
    return f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"


def extract_numbers(text: str) -> list[str]:
    """Nombres d'un texte, forme canonique (point decimal, sans signe) ; les chiffres
    inclus dans un identifiant (v1, hash) sont ignores."""
    out = []
    for token in NUMBER.findall(text or ""):
        canonical = token.lstrip("+-−").replace(",", ".")
        for sep in THOUSANDS:
            canonical = canonical.replace(sep, "")
        out.append(canonical)
    return out


def grounding(candidate: str, reference: str) -> tuple[bool, list[str]]:
    """(accepte, nombres non justifies) : chaque nombre du candidat doit exister
    dans le texte de reference avec le meme arrondi."""
    allowed = set(extract_numbers(reference))
    unsupported = [n for n in extract_numbers(candidate) if n not in allowed]
    return not unsupported, unsupported


# --------------------------------------------------------------------------- gabarits
def _country(record: Mapping[str, Any], lang: str) -> str:
    if record["iso3"] == "PEERS":
        return "Moyenne des pairs" if lang == "fr" else "Peer average"
    return record["country"]


def _unit(record: Mapping[str, Any], lang: str) -> str:
    return UNIT_LABELS[lang].get(record["unit"], record["unit"])


def template_text(record: Mapping[str, Any], lang: str = "fr") -> str:
    """Phrase deterministe d'une ligne KPI (valeur, origine, calcul, statut)."""
    fr = lang == "fr"
    name = (record.get("kpi_name") if fr else record.get("kpi_name_en") or record.get("kpi_name")) \
        or record["kpi_id"]
    head = f"{name} - {_country(record, lang)} ({record['iso3']}), {record['year']}"
    status = STATUS_LABELS[lang].get(record.get("publication_status"), record.get("publication_status"))
    if record["value"] is None:
        why = record.get("reason") or "missing_observation"
        return (f"{head} : indisponible ({why}). Aucune valeur n'est imputee. Statut : {status}."
                if fr else f"{head}: unavailable ({why}). No value is imputed. Status: {status}.")
    unit = _unit(record, lang)
    parts = [f"{head} : {fmt(record['value'], lang)} {unit}." if fr
             else f"{head}: {fmt(record['value'], lang)} {unit}."]
    deps = record.get("dependencies") or []
    if record["iso3"] == "PEERS":
        included = [d for d in deps if d.get("included")]
        listing = ", ".join(f"{d['iso3']} {fmt(d['value'], lang)}" for d in included)
        missing = [d["iso3"] for d in deps if not d.get("included")]
        parts.append(f"Moyenne simple de {len(included)} pair(s) : {listing}." if fr
                     else f"Simple mean of {len(included)} peer(s): {listing}.")
        if missing:
            parts.append(f"Pairs sans valeur : {', '.join(missing)}." if fr
                         else f"Peers without a value: {', '.join(missing)}.")
    elif len(deps) == 2:
        a, b = deps
        parts.append(f"Écart = {a['label']} {fmt(a['value'], lang)} % - {b['label']} {fmt(b['value'], lang)} %."
                     if fr else f"Gap = {a['label']} {fmt(a['value'], lang)}% - {b['label']} {fmt(b['value'], lang)}%.")
    elif len(deps) == 1:
        d = deps[0]
        parts.append(f"Calculé comme 100 - {d['label']} ({fmt(d['value'], lang)} %)." if fr
                     else f"Computed as 100 - {d['label']} ({fmt(d['value'], lang)}%).")
    inputs = record.get("inputs") or []
    if inputs and record["iso3"] != "PEERS":
        raw = inputs[0]["raw"]
        texts = ", ".join(str(i["raw"].get("raw_value_text")) for i in inputs)
        parts.append(f"Source : {raw['source']}, colonne {raw['column']}, valeur(s) brute(s) {texts} "
                     f"(snapshot {raw.get('snapshot_id')}) ; {record['transformation']}." if fr
                     else f"Source: {raw['source']}, column {raw['column']}, raw value(s) {texts} "
                     f"(snapshot {raw.get('snapshot_id')}); "
                     f"{record.get('transformation_en') or record['transformation']}.")
    reasons = list(record.get("review_reasons") or []) + [c["check_id"] for c in record.get("checks") or []
                                                          if c.get("affects_publication", True)]
    parts.append(f"Statut : {status}" + (f" ({', '.join(reasons)})." if reasons else ".") if fr
                 else f"Status: {status}" + (f" ({', '.join(reasons)})." if reasons else "."))
    return " ".join(parts)


def change_text(change: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any],
                lang: str = "fr") -> str:
    """Phrase deterministe d'une variation (annees ou pays) et de sa decomposition."""
    fr = lang == "fr"
    name = (right.get("kpi_name") if fr else right.get("kpi_name_en") or right.get("kpi_name")) \
        or right["kpi_id"]
    unit = _unit(right, lang)
    delta_unit = "pts" if change["delta_unit"] == "percentage_points" else unit
    side = lambda r: f"{_country(r, lang)} {r['year']}"  # noqa: E731
    if change["delta"] is None:
        return (f"{name} : comparaison impossible ({change.get('reason')})." if fr
                else f"{name}: comparison not possible ({change.get('reason')}).")
    text = (f"{name}{' :' if fr else ':'} {side(left)} {fmt(left['value'], lang)} {unit} -> {side(right)} "
            f"{fmt(right['value'], lang)} {unit}, {'variation' if fr else 'change'} "
            f"{fmt(change['delta'], lang, signed=True)} {delta_unit}.")
    comps = change.get("components") or []
    if comps and left["iso3"] == "PEERS":
        text += (" Contributions des pairs : " if fr else " Peer contributions: ") + ", ".join(
            f"{c['label']} {fmt(c['contribution'], lang, signed=True)}" for c in comps
            if c.get("contribution") is not None) + "."
    elif len(comps) == 2:
        text += (" Décomposition : " if fr else " Breakdown: ") + ", ".join(
            f"{c['label']} {fmt(c['delta'], lang, signed=True)} pts" for c in comps) + "."
    elif (left["iso3"] == "PEERS") != (right["iso3"] == "PEERS"):
        peers = left if left["iso3"] == "PEERS" else right
        listed = [d for d in peers.get("dependencies") or [] if d.get("included")]
        text += (" Pairs : " if fr else " Peers: ") + ", ".join(
            f"{d['iso3']} {fmt(d['value'], lang)}" for d in listed) + "."
    if not change.get("comparable", True):
        text += (f" Non comparable : {change.get('reason')}." if fr else f" Not comparable: {change.get('reason')}.")
    if change.get("within_survey_noise"):
        text += (f" Variation inférieure à {fmt(change['min_meaningful_change_pp'], lang)} pts : "
                 "dans le bruit d'enquete." if fr else
                 f" Change below {fmt(change['min_meaningful_change_pp'], lang)} pts: within survey noise.")
    return text


# --------------------------------------------------------------------------- LLM
def rephrase(template: str, lang: str, ask: Callable[[str, str], str | None] | None) -> dict[str, Any]:
    """Reformulation LLM optionnelle, acceptee seulement si elle est ancree dans le gabarit."""
    result = {"text": template, "origin": "template", "unsupported_numbers": []}
    if ask is None:
        return result
    language = "francais" if lang == "fr" else "English"
    prompt = (f"Reformule ce texte en {language} clair pour un lecteur non technique, en une ou deux "
              "phrases. N'ajoute, ne retire, n'arrondis et ne calcule aucun nombre : recopie chaque "
              f"nombre exactement.\n\nTexte : {template}")
    answer = ask(prompt, "Tu reformules des explications de KPI sans jamais inventer de chiffres.")
    if not answer or not answer.strip():
        return {**result, "origin": "template", "llm_status": "no_answer"}
    ok, unsupported = grounding(answer, template)
    if not ok:
        return {**result, "llm_status": "rejected_ungrounded", "unsupported_numbers": unsupported,
                "rejected_text": answer.strip()}
    return {"text": answer.strip(), "origin": "llm", "unsupported_numbers": [], "llm_status": "accepted"}


# --------------------------------------------------------------------------- Markdown
def render_markdown(record: Mapping[str, Any], lang: str = "fr", change: Mapping[str, Any] | None = None,
                    other: Mapping[str, Any] | None = None) -> str:
    """Explication lisible (CLI explain) a partir des enregistrements stockes."""
    fr = lang == "fr"
    narrative = (record.get("narrative") or {}).get(lang) or template_text(record, lang)
    lines = [f"# {record.get('kpi_name') or record['kpi_id']} - {_country(record, lang)} {record['year']}", "",
             narrative, ""]
    if change is not None and other is not None:
        lines += ["## " + ("Variation" if fr else "Change"), "", change_text(change, other, record, lang), ""]
    lines += ["## " + ("Tracabilite" if fr else "Traceability"), "",
              "| " + (" | ".join(["Champ", "Valeur"] if fr else ["Field", "Value"])) + " |", "|---|---|"]
    rows = [("kpi_id", record["kpi_id"]), ("value", record["value"]), ("unit", record["unit"]),
            ("formula", record.get("formula")), ("catalog", f"{record.get('catalog_version')} "
             f"({str(record.get('catalog_sha256'))[:12]})"), ("snapshot", record.get("snapshot_id")),
            ("definition_status", record.get("definition_status")),
            ("publication_status", record.get("publication_status"))]
    for item in record.get("inputs") or []:
        raw = item["raw"]
        rows.append((f"input ({item['role']})", f"{item['fact_key']} = {item['fact_value']} ; brut "
                     f"{raw.get('record_key')} [{raw.get('column')}] = {raw.get('raw_value_text')} ; "
                     f"sha256 {str(raw.get('sha256'))[:12]}"))
    for dep in record.get("dependencies") or []:
        rows.append((f"dependency {dep.get('label')}", dep.get("value")))
    for check in record.get("checks") or []:
        rows.append((f"check {check['check_id']}", check["result"]))
    lines += [f"| {k} | {str(v).replace('|', '/')} |" for k, v in rows]
    return "\n".join(lines) + "\n"


__all__ = ["change_text", "extract_numbers", "fmt", "grounding", "render_markdown", "rephrase", "template_text"]
