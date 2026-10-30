"""Explications (XAI) deterministes de l'Auditor.

Chaque enregistrement d'explication est construit uniquement a partir de ce
que l'Auditor a verifie : faits d'entree recalcules, enregistrement brut du
snapshot, catalogue, controles et decisions de publication. Aucun nombre n'est
invente : un nombre absent des donnees reste absent de l'explication.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from biflow.tools.audit_checks import touched_rows

PEERS_ISO3 = "PEERS"
TRANSFORMATIONS = {
    "value": "valeur publiee telle quelle (aucune transformation)",
    "100 * value": "fraction Findex x 100 (part des adultes en %)",
    "100 * (1 - value)": "complement : 100 x (1 - fraction de detention de compte)",
}


TRANSFORMATIONS_EN = {
    "value": "published value as is (no transformation)",
    "100 * value": "Findex fraction x 100 (share of adults in %)",
    "100 * (1 - value)": "complement: 100 x (1 - account ownership fraction)",
}


def _transformation(formula: str, lang: str = "fr") -> str:
    table = TRANSFORMATIONS if lang == "fr" else TRANSFORMATIONS_EN
    if formula in table:
        return table[formula]
    return ("ecart en points : 100 x (fraction du premier sous-groupe - fraction du second)" if lang == "fr"
            else "gap in points: 100 x (first subgroup fraction - second subgroup fraction)")


def build_explanations(
    rows: list[dict[str, Any]],
    recomputed: Mapping[tuple, Mapping[str, Any]],
    raw_lookups: Mapping[tuple, Mapping[str, Any]],
    catalog: Mapping[str, Any],
    catalog_sha256: str,
    decisions: Mapping[tuple, str],
    checks: Iterable[Mapping[str, Any]],
    quality: Mapping[str, Any],
    source_meta: Mapping[str, Mapping[str, Any]],
    country_names: Mapping[str, str],
    snapshot_id: str | None,
) -> list[dict[str, Any]]:
    """Un enregistrement par ligne de kpi_values (ordre kpi_id, iso3, annee)."""
    checks = list(checks)
    touching: dict[tuple, list[dict]] = {}
    for check in checks:
        if check["result"] == "pass":
            continue
        for key in touched_rows(check, rows):  # meme regle que la publication
            touching.setdefault(key, []).append(
                {"check_id": check["check_id"], "result": check["result"],
                 "affects_publication": check.get("affects_publication", True)})
    findings: dict[tuple, list] = {}
    for check in checks:
        if check["check_id"] == "C3_input_quality_findings":
            for ref in check["affected_rows"]:
                findings.setdefault((ref["kpi_id"], ref["iso3"], int(ref["year"])), []).append(ref)
    notices = {}
    for issue in quality.get("issues") or []:
        notices.setdefault(issue.get("source"), []).append(
            {"code": issue.get("code"), "severity": issue.get("severity"), "message": issue.get("message")})
    by_key = {(r["kpi_id"], r["iso3"], int(r["year"])): r for r in rows}

    records = []
    for key in sorted(by_key):
        row = by_key[key]
        kpi_id, iso3, year = key
        kpi = catalog["kpis"].get(kpi_id) or {}
        w = kpi.get("warehouse") or {}
        formula = (kpi.get("formula") or {}).get("from_fact", "")
        record: dict[str, Any] = {
            "kpi_id": kpi_id, "kpi_name": kpi.get("name"), "iso3": iso3,
            "country": "Moyenne des pairs" if iso3 == PEERS_ISO3 else country_names.get(iso3, iso3),
            "year": year, "value": row["value"], "unit": row["unit"],
            "availability_status": row.get("availability_status"), "reason": row.get("reason"),
            "definition": kpi.get("definition"), "definition_status": row.get("definition_status"),
            "catalog_version": catalog.get("catalog_version"), "catalog_sha256": catalog_sha256,
            "definition_version": kpi.get("definition_version"), "formula": formula,
            "transformation": _transformation(formula) if iso3 != PEERS_ISO3 else
            "moyenne simple des pairs disponibles (non ponderee)",
            "transformation_en": _transformation(formula, "en") if iso3 != PEERS_ISO3 else
            "simple (unweighted) mean of available peers",
            "snapshot_id": snapshot_id, "inputs": [], "dependencies": [],
            "quality_findings": findings.get(key, []),
            "source_notices": notices.get(w.get("source"), []),
            "review_reasons": list(row.get("review_reasons") or []),
            "checks": touching.get(key, []),
            "publication_status": decisions.get(key, row.get("publication_status")),
        }
        if iso3 == PEERS_ISO3:
            record["aggregation_method"] = row.get("aggregation_method")
            record["peer_status"] = row.get("peer_status")
            record["dependencies"] = [
                {"label": peer, "kpi_id": kpi_id, "iso3": peer, "year": year,
                 "country": country_names.get(peer, peer),
                 "value": (recomputed.get((kpi_id, peer, year)) or {}).get("value"),
                 "included": peer in (row.get("peers_included") or [])}
                for peer in list(row.get("peers_included") or []) + list(row.get("missing_peers") or [])]
        else:
            exp = recomputed.get(key) or {"inputs": []}
            roles = (["premier terme", "terme soustrait"] if len(exp["inputs"]) == 2 else ["valeur"])
            for role, item in zip(roles, exp["inputs"]):
                raw = raw_lookups.get(tuple(item["fact_key"])) or {}
                source = item["fact_key"][2]
                meta = source_meta.get(source) or {}
                record["inputs"].append({
                    "role": role, "fact_key": list(item["fact_key"]), "fact_value": item["value"],
                    "fact_unit": item["unit"], "status": item["status"],
                    "raw": {"source": source, "file": meta.get("file") or raw.get("file"),
                            "sha256": meta.get("sha256"), "snapshot_id": snapshot_id,
                            "record_key": raw.get("key"), "column": raw.get("column"),
                            "raw_value_text": raw.get("raw_text")},
                })
            if len(record["inputs"]) == 2:  # ecart : les deux sous-groupes en %
                record["dependencies"] = [
                    {"label": inp["fact_key"][5], "dimension": inp["fact_key"][4],
                     "value": None if inp["fact_value"] is None else 100 * inp["fact_value"], "unit": "percent"}
                    for inp in record["inputs"]]
            elif kpi.get("dependencies"):
                for dep in kpi["dependencies"]:
                    dep_row = by_key.get((dep, iso3, year)) or {}
                    record["dependencies"].append({"label": dep, "kpi_id": dep, "iso3": iso3, "year": year,
                                                   "value": dep_row.get("value"), "unit": dep_row.get("unit")})
        records.append(record)
    return records


# --------------------------------------------------------------------------- variations
def explain_change(left: Mapping[str, Any], right: Mapping[str, Any], min_change_pp: float = 2.0) -> dict[str, Any]:
    """Decompose right - left : ecart = variation du 1er sous-groupe - variation du
    second ; PEERS = contribution de chaque pair (variation / nombre de pairs)."""
    kind = "years" if (left["kpi_id"], left["iso3"]) == (right["kpi_id"], right["iso3"]) else "countries"
    out: dict[str, Any] = {
        "kind": kind, "kpi_id": right["kpi_id"], "unit": right["unit"],
        "left": {"iso3": left["iso3"], "year": left["year"], "value": left["value"]},
        "right": {"iso3": right["iso3"], "year": right["year"], "value": right["value"]},
        "delta": None, "delta_unit": "percentage_points" if right["unit"] in ("percent", "percentage_points")
        else right["unit"], "components": [], "comparable": True, "within_survey_noise": None,
    }
    if left["value"] is None or right["value"] is None:
        out.update(comparable=False, reason="valeur indisponible d'un cote")
        return out
    out["delta"] = right["value"] - left["value"]
    if left["iso3"] == PEERS_ISO3 and right["iso3"] == PEERS_ISO3:
        left_peers = {d["iso3"]: d["value"] for d in left["dependencies"] if d["included"]}
        right_peers = {d["iso3"]: d["value"] for d in right["dependencies"] if d["included"]}
        if set(left_peers) != set(right_peers):
            out.update(comparable=False, reason="ensembles de pairs differents : "
                       f"{sorted(left_peers)} / {sorted(right_peers)}")
        n = len(right_peers)
        out["components"] = [
            {"label": peer, "left": left_peers.get(peer), "right": right_peers[peer],
             "delta": None if peer not in left_peers else right_peers[peer] - left_peers[peer],
             "contribution": None if peer not in left_peers or not n else (right_peers[peer] - left_peers[peer]) / n}
            for peer in sorted(right_peers)]
    elif len(left.get("dependencies") or []) == 1 and len(right.get("dependencies") or []) == 1:
        l, r = left["dependencies"][0], right["dependencies"][0]
        if l["value"] is not None and r["value"] is not None:
            out["components"] = [{"label": r["label"], "left": l["value"], "right": r["value"],
                                  "delta": r["value"] - l["value"]}]
    elif len(left.get("dependencies") or []) == 2 and len(right.get("dependencies") or []) == 2:
        signs = (1, -1)
        out["components"] = [
            {"label": r["label"], "left": l["value"], "right": r["value"], "delta": r["value"] - l["value"],
             "contribution": sign * (r["value"] - l["value"])}
            for sign, l, r in zip(signs, left["dependencies"], right["dependencies"])]
    if kind == "years" and right["unit"] in ("percent", "percentage_points") \
            and (left.get("inputs") or [{}])[0].get("raw", {}).get("source", "findex") == "findex":
        out["within_survey_noise"] = abs(out["delta"]) < min_change_pp
        out["min_meaningful_change_pp"] = min_change_pp
    return out


# --------------------------------------------------------------------------- journal
def decision_log(*, snapshot: Mapping[str, Any] | None, lineage: Mapping[str, Any],
                 quality: Mapping[str, Any], aggregates: list[str], kpi_rows: list[dict[str, Any]],
                 audit_counts: Mapping[str, int] | None = None, verdict: str | None = None) -> list[dict]:
    """Ce qui a ete decide a chaque etape, et pourquoi (a partir des artefacts du run)."""
    log = []
    inputs = lineage.get("inputs") or {}
    log.append({"step": "collector", "decision": f"{len(inputs)} source(s) collectee(s) et hachee(s)",
                "reasons": [f"{name} : sha256 {str(meta.get('sha256'))[:12]}, {meta.get('rows')} lignes"
                            for name, meta in sorted(inputs.items())]})
    snapshot = snapshot or {}
    status = snapshot.get("status")
    text = {"new": "nouvelles donnees : nouvelle version", "published": "nouvelle version publiee",
            "rebuild": "reconstruction depuis la version publiee", "pending": "version candidate"}.get(
        status, f"statut {status}")
    log.append({"step": "snapshot", "decision": f"{snapshot.get('snapshot_id')} ({text})",
                "reasons": ["empreinte de contenu insensible a l'ordre des lignes comparee a la version publiee"]})
    issues = quality.get("issues") or []
    log.append({"step": "quality",
                "decision": f"gate {'PASS' if quality.get('passed') else 'FAIL'}, score {quality.get('overall_score')}",
                "reasons": [f"{i.get('source')} {i.get('code')} ({i.get('severity')}) : {i.get('message')}"
                            for i in issues]
                + [f"{len(quality.get('diagnostics') or [])} diagnostic(s) de plausibilite (revue, sans effet sur le score)"]})
    rejected = lineage.get("rejected") or {}
    period = lineage.get("period") or {}
    log.append({"step": "etl",
                "decision": f"annees {period.get('min_year')}-{period.get('max_year')} conservees",
                "reasons": [f"{source} : {count} ligne(s) rejetee(s) ({reason})"
                            for source, reasons in sorted(rejected.items()) for reason, count in sorted(reasons.items())]
                + [f"{len(aggregates)} agregat(s) regionaux/mondiaux conserves dans country_dim mais exclus "
                   "des KPI (is_aggregate = true)"]})
    available = sum(r["value"] is not None for r in kpi_rows)
    log.append({"step": "semantic_kpi", "decision": f"{len(kpi_rows)} valeurs KPI, {available} disponibles",
                "reasons": ["valeurs absentes conservees en NULL (jamais 0, ni interpolees)"]})
    if verdict:
        log.append({"step": "auditor", "decision": f"verdict {verdict}",
                    "reasons": [f"{audit_counts.get(k, 0)} {k}" for k in ("pass", "warn", "fail")]
                    if audit_counts else []})
    return log


__all__ = ["build_explanations", "decision_log", "explain_change"]
