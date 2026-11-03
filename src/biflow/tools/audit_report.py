"""Rapport d'audit (JSON + Markdown en francais) a partir de la sortie de l'Auditor."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

VERDICT_LABELS = {"pass": "CONFORME", "pass_with_warnings": "CONFORME AVEC AVERTISSEMENTS", "fail": "NON CONFORME"}
RESULT_LABELS = {"pass": "OK", "warn": "AVERT.", "fail": "ECHEC"}


def build_report(audit: Mapping[str, Any], decisions: Mapping[tuple, str], timing_s: float) -> dict[str, Any]:
    """Rapport JSON : verdict, controles, avertissements, publication, journal, exemples."""
    checks = audit["checks"]
    blocked = sorted([{"kpi_id": k, "iso3": i, "year": y} for (k, i, y), s in decisions.items() if s == "blocked"],
                     key=lambda r: (r["kpi_id"], r["iso3"], r["year"]))
    return {
        "run_id": audit.get("run_id"),
        "snapshot_id": audit.get("snapshot_id"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": audit["verdict"],
        "counts": audit["counts"],
        "rows": audit.get("rows"),
        "checks": checks,
        "caveats": [c for c in checks if c["category"] == "caveat" and c["result"] != "pass"],
        "publication": {"by_status": audit.get("publication"), "blocked_rows": blocked},
        "decision_log": audit.get("decision_log") or [],
        "examples": [{key: example[key] for key in ("title", "kpi_id", "iso3", "year", "compare", "change",
                                                    "text", "origin", "llm")}
                     for example in audit.get("examples") or []],
        "insight_audit": audit.get("insight_audit"),
        "timing_s": round(timing_s, 3),
    }


def render_report(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# Rapport d'audit BIFlow (BI Auditor / XAI)", "",
        f"- Run : `{report['run_id']}` - snapshot `{report['snapshot_id']}` - {report['created_at']}",
        f"- **Verdict : {VERDICT_LABELS.get(report['verdict'], report['verdict'])}** "
        f"({counts['pass']} OK, {counts['warn']} avertissement(s), {counts['fail']} echec(s))",
        f"- Lignes KPI auditees : {report['rows']} ; duree de l'etape : {report['timing_s']} s", "",
        "## Controles", "",
        "| Controle | Categorie | Resultat | Detail | Lignes |", "|---|---|---|---|---|",
    ]
    for check in report["checks"]:
        detail = str(check["detail"]).replace("|", "/")
        lines.append(f"| {check['check_id']} | {check['category']} | {RESULT_LABELS[check['result']]} | "
                     f"{detail} | {len(check['affected_rows'])} |")
    lines += ["", "## Avertissements (n'empechent pas la publication)", ""]
    if not report["caveats"]:
        lines.append("Aucun.")
    for caveat in report["caveats"]:
        sample = ", ".join(f"{r.get('kpi_id')}/{r.get('iso3')}/{r.get('year')}" for r in caveat["affected_rows"][:6])
        more = len(caveat["affected_rows"]) - 6
        lines.append(f"- **{caveat['check_id']}** : {caveat['detail']}"
                     + (f" Exemples : {sample}" + (f" (+{more})" if more > 0 else "") + "." if sample else ""))
    publication = report["publication"]
    lines += ["", "## Decisions de publication", "",
              "| Statut | Lignes |", "|---|---|"]
    lines += [f"| {status} | {count} |" for status, count in (publication["by_status"] or {}).items()]
    if publication["blocked_rows"]:
        lines += ["", "Lignes bloquees : " + ", ".join(
            f"{r['kpi_id']}/{r['iso3']}/{r['year']}" for r in publication["blocked_rows"][:30])
            + (" ..." if len(publication["blocked_rows"]) > 30 else "")]
    lines += ["", "## Journal des decisions du pipeline", ""]
    for entry in report["decision_log"]:
        lines.append(f"- **{entry['step']}** : {entry['decision']}")
        lines += [f"  - {reason}" for reason in entry.get("reasons") or []]
    lines += ["", "## Exemples d'explications", ""]
    for example in report["examples"]:
        origin = example["origin"]["fr"]
        lines += [f"### {example['title']}", "", example["text"]["fr"], "",
                  f"*English* : {example['text']['en']}", "",
                  f"Texte francais : {'reformulation LLM verifiee' if origin == 'llm' else 'gabarit deterministe'}"
                  + (f" (reformulation LLM ecartee : nombres non justifies "
                     f"{example['llm'].get('unsupported_numbers')})"
                     if (example.get("llm") or {}).get("llm_status") == "rejected_ungrounded" else "") + ".", ""]
    if report.get("insight_audit") is not None:
        lines += ["## Insights audites", "", "| Insight | Accepte | Raisons |", "|---|---|---|"]
        lines += [f"| {i['insight_id']} | {'oui' if i['accepted'] else 'non'} | "
                  f"{'; '.join(i['reasons']).replace('|', '/') or '-'} |" for i in report["insight_audit"]]
    route2 = report.get("route2_insight_audit")
    if route2:
        lines += ["", "## Insights de la Route 2 (FinOVA Analyst)", "",
                  f"- Run Route 2 : `{route2.get('run_id')}` ({route2.get('created_at')})",
                  f"- Insights audites : {route2.get('audited')} ; acceptes : {route2.get('accepted')} ; "
                  f"rejetes : {route2.get('rejected')} ; sans fait KPI (non auditables) : "
                  f"{route2.get('not_auditable')}", ""]
        rejected = [r for r in route2.get("results") or [] if not r.get("accepted")]
        if rejected:
            lines += ["| Insight | Raisons |", "|---|---|"]
            lines += [f"| {r['insight_id']} | {'; '.join(r['reasons']).replace('|', '/')} |" for r in rejected]
    return "\n".join(lines) + "\n"


def record_insight_audit(audit_dir: Path, block: Mapping[str, Any]) -> dict[str, str] | None:
    """Ajoute l'audit des insights de la Route 2 au rapport d'audit existant
    (aucun rapport : rien n'est ecrit, None)."""
    path = Path(audit_dir) / "audit_report.json"
    if not path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    report["route2_insight_audit"] = dict(block)
    return write_report(report, Path(audit_dir))


def write_report(report: Mapping[str, Any], audit_dir: Path) -> dict[str, str]:
    audit_dir.mkdir(parents=True, exist_ok=True)
    paths = {"json": audit_dir / "audit_report.json", "markdown": audit_dir / "audit_report.md"}
    for kind, path in paths.items():
        tmp = path.with_name(f".{path.name}.tmp")
        content = (json.dumps(report, indent=2, ensure_ascii=False, default=str) if kind == "json"
                   else render_report(report))
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    return {kind: str(path) for kind, path in paths.items()}


__all__ = ["build_report", "record_insight_audit", "render_report", "write_report"]
