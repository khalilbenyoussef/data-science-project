"""Approche de reference : recalcul naif de 4 KPI depuis les CSV bruts (pandas).

Reproduit ce qu'un analyste ferait dans Excel : ouvrir findex.csv et fas.csv,
filtrer le pays et l'annee, lire la colonne, multiplier par 100 ou soustraire deux
groupes. Aucun code du pipeline n'est utilise pour le calcul. Les valeurs sont
comparees a la table kpi_values (doivent etre egales a la tolerance de l'Auditor)
et les deux approches sont chronometrees.

    python scripts/baseline_reference.py [--out outputs/evaluation/baseline.json]

Code de sortie 1 si une valeur differe.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from biflow.config import load_config, resolve  # noqa: E402

KPIS = {
    "account_ownership": "Taux de détention d'un compte (findex account_t_d × 100, groupe « all »)",
    "gender_gap": "Écart hommes − femmes (findex account_t_d, groupes « men » et « women »)",
    "digital_payment_rate": "Paiement numérique (findex g20_any × 100, groupe « all »)",
    "branch_density": "Agences pour 100 000 adultes (fas, série <ISO3>.FA26N.PHTADLT_NUM.A)",
}


def naive_values(findex_csv: Path, fas_csv: Path, countries: list[str]) -> list[dict]:
    """Calcul « tableur » : un filtre, une colonne, une operation par KPI."""
    findex = pd.read_csv(findex_csv, low_memory=False)
    fas = pd.read_csv(fas_csv, sep=";", skiprows=1, low_memory=False, dtype=str)  # 2 lignes d'en-tete
    out = []
    for iso3 in countries:
        rows = findex[findex["codewb"] == iso3]
        for year in sorted(rows["year"].dropna().astype(int).unique()):
            year_rows = rows[rows["year"] == year]
            total = year_rows[year_rows["group"] == "all"]
            men = year_rows[year_rows["group2"] == "men"]
            women = year_rows[year_rows["group2"] == "women"]
            if len(total) == 1 and pd.notna(total["account_t_d"].iloc[0]):
                out.append(("account_ownership", iso3, year, 100 * float(total["account_t_d"].iloc[0])))
            if len(total) == 1 and pd.notna(total["g20_any"].iloc[0]):
                out.append(("digital_payment_rate", iso3, year, 100 * float(total["g20_any"].iloc[0])))
            if len(men) == 1 and len(women) == 1 and pd.notna(men["account_t_d"].iloc[0]) \
                    and pd.notna(women["account_t_d"].iloc[0]):
                out.append(("gender_gap", iso3, year,
                            100 * float(men["account_t_d"].iloc[0]) - 100 * float(women["account_t_d"].iloc[0])))
        series = fas[fas["SERIES_CODE"] == f"{iso3}.FA26N.PHTADLT_NUM.A"]
        if len(series) == 1:
            for column in series.columns:
                if column.isdigit() and pd.notna(series[column].iloc[0]) and str(series[column].iloc[0]).strip():
                    out.append(("branch_density", iso3, int(column), float(series[column].iloc[0])))
    return [{"kpi_id": k, "iso3": c, "year": int(y), "value": v} for k, c, y, v in out]


def published_values(warehouse: Path, countries: list[str]) -> dict[tuple, float | None]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        rows = con.execute(
            "SELECT kpi_id, iso3, year, value FROM kpi_values WHERE list_contains(?, kpi_id) "
            "AND list_contains(?, iso3)", [list(KPIS), countries]).fetchall()
    return {(k, c, int(y)): v for k, c, y, v in rows}


def compare(naive: list[dict], published: dict[tuple, float | None], tolerance: float) -> dict:
    """Seules les lignes publiees (annees valides du catalogue) sont comparees."""
    matched, mismatched, missing = [], [], []
    naive_by_key = {(r["kpi_id"], r["iso3"], r["year"]): r["value"] for r in naive}
    for key, value in sorted(published.items()):
        if value is None:
            continue
        found = naive_by_key.get(key)
        if found is None:
            missing.append({"kpi_id": key[0], "iso3": key[1], "year": key[2], "published": value})
        elif abs(found - value) <= tolerance:
            matched.append(key)
        else:
            mismatched.append({"kpi_id": key[0], "iso3": key[1], "year": key[2], "published": value,
                               "naive": found, "difference": found - value})
    by_kpi = {k: {"compared": sum(1 for m in matched if m[0] == k) + sum(1 for m in mismatched if m["kpi_id"] == k),
                  "matched": sum(1 for m in matched if m[0] == k)} for k in KPIS}
    return {"compared": len(matched) + len(mismatched), "matched": len(matched), "mismatched": mismatched,
            "missing_in_naive": missing, "by_kpi": by_kpi}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="outputs/evaluation/baseline.json")
    parser.add_argument("--repeat", type=int, default=3, help="repetitions du chronometrage (mediane)")
    args = parser.parse_args(argv)
    cfg = load_config()
    sources = cfg.get("sources") or {}
    findex_csv, fas_csv = resolve(sources["findex"]["path"]), resolve(sources["fas"]["path"])
    warehouse = resolve((cfg.get("paths") or {}).get("processed", "data/processed")) / "warehouse.duckdb"
    kpi_cfg = cfg.get("kpi") or {}
    countries = [kpi_cfg.get("focus", "TUN"), *kpi_cfg.get("peers", [])]
    tolerance = float((cfg.get("auditor") or {}).get("tolerance", 1e-9))

    naive_times, published_times = [], []
    for _ in range(max(1, args.repeat)):
        start = time.perf_counter()
        naive = naive_values(findex_csv, fas_csv, countries)
        naive_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        published = published_values(warehouse, countries)
        published_times.append(time.perf_counter() - start)
    result = compare(naive, published, tolerance)
    median = lambda values: sorted(values)[len(values) // 2]  # noqa: E731
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "countries": countries, "tolerance": tolerance, "kpis": KPIS,
        "inputs": {"findex": str(findex_csv.relative_to(resolve("."))), "fas": str(fas_csv.relative_to(resolve(".")))},
        "timing_s": {"naive_pandas": round(median(naive_times), 4),
                     "kpi_values_read": round(median(published_times), 4), "repeat": len(naive_times)},
        **result,
    }
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['matched']}/{result['compared']} valeurs identiques ; "
          f"naif {payload['timing_s']['naive_pandas']} s, lecture kpi_values {payload['timing_s']['kpi_values_read']} s")
    for item in result["mismatched"]:
        print(f"ECART {item['kpi_id']} {item['iso3']} {item['year']} : publie {item['published']}, naif {item['naive']}")
    print(f"ecrit : {out}")
    return 1 if result["mismatched"] or result["missing_in_naive"] else 0


if __name__ == "__main__":
    sys.exit(main())
