from __future__ import annotations

import pandas as pd
import yaml

from biflow.agents.semantic import SemanticAgent


def test_semantic_computes_global_and_dimensional_kpis(tmp_path):
    year = pd.DataFrame(
        {
            "iso3": ["MAR", "FRA", "IND", "MAR", "FRA", "IND"],
            "country": ["Morocco", "France", "India"] * 2,
            "year": [2020, 2020, 2020, 2021, 2021, 2021],
            "account_own": [50.0, 90.0, 70.0, 55.0, 91.0, 72.0],
            "gender_gap_pp": [20.0, 5.0, 15.0, 18.0, 4.0, 14.0],
            "income_group": ["Lower middle", "High", "Lower middle"] * 2,
            "is_country": [True] * 6,
            "is_aggregate": [False] * 6,
        }
    )
    year_path = tmp_path / "country_year.parquet"
    year.to_parquet(year_path, index=False)

    catalog = {
        "domain": "test",
        "kpis": [
            {
                "id": "inclusion_rate",
                "label": "Taux de detention",
                "unit": "%",
                "source": "findex",
                "expr": "avg(account_own)",
                "by": ["income_group"],
            },
            {
                "id": "gender_gap",
                "label": "Ecart de genre",
                "unit": "pp",
                "source": "findex",
                "expr": "avg(gender_gap_pp)",
            },
        ],
    }
    catalog_path = tmp_path / "kpis.yaml"
    catalog_path.write_text(yaml.safe_dump(catalog, allow_unicode=True), encoding="utf-8")

    cfg = {
        "llm": {"enabled": False},
        "kpis": {"catalog": str(catalog_path), "output": str(tmp_path / "kpis")},
        "paths": {"reports": str(tmp_path / "reports")},
    }
    out = SemanticAgent(cfg=cfg, run_id="test").execute(
        {"staging_paths": {"country_year": str(year_path)}, "run_id": "test"}
    )

    values = pd.read_parquet(out["kpi_values_path"])
    global_rows = values[values["dimension"] == "global"]
    assert len(global_rows) == 4
    assert set(values["kpi_id"]) == {"inclusion_rate", "gender_gap"}
    assert "income_group" in set(values["dimension"])
    latest = values[(values["kpi_id"] == "inclusion_rate") & (values["year"] == 2021)]
    assert round(float(latest["value"].iloc[0]), 2) == 72.67
    assert out["kpis"]["count"] == 2
