"""Genere les livrables ecrits de docs/deliverables/ depuis l'etat courant.

Chaque nombre est lu dans l'entrepot, le rapport d'audit, le rapport qualite, le
catalogue, les rapports de run et les evaluations enregistrees : rien n'est saisi
a la main. Relancable a volonte (seule la ligne « Genere le » change).

    python scripts/build_deliverables.py            # ecrit les fichiers
    python scripts/build_deliverables.py --check    # echoue si un fichier est perime
    python scripts/build_deliverables.py --only KPI_CATALOG.md

Ecrit aussi docs/DEMO.md (script de demonstration de 10 minutes).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from biflow.tools.deliverables import DELIVERABLES_DIR, RENDERERS, TARGETS, load_context, stable  # noqa: E402


def build(out_dir: Path, only: list[str] | None = None, check: bool = False) -> int:
    ctx = load_context()
    names = only or list(RENDERERS)
    stale = []
    for name in names:
        text = RENDERERS[name](ctx)
        # DEMO.md va dans docs/ quand la sortie est le dossier par defaut
        target = ROOT / TARGETS[name] if name in TARGETS and out_dir == DELIVERABLES_DIR else out_dir / name
        if check:
            current = target.read_text(encoding="utf-8") if target.is_file() else ""
            if stable(current) != stable(text):
                stale.append(name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        print(f"ecrit : {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}")
    if check:
        for name in stale:
            print(f"perime : {name} (relancer python scripts/build_deliverables.py)")
        print("livrables a jour" if not stale else f"{len(stale)} livrable(s) perime(s)")
        return 1 if stale else 0
    print(f"run {ctx.run_id}, snapshot {ctx.snapshot_id}, catalogue {ctx.catalog_version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DELIVERABLES_DIR), help="dossier de sortie")
    parser.add_argument("--only", action="append", choices=sorted(RENDERERS), help="un seul document")
    parser.add_argument("--check", action="store_true", help="compare sans ecrire (code 1 si perime)")
    args = parser.parse_args(argv)
    return build(Path(args.out).resolve(), args.only, args.check)


if __name__ == "__main__":
    sys.exit(main())
