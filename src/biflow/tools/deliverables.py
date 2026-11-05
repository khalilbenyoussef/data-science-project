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
from biflow.tools.kpi import DEFAULT_CATALOG, load_catalog

NA = "non disponible"
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
    return f"{float(value):,.{decimals}f}".replace(",", " ")


def fmt_s(value: Any) -> str:
    return f"{float(value):.2f} s" if isinstance(value, (int, float)) else NA


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


def agent_summaries(ctx: Context) -> list[dict[str, Any]]:
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
            if aid == "collector" and report is None and ctx.collector:
                report, run_id = ctx.collector, ctx.collector.get("run_id")
                note = "run courant reconstruit depuis le snapshot publié : dernier Collector exécuté"
        elif aid in ROUTE2:
            run = ctx.route2 or {}
            report, run_id, note = (run.get("agents") or {}).get(aid), run.get("run_id"), None
        else:
            report, run_id, note = None, None, "à la demande (POST /api/ask), aucun rapport de run"
        key = _key_output(aid, report or {}, ctx, counts) if report else {"text": NA}
        out.append({
            **{k: agent[k] for k in ("id", "route", "label", "role", "inputs", "outputs", "tools", "module")},
            "llm_mode": llm_mode(aid, ctx.cfg),
            "llm_measured": llm_measured(report) if report else NA,
            "llm_usage": (report or {}).get("llm_usage") if report else None,
            "run_id": run_id, "status": (report or {}).get("status") if report else None,
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
                   ([a["label"], f"`{a['run_id']}`" if a["run_id"] else NA, a["status"] or NA,
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
            f"- **Définition** : {v.get('definition', NA)}",
            f"- **Formule** : `{formula.get('from_fact', NA)}` depuis `fact` "
            f"(`{(v.get('warehouse') or {}).get('indicator_code', NA)}`)"
            + (f" ; dépendances : {', '.join(f'`{d}`' for d in v.get('dependencies') or [])}"
               if v.get("dependencies") else ""),
            f"- **Unité** : {v.get('unit', NA)}",
            f"- **Dénominateur** : {den.get('population', NA)} ({den.get('basis', NA)})",
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


RENDERERS = {
    "ARCHITECTURE.md": render_architecture,
    "DATA_QUALITY_REPORT.md": render_quality,
    "KPI_CATALOG.md": render_kpi_catalog,
}


def stable(text: str) -> str:
    """Texte compare par --check : sans la ligne de date de generation."""
    return "\n".join(line for line in text.splitlines() if not line.startswith("- **Généré le**"))


__all__ = ["AGENTS", "Context", "DELIVERABLES_DIR", "NA", "RENDERERS", "agent_summaries", "load_context",
           "stable", "warehouse_counts"]
