"""Pistes de recommandation deterministes (config/recommendations.yaml).

Une regle lit les lignes kpi_values auditees (statut approved ou
approved_with_review_note) du pays et de l'annee selectionnes, compare a un seuil
et, si elle se declenche, ecrit une « piste a explorer » a partir d'un gabarit :
elle cite ses chiffres, nomme le groupe cible et rappelle « association, pas
causalite ». Aucun LLM. Les nombres du texte passent ensuite l'audit des insights
(valeur d'un claim, annee d'un claim ou difference entre deux claims du meme KPI) ;
une piste non justifiee est ecartee et comptee comme rejetee.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

import duckdb
import yaml

from biflow.config import ROOT
from biflow.tools.audit_text import UNIT_LABELS
from biflow.tools.dashboard_spec import COUNTRY_LABELS
from biflow.tools.insights import audit_insights

RULES_PATH = ROOT / "config" / "recommendations.yaml"
KINDS = ("subgroup_gap", "above_peers", "below_peers", "below_peers_relative")
# KPI d'ecart -> (KPI du groupe favorise, KPI du groupe cible), selon la definition du catalogue
GAP_COMPONENTS = {
    "gender_gap": ("account_ownership_men", "account_ownership_women"),
    "income_gap": ("account_ownership_richest_60", "account_ownership_poorest_40"),
    "education_gap": ("account_ownership_secondary_or_more", "account_ownership_primary_or_less"),
    "laborforce_gap": ("account_ownership_in_laborforce", "account_ownership_out_of_laborforce"),
    "age_gap": ("account_ownership_age_25_plus", "account_ownership_age_15_24"),
    "urban_gap": ("account_ownership_urban", "account_ownership_rural"),
}
UNIT_TEXT = {"percent": "%", "percentage_points": "pts", "per_100k_adults": UNIT_LABELS["fr"]["per_100k_adults"]}


class RulesError(ValueError):
    """Fichier de regles invalide."""


def load_rules(path: str | Path = RULES_PATH) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise RulesError(f"{path} : liste « rules » attendue")
    for rule in data["rules"]:
        if rule.get("kind") not in KINDS:
            raise RulesError(f"regle {rule.get('id')} : type inconnu {rule.get('kind')}")
        key = "threshold_pct" if rule["kind"] == "below_peers_relative" else "threshold_pp"
        if not isinstance(rule.get(key), (int, float)) or rule[key] <= 0:
            raise RulesError(f"regle {rule.get('id')} : {key} positif attendu")
        if not isinstance(rule.get("kpis"), dict) or not rule["kpis"]:
            raise RulesError(f"regle {rule.get('id')} : kpis attendus")
    return data


def read_rows(warehouse: str | Path, iso3: str, year: int) -> list[dict[str, Any]]:
    """Lignes kpi_values du pays, de la moyenne des pairs et de l'annee (lecture seule)."""
    path = Path(warehouse)
    if not path.is_file():
        return []
    with duckdb.connect(str(path), read_only=True) as con:
        cursor = con.execute(
            "SELECT kpi_id, iso3, year, value, unit, publication_status, review_reasons, peer_status, "
            "peers_included, missing_peers FROM kpi_values WHERE year = ? AND iso3 IN (?, 'PEERS')",
            [int(year), iso3])
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def _r1(value: float) -> str:
    return f"{value:.1f}"


def _country(iso3: str) -> str:
    return COUNTRY_LABELS.get(iso3, iso3)


def _in_country(iso3: str) -> str:
    """« en Tunisie », « au Maroc » ; code ISO3 seul pour un pays sans libelle."""
    return {"MAR": "au Maroc"}.get(iso3) or (f"en {COUNTRY_LABELS[iso3]}" if iso3 in COUNTRY_LABELS else f"en {iso3}")


def _peer_note(peers: Mapping[str, Any], iso3: str) -> str:
    notes = []
    missing = [_country(c) for c in peers.get("missing_peers") or []]
    if peers.get("peer_status") == "partial" or missing:
        notes.append("moyenne partielle, sans " + ", ".join(missing) if missing else "moyenne partielle")
    if iso3 in (peers.get("peers_included") or []):
        notes.append(f"moyenne incluant {_country(iso3)}")
    return f" ({' ; '.join(notes)})" if notes else ""


def _claim(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"kpi_id": row["kpi_id"], "iso3": row["iso3"], "year": int(row["year"]),
            "value": float(row["value"]), "unit": row["unit"]}


def _evidence(row: Mapping[str, Any], name: str) -> dict[str, Any]:
    return {"id": f"EV-{row['kpi_id']}-{row['iso3']}-{int(row['year'])}", "kpi_id": row["kpi_id"],
            "kpi": name, "iso3": row["iso3"], "year": int(row["year"]), "value": float(row["value"]),
            "unit": row["unit"], "publication_status": row["publication_status"],
            "review_reasons": list(row.get("review_reasons") or [])}


def _strip_labels(text: str, labels: Iterable[str]) -> str:
    """Texte audite : sans les libelles de configuration (groupes, unites) qui
    contiennent des chiffres sans etre des donnees (« 40 % les plus pauvres »)."""
    for label in sorted({l for l in labels if l}, key=len, reverse=True):
        text = text.replace(label, " ")
    return text


