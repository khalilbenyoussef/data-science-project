"""Deterministic BI Analyst agent for Route 2.

Consumes the Semantic & KPI contracts through ``AnalysisService`` and turns the
resulting dataset into evidence-backed findings. The LLM is never called: every
number and every statement is derived from the deterministic dataset.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from biflow.agents.base import BaseAgent
from biflow.config import resolve
from biflow.tools.analysis import AnalysisRequest, AnalysisService
from biflow.tools.kpi import DEFAULT_CATALOG
from biflow.utils.io import load_json, save_json

SEVERITY_ORDER = {"review": 0, "warning": 1, "info": 2}
DIGITAL_KPI = "digital_payment_rate"
ACCOUNT_KPI = "account_ownership"

LIMITATIONS = [
    "Les valeurs proviennent uniquement des contrats KPI déterministes ; aucun chiffre n'est recalculé, lissé ou extrapolé.",
    "Le statut de publication reste « non évalué » : ce rapport ne vaut pas approbation.",
    "Les observations marquées « revue requise » conservent leurs motifs et ne sont pas certifiées.",
    "Les définitions provisoires (épargne, emprunt) ne sont pas vérifiées.",
    "Les comparaisons sont des différences absolues (droite − gauche), jamais des taux de croissance.",
    "Le paiement numérique et la détention de compte sont deux mesures distinctes : aucun écart n'est interprété comme une causalité.",
]


def limitations(dataset: dict[str, Any]) -> list[str]:
    """LIMITATIONS, sans les phrases que le backend a rendues fausses : statut de
    publication evalue par l'Auditor, aucune definition provisoire au catalogue."""
    provisional = any(item.get("verification_status") == "provisional"
                      for item in (dataset.get("scope") or {}).get("kpis") or [])
    evaluated = dataset.get("publication_status", "not_evaluated") != "not_evaluated"
    return [text for text in LIMITATIONS
            if not (evaluated and text.startswith("Le statut de publication reste"))
            and not (not provisional and text.startswith("Les définitions provisoires"))]


def format_value(value: float | None, unit: str) -> str:
    if value is None:
        return "indisponible"
    if unit == "percent":
        return f"{value:.2f} %"
    if unit == "per_100k_adults":
        return f"{value:.2f} / 100k adultes"
    if unit == "percentage_points":
        return f"{value:+.2f} pts de %"
    return f"{value:.2f} {unit}"


def _label(value: Any) -> str:
    return "indisponible" if value is None else str(value)


