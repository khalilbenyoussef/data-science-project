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

    kpis = state.get("kpis") or {}
    if kpis:
        print(f"\nKPI : {kpis.get('count')} calcule(s)")
        for item in (kpis.get("items") or [])[:10]:
            print(
                f"  {item['id']:26s} {item['latest_year']} "
                f"{item['latest_value']:>8.2f} {item['unit']}"
            )

    insights = state.get("insights") or {}
    if insights:
        print("\nSynthese")
        print(f"  {insights.get('summary')}")
        print(f"  rapport : {insights.get('path')}")

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

    sub.add_parser("steps", help="liste les etapes du pipeline")

    args = parser.parse_args()
    if args.command == "steps":
        for index, step in enumerate(STEP_ORDER, 1):
            print(f"S{index + 5:02d} {step}")
        return 0
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