def evaluate(rows: Iterable[Mapping[str, Any]], iso3: str, year: int, rules: Mapping[str, Any],
             catalog_kpis: Mapping[str, Any]) -> dict[str, Any]:
    """Pistes declenchees pour (iso3, year) ; chaque piste est auditee avant d'etre rendue."""
    statuses = tuple(rules.get("publication_statuses") or ("approved", "approved_with_review_note"))
    all_rows = list(rows)
    usable = {(r["kpi_id"], r["iso3"]): r for r in all_rows
              if r.get("value") is not None and r.get("publication_status") in statuses and int(r["year"]) == year}
    prefix, caveat = rules.get("prefix", "Piste à explorer : "), rules.get("caveat", "Association, pas causalité.")
    forbidden = [p.lower() for p in rules.get("forbidden_phrases") or []]
    country, in_country = _country(iso3), _in_country(iso3)
    out, rejected, checked = [], [], 0

    def name(kpi_id: str) -> str:
        kpi = catalog_kpis.get(kpi_id) or {}
        return kpi.get("name_fr") or kpi.get("name") or kpi_id

    for rule in rules["rules"]:
        kind = rule["kind"]
        threshold = rule.get("threshold_pct" if kind == "below_peers_relative" else "threshold_pp")
        for kpi_id, spec in rule["kpis"].items():
            row, peers = usable.get((kpi_id, iso3)), usable.get((kpi_id, "PEERS"))
            if row is None:
                continue
            labels = [spec.get("target"), spec.get("advantaged"), UNIT_TEXT["per_100k_adults"]]
            value, unit = float(row["value"]), UNIT_TEXT.get(row["unit"], row["unit"])
            if kind == "subgroup_gap":
                checked += 1
                if abs(value) < threshold:
                    continue
                hi_id, lo_id = GAP_COMPONENTS.get(kpi_id, (None, None))
                advantaged, target = spec.get("advantaged"), spec.get("target")
                if value < 0:
                    advantaged, target, hi_id, lo_id = target, advantaged, lo_id, hi_id
                hi, lo = usable.get((hi_id, iso3)), usable.get((lo_id, iso3))
                cited = [row] + [r for r in (hi, lo) if r is not None]
                detail = (f" ({_r1(float(hi['value']))} % contre {_r1(float(lo['value']))} %)"
                          if hi is not None and lo is not None else "")
                fact = (f"en {year}, {in_country}, l'écart de {spec.get('topic', name(kpi_id))} entre {advantaged} "
                        f"et {target} est de {_r1(abs(value))} pts{detail}")
                trigger = {"value": abs(value), "threshold": threshold, "unit": "pts"}
            else:
                if peers is None:
                    continue
                checked += 1
                peer = float(peers["value"])
                gap = value - peer if kind == "above_peers" else peer - value
                if kind == "below_peers_relative":
                    relative = 100 * gap / peer if peer else 0.0
                    if relative < threshold:
                        continue
                    trigger = {"value": relative, "threshold": threshold, "unit": "%"}
                elif gap < threshold:
                    continue
                else:
                    trigger = {"value": gap, "threshold": threshold, "unit": "pts"}
                target = spec.get("target")
                cited = [row, peers]
                note = _peer_note(peers, iso3)
                if kind == "above_peers":
                    reason = name(kpi_id).split(":", 1)[-1].strip()
                    fact = (f"en {year}, {_r1(value)} % des adultes {in_country} n'ont pas de compte et citent "
                            f"« {reason} », contre {_r1(peer)} % en moyenne chez les pairs{note}, "
                            f"soit {_r1(gap)} pts de plus")
                elif kind == "below_peers":
                    fact = (f"en {year}, {name(kpi_id).lower()} : {_r1(value)} % {in_country}, contre "
                            f"{_r1(peer)} % en moyenne chez les pairs{note}, soit {_r1(gap)} pts de moins")
                else:
                    fact = (f"en {year}, {name(kpi_id).lower()} : {_r1(value)} {unit} {in_country}, contre "
                            f"{_r1(peer)} en moyenne chez les pairs{note}")
            piste = str(spec.get("piste", "")).format(target=target)
            text = f"{prefix}{piste}. Constat : {fact}. {caveat}"
            rec = {
                "id": f"REC-{rule['id']}-{kpi_id}-{iso3}-{year}", "rule_id": rule["id"], "kind": kind,
                "kpi_id": kpi_id, "kpi": name(kpi_id), "iso3": iso3, "year": year, "country": country,
                "target_group": target, "text": text,
                "rule": str(rule.get("rule_label", "")).format(threshold=threshold), "trigger": trigger,
                "evidence": [_evidence(r, name(r["kpi_id"])) for r in cited],
                "review_note": any(r["publication_status"] == "approved_with_review_note" for r in cited),
            }
            audit = audit_insights([{"insight_id": rec["id"], "text": _strip_labels(text, labels),
                                     "claims": [_claim(r) for r in cited], "recommendation": piste,
                                     "confidence": "medium"}], all_rows)[0]
            lowered = text.lower()
            bad_words = [p.strip() for p in forbidden if p in lowered]
            if bad_words:
                audit = {**audit, "accepted": False,
                         "reasons": list(audit["reasons"]) + [f"formulation interdite : {w}" for w in bad_words]}
            rec["audit"] = {"accepted": audit["accepted"], "reasons": audit["reasons"], "notes": audit["notes"]}
            (out if audit["accepted"] else rejected).append(rec)
    return {"iso3": iso3, "year": year, "country": country, "rules_version": rules.get("version"),
            "rules_checked": checked, "recommendations": out, "rejected": rejected}


def recommendations_for(warehouse: str | Path, iso3: str, year: int, catalog_kpis: Mapping[str, Any],
                        rules_path: str | Path = RULES_PATH) -> dict[str, Any]:
    return evaluate(read_rows(warehouse, iso3, year), iso3, year, load_rules(rules_path), catalog_kpis)


__all__ = ["GAP_COMPONENTS", "RULES_PATH", "RulesError", "evaluate", "load_rules", "read_rows",
           "recommendations_for"]