def build_findings(
    dataset: dict[str, Any],
    *,
    epsilon: float = 0.01,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    kpis = {item["kpi_id"]: item for item in dataset["scope"]["kpis"]}
    observations = dataset["observations"]
    findings: list[dict[str, Any]] = []

    def add(
        code: str,
        severity: str,
        statement: str,
        evidence_ids: list[str],
        **extra: Any,
    ) -> None:
        evidence = [item for item in dict.fromkeys(evidence_ids) if item]
        if not evidence:
            raise ValueError(f"finding without evidence: {code}")
        findings.append({
            "code": code,
            "severity": severity,
            "statement": statement,
            "evidence_ids": evidence,
            **extra,
        })

    # ------------------------------------------------------------ observations
    for row in observations:
        name = kpis[row["kpi_id"]]["name"]
        if row["value"] is None:
            add(
                "unavailable", "warning",
                f"{name} indisponible pour {row['iso3']} "
                f"({row['selection']}, motif : {row['reason']}).",
                [row["evidence_id"]],
                kpi_id=row["kpi_id"], iso3=row["iso3"], year=row["year"],
            )
        elif row["requires_review"]:
            reasons = ", ".join(row["review_reasons"][:3]) or "motif non détaillé"
            add(
                "requires_review", "review",
                f"{name} pour {row['iso3']} en {row['year']} : revue requise ({reasons}).",
                [row["evidence_id"]],
                kpi_id=row["kpi_id"], iso3=row["iso3"], year=row["year"],
            )

    # -------------------------------------------------------- provisional KPIs
    for kpi_id, meta in kpis.items():
        if meta["verification_status"] != "provisional":
            continue
        evidence = [
            row["evidence_id"] for row in observations if row["kpi_id"] == kpi_id
        ][:3]
        if evidence:
            add(
                "provisional_definition", "review",
                f"{meta['name']} repose sur une définition provisoire : "
                "les valeurs ne doivent pas être présentées comme vérifiées.",
                evidence, kpi_id=kpi_id,
            )

    # ------------------------------------------------------------------ trends
    for trend in dataset["trends"]:
        name = kpis[trend["kpi_id"]]["name"]
        if trend["status"] != "complete":
            evidence = trend["evidence_ids"] or [
                row["evidence_id"] for row in observations
                if row["kpi_id"] == trend["kpi_id"] and row["iso3"] == trend["iso3"]
            ]
            add(
                "trend_insufficient", "warning",
                f"Tendance non calculable pour {name} ({trend['iso3']}) : "
                "moins de deux observations disponibles.",
                evidence, kpi_id=trend["kpi_id"], iso3=trend["iso3"],
            )
            continue
        difference = trend["difference"]
        code = "trend_stable"
        if difference > epsilon:
            code = "trend_up"
        elif difference < -epsilon:
            code = "trend_down"
        add(
            code, "info",
            f"{name} pour {trend['iso3']} : {trend['from_year']} → {trend['to_year']}, "
            f"variation de {format_value(difference, trend['unit'])} "
            "(première et dernière observation disponibles).",
            trend["evidence_ids"],
            kpi_id=trend["kpi_id"], iso3=trend["iso3"],
            from_year=trend["from_year"], to_year=trend["to_year"],
        )

    # --------------------------------------------------------------- rankings
    for ranking in dataset["rankings"]:
        name = kpis[ranking["kpi_id"]]["name"]
        available = [row for row in ranking["rows"] if row["value"] is not None]
        if ranking["status"] != "complete" or not available:
            evidence = [
                row["evidence_id"] for row in ranking["rows"]
            ] or [
                row["evidence_id"] for row in observations
                if row["kpi_id"] == ranking["kpi_id"]
            ]
            add(
                "ranking_unavailable", "warning",
                f"Classement indisponible pour {name} : aucune année commune "
                "à tous les pays demandés.",
                evidence, kpi_id=ranking["kpi_id"],
            )
            continue
        if len(available) >= 2:
            top, bottom = available[0], available[-1]
            add(
                "highest_value", "info",
                f"En {ranking['year']}, {top['iso3']} présente la valeur la plus élevée "
                f"pour {name} ({format_value(top['value'], top['unit'])}), "
                f"devant {bottom['iso3']} ({format_value(bottom['value'], bottom['unit'])}).",
                [top["evidence_id"], bottom["evidence_id"]],
                kpi_id=ranking["kpi_id"], year=ranking["year"],
            )

    # ----------------------------------------------------------- comparisons
    for comparison in dataset["comparisons"]:
        name = kpis[comparison["kpi_id"]]["name"]
        if comparison["status"] != "complete":
            evidence = [
                row["evidence_id"] for row in observations
                if row["kpi_id"] == comparison["kpi_id"]
            ]
            add(
                "comparison_unavailable", "warning",
                f"Comparaison indisponible pour {name} : aucune année comparable "
                "entre les pays demandés.",
                evidence, kpi_id=comparison["kpi_id"],
            )
            continue
        for row in comparison["rows"]:
            if row["difference"] is None:
                add(
                    "comparison_incomplete", "warning",
                    f"Comparaison incomplète pour {name} ({row['iso3']} vs "
                    f"{comparison['reference_iso3']}) : {row['reason'] or 'valeur manquante'}.",
                    [row["evidence_id"]],
                    kpi_id=comparison["kpi_id"], iso3=row["iso3"],
                )
                continue
            add(
                "comparison_gap", "info",
                f"{name} en {comparison['year']} : {row['iso3']} − "
                f"{comparison['reference_iso3']} = "
                f"{format_value(row['difference'], row['unit'])}.",
                [row["evidence_id"]],
                kpi_id=comparison["kpi_id"], iso3=row["iso3"],
            )

    # -------------------------------------------------------------- coverage
    for coverage in dataset["coverage"]:
        if coverage["unavailable"] == 0:
            continue
        name = kpis[coverage["kpi_id"]]["name"]
        evidence = [
            row["evidence_id"] for row in observations
            if row["kpi_id"] == coverage["kpi_id"] and row["value"] is None
        ]
        add(
            "coverage_gap", "warning",
            f"{coverage['unavailable']} observation(s) sur "
            f"{coverage['selected_observations']} indisponible(s) pour {name}.",
            evidence, kpi_id=coverage["kpi_id"],
        )

    # ------------------------------------------- digital vs account (descriptive)
    if DIGITAL_KPI in kpis and ACCOUNT_KPI in kpis:
        by_key = {(row["kpi_id"], row["iso3"]): row for row in observations}
        for iso3 in dataset["request"]["iso3"]:
            digital = by_key.get((DIGITAL_KPI, iso3))
            account = by_key.get((ACCOUNT_KPI, iso3))
            if not digital or not account:
                continue
            if digital["value"] is None or account["value"] is None:
                continue
            if digital["year"] != account["year"]:
                continue
            gap = account["value"] - digital["value"]
            add(
                "digital_account_gap", "info",
                f"{iso3} en {digital['year']} : détention de compte "
                f"{format_value(account['value'], account['unit'])} contre paiement "
                f"numérique {format_value(digital['value'], digital['unit'])}, "
                f"soit un écart descriptif de {gap:.2f} pts. "
                "Les définitions diffèrent : aucune équivalence ni causalité.",
                [account["evidence_id"], digital["evidence_id"]],
                iso3=iso3, year=digital["year"],
            )

    # ------------------------------------------------- truncate and renumber
    known = (
        {row["evidence_id"] for row in observations}
        | {
            row["evidence_id"]
            for ranking in dataset["rankings"] for row in ranking["rows"]
        }
        | {
            point["evidence_id"]
            for series in dataset.get("series", []) for point in series["points"]
        }
        | {item for trend in dataset["trends"] for item in trend["evidence_ids"]}
        | {trend["trend_id"] for trend in dataset["trends"] if trend["trend_id"]}
        | {
            row["evidence_id"]
            for comparison in dataset["comparisons"] for row in comparison["rows"]
        }
    )
    for finding in findings:
        unknown = set(finding["evidence_ids"]) - known
        if unknown:
            raise ValueError(f"unknown evidence reference: {sorted(unknown)}")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        grouped[finding["code"]].append(finding)
    limited: list[dict[str, Any]] = []
    for code, items in grouped.items():
        limited.extend(items[:top_n])
        if len(items) > top_n:
            limited.append({
                "code": f"{code}_truncated",
                "severity": "info",
                "statement": f"{len(items) - top_n} constat(s) supplémentaire(s) "
                             f"non listés pour le code « {code} ».",
                "evidence_ids": items[top_n]["evidence_ids"],
            })
    limited.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["code"]))
    for index, finding in enumerate(limited, 1):
        finding["id"] = f"F-{index:03d}"
    return limited


