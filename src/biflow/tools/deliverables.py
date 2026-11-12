"""Livrables ecrits generes depuis l'etat courant (lecture seule).

Chaque nombre des documents de docs/deliverables/ est lu ici : entrepot DuckDB
(lecture seule), rapport d'audit, rapport qualite, catalogue KPI, rapports de run
(Route 1 et Route 2), spec FinOVA publiee et evaluations enregistrees. Aucune
valeur n'est saisie a la main ni recalculee autrement que par simple comptage.
Une entree absente donne « non disponible », jamais un chiffre invente.

Les memes fonctions servent les rapports PDF de l'API et la frise des agents
de la page « Data & Pipeline » : un seul chemin de lecture pour tous les supports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import duckdb
import yaml

from biflow.config import ROOT, load_config, path_of, resolve
from biflow.tools.audit_text import VERDICTS_FR, check_name, fr_number, insight_faults_note
from biflow.tools.dashboard_spec import COUNTRY_LABELS
from biflow.tools.kpi import DEFAULT_CATALOG, load_catalog

NA = "non disponible"
STATUS_FR = {"success": "réussi", "failed": "échec", "skipped": "ignoré", "on_demand": "à la demande"}
SEVERITY = {"critical": "critiques", "high": "élevées", "medium": "moyennes", "low": "faibles"}
DELIVERABLES_DIR = ROOT / "docs" / "deliverables"
EVALUATION_DIR = "outputs/evaluation"

# Description des agents (texte de conception ; aucun chiffre). L'ordre suit le graphe.
AGENTS: list[dict[str, Any]] = [
    {"id": "collector", "route": "Route 1", "label": "Collector", "module": "biflow.agents.collector",
     "role": "Collecte les sources officielles (Findex, FAS, PIB WDI) et les sources utilisateur confirmées ; "
             "calcule l'empreinte SHA-256 de chaque fichier.",
     "inputs": "config.yaml (sources), API Banque mondiale (PIB), fichiers statiques data/raw/",
     "outputs": "fichiers bruts, empreintes, métadonnées de collecte",
     "tools": "requests (API WDI / SDMX FMI optionnelle), hashlib, pandas"},
    {"id": "snapshot", "route": "Route 1", "label": "Snapshot", "module": "biflow.agents.snapshot",
     "role": "Versionne les fichiers bruts (blobs dédupliqués par SHA-256) ; sans donnée nouvelle, le run s'arrête.",
     "inputs": "fichiers bruts et empreintes du Collector",
     "outputs": "data/snapshots/ (index.json, vN/manifest.json, blobs/)",
     "tools": "SnapshotStore"},
    {"id": "profiler", "route": "Route 1", "label": "Profiler", "module": "biflow.agents.profiler",
     "role": "Profile chaque source : dimensions, valeurs manquantes, types, colonnes de métadonnées, "
             "valeurs atypiques (IsolationForest).",
     "inputs": "fichiers du snapshot", "outputs": "outputs/profiles/ (profils JSON)",
     "tools": "pandas, scikit-learn (IsolationForest)"},
    {"id": "quality", "route": "Route 1", "label": "Quality", "module": "biflow.agents.quality",
     "role": "Contrôle qualité : score par source, gate (seuil configuré), anomalies classées par sévérité, "
             "diagnostics de plausibilité, exclusion des sources utilisateur non conformes.",
     "inputs": "fichiers du snapshot, profils", "outputs": "data/quality/quality_report.json et .md",
     "tools": "pandas, règles de config.yaml (quality)"},
    {"id": "etl", "route": "Route 1", "label": "ETL", "module": "biflow.agents.etl",
     "role": "Harmonise les sources (codes pays ISO3, années, unités) et construit le modèle en étoile.",
     "inputs": "fichiers du snapshot ayant passé le gate",
     "outputs": "data/processed/warehouse.duckdb (fact, country_dim, indicator_dim, country_year, population), "
                "lineage.json", "tools": "pandas, DuckDB, pycountry"},
    {"id": "semantic_kpi", "route": "Route 1", "label": "Semantic & KPI", "module": "biflow.agents.semantic_kpi",
     "role": "Calcule chaque KPI du catalogue pour le pays focus et les pairs, sur chaque année valide ; "
             "attribue un statut de publication.",
     "inputs": "entrepôt (table fact), catalogue KPI", "outputs": "table kpi_values, kpi_values.parquet",
     "tools": "KpiCalculator, catalogue config/kpi_catalog.v1.yaml"},
    {"id": "auditor", "route": "Route 1", "label": "Auditor (BI Auditor / XAI)", "module": "biflow.agents.auditor",
     "role": "Vérification indépendante : recalcul depuis fact sans le code KPI, contrôles de cohérence et de "
             "traçabilité, verdict d'audit, explications par valeur ; décide la publication du snapshot.",
     "inputs": "kpi_values, fact, lineage, rapport qualité, index des snapshots",
     "outputs": "data/audit/audit_report.json et .md, table kpi_explanations",
     "tools": "contrôles A1–A6, B1–B9, C1–C4 (biflow.tools.audit_checks)"},
    {"id": "analyst", "route": "Route 2", "label": "Analyst (FinOVA)", "module": "biflow.agents.analyst",
     "role": "Écrit les constats et la carte XAI à partir des faits exportés ; tout nombre d'une phrase doit "
             "exister dans les faits (verify_numbers).",
     "inputs": "faits de la spec (analysis dataset)", "outputs": "constats par page, carte XAI",
     "tools": "gabarits déterministes, verify_numbers"},
    {"id": "dashboard_spec", "route": "Route 2", "label": "Dashboard spec", "module": "biflow.agents.dashboard",
     "role": "Construit le contrat FinOVA 2.0 validé (pages, métriques, graphiques, faits, avertissements) ; "
             "ne calcule aucun KPI et n'approuve aucune publication.",
     "inputs": "analysis dataset, entrepôt en lecture seule, référence statique",
     "outputs": "finova_spec.json, dashboard_app/public/data/finova.json, historique",
     "tools": "DashboardSpec (pydantic), WarehouseReader"},
    {"id": "ask", "route": "Interface", "label": "Ask Finova", "module": "biflow.agents.ask",
     "role": "Répond aux questions de l'utilisateur sur la vue affichée ; lit les chiffres uniquement via des "
             "outils sur les faits ; chaque nombre de la réponse est contrôlé (grounding).",
     "inputs": "question, faits de la spec du pays et de l'année choisis",
     "outputs": "réponse et faits cités (POST /api/ask)",
     "tools": "outils FactTools, audit_text.grounding, repli déterministe"},
]
ROUTE1 = [a["id"] for a in AGENTS if a["route"] == "Route 1"]
ROUTE2 = ["analyst", "dashboard_spec"]
# Agents sans aucun appel LLM possible (le code n'en fait aucun)
DETERMINISTIC = {"collector", "snapshot", "profiler", "etl", "semantic_kpi", "dashboard_spec"}
LLM_ROLE = {
    "quality": "plan de remédiation rédigé, sans effet sur le score ni le gate",
    "auditor": "reformulation de quelques explications, rejetée si un nombre n'est pas justifié",
    "analyst": "narration optionnelle (analyst.narrate), chiffres vérifiés",
    "ask": "conversation avec outils sur les faits, nombres contrôlés",
}


# ------------------------------------------------------------------ lecture
def _json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _stamp(value: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(value)).timestamp() if value else None
    except ValueError:
        return None


def _run_reports(folder: Path) -> dict[str, Any]:
    reports = {p.stem: _json(p) for p in sorted(folder.glob("*.json"))}
    return {"run_id": folder.name, "dir": folder, "run": reports.pop("run", {}), "agents": reports}


def find_route1_run(reports_dir: Path, run_id: str | None) -> dict[str, Any] | None:
    """Run Route 1 de l'audit courant ; sinon le plus recent qui contient un rapport auditor."""
    if run_id and (reports_dir / run_id / "run.json").is_file():
        return _run_reports(reports_dir / run_id)
    if not reports_dir.is_dir():
        return None
    folders = sorted((p for p in reports_dir.iterdir() if (p / "auditor.json").is_file()),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    return _run_reports(folders[0]) if folders else None


def find_route2_run(reports_dir: Path, run_id: str | None) -> dict[str, Any] | None:
    """Run Route 2 de la spec publiee ; sinon le plus recent qui contient finova_spec.json."""
    if run_id and (reports_dir / run_id / "run.json").is_file():
        return _run_reports(reports_dir / run_id)
    if not reports_dir.is_dir():
        return None
    folders = sorted((p for p in reports_dir.iterdir() if (p / "finova_spec.json").is_file()),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    return _run_reports(folders[0]) if folders else None


def latest_collector(reports_dir: Path) -> dict[str, Any] | None:
    """Dernier rapport du Collector (un run reconstruit depuis un snapshot n'en a pas)."""
    if not reports_dir.is_dir():
        return None
    found = sorted((p / "collector.json" for p in reports_dir.iterdir() if (p / "collector.json").is_file()),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return {"run_id": found[0].parent.name, **_json(found[0])} if found else None


@dataclass
class Context:
    cfg: dict[str, Any]
    generated_at: str
    catalog: dict[str, Any]
    audit: dict[str, Any]
    quality: dict[str, Any]
    spec: dict[str, Any]
    route1: dict[str, Any] | None
    route2: dict[str, Any] | None
    collector: dict[str, Any] | None
    warehouse: Path
    fault_injection: dict[str, Any]
    agents_eval: dict[str, Any]
    baseline: dict[str, Any]
    manual: dict[str, Any]
    ask_live: dict[str, Any]
    paths: dict[str, Path] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return str(self.audit.get("run_id") or (self.route1 or {}).get("run_id") or NA)

    @property
    def snapshot_id(self) -> str:
        return str(self.audit.get("snapshot_id") or self.quality.get("snapshot_id") or NA)

    @property
    def catalog_version(self) -> str:
        return str(self.catalog.get("catalog_version") or NA)

    @property
    def route2_run_id(self) -> str:
        return str(self.spec.get("run_id") or (self.route2 or {}).get("run_id") or NA)

    def official_kpis(self) -> dict[str, Any]:
        return {k: v for k, v in (self.catalog.get("kpis") or {}).items()
                if (v.get("verification") or {}).get("status") != "user_declared"}


def load_context(cfg: Mapping[str, Any] | None = None, *, now: datetime | None = None,
                 catalog_path: str | Path = DEFAULT_CATALOG,
                 evaluation_dir: str | Path = EVALUATION_DIR,
                 manual_path: str | Path | None = None) -> Context:
    cfg = dict(cfg if cfg is not None else load_config())
    paths = cfg.get("paths") or {}
    reports_dir = path_of(cfg, "reports")
    audit_dir = resolve(paths.get("audit", "data/audit"))
    quality_path = resolve(paths.get("quality", "data/quality")) / "quality_report.json"
    warehouse = resolve(paths.get("processed", "data/processed")) / "warehouse.duckdb"
    spec_path = resolve((cfg.get("dashboard") or {}).get("spec_output", "dashboard_app/public/data/finova.json"))
    eval_dir = resolve(evaluation_dir)
    manual = resolve(manual_path) if manual_path else DELIVERABLES_DIR / "manual_baseline.yaml"
    audit = _json(audit_dir / "audit_report.json")
    spec = _json(spec_path)
    return Context(
        cfg=cfg,
        generated_at=(now or datetime.now()).isoformat(timespec="seconds"),
        catalog=load_catalog(catalog_path),
        audit=audit,
        quality=_json(quality_path),
        spec=spec,
        route1=find_route1_run(reports_dir, audit.get("run_id")),
        route2=find_route2_run(reports_dir, spec.get("run_id")),
        collector=latest_collector(reports_dir),
        warehouse=warehouse,
        fault_injection=_json(audit_dir / "evaluation.json"),
        agents_eval=_json(eval_dir / "agents.json"),
        baseline=_json(eval_dir / "baseline.json"),
        manual=_yaml(manual),
        ask_live=_json(eval_dir / "ask_live.json"),
        paths={"reports": reports_dir, "audit": audit_dir, "quality": quality_path, "spec": spec_path,
               "evaluation": eval_dir, "manual": manual},
    )


def warehouse_counts(ctx: Context) -> dict[str, Any]:
    """Comptages simples de l'entrepot (lecture seule) ; vide si indisponible."""
    if not ctx.warehouse.is_file():
        return {}
    try:
        with duckdb.connect(str(ctx.warehouse), read_only=True) as con:
            fact = con.execute("SELECT count(*), count(DISTINCT iso3) FROM fact").fetchone()
            by_source = dict(con.execute("SELECT source, count(*) FROM fact GROUP BY 1 ORDER BY 1").fetchall())
            kpi = con.execute("SELECT count(*), count(DISTINCT kpi_id) FROM kpi_values").fetchone()
    except duckdb.Error:
        return {}
    return {"fact_rows": int(fact[0]), "countries": int(fact[1]),
            "by_source": {k: int(v) for k, v in by_source.items()},
            "kpi_rows": int(kpi[0]), "kpi_ids": int(kpi[1])}


# ------------------------------------------------------------------ format
def fmt_int(value: Any) -> str:
    return f"{int(value):,}".replace(",", "\u202f") if isinstance(value, (int, float)) else NA


def fmt_num(value: Any, decimals: int = 1) -> str:
    if not isinstance(value, (int, float)):
        return NA
    return fr_number(float(value), decimals)


def fmt_s(value: Any) -> str:
    return f"{fr_number(float(value), 2)} s" if isinstance(value, (int, float)) else NA


def md_cell(value: Any) -> str:
    return str(value if value not in (None, "") else NA).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: Iterable[Iterable[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(md_cell(c) for c in row) + " |" for row in rows]
    return lines


def header(ctx: Context, title: str, sources: Iterable[str]) -> list[str]:
    return [
        f"# {title}", "",
        f"- **Généré le** : {ctx.generated_at}",
        f"- **Run audité (Route 1)** : `{ctx.run_id}`",
        f"- **Snapshot** : `{ctx.snapshot_id}`",
        f"- **Version du catalogue KPI** : {ctx.catalog_version}",
        f"- **Run Route 2 (spec publiée)** : `{ctx.route2_run_id}`",
        f"- **Sources lues** : {', '.join(f'`{s}`' for s in sources)}",
        "- Document généré par `scripts/build_deliverables.py` : ne pas modifier à la main.",
        "",
    ]


# ------------------------------------------------------------------ agents
def llm_mode(agent_id: str, cfg: Mapping[str, Any]) -> str:
    """« déterministe » ou « LLM optionnel (...) » selon le code et config.yaml."""
    llm = cfg.get("llm") or {}
    if agent_id in DETERMINISTIC or agent_id in (llm.get("disabled_agents") or []):
        return "déterministe"
    if agent_id == "analyst" and not (cfg.get("analyst") or {}).get("narrate"):
        return "déterministe (narration LLM désactivée : analyst.narrate = false)"
    if not llm.get("enabled", True) or not (llm.get("routing") or {}).get(agent_id):
        return "déterministe (aucun LLM configuré)"
    providers = " → ".join((llm.get("routing") or {}).get(agent_id) or [])
    return f"déterministe + LLM optionnel ({LLM_ROLE.get(agent_id, 'assistance')} ; {providers})"


def llm_measured(report: Mapping[str, Any] | None) -> str:
    usage = (report or {}).get("llm_usage") or {}
    if not report:
        return NA
    if not usage:
        return "0 appel"
    calls = usage.get("calls", usage.get("requests"))
    tokens = usage.get("total_tokens") or (
        (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)) or None
    parts = [f"{fmt_int(calls)} appel(s)" if calls is not None else None,
             f"{fmt_int(tokens)} jetons" if tokens else None]
    return ", ".join(p for p in parts if p) or json.dumps(usage, ensure_ascii=False)


def _key_output(agent_id: str, report: Mapping[str, Any], ctx: Context, counts: Mapping[str, Any]) -> dict[str, Any]:
    """(rows_in, rows_out, texte de la sortie cle) pour un agent, lus dans son rapport."""
    out = (report or {}).get("outputs") or {}
    run = (ctx.route1 or {}).get("run") or {}
    profiles = run.get("profiles") or {}
    raw_rows = sum(int(p.get("rows") or 0) for p in profiles.values()) or None
    if agent_id == "collector":
        meta = (((ctx.route1 or {}).get("agents") or {}).get("snapshot") or {}).get("outputs", {}).get("raw_meta") or {}
        return {"rows_out": raw_rows,
                "text": f"{len(out.get('raw_paths') or {}) or len(meta)} source(s) collectée(s)"}
    if agent_id == "snapshot":
        snap = out.get("snapshot") or {}
        return {"rows_out": raw_rows, "text": f"snapshot {snap.get('snapshot_id', NA)} ({snap.get('status', NA)})"}
    if agent_id == "profiler":
        prof = out.get("profiles") or profiles
        text = " ; ".join(f"{name} {fmt_int(p.get('rows'))} × {p.get('cols')}" for name, p in prof.items())
        return {"rows_in": raw_rows, "rows_out": raw_rows, "text": text or NA}
    if agent_id == "quality":
        q = out.get("quality") or {}
        score = q.get("overall_score", ctx.quality.get("overall_score"))
        passed = q.get("passed", ctx.quality.get("passed"))
        return {"rows_in": raw_rows, "score": score, "gate": passed,
                "text": f"score {fmt_num(score, 3)}, gate {'réussi' if passed else 'échoué' if passed is False else NA}"}
    if agent_id == "etl":
        return {"rows_in": raw_rows, "rows_out": counts.get("fact_rows"),
                "text": f"{fmt_int(counts.get('fact_rows'))} lignes fact, {fmt_int(counts.get('countries'))} pays"}
    if agent_id == "semantic_kpi":
        s = out.get("kpi_summary") or {}
        return {"rows_in": counts.get("fact_rows"), "rows_out": s.get("rows"),
                "text": f"{s.get('kpis', NA)} KPI, {fmt_int(s.get('rows'))} lignes kpi_values "
                        f"({fmt_int(s.get('available'))} disponibles, {fmt_int(s.get('requires_review'))} avec revue)"}
    if agent_id == "auditor":
        a = out.get("audit") or ctx.audit
        c = a.get("counts") or {}
        return {"rows_in": a.get("rows"), "verdict": a.get("verdict"),
                "checks": c, "text": f"verdict {a.get('verdict', NA)} ({c.get('pass', NA)} réussis, "
                                     f"{c.get('warn', NA)} avertissements, {c.get('fail', NA)} échecs)"}
    if agent_id == "analyst":
        s = out.get("analyst_summary") or {}
        return {"rows_in": s.get("facts"), "rows_out": s.get("insights"),
                "text": f"{s.get('insights', NA)} constats sur {s.get('facts', NA)} faits, carte XAI "
                        f"{'oui' if s.get('xai') else 'non'}"}
    if agent_id == "dashboard_spec":
        s = out.get("dashboard_spec_summary") or {}
        return {"rows_out": s.get("facts"),
                "text": f"{s.get('pages', NA)} pages, {s.get('facts', NA)} faits, publication "
                        f"{s.get('publication_status', NA)}"}
    return {"text": NA}


def agent_summaries(ctx: Context, *, collector_fallback: bool = True) -> list[dict[str, Any]]:
    """Un enregistrement par agent : role, mode LLM, statut, duree, sortie cle (dernier run)."""
    counts = warehouse_counts(ctx)
    out = []
    for agent in AGENTS:
        aid = agent["id"]
        if aid in ROUTE1:
            run = ctx.route1 or {}
            report = (run.get("agents") or {}).get(aid)
            run_id = run.get("run_id")
            note = None
            if aid == "collector" and report is None and ctx.collector and collector_fallback:
                report, run_id = ctx.collector, ctx.collector.get("run_id")
                note = "run courant reconstruit depuis le snapshot publié : dernier Collector exécuté"
        elif aid in ROUTE2:
            run = ctx.route2 or {}
            report, run_id, note = (run.get("agents") or {}).get(aid), run.get("run_id"), None
        else:
            report, run_id, note = None, None, "à la demande (POST /api/ask), aucun rapport de run"
        key = _key_output(aid, report or {}, ctx, counts) if report else {"text": NA}
        status = (report or {}).get("status") if report else None
        if aid == "ask":
            status, key = "on_demand", {"text": "réponses à la demande, nombres contrôlés contre les faits"}
        out.append({
            **{k: agent[k] for k in ("id", "route", "label", "role", "inputs", "outputs", "tools", "module")},
            "llm_mode": llm_mode(aid, ctx.cfg),
            "llm_measured": llm_measured(report) if report else NA,
            "llm_usage": (report or {}).get("llm_usage") if report else None,
            "run_id": run_id, "status": status,
            "started_at": (report or {}).get("started_at"), "duration_s": (report or {}).get("duration_s"),
            "warnings": len((report or {}).get("warnings") or []), "errors": list((report or {}).get("errors") or []),
            "key_output": key.get("text"), "metrics": {k: v for k, v in key.items() if k != "text"},
            "note": note,
        })
    return out


# ------------------------------------------------------------------ mermaid
def mermaid_route1(cfg: Mapping[str, Any]) -> str | None:
    """Graphe Route 1 exporte par LangGraph (structure reelle du graphe compile)."""
    from biflow import graph as pipeline_graph
    if not pipeline_graph.LANGGRAPH_AVAILABLE:
        return None
    return pipeline_graph.build_graph(dict(cfg), "deliverables").get_graph().draw_mermaid()


def mermaid_route2() -> str | None:
    from biflow.route2_graph import build_route2_graph
    built = build_route2_graph(*(lambda state: {},) * 4)
    return built.get_graph().draw_mermaid() if built is not None else None


def _strip_frontmatter(mermaid: str) -> str:
    """Retire l'en-tete YAML de LangGraph (rendu identique, compatible avec plus de lecteurs)."""
    lines = mermaid.strip().splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        lines = lines[end + 1:]
    return "\n".join(line.rstrip() for line in lines)


# ------------------------------------------------------------------ documents
def render_architecture(ctx: Context) -> str:
    agents = agent_summaries(ctx)
    counts = warehouse_counts(ctx)
    lines = header(ctx, "Architecture multi-agents — FinOVA / BIFlow",
                   ["config/config.yaml", "outputs/reports/<run>/*.json", "data/processed/warehouse.duckdb",
                    "graphes LangGraph (biflow.graph, biflow.route2_graph)"])
    lines += [
        "## Vue d'ensemble", "",
        "Deux routes orchestrées par LangGraph, plus un assistant à la demande :", "",
        f"- **Route 1** (`python main.py run`) : {len(ROUTE1)} agents en séquence, de la collecte au verdict "
        "d'audit. Le snapshot publié ne change que si l'audit n'a aucun échec.",
        f"- **Route 2** (`run_route2`) : préparation des faits, puis {len(ROUTE2)} agents en parallèle "
        "(Analyst, Dashboard spec) et fusion dans le contrat FinOVA validé.",
        "- **Ask Finova** (`POST /api/ask`) : questions de l'utilisateur sur la vue affichée, réponses "
        "fondées uniquement sur les faits de la spec.", "",
        "## Agents", "",
    ]
    lines += table(["Agent", "Route", "Rôle", "Entrées", "Sorties", "Outils", "LLM / déterministe"],
                   ([a["label"], a["route"], a["role"], a["inputs"], a["outputs"], a["tools"], a["llm_mode"]]
                    for a in agents))
    lines += ["", "## Dernier run mesuré", "",
              "Durées, statuts et appels LLM lus dans les rapports d'agent (`outputs/reports/<run_id>/<agent>.json`).", ""]
    lines += table(["Agent", "Run", "Statut", "Durée", "Sortie clé", "Appels LLM mesurés"],
                   ([a["label"], f"`{a['run_id']}`" if a["run_id"] else NA, STATUS_FR.get(a["status"], a["status"] or NA),
                     fmt_s(a["duration_s"]), a["key_output"], a["llm_measured"]] for a in agents))
    notes = [f"- {a['label']} : {a['note']}." for a in agents if a["note"]]
    if notes:
        lines += ["", *notes]
    lines += ["", "## Graphe LangGraph", "",
              "Diagrammes exportés depuis les graphes compilés (`get_graph().draw_mermaid()`), pas dessinés à la main. "
              "Les flèches en pointillés sont des arêtes conditionnelles : `snapshot` termine le run sans donnée "
              "nouvelle, `quality` le termine si le gate échoue.", "", "### Route 1", ""]
    route1 = mermaid_route1(ctx.cfg)
    lines += ["```mermaid", _strip_frontmatter(route1), "```"] if route1 else ["LangGraph indisponible : " + NA]
    lines += ["", "### Route 2", ""]
    route2 = mermaid_route2()
    lines += ["```mermaid", _strip_frontmatter(route2), "```"] if route2 else ["LangGraph indisponible : " + NA]
    by_source = counts.get("by_source") or {}
    lines += [
        "", "## Flux de données", "",
        "```mermaid",
        "flowchart LR",
        "  RAW[\"Fichiers bruts<br/>Findex · FAS · PIB · sources utilisateur\"] --> SNAP[\"Snapshot " + ctx.snapshot_id + "\"]",
        "  SNAP --> PROF[Profils] --> QUAL[\"Rapport qualité<br/>score " + fmt_num(ctx.quality.get('overall_score'), 3) + "\"]",
        "  QUAL -->|gate réussi| DW[(\"Entrepôt DuckDB<br/>" + fmt_int(counts.get('fact_rows')) + " lignes fact\")]",
        "  DW --> KPI[(\"kpi_values<br/>" + fmt_int(counts.get('kpi_rows')) + " lignes\")]",
        "  KPI --> AUD[\"Audit<br/>" + str(ctx.audit.get('verdict', NA)) + "\"]",
        "  AUD --> SPEC[\"Spec FinOVA<br/>faits + constats audités\"]",
        "  SPEC --> UI[Interface FinOVA] --> ASK[Ask Finova]",
        "```", "",
        "| Étape | Mesure | Valeur |", "|---|---|---|",
        *[f"| Entrepôt | lignes fact `{src}` | {fmt_int(n)} |" for src, n in by_source.items()],
        f"| Entrepôt | pays | {fmt_int(counts.get('countries'))} |",
        f"| KPI | lignes kpi_values | {fmt_int(counts.get('kpi_rows'))} |",
        f"| KPI | indicateurs distincts | {fmt_int(counts.get('kpi_ids'))} |",
        f"| Audit | lignes auditées | {fmt_int(ctx.audit.get('rows'))} |", "",
        "## Garde-fous", "",
        "- Aucun agent ne modifie une valeur publiée ; l'Auditor décide seul de la publication du snapshot.",
        "- Tout texte (constat, explication, réponse d'Ask Finova) ne peut citer qu'un nombre présent dans les "
        "faits audités ; sinon il est rejeté et remplacé par la version déterministe.",
        "- Le LLM n'est jamais nécessaire : sans clé, chaque agent utilise son repli déterministe.", "",
    ]
    return "\n".join(lines)


def render_quality(ctx: Context) -> str:
    q = ctx.quality
    lines = header(ctx, "Rapport de qualité des données", ["data/quality/quality_report.json",
                                                            "outputs/reports/<run>/quality.json"])
    if not q:
        return "\n".join(lines + [f"Rapport qualité {NA} : lancez `python main.py run`.", ""])
    threshold = (ctx.cfg.get("quality") or {}).get("score_threshold")
    report = ((ctx.route1 or {}).get("agents") or {}).get("quality") or {}
    lines += [
        "## Synthèse", "",
        "| Mesure | Valeur |", "|---|---|",
        f"| Run qualité | `{q.get('run_id', NA)}` ({q.get('created_at', NA)}) |",
        f"| Score global | {fmt_num(q.get('overall_score'), 3)} |",
        f"| Seuil du gate (`quality.score_threshold`) | {fmt_num(threshold, 2)} |",
        f"| Gate | {'réussi' if q.get('passed') else 'échoué'} |",
        *[f"| Anomalies {SEVERITY.get(sev, sev)} | {fmt_int(n)} |" for sev, n in (q.get("issue_counts") or {}).items()],
        f"| Diagnostics (sans effet sur le score) | {fmt_int(len(q.get('diagnostics') or []))} |",
        f"| Durée de l'agent Quality | {fmt_s(report.get('duration_s'))} |", "",
        "## Score et gate par source", "",
    ]
    checks = q.get("checks") or {}
    lines += table(["Source", "Lignes", "Colonnes", "Doublons", "Cellules vides", "Score", "Gate", "Anomalies"],
                   ([name, fmt_int(c.get("rows")), fmt_int(c.get("cols")),
                     fmt_int((c.get("metrics") or {}).get("duplicates")),
                     f"{fmt_num((c.get('metrics') or {}).get('missing_cells_pct'), 2)} %",
                     fmt_num(c.get("score"), 3), "réussi" if c.get("gate") else "échoué",
                     fmt_int(len(c.get("issues") or []))] for name, c in checks.items()))
    issues = q.get("issues") or []
    lines += ["", "## Anomalies par source", ""]
    lines += table(["Source", "Code", "Sévérité", "Message", "Nombre"],
                   ([i.get("source"), f"`{i.get('code')}`", i.get("severity"), i.get("message"),
                     fmt_int(i.get("count")) if i.get("count") is not None else NA] for i in issues)) \
        if issues else ["Aucune anomalie."]
    diags = q.get("diagnostics") or []
    lines += ["", "## Diagnostics", "",
              "Signalements de plausibilité : ils n'entrent ni dans le score ni dans le gate et ne modifient "
              "aucune valeur.", ""]
    lines += table(["Source", "Code", "Pays", "Année", "Indicateur", "Valeur", "Seuil", "Motif"],
                   ([d.get("source"), f"`{d.get('code')}`", d.get("iso3"), d.get("year"), d.get("indicator_code"),
                     fmt_num(d.get("value"), 2),
                     d.get("threshold"), d.get("reason")] for d in diags)) if diags else ["Aucun diagnostic."]
    users = q.get("user_sources") or {}
    excluded = q.get("excluded_sources") or []
    lines += ["", "## Sources utilisateur", ""]
    if users:
        lines += table(["Source", "Score", "Gate", "Anomalies"],
                       ([n, fmt_num(c.get("score"), 3), "réussi" if c.get("gate") else "échoué",
                         fmt_int(len(c.get("issues") or []))] for n, c in users.items()))
    else:
        lines += ["Aucune source utilisateur contrôlée dans ce run."]
    lines += ["", "### Exclusions", ""]
    if excluded:
        lines += table(["Source", "Motif"], ([e.get("source", e) if isinstance(e, dict) else e,
                                             (e.get("reason") or e.get("message")) if isinstance(e, dict) else NA]
                                            for e in excluded))
    else:
        lines += ["Aucune source utilisateur exclue : les sources officielles ne sont jamais exclues par ce mécanisme."]
    plan = q.get("llm_plan") or []
    if plan:
        origin = "rédigé par LLM" if report.get("llm_usage") else "règles déterministes, aucun appel LLM dans ce run"
        lines += ["", "## Plan de remédiation", "", f"Origine : {origin}.", "",
                  *[f"{i}. {s}" for i, s in enumerate(plan, 1)]]
    lines += [""]
    return "\n".join(lines)


def _verification_cell(kpi_id: str, kpi: Mapping[str, Any], stats: Mapping[str, Any], a1_failed: set[str]) -> str:
    ver = kpi.get("verification") or {}
    s = stats.get(kpi_id) or {}
    parts = [f"statut `{ver.get('status', NA)}`",
             "preuves : " + ", ".join(f"`{e}`" for e in ver.get("evidence") or []) if ver.get("evidence") else None,
             f"recalcul A1 : {'écart' if kpi_id in a1_failed else 'conforme'}",
             f"{fmt_int(s.get('rows'))} lignes ({fmt_int(s.get('approved'))} approuvées, "
             f"{fmt_int(s.get('review'))} avec réserve, {fmt_int(s.get('blocked'))} bloquées)" if s else None]
    return " ; ".join(p for p in parts if p)


def kpi_stats(ctx: Context) -> dict[str, dict[str, int]]:
    if not ctx.warehouse.is_file():
        return {}
    try:
        with duckdb.connect(str(ctx.warehouse), read_only=True) as con:
            rows = con.execute(
                "SELECT kpi_id, count(*), count(value), "
                "count(*) FILTER (WHERE publication_status = 'approved'), "
                "count(*) FILTER (WHERE publication_status = 'approved_with_review_note'), "
                "count(*) FILTER (WHERE publication_status = 'blocked') FROM kpi_values GROUP BY 1").fetchall()
    except duckdb.Error:
        return {}
    return {r[0]: {"rows": r[1], "available": r[2], "approved": r[3], "review": r[4], "blocked": r[5]} for r in rows}


def render_kpi_catalog(ctx: Context) -> str:
    kpis = ctx.official_kpis()
    stats = kpi_stats(ctx)
    a1 = next((c for c in ctx.audit.get("checks") or [] if c.get("check_id") == "A1_recomputed_values"), {})
    a1_failed = {r.get("kpi_id") for r in a1.get("affected_rows") or []}
    lines = header(ctx, "Catalogue des KPI", ["config/kpi_catalog.v1.yaml", "table kpi_values",
                                             "data/audit/audit_report.json (A1)"])
    lines += [
        f"{len(kpis)} indicateurs officiels, catalogue `{ctx.catalog.get('catalog_id', NA)}` version "
        f"{ctx.catalog_version} (mis à jour le {ctx.catalog.get('updated_on', NA)}). "
        f"Contrôle A1 de l'audit : {a1.get('result', NA)} — {a1.get('detail', NA)}.", "",
        "## Synthèse", "",
    ]
    lines += table(["Identifiant", "Nom", "Unité", "Source", "Années valides", "Lignes disponibles"],
                   ([f"`{k}`", v.get("name_fr") or v.get("name"), v.get("unit"),
                     f"{(v.get('source') or {}).get('dataset', NA)} `{(v.get('source') or {}).get('indicator', NA)}`",
                     ", ".join(str(y) for y in v.get("valid_years") or []) or NA,
                     f"{fmt_int((stats.get(k) or {}).get('available'))} / {fmt_int((stats.get(k) or {}).get('rows'))}"]
                    for k, v in kpis.items()))
    lines += ["", "## Fiches", ""]
    for k, v in kpis.items():
        den = v.get("denominator") or {}
        formula = v.get("formula") or {}
        src = v.get("source") or {}
        lines += [
            f"### {v.get('name_fr') or v.get('name')} (`{k}`)", "",
            f"- **Définition** : {v.get('definition_fr') or v.get('definition', NA)}",
            f"  <br><sub>Source (EN) : {v.get('definition', NA)}</sub>",
            f"- **Formule** : `{formula.get('from_fact', NA)}` depuis `fact` "
            f"(`{(v.get('warehouse') or {}).get('indicator_code', NA)}`)"
            + (f" ; dépendances : {', '.join(f'`{d}`' for d in v.get('dependencies') or [])}"
               if v.get("dependencies") else ""),
            f"- **Unité** : {v.get('unit', NA)}",
            f"- **Dénominateur** : {v.get('denominator_fr') or NA}",
            f"  <br><sub>Source (EN) : {den.get('population', NA)} ({den.get('basis', NA)})</sub>",
            f"- **Code source** : {src.get('dataset', NA)} `{src.get('indicator', NA)}`"
            + (f" (indicateur officiel `{src['official_indicator']}`)" if src.get("official_indicator") else ""),
            f"- **Années valides** : {', '.join(str(y) for y in v.get('valid_years') or []) or NA}",
            f"- **Vérification** : {_verification_cell(k, v, stats, a1_failed)}",
        ]
        unc = (v.get("verification") or {}).get("uncertainties") or []
        if unc:
            lines += [f"- **Incertitudes déclarées** : {' '.join(unc)}"]
        lines += [""]
    refs = ctx.catalog.get("references") or {}
    if refs:
        lines += ["## Références des preuves", ""]
        lines += table(["Preuve", "Localisation", "Contenu"],
                       ([f"`{rid}`", r.get("locator", NA), r.get("evidence", NA)] for rid, r in refs.items()))
        lines += [""]
    return "\n".join(lines)


def _status_fr(accepted: Any) -> str:
    return "accepté" if accepted is True else "rejeté" if accepted is False else "non auditable"


def scope_recommendations(ctx: Context, iso3: str | None = None, year: int | None = None) -> dict[str, Any]:
    """Pistes du perimetre (pays et annee de la spec publiee par defaut)."""
    from biflow.tools.recommendations import recommendations_for

    iso3 = iso3 or (ctx.spec.get("country") or {}).get("iso3") or (ctx.cfg.get("kpi") or {}).get("focus", "TUN")
    year = int(year or ctx.spec.get("year") or (ctx.cfg.get("dashboard") or {}).get("default_year", 2024))
    return recommendations_for(ctx.warehouse, iso3, year, ctx.official_kpis())


def render_insights(ctx: Context) -> str:
    from biflow.tools.insights import insight_details
    from biflow.tools.recommendations import load_rules

    audit = ctx.audit.get("route2_insight_audit") or {}
    rows = insight_details(ctx.spec, audit, ctx.catalog["kpis"])
    lines = header(ctx, "Constats et pistes de recommandation",
                   ["dashboard_app/public/data/finova.json", "data/audit/audit_report.json (route2_insight_audit)",
                    "table kpi_values", "config/recommendations.yaml"])
    lines += [
        "## Constats audités", "",
        f"Constats du run Route 2 `{audit.get('run_id', NA)}` (audit du {audit.get('created_at', NA)}) : "
        f"{fmt_int(audit.get('audited'))} audités, {fmt_int(audit.get('accepted'))} acceptés, "
        f"{fmt_int(audit.get('rejected'))} rejetés, {fmt_int(audit.get('not_auditable'))} non auditables "
        "(aucun fait KPI derrière la phrase, par exemple une référence statique).", "",
        "Un constat est accepté quand chaque nombre de la phrase est une valeur publiée de `kpi_values`, "
        "une année ou une différence entre deux valeurs citées du même indicateur, au même arrondi.", "",
    ]
    lines += table(["Constat", "Texte", "Statut", "KPI · pays · année cités"],
                   ([f"`{r['insight_id']}`", r.get("statement") or NA, _status_fr(r["accepted"])
                     + (f" ({'; '.join(r['reasons'])})" if r["accepted"] is False else ""),
                     "<br>".join(f"{c['kpi']} · {c['iso3']} · {c['year']}" for c in r["cited"]) or "—"]
                    for r in rows)) if rows else [f"Aucun constat : {NA}."]
    rules = load_rules()
    result = scope_recommendations(ctx)
    lines += [
        "", "## Pistes de recommandation", "",
        f"Périmètre : **{result['country']} ({result['iso3']}), {result['year']}**. Règles déterministes de "
        f"`config/recommendations.yaml` (version {rules.get('version', NA)}), appliquées aux seules lignes "
        f"`kpi_values` au statut {', '.join(f'`{s}`' for s in rules.get('publication_statuses') or [])}. "
        f"{result['rules_checked']} comparaisons évaluées, {len(result['recommendations'])} pistes retenues, "
        f"{len(result['rejected'])} écartées par l'audit des nombres.", "",
        "Chaque piste est une **piste à explorer**, pas une conclusion : elle décrit une association observée "
        "dans les données, jamais une cause.", "",
        "### Règles et seuils", "",
    ]
    lines += table(["Règle", "Condition", "Indicateurs"],
                   ([f"`{r['id']}`", str(r.get("rule_label", "")).format(
                       threshold=r.get("threshold_pct", r.get("threshold_pp"))),
                     ", ".join(f"`{k}`" for k in r["kpis"])] for r in rules["rules"] if "kpis" in r))
    user_rules = [r for r in rules["rules"] if r.get("kind") == "user_vs_official"]
    if user_rules:
        lines += ["", f"La règle `{user_rules[0]['id']}` (vos données de « Mes données » face à l'indicateur "
                  "officiel déclaré comparable) n'est jamais appliquée dans ce document : ses pistes, étiquetées "
                  "« à partir de vos données », ne s'affichent que dans l'application et dans l'annexe facultative "
                  "du PDF des constats."]
    lines += ["", "### Pistes retenues", ""]
    if not result["recommendations"]:
        lines += ["Aucune règle déclenchée pour ce périmètre."]
    for index, rec in enumerate(result["recommendations"], 1):
        lines += [f"{index}. {rec['text']}", "",
                  f"   - Groupe cible : {rec['target_group']}",
                  f"   - Règle : `{rec['rule_id']}` ({rec['rule']})",
                  "   - Sources : " + " ; ".join(
                      f"{e['kpi']} · {e['iso3']} · {e['year']} = {fmt_num(e['value'], 2)} ({e['unit']}, "
                      f"`{e['publication_status']}`)" for e in rec["evidence"]), ""]
    if result["rejected"]:
        lines += ["### Pistes écartées", ""]
        lines += [f"- `{r['id']}` : {'; '.join(r['audit']['reasons'])}" for r in result["rejected"]]
    lines += [""]
    return "\n".join(lines)


def evaluation_freshness(ctx: Context) -> dict[str, Any]:
    """Dates des evaluations enregistrees et avis « resultat anterieur au dernier audit »."""
    audit_time = _stamp(ctx.audit.get("created_at"))
    out = {"audit_created_at": ctx.audit.get("created_at")}
    for key, data in (("fault_injection", ctx.fault_injection), ("agents", ctx.agents_eval),
                      ("baseline", ctx.baseline), ("ask_live", ctx.ask_live)):
        stamp = data.get("created_at") or data.get("run_at")
        when = _stamp(stamp)
        out[key] = {"created_at": stamp, "stale": bool(audit_time and when and when < audit_time)}
    return out


STALE = "résultat antérieur au dernier audit"


def _dated(label: str, info: Mapping[str, Any]) -> str:
    if not info.get("created_at"):
        return f"{label} : {NA}"
    return f"{label} : {info['created_at']}" + (f" — **{STALE}**" if info.get("stale") else "")


def manual_minutes(ctx: Context, kpi_id: str) -> str:
    value = ((ctx.manual.get("minutes_per_kpi") or {}) if isinstance(ctx.manual, dict) else {}).get(kpi_id)
    return f"{fmt_num(value, 1)} min" if isinstance(value, (int, float)) else "non mesuré"


def render_evaluation(ctx: Context) -> str:
    fresh = evaluation_freshness(ctx)
    agents = {a["id"]: a for a in agent_summaries(ctx)}
    lines = header(ctx, "Évaluation des agents et approche de référence",
                   ["outputs/reports/<run>/*.json", "data/audit/evaluation.json", "data/audit/audit_report.json",
                    "outputs/evaluation/agents.json", "outputs/evaluation/ask_live.json",
                    "outputs/evaluation/baseline.json", "docs/deliverables/manual_baseline.yaml"])
    lines += [
        "## Fraîcheur des mesures", "",
        f"- Dernier audit : {ctx.audit.get('created_at', NA)}",
        f"- {_dated('Injection de fautes', fresh['fault_injection'])}",
        f"- {_dated('Évaluation des agents (scripts/evaluate_agents.py)', fresh['agents'])}",
        f"- {_dated('Contrôle en direct d’Ask Finova', fresh['ask_live'])}",
        f"- {_dated('Approche de référence (scripts/baseline_reference.py)', fresh['baseline'])}", "",
        "## Synthèse par agent", "",
    ]
    lines += table(["Agent", "Mode", "Statut", "Durée", "Lignes entrée → sortie", "Sortie clé", "Appels LLM"],
                   ([a["label"], a["llm_mode"].split(" (")[0], STATUS_FR.get(a["status"], a["status"] or NA),
                     fmt_s(a["duration_s"]),
                     f"{fmt_int(a['metrics'].get('rows_in'))} → {fmt_int(a['metrics'].get('rows_out'))}",
                     a["key_output"], a["llm_measured"]] for a in agents.values()))

    def section(aid: str, extra: list[str]) -> list[str]:
        a = agents[aid]
        return ["", f"## {a['label']}", "", f"*{a['role']}*", "",
                f"- Mode : {a['llm_mode']}",
                *([f"- Run : `{a['run_id'] or NA}` — statut {STATUS_FR.get(a['status'], a['status'] or NA)}, "
                   f"durée {fmt_s(a['duration_s'])}, {a['warnings']} avertissement(s), {len(a['errors'])} erreur(s)",
                   f"- Sortie clé : {a['key_output']}", f"- Appels LLM mesurés : {a['llm_measured']}"]
                  if a["status"] != "on_demand" else ["- Exécution : à la demande (`POST /api/ask`), pas de rapport de run"]),
                *extra]

    run = (ctx.route1 or {}).get("run") or {}
    q = ctx.quality
    lines += section("collector", [f"- {a}" for a in [agents["collector"]["note"]] if a])
    lines += section("snapshot", [f"- Snapshot publié après l'audit : `{(run.get('snapshot') or {}).get('snapshot_id', NA)}` "
                                  f"({(run.get('snapshot') or {}).get('status', NA)})"])
    lines += section("profiler", [f"- Lignes profilées : {fmt_int(agents['profiler']['metrics'].get('rows_in'))}"])
    lines += section("quality", [
        f"- Score global {fmt_num(q.get('overall_score'), 3)} (seuil {fmt_num((ctx.cfg.get('quality') or {}).get('score_threshold'), 2)}), "
        f"gate {'réussi' if q.get('passed') else 'échoué'}",
        f"- Anomalies : " + ", ".join(f"{SEVERITY.get(k, k)} {v}" for k, v in (q.get("issue_counts") or {}).items()),
        f"- Diagnostics : {fmt_int(len(q.get('diagnostics') or []))} ; sources utilisateur exclues : "
        f"{fmt_int(len(q.get('excluded_sources') or []))}"])
    lines += section("etl", [f"- Lignes fact par source : " + ", ".join(
        f"{k} {fmt_int(v)}" for k, v in (warehouse_counts(ctx).get("by_source") or {}).items())])
    lines += section("semantic_kpi", [])
    counts = ctx.audit.get("counts") or {}
    publication = (ctx.audit.get("publication") or {}).get("by_status") or {}
    fi = ctx.fault_injection
    lines += section("auditor", [
        f"- Contrôles : {counts.get('pass', NA)} réussis, {counts.get('warn', NA)} avertissements, "
        f"{counts.get('fail', NA)} échecs sur {fmt_int(ctx.audit.get('rows'))} lignes",
        f"- Publication : {fmt_int(publication.get('approved'))} approuvées, "
        f"{fmt_int(publication.get('approved_with_review_note'))} avec réserve, {fmt_int(publication.get('blocked'))} bloquées",
        "", f"### Injection de fautes ({fi.get('detected', NA)}/{fi.get('total', NA)} détectées)", "",
        _dated("Mesure", fresh["fault_injection"]), "",
        *(table(["Faute injectée", "Contrôle attendu", "Détectée", "Verdict"],
                ([f"{i}. {f.get('label')}", f"{check_name(f.get('expected_check'))}<br><sub>`{f.get('expected_check')}`</sub>",
                  "oui" if f.get("detected") else "non", VERDICTS_FR.get(f.get("verdict"), f.get("verdict"))]
                 for i, f in enumerate(fi.get("faults") or [], 1)))
          + ([""] + [insight_faults_note(fi.get("faults") or [])] if insight_faults_note(fi.get("faults") or []) else [])
          if fi else [f"Injection de fautes : {NA}."])])
    insight = ctx.audit.get("route2_insight_audit") or {}
    lines += section("analyst", [
        f"- Audit des constats (run `{insight.get('run_id', NA)}`) : {fmt_int(insight.get('audited'))} audités, "
        f"{fmt_int(insight.get('accepted'))} acceptés, {fmt_int(insight.get('rejected'))} rejetés, "
        f"{fmt_int(insight.get('not_auditable'))} non auditables"])
    lines += section("dashboard_spec", [])
    unit = ctx.agents_eval.get("ask_unit_tests") or {}
    live = ctx.ask_live
    ask_extra = [
        f"- Tests unitaires (LLM simulé), `{unit.get('file', 'tests/test_ask_chat.py')}` : "
        + (f"{unit.get('passed')}/{unit.get('total')} réussis, dont {unit.get('grounding_passed')}/"
           f"{len(unit.get('grounding_tests') or [])} tests de grounding (exécutés le {unit.get('run_at', NA)})"
           if unit.get("total") else "non mesuré")]
    if live.get("status") == "mesuré":
        ask_extra += [
            f"- Contrôle en direct : **{live.get('grounded')}/{live.get('questions')} réponses fondées**, "
            f"{live.get('llm_answers')} rédigées par le LLM (les autres en repli déterministe) ; modèle "
            f"{live.get('model')}, le {live.get('run_at')}.",
            f"- Méthode : {live.get('method', NA)}.", "",
            *table(["Question", "Mode", "Fondée", "Nombres hors faits", "Réponse"],
                   ([r["question"], r["mode"], "oui" if r["grounded"] else "non", ", ".join(r["unknown"]) or "—",
                     (r.get("answer") or "")[:220]] for r in live.get("results") or []))]
    else:
        ask_extra += ["- Contrôle en direct (10 questions fixes, `config/ask_eval_questions.yaml`) : non mesuré "
                      f"({live.get('reason', 'scripts/evaluate_agents.py --ask-live non exécuté')})."]
    lines += section("ask", ask_extra)

    base = ctx.baseline
    lines += ["", "## Approche de référence", "",
              "Recalcul naïf de 4 indicateurs directement depuis les CSV bruts (`scripts/baseline_reference.py`), "
              "comme un analyste le ferait dans un tableur : filtrer le pays et l'année, lire la colonne, multiplier "
              "par 100 ou soustraire deux groupes. Comparaison avec `kpi_values` à la tolérance de l'Auditor.", "",
              _dated("Mesure", fresh["baseline"]), ""]
    if base:
        timing = base.get("timing_s") or {}
        lines += table(["Indicateur", "Valeurs comparées", "Identiques", "Temps Excel (manuel)"],
                       ([f"`{k}`", fmt_int(v.get("compared")), fmt_int(v.get("matched")), manual_minutes(ctx, k)]
                        for k, v in (base.get("by_kpi") or {}).items()))
        semantic, auditor = agents["semantic_kpi"], agents["auditor"]
        lines += ["", *table(["Approche", "Périmètre", "Temps mesuré"], [
            ["Recalcul naïf (pandas)", f"4 indicateurs, {len(base.get('countries') or [])} pays, toutes années",
             fmt_s(timing.get("naive_pandas"))],
            ["Lecture de `kpi_values`", "mêmes valeurs, déjà calculées et auditées", fmt_s(timing.get("kpi_values_read"))],
            ["Agent Semantic & KPI", f"{semantic['key_output']}", fmt_s(semantic["duration_s"])],
            ["Agent Auditor", "recalcul indépendant et contrôles de toutes les lignes", fmt_s(auditor["duration_s"])],
            ["Excel (manuel)", "4 indicateurs", "non mesuré" if not any(
                isinstance(v, (int, float)) for v in (ctx.manual.get("minutes_per_kpi") or {}).values())
             else f"{fmt_num(sum(v for v in ctx.manual['minutes_per_kpi'].values() if isinstance(v, (int, float))), 1)} min"],
        ])]
        lines += ["", f"Résultat : **{base.get('matched')}/{base.get('compared')} valeurs identiques** "
                      f"(tolérance {base.get('tolerance')}), {len(base.get('mismatched') or [])} écart(s), "
                      f"{len(base.get('missing_in_naive') or [])} valeur(s) publiée(s) introuvable(s) dans le calcul naïf. "
                      "Le pipeline ajoute ce que le calcul naïf n'apporte pas : statut de publication, moyenne des "
                      "pairs avec couverture, traçabilité jusqu'au fichier brut et audit indépendant."]
    else:
        lines += [f"Approche de référence : {NA} (lancer `python scripts/baseline_reference.py`)."]
    lines += [""]
    return "\n".join(lines)


SKIPPED_NOTE = "ignoré : aucune donnée nouvelle"
STOPPED = {"no_change": SKIPPED_NOTE, "quality_failed": "ignoré : gate qualité échoué",
           "failed": "non exécuté : run en échec", "audit_failed": "non exécuté : audit en échec"}


def run_timeline(ctx: Context, run_id: str | None = None) -> dict[str, Any]:
    """Frise des agents : dernier run (audit courant + spec publiee) ou un run donne.

    Pour un run donne, un agent sans rapport est « ignoré » (aucune donnee nouvelle,
    gate qualite) ou « non exécuté » ; la Route 2 n'est lue que si le run a abouti.
    KeyError si le run n'existe pas."""
    no_change = False
    if run_id is not None:
        folder = ctx.paths["reports"] / run_id
        if not (folder / "run.json").is_file():
            raise KeyError(run_id)
        selected = _run_reports(folder)
        status = (selected["run"] or {}).get("status")
        no_change = status == "no_change" or ((selected["run"] or {}).get("snapshot") or {}).get("status") == "no_change"
        ctx = Context(**{**ctx.__dict__, "route1": selected,
                         "route2": ctx.route2 if status == "success" else None})
    rows = agent_summaries(ctx, collector_fallback=run_id is None)
    stopped = STOPPED.get("no_change" if no_change else str(((ctx.route1 or {}).get("run") or {}).get("status")))
    for row in rows:
        row["llm"] = row["llm_mode"] != "déterministe" and not row["llm_mode"].startswith("déterministe (")
        if run_id is not None and row["status"] is None and row["id"] != "ask" and stopped:
            row.update(status="skipped", note=stopped, key_output=None)
    run = (ctx.route1 or {}).get("run") or {}
    return {
        "route1_run_id": (ctx.route1 or {}).get("run_id") or ctx.run_id,
        "route2_run_id": (ctx.route2 or {}).get("run_id") if ctx.route2 else None,
        "snapshot_id": (run.get("snapshot") or {}).get("snapshot_id") or ctx.snapshot_id,
        "status": run.get("status"), "no_change": no_change, "finished_at": run.get("finished_at"),
        "agents": [{k: row[k] for k in ("id", "route", "label", "role", "status", "started_at", "duration_s",
                                        "key_output", "llm", "llm_mode", "llm_measured", "note")} for row in rows],
    }


def kpi_value(ctx: Context, kpi_id: str, iso3: str, year: int) -> float | None:
    """Valeur publiee (lecture seule) ; None si absente ou bloquee."""
    if not ctx.warehouse.is_file():
        return None
    try:
        with duckdb.connect(str(ctx.warehouse), read_only=True) as con:
            row = con.execute("SELECT value FROM kpi_values WHERE kpi_id = ? AND iso3 = ? AND year = ? "
                              "AND publication_status <> 'blocked'", [kpi_id, iso3, year]).fetchone()
    except duckdb.Error:
        return None
    return float(row[0]) if row and row[0] is not None else None


def render_demo(ctx: Context) -> str:
    iso3 = (ctx.spec.get("country") or {}).get("iso3") or "TUN"
    year = int(ctx.spec.get("year") or 2024)
    v = lambda k, c=iso3, y=year: kpi_value(ctx, k, c, y)  # noqa: E731
    peers = (ctx.cfg.get("kpi") or {}).get("peers") or []
    agents = {a["id"]: a for a in agent_summaries(ctx)}
    recs = scope_recommendations(ctx, iso3, year)
    first = recs["recommendations"][0] if recs["recommendations"] else None
    barriers = sorted(((v(k), (ctx.catalog["kpis"].get(k) or {}).get("name_fr", k)) for k in ctx.official_kpis()
                       if k.startswith("barrier_")), key=lambda item: -(item[0] or -1))
    top_barrier = barriers[0] if barriers and barriers[0][0] is not None else None
    counts = ctx.audit.get("counts") or {}
    publication = (ctx.audit.get("publication") or {}).get("by_status") or {}
    fi, insight = ctx.fault_injection, ctx.audit.get("route2_insight_audit") or {}
    base, live = ctx.baseline, ctx.ask_live
    total_r1 = sum(a["duration_s"] or 0 for a in agents.values() if a["route"] == "Route 1" and a["id"] != "collector")
    lines = header(ctx, "Script de démonstration (10 minutes)",
                   ["table kpi_values", "data/audit/audit_report.json", "outputs/reports/<run>/*.json",
                    "outputs/evaluation/*.json", "config/recommendations.yaml"])
    lines += [
        "Lancement : `./start.ps1` puis ouvrir l'adresse affichée (ajouter `?demo=1` pour passer l'écran d'accueil). "
        f"Périmètre de la démonstration : **{COUNTRY_LABELS.get(iso3, iso3)}, {year}**. Les chiffres ci-dessous sont lus "
        "dans les données courantes : régénérer ce script après un nouveau run.", "",
        "| Minute | Écran | Ce que je clique | Ce que je dis | Chiffres attendus |", "|---|---|---|---|---|",
        f"| 0:00–1:00 | Accueil → Vue d'ensemble | « Entrer », pays {iso3}, année {year} | FinOVA mesure l'inclusion "
        "financière de la Tunisie face à quatre pairs, à partir de sources officielles auditées. | "
        f"Détention d'un compte : {fmt_num(v('account_ownership'))} % ; pairs : "
        + ", ".join(f"{c} {fmt_num(v('account_ownership', c))} %" for c in peers) + " |",
        f"| 1:00–2:30 | Vue d'ensemble, bas de page | Faire défiler jusqu'à « Pistes de recommandation » | Les pistes "
        "viennent de règles fixes appliquées aux valeurs auditées ; chacune cite ses chiffres et son groupe cible ; "
        f"association, pas causalité. | {len(recs['recommendations'])} pistes"
        + (f" ; ex. groupe cible « {first['target_group']} »" if first else "") + " |",
        f"| 2:30–3:00 | Vue d'ensemble | « Télécharger le rapport (PDF) » | Le rapport des constats est construit à la "
        "demande, pour le pays et l'année affichés. | page de garde : run, snapshot, catalogue |",
        f"| 3:00–4:00 | Inclusion et inégalités | Graphique des groupes | Les écarts entre groupes sont les plus forts "
        f"signaux. | Écart hommes − femmes : {fmt_num(v('gender_gap'))} pts ; revenu : {fmt_num(v('income_gap'))} pts |",
        f"| 4:00–5:00 | Pourquoi l'exclusion ? | Carte des obstacles | Obstacles déclarés par les adultes sans compte, "
        "comparés aux pairs. | "
        + (f"{top_barrier[1]} : {fmt_num(top_barrier[0])} %" if top_barrier else NA) + " |",
        f"| 5:00–7:00 | Sources et qualité → « Agents » | Lire la frise, puis « Relancer la démonstration » | "
        f"{len(ROUTE1)} agents en Route 1 puis {len(ROUTE2)} en Route 2, chacun déterministe ou avec LLM optionnel. "
        "Le recalcul reprend les sources officielles du snapshot publié ; sans donnée nouvelle, il s'arrête après "
        "le snapshot et les autres agents sont marqués « ignoré ». | "
        f"score qualité {fmt_num(ctx.quality.get('overall_score'), 3)} ; {fmt_int(warehouse_counts(ctx).get('fact_rows'))} "
        f"lignes fact ; {fmt_int(ctx.audit.get('rows'))} lignes KPI ; Route 1 (hors collecte) "
        f"{fmt_num(total_r1, 1)} s |",
        f"| 7:00–8:30 | Audit et confiance | Verdict, contrôles, injection de fautes, « Télécharger le rapport (PDF) » | "
        "Un auditeur indépendant recalcule chaque valeur ; on a vérifié qu'il détecte des fautes injectées. | "
        f"{ctx.audit.get('verdict', NA)} : {counts.get('pass', NA)} réussis, {counts.get('warn', NA)} avertissements, "
        f"{counts.get('fail', NA)} échecs ; {fmt_int(publication.get('approved'))} approuvées, "
        f"{fmt_int(publication.get('approved_with_review_note'))} avec réserve ; fautes "
        f"{fi.get('detected', NA)}/{fi.get('total', NA)} ; constats {insight.get('accepted', NA)}/"
        f"{insight.get('audited', NA)} acceptés |",
        f"| 8:30–9:30 | Ask Finova | Poser « Quel est le taux de détention d'un compte en Tunisie ? » | Chaque nombre "
        "de la réponse est contrôlé contre les faits ; sinon réponse déterministe. | "
        f"{fmt_num(v('account_ownership'))} % ; contrôle en direct "
        + (f"{live.get('grounded')}/{live.get('questions')} réponses fondées" if live.get("status") == "mesuré"
           else "non mesuré") + " |",
        "| 9:30–10:00 | Conclusion | — | Recalcul naïf depuis les CSV : mêmes valeurs ; le pipeline ajoute statut, "
        "pairs, traçabilité et audit. | "
        + (f"{base.get('matched')}/{base.get('compared')} valeurs identiques" if base else NA) + " |",
        "", "## Mode banquier (2 minutes, facultatif)", "",
        "Fichier : `docs/examples/banque_fictive_exemple.csv` (**données fictives**, « exemple fictif » dans chaque "
        "libellé). Les valeurs utilisateur ne sont pas reprises ici : ce document ne contient que des données "
        "officielles.", "",
        "| Étape | Ce que je clique | Ce que je dis |", "|---|---|---|",
        "| 1 | Mes données → « Ajouter un fichier », déposer l'exemple, « Continuer » | Structure détectée ; les "
        "chiffres officiels ne seront pas modifiés. |",
        "| 2 | Étape « Indicateurs » : unités « par 100 000 adultes » et « % » ; distributeurs → "
        "`atm_density`, agences → `branch_density` ; cocher « Mon indicateur mesure la même chose » | Seuls les KPI "
        "de même unité sont proposés ; même unité n'est pas même définition : je la déclare, avec la définition "
        "officielle sous les yeux. |",
        "| 3 | « Ajouter et recalculer » | Recalcul hors ligne : sources officielles reprises du snapshot. |",
        f"| 4 | Vue d'ensemble ({COUNTRY_LABELS.get(iso3, iso3)}, {year}) → « Vos indicateurs face aux données "
        "officielles » | Chaque valeur porte « Données utilisateur · non vérifiée par BIFlow » ; les agences "
        "s'arrêtent en 2023 : « années différentes : comparaison indicative », et aucune piste. |",
        "| 5 | « Pistes de recommandation » → « À partir de vos données » | Même règle fixe, seulement à année "
        "identique : ici les distributeurs. |",
        "| 6 | Ask Finova : « Quel est le taux de clients utilisant la banque mobile de ma banque ? » | Réponse "
        "« D'après vos données », en mode simple : rien n'est envoyé au LLM tant que "
        "`llm.ask.allow_user_data_to_llm` est désactivé. |",
        "| 7 | Cocher « Inclure l'annexe : vos données », « Télécharger le rapport (PDF) » | L'annexe est une "
        "section séparée, chaque valeur étiquetée. |",
        "| 8 | Mes données → « Supprimer » | Les lignes quittent l'entrepôt au recalcul. |", "",
        "## Limites (à dire si on demande)", "",
        "- Connexion de démonstration : aucune authentification réelle, aucun compte ni droit.",
        "- Niveau pays uniquement : pas encore de gouvernorat, d'agence ni de client.",
        "- Données locales, sauf si `llm.ask.allow_user_data_to_llm` est activé : Ask Finova envoie alors les "
        "valeurs lues au fournisseur LLM configuré.",
        "- Définition déclarée par l'utilisateur : comparaison indicative, pas vérifiée par BIFlow.", "",
        "## Si une question arrive", "",
        "- *Le LLM invente-t-il des chiffres ?* Non : tout nombre est vérifié contre les faits ; voir EVALUATION.md.",
        "- *Pourquoi « association, pas causalité » ?* Les données Findex sont des enquêtes transversales : elles "
        "décrivent des écarts, pas leurs causes.",
        "- *Et sans clé LLM ?* Chaque agent a un repli déterministe ; la démonstration fonctionne hors ligne.", "",
    ]
    return "\n".join(lines)


RENDERERS = {
    "ARCHITECTURE.md": render_architecture,
    "DATA_QUALITY_REPORT.md": render_quality,
    "KPI_CATALOG.md": render_kpi_catalog,
    "INSIGHTS_ET_RECOMMANDATIONS.md": render_insights,
    "EVALUATION.md": render_evaluation,
    "DEMO.md": render_demo,
}
# Documents ecrits hors de docs/deliverables/ (chemin relatif a la racine du projet)
TARGETS = {"DEMO.md": "docs/DEMO.md"}


def stable(text: str) -> str:
    """Texte compare par --check : sans la ligne de date de generation."""
    return "\n".join(line for line in text.splitlines() if not line.startswith("- **Généré le**"))


__all__ = ["AGENTS", "Context", "DELIVERABLES_DIR", "NA", "RENDERERS", "TARGETS", "agent_summaries", "load_context",
           "evaluation_freshness", "run_timeline", "scope_recommendations", "stable", "warehouse_counts"]
