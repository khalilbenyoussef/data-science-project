"""docs/examples/user_source_example.csv : fichier de demonstration FICTIF de la page
« Mes données » (annees en colonnes, point-virgule, virgule decimale, noms francais)."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard_app.api.sources import create_sources_router
from test_sources_api import Runner, cfg, roles_of, wait_job  # noqa: F401 - fixture cfg

EXAMPLE = Path(__file__).resolve().parents[1] / "docs" / "examples" / "user_source_example.csv"


def test_example_is_marked_fictitious():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("# Données FICTIVES")
    labels = {line.split(";")[1] for line in text.splitlines()[2:]}
    assert labels and all("exemple fictif" in label for label in labels)


def test_example_runs_through_the_whole_api_flow(cfg, tmp_path):
    cfg["uploads"]["max_file_mb"] = 1
    app = FastAPI()
    router, _ = create_sources_router(cfg, warehouse=tmp_path / "missing.duckdb", runner=Runner())
    app.include_router(router)
    client = TestClient(app)
    detected = client.post("/api/sources/detect",
                           files={"file": (EXAMPLE.name, EXAMPLE.read_bytes(), "text/csv")}).json()
    assert detected["layout"] == "wide_by_year" and detected["read"]["header_row"] == 1  # ligne de commentaire
    assert (detected["read"]["separator"], detected["read"]["decimal"]) == (";", ",")
    assert detected["country"]["kind"] == "name"
    request = {"upload_id": detected["upload_id"], "name": "microfinance_demo",
               "mapping": {"roles": roles_of(detected)}}
    dry = client.post("/api/sources/dry-run", json=request).json()
    assert [m["field"] for m in dry["missing_fields"]] == ["unit", "unit"]  # unites jamais devinees
    assert list(dry["unmapped_countries"]) == ["Rép. islamique de Mauritanie"]
    assert dry["non_numeric"]["count"] == 1 and dry["empty_cells"] == 1
    codes = [item["code"] for item in dry["indicators"]]
    request["mapping"].update(
        indicators={codes[0]: {"unit": "count"}, codes[1]: {"unit": "percent"}},
        country_names={"Rép. islamique de Mauritanie": "MRT"})
    ready = client.post("/api/sources/dry-run", json=request).json()
    assert ready["blocking"] == [] and ready["mapped"] == 58 and ready["year_range"] == [2019, 2023]
    assert ready["preview"][0] == {"iso3": "TUN", "year": 2019, "indicator_code": f"microfinance_demo.{codes[0]}",
                                   "indicator_label": "Clients de la microfinance (exemple fictif)",
                                   "value": 410250.0, "unit": "count", "raw_value": "410 250",
                                   "raw_column": "2019", "line": 3}
    job = client.post("/api/sources/confirm", json=request).json()
    assert wait_job(client, job["job_id"])["status"] == "success"