def build_report(dataset: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    observations = dataset["observations"]
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        counts[finding["severity"]] += 1
    available = sum(1 for row in observations if row["value"] is not None)
    return {
        "agent": "bi_analyst",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "request": dataset["request"],
        "catalog": dataset["catalog"],
        "scope": dataset["scope"],
        "summary": {
            "kpis": [item["kpi_id"] for item in dataset["scope"]["kpis"]],
            "countries": [item["iso3"] for item in dataset["scope"]["countries"]],
            "mode": dataset["scope"]["mode"],
            "year": dataset["scope"]["year"],
            "selected_observations": len(observations),
            "available": available,
            "unavailable": len(observations) - available,
            "requires_review": sum(1 for row in observations if row["requires_review"]),
            "findings": {"total": len(findings), **counts},
        },
        "findings": findings,
        "coverage": dataset["coverage"],
        "notices": dataset["notices"],
        "provenance": dataset["provenance"],
        "limitations": limitations(dataset),
        "publication_status": dataset.get("publication_status", "not_evaluated"),
    }


def render_markdown(report: dict[str, Any], dataset: dict[str, Any]) -> str:
    kpis = {item["kpi_id"]: item for item in dataset["scope"]["kpis"]}
    countries = {item["iso3"]: item["name"] for item in dataset["scope"]["countries"]}
    scope = report["scope"]
    summary = report["summary"]
    lines = [
        f"# Rapport BI Analyst — {dataset['request'].get('action', 'analyze')}",
        "",
        f"- Pays : {', '.join(f'{code} ({countries.get(code, code)})' for code in summary['countries'])}",
        f"- KPI : {', '.join(kpis[kpi]['name'] for kpi in summary['kpis'])}",
        f"- Mode : {scope['mode']}" + (f" ({scope['year']})" if scope.get("year") else ""),
        f"- Observations : {summary['available']}/{summary['selected_observations']} disponibles, "
        f"{summary['requires_review']} en revue",
        f"- Constats : {summary['findings']['total']} "
        f"(revue {summary['findings']['review']}, alerte {summary['findings']['warning']}, "
        f"info {summary['findings']['info']})",
        "",
        "## Valeurs sélectionnées",
        "",
        "| KPI | Pays | Année | Valeur | Unité | Définition | Revue |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in dataset["observations"]:
        lines.append(
            f"| {kpis[row['kpi_id']]['name']} | {row['iso3']} | {_label(row['year'])} | "
            f"{format_value(row['value'], row['unit'])} | {row['unit']} | "
            f"{row['definition_status']} | {'oui' if row['requires_review'] else 'non'} |"
        )

    lines += ["", "## Tendances", "", "| KPI | Pays | De | À | Variation | Statut |",
              "|---|---|---|---|---|---|"]
    for trend in dataset["trends"]:
        lines.append(
            f"| {kpis[trend['kpi_id']]['name']} | {trend['iso3']} | "
            f"{_label(trend['from_year'])} | {_label(trend['to_year'])} | "
            f"{format_value(trend['difference'], trend['unit'])} | {trend['status']} |"
        )

    lines += ["", "## Classements", ""]
    for ranking in dataset["rankings"]:
        lines.append(f"### {kpis[ranking['kpi_id']]['name']} — {_label(ranking['year'])}")
        if ranking["status"] != "complete":
            lines.append("")
            lines.append("Aucune année commune à tous les pays.")
            lines.append("")
            continue
        lines += ["", "| Rang | Pays | Valeur | Revue |", "|---|---|---|---|"]
        for row in ranking["rows"]:
            lines.append(
                f"| {_label(row['rank'])} | {row['iso3']} | "
                f"{format_value(row['value'], row['unit'])} | "
                f"{'oui' if row['requires_review'] else 'non'} |"
            )
        lines.append("")

    lines += ["## Comparaisons", ""]
    for comparison in dataset["comparisons"]:
        reference = comparison["reference_iso3"]
        lines.append(f"### {kpis[comparison['kpi_id']]['name']} — référence {reference}")
        if comparison["status"] != "complete":
            lines.append("")
            lines.append("Aucune année comparable.")
            lines.append("")
            continue
        lines += ["", f"| Pays | Valeur | Écart vs {reference} | Statut |",
                  "|---|---|---|---|"]
        for row in comparison["rows"]:
            lines.append(
                f"| {row['iso3']} | {format_value(row['value'], row['unit'])} | "
                f"{format_value(row['difference'], row['unit'])} | "
                f"{row['comparison_status']} |"
            )
        lines.append("")

    lines += ["## Constats", ""]
    for finding in report["findings"]:
        lines.append(
            f"- **{finding['id']}** `{finding['code']}` ({finding['severity']}) — "
            f"{finding['statement']} Preuves : {', '.join(finding['evidence_ids'])}."
        )

    lines += ["", "## Avertissements de provenance", ""]
    for notice in dataset["notices"]:
        lines.append(f"- `{notice['code']}` ({notice['severity']}) — {notice['message']}")

    provenance = dataset["provenance"]
    lines += [
        "",
        "## Provenance",
        "",
        f"- Warehouse : `{provenance['warehouse_path']}`",
        f"- SHA-256 warehouse : `{provenance['warehouse_sha256']}`",
        f"- Run lineage : `{_label(provenance['lineage_run_id'])}`",
        f"- Qualité : score {_label(provenance['quality_score'])}, "
        f"gate {'PASS' if provenance['quality_gate_passed'] else _label(provenance['quality_gate_passed'])}",
        f"- Liaison de contenu : {provenance['content_binding']}",
        f"- Catalogue : {dataset['catalog']['version']} ({dataset['catalog']['sha256'][:12]}…)",
        "",
        "## Limites",
        "",
    ]
    lines += [f"- {item}" for item in report["limitations"]]
    lines.append("")
    return "\n".join(lines)


class BiAnalystAgent(BaseAgent):
    """Deterministic analyst; never instantiates an LLM client."""

    name = "bi_analyst"

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        run_id: str | None = None,
        log=None,
        *,
        warehouse_path: str | Path | None = None,
        catalog_path: str | Path = DEFAULT_CATALOG,
        lineage_path: str | Path | None = None,
        quality_report_path: str | Path | None = None,
    ) -> None:
        super().__init__(cfg=cfg, run_id=run_id, log=log)
        self.warehouse_path = warehouse_path
        self.catalog_path = catalog_path
        self.lineage_path = lineage_path
        self.quality_report_path = quality_report_path

    def get_llm(self):
        self.llm_error = "BI Analyst is deterministic and never uses an LLM"
        return None

    def _service(self) -> AnalysisService:
        paths = self.cfg.get("paths") or {}
        warehouse = self.warehouse_path or Path(
            paths.get("processed", "data/processed")
        ) / "warehouse.duckdb"
        lineage = self.lineage_path or Path(warehouse).with_name("lineage.json")
        quality = self.quality_report_path or Path(
            paths.get("quality", "data/quality")
        ) / "quality_report.json"
        return AnalysisService(
            resolve(warehouse), self.catalog_path,
            lineage_path=lineage, quality_report_path=quality,
        )

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        request = AnalysisRequest.model_validate(ctx.get("analysis_request"))
        reports_dir = self.report_path().parent
        dataset_path = reports_dir / "analysis_dataset.json"
        existing = ctx.get("analysis_dataset_path")
        if existing and Path(existing).is_file():
            dataset = load_json(existing)
            dataset_path = Path(existing)
        else:
            dataset = self._service().build(request)
            save_json(dataset, dataset_path)

        analyst_cfg = self.cfg.get("analyst") or {}
        findings = build_findings(
            dataset,
            epsilon=float(analyst_cfg.get("trend_epsilon", 0.01)),
            top_n=request.top_n,
        )
        report = build_report(dataset, findings)
        markdown_path = reports_dir / "bi_analyst.md"
        temporary = markdown_path.with_name(markdown_path.name + ".tmp")
        temporary.write_text(render_markdown(report, dataset), encoding="utf-8")
        temporary.replace(markdown_path)
        warnings = [
            notice["message"] for notice in dataset["notices"]
            if notice["severity"] in {"warning", "review"}
        ]
        return {
            "analysis_report": report,
            "analysis_dataset_path": str(dataset_path),
            "warnings": warnings,
        }


__all__ = ["BiAnalystAgent", "build_findings", "build_report", "render_markdown"]
