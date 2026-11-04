"""Point d'entree CLI du pipeline BIFlow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if str(Path(__file__).parent / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent / "src"))

try:  # console Windows cp1252 : eviter un crash sur les caracteres Unicode du LLM
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from biflow.config import load_config  # noqa: E402
from biflow.graph import STEP_ORDER, run_pipeline  # noqa: E402


def _print_state(state: dict) -> None:
    print("=" * 74)
    print(f"BIFlow - run {state.get('run_id')} | statut : {state.get('status')}")
    print("=" * 74)

    raw_meta = state.get("raw_meta") or {}
    if raw_meta:
        print("\nSources")
        for name, meta in raw_meta.items():
            print(
                f"  [OK] {name:8s} {meta.get('path')} "
                f"sha256={(meta.get('sha256') or '')[:12]} "
                f"lignes={meta.get('rows')}"
            )

    snapshot = state.get("snapshot") or {}
    if snapshot:
        print(f"\nSnapshot : {snapshot.get('snapshot_id')} ({snapshot.get('status')})")

    profiles = state.get("profiles") or {}
    if profiles:
        print("\nProfils")
        for name, info in profiles.items():
            print(
                f"  [OK] {name:8s} {info.get('rows')} x {info.get('cols')} "
                f"({info.get('format')}, {info.get('missing_cells_pct')} % NaN)"
            )

    quality = state.get("quality") or {}
    if quality:
        print(
            f"\nQualite : score={quality.get('overall_score'):.2%} "
            f"gate={'PASS' if quality.get('passed') else 'FAIL'} "
            f"critiques={quality.get('critical_issues')}"
        )

    if state.get("warehouse_path"):
        print(f"\nWarehouse : {state['warehouse_path']}")

    audit = state.get("audit") or {}
    if audit:
        counts = audit.get("counts") or {}
        print(
            f"\nAudit : verdict={audit.get('verdict')} pass={counts.get('pass')} "
            f"warn={counts.get('warn')} fail={counts.get('fail')} publication={audit.get('publication')}"
        )

    kpi = state.get("kpi_summary") or {}
    if kpi:
        print(
            f"\nKPI : {kpi.get('rows')} valeurs ({kpi.get('kpis')} KPI, focus {kpi.get('focus')}, "
            f"pairs {', '.join(kpi.get('peers') or [])}) - disponibles={kpi.get('available')} "
            f"indisponibles={kpi.get('unavailable')} a_revoir={kpi.get('requires_review')}"
        )

    warnings = state.get("warnings") or []
    if warnings:
        print("\nAvertissements")
        for warning in warnings:
            print(f"  - {warning}")

    errors = state.get("errors") or []
    if errors:
        print("\nErreurs")
        for error in errors:
            print(f"  - {error}")


def _csv(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        items.extend(part.strip() for part in value.split(",") if part.strip())
    return items


def _add_analysis_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--country", action="append", default=None,
        help="pays ISO3, option répétable ou valeurs séparées par des virgules",
    )
    parser.add_argument("--kpis", default=None, help="KPI séparés par des virgules")
    parser.add_argument("--mode", choices=("latest", "year"), default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--reference", default=None, help="pays de référence")
    parser.add_argument("--top", type=int, default=None, help="constats max par code")
    parser.add_argument("--no-series", action="store_true", help="omettre les séries")
    parser.add_argument("--run-id", default=None)


def _analysis_request(args: argparse.Namespace, cfg: dict) -> dict:
    analyst = cfg.get("analyst") or {}
    dashboard = cfg.get("dashboard") or {}
    if args.mode == "latest" and args.year is not None:
        raise SystemExit("--year est incompatible avec --mode latest")
    mode = args.mode or (
        "year" if args.year is not None else dashboard.get("default_mode", "latest")
    )
    year = args.year if args.year is not None else (
        dashboard.get("default_year") if mode == "year" else None
    )
    return {
        "action": "analyze",
        "iso3": _csv(args.country) or list(analyst.get("default_countries") or []),
        "kpi_ids": _csv([args.kpis] if args.kpis else None) or list(analyst.get("default_kpis") or []),
        "mode": mode,
        "year": year,
        "reference_iso3": args.reference,
        "include_series": not args.no_series,
        "top_n": args.top or analyst.get("top_n", 10),
    }


def _print_analysis_state(state: dict) -> None:
    print("=" * 74)
    print(f"BIFlow Route 2 - run {state.get('run_id')} | statut : {state.get('status')}")
    print("=" * 74)

    report = state.get("analysis_report") or {}
    summary = report.get("summary") or {}
    if summary:
        print(
            f"\nObservations : {summary.get('available')}/"
            f"{summary.get('selected_observations')} disponibles, "
            f"{summary.get('requires_review')} en revue"
        )
        findings = summary.get("findings") or {}
        print(
            f"Constats     : {findings.get('total', 0)} "
            f"(revue {findings.get('review', 0)}, alerte {findings.get('warning', 0)}, "
            f"info {findings.get('info', 0)})"
        )
        for finding in (report.get("findings") or [])[:8]:
            print(f"  [{finding['severity']}] {finding['id']} {finding['statement']}")
        if findings.get("total", 0) > 8:
            print("  ...")

    if state.get("analysis_dataset_path"):
        print(f"\nDataset      : {state['analysis_dataset_path']}")
    paths = state.get("dashboard_paths") or {}
    if paths:
        print(f"\nDashboard    : {paths.get('data')}")
        print(f"Front React  : {paths.get('public')}")
        print("Lancer       : cd dashboard && npm run dev")

    warnings = state.get("warnings") or []
    if warnings:
        print("\nAvertissements")
        for warning in warnings[:8]:
            print(f"  - {warning}")

    errors = state.get("errors") or []
    if errors:
        print("\nErreurs")
        for error in errors:
            print(f"  - {error}")


def source_command(args) -> int:
    """add-source / remove-source ; erreurs affichees en francais, code 1."""
    from biflow.agents.mapper import MapperAgent
    from biflow.config import load_config
    from biflow.tools.user_sources import UserSourceError
    from biflow.tools.user_sources.cli import add_source, remove_source

    cfg = load_config()
    if args.command == "remove-source":
        return 0 if remove_source(args.name, cfg) else 1
    llm_suggest = None
    if not args.no_llm and (cfg.get("llm") or {}).get("enabled", True):
        llm_suggest = MapperAgent(cfg=cfg).suggester()
    try:
        result = add_source(args.file, args.name, mapping_file=args.mapping, dry_run=args.dry_run,
                            assume_yes=args.yes, cfg=cfg, llm_suggest=llm_suggest, draft_path=args.draft)
    except UserSourceError as exc:
        print(f"Erreur : {exc}")
        return 1
    return 0 if result["registered"] or args.dry_run else 1


def explain_command(args) -> int:
    """Affiche l'explication stockee par l'Auditor (table kpi_explanations).

    Lecture seule du warehouse : aucun recalcul de KPI, aucun appel reseau ni LLM.
    """
    import json

    import duckdb

    from biflow.config import load_config, resolve
    from biflow.tools.audit_explain import explain_change
    from biflow.tools.audit_text import render_markdown
    from biflow.utils.countries import normalize_iso3

    cfg = load_config()
    warehouse = resolve(args.warehouse or f"{(cfg.get('paths') or {}).get('processed', 'data/processed')}/warehouse.duckdb")

    def code(value):
        return "PEERS" if str(value).strip().upper() == "PEERS" else normalize_iso3(value)

    keys = [(args.kpi, code(args.iso3), args.year)]
    if args.compare_year is not None or args.compare_iso3:
        keys.append((args.kpi, code(args.compare_iso3 or args.iso3), args.compare_year or args.year))
    try:
        with duckdb.connect(str(warehouse), read_only=True) as con:
            found = [con.execute("SELECT explanation FROM kpi_explanations WHERE kpi_id = ? AND iso3 = ? "
                                 "AND year = ?", list(key)).fetchone() for key in keys]
    except duckdb.Error as exc:
        print(f"Explications indisponibles ({exc}) : lancer d'abord le pipeline avec l'etape auditor.")
        return 1
    missing = [key for key, row in zip(keys, found) if row is None]
    if missing:
        print(f"Aucune explication pour {missing}.")
        return 1
    record = json.loads(found[0][0])
    other = json.loads(found[1][0]) if len(found) > 1 else None
    change = None
    if other is not None:
        threshold = float((cfg.get("auditor") or {}).get("min_meaningful_change_pp", 2.0))
        change = explain_change(other, record, threshold)
    print(render_markdown(record, args.lang, change, other))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BIFlow - pipeline BI multi-agents")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="execute le pipeline")
    run.add_argument("--only", choices=STEP_ORDER, help="execute un seul agent")
    run.add_argument("--from", dest="start", choices=STEP_ORDER, help="premier agent")
    run.add_argument("--to", dest="stop", choices=STEP_ORDER, help="dernier agent")
    run.add_argument("--objective", default=None, help="objectif metier du run")
    run.add_argument("--run-id", default=None, help="identifiant du run")
    run.add_argument("--no-llm", action="store_true", help="desactive tous les appels LLM")
    run.add_argument("--offline-official", action="store_true",
                     help="sources officielles reprises du snapshot publie, sans reseau "
                          "(seules les sources utilisateur peuvent changer)")
    run.add_argument("--rebuild", action="store_true",
                     help="rejoue snapshot -> auditor sur les blobs du snapshot publie (nouveau run_id)")

    sub.add_parser("steps", help="liste les etapes du pipeline (Route 1)")

    analyze = sub.add_parser("analyze", help="Route 2 : rapport BI Analyst deterministe")
    dashboard = sub.add_parser(
        "dashboard", help="Route 2 : analyste + dashboard React (ECharts)"
    )
    for command in (analyze, dashboard):
        _add_analysis_args(command)

    add = sub.add_parser("add-source", help="ajoute un CSV utilisateur (detection, mapping, dry-run)")
    add.add_argument("--file", required=True, help="fichier CSV a ajouter")
    add.add_argument("--name", required=True, help="nom de la source (minuscules, chiffres, _)")
    add.add_argument("--mapping", default=None, help="mapping YAML : mode non interactif")
    add.add_argument("--dry-run", action="store_true", help="rapport seulement, rien n'est enregistre")
    add.add_argument("--yes", action="store_true", help="aucune question (echoue si une reponse manque)")
    add.add_argument("--draft", default=None, help="ecrit le brouillon de mapping a completer")
    add.add_argument("--no-llm", action="store_true", help="aucune suggestion LLM des roles de colonnes")
    remove = sub.add_parser("remove-source", help="retire une source utilisateur")
    remove.add_argument("--name", required=True)

    explain = sub.add_parser("explain", help="explique une valeur KPI (lecture seule, sans reseau)")
    explain.add_argument("--kpi", required=True, help="identifiant du KPI (ex. account_ownership)")
    explain.add_argument("--iso3", required=True, help="pays ISO3 ou PEERS")
    explain.add_argument("--year", required=True, type=int)
    explain.add_argument("--compare-year", type=int, default=None, help="annee de comparaison")
    explain.add_argument("--compare-iso3", default=None, help="pays de comparaison (ex. PEERS)")
    explain.add_argument("--lang", choices=("fr", "en"), default="fr")
    explain.add_argument("--warehouse", default=None, help="warehouse DuckDB (defaut : config)")

    args = parser.parse_args()
    if args.command == "steps":
        for index, step in enumerate(STEP_ORDER, 1):
            print(f"S{index + 5:02d} {step}")
        return 0
    if args.command in {"analyze", "dashboard"}:
        from biflow.analysis_graph import run_analysis_pipeline

        cfg = load_config()
        state = run_analysis_pipeline(
            _analysis_request(args, cfg),
            cfg=cfg,
            run_id=args.run_id,
            stage="analyst" if args.command == "analyze" else "all",
        )
        _print_analysis_state(state)
        return 0 if state.get("status") == "success" else 2
    if args.command == "explain":
        return explain_command(args)
    if args.command in ("add-source", "remove-source"):
        return source_command(args)
    if args.command != "run":
        parser.print_help()
        return 1

    state = run_pipeline(
        objective=args.objective,
        only=args.only,
        start=args.start,
        stop=args.stop,
        run_id=args.run_id,
        use_llm=not args.no_llm,
        rebuild=args.rebuild,
        offline_official=args.offline_official,
    )
    _print_state(state)
    return 0 if state.get("status") in ("success", "no_change") else 2


if __name__ == "__main__":
    raise SystemExit(main())
