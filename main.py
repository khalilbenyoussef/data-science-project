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
        "kpi_ids": _csv(args.kpis) or list(analyst.get("default_kpis") or []),
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

    sub.add_parser("steps", help="liste les etapes du pipeline (Route 1)")

    analyze = sub.add_parser("analyze", help="Route 2 : rapport BI Analyst deterministe")
    dashboard = sub.add_parser(
        "dashboard", help="Route 2 : analyste + dashboard React (ECharts)"
    )
    for command in (analyze, dashboard):
        _add_analysis_args(command)

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
    )
    _print_state(state)
    return 0 if state.get("status") == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
