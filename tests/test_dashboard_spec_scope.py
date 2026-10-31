"""Country scope and survey-wave behaviour of the Finova dashboard contract."""
import json

import duckdb
import pytest
from fastapi.testclient import TestClient

from biflow.tools.analysis import AnalysisRequest, AnalysisService
from biflow.tools.dashboard_spec import build_finova_spec, load_reference
from biflow.tools.warehouse_reader import WarehouseReader
from dashboard_app.api.app import create_app

PEERS = ("TUN", "DZA", "EGY", "JOR", "MAR")
KPIS = (
    "account_ownership", "branch_density", "digital_payment_rate",
    "saving_rate", "borrowing_rate",
)
TUNISIA_ONLY_REFERENCES = {
    "fx_tnd_usd_2024", "smig_2025",
    "poverty_rate_urban_2021", "poverty_rate_rural_2021",
}


def _row(iso3, year, source, indicator, dimension, value, unit="fraction",
         dimension_value=None):
    return (
        iso3, year, source, indicator, dimension,
        dimension_value if dimension_value is not None else dimension, value, unit,
    )


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    path = tmp_path_factory.mktemp("scope") / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE country_dim (iso3 VARCHAR, country VARCHAR, region VARCHAR, "
            "income_group VARCHAR, is_country BOOLEAN, is_aggregate BOOLEAN)"
        )
        con.executemany(
            "INSERT INTO country_dim VALUES (?, ?, ?, ?, true, false)",
            [(code, code.title(), "MENA", "LMIC") for code in PEERS],
        )
        con.execute("CREATE TABLE country_year (iso3 VARCHAR, year INTEGER, gdp_pc DOUBLE)")
        con.executemany(
            "INSERT INTO country_year VALUES (?, ?, ?)",
            [("TUN", 2022, 3707.29), ("TUN", 2024, 4213.0), ("JOR", 2024, 5073.9)],
        )
        con.execute(
            "CREATE TABLE fact (iso3 VARCHAR, year INTEGER, source VARCHAR, "
            "indicator_code VARCHAR, dimension VARCHAR, dimension_value VARCHAR, "
            "value DOUBLE, unit VARCHAR)"
        )
        rows = []
        # Tunisie 2024 : vague d'enquête complète.
        rows += [
            _row("TUN", 2024, "findex", "account_t_d", "all", 0.3784, dimension_value="all"),
            _row("TUN", 2021, "findex", "account_t_d", "all", 0.3691, dimension_value="all"),
            _row("TUN", 2024, "findex", "g20_any", "all", 0.2368, dimension_value="all"),
            _row("TUN", 2024, "findex", "save_any_t_d", "all", 0.216, dimension_value="all"),
            _row("TUN", 2024, "findex", "borrow_any_t_d", "all", 0.035, dimension_value="all"),
            _row("TUN", 2024, "findex", "fin24aP", "all", 0.8839, dimension_value="all"),
            _row("TUN", 2024, "fas", "branch_density", "bank_type", 22.37,
                 "per_100k_adults", "commercial_banks"),
            _row("TUN", 2024, "fas", "atm_density", "bank_type", 35.44,
                 "per_100k_adults", "commercial_banks"),
        ]
        for year, women, men in ((2021, 0.285, 0.449), (2024, 0.266, 0.496)):
            rows += [
                _row("TUN", year, "findex", "account_t_d", "gender", women,
                     dimension_value="women"),
                _row("TUN", year, "findex", "account_t_d", "gender", men,
                     dimension_value="men"),
            ]
        rows += [
            _row("TUN", 2024, "findex", "account_t_d", "income", 0.28,
                 dimension_value="poorest 40%"),
            _row("TUN", 2024, "findex", "account_t_d", "income", 0.44,
                 dimension_value="richest 60%"),
            _row("TUN", 2024, "findex", "account_t_d", "urbanicity", 0.302,
                 dimension_value="rural"),
            _row("TUN", 2024, "findex", "account_t_d", "urbanicity", 0.467,
                 dimension_value="urban"),
        ]
        # Tunisie 2022 : année hors enquête, seuls les indicateurs bancaires existent.
        rows += [
            _row("TUN", 2022, "fas", "branch_density", "bank_type", 22.508,
                 "per_100k_adults", "commercial_banks"),
            _row("TUN", 2022, "fas", "atm_density", "bank_type", 33.318,
                 "per_100k_adults", "commercial_banks"),
        ]
        # Jordanie 2024 : vague d'enquête.
        rows += [
            _row("JOR", 2024, "findex", "account_t_d", "all", 0.4646, dimension_value="all"),
            _row("JOR", 2021, "findex", "account_t_d", "all", 0.4712, dimension_value="all"),
            _row("JOR", 2024, "findex", "g20_any", "all", 0.3823, dimension_value="all"),
            _row("JOR", 2024, "findex", "save_any_t_d", "all", 0.3161, dimension_value="all"),
            _row("JOR", 2024, "findex", "borrow_any_t_d", "all", 0.6522, dimension_value="all"),
            _row("JOR", 2024, "findex", "fin24aP", "all", 0.8961, dimension_value="all"),
        ]
        con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return path


def _spec(warehouse, tmp_path, iso3: str, year: int):
    request = AnalysisRequest(
        iso3=(iso3, *(code for code in PEERS if code != iso3)),
        mode="year", year=year, kpi_ids=KPIS,
    )
    dataset = AnalysisService(
        warehouse, lineage_path=tmp_path / "lineage.json",
        quality_report_path=tmp_path / "quality_report.json",
    ).build(request)
    return build_finova_spec(
        dataset, run_id=f"scope_{iso3}_{year}", iso3=iso3, year=year,
        reader=WarehouseReader(warehouse), reference=load_reference(),
    ).model_dump(mode="json")


@pytest.fixture(scope="module")
def tun_2022(warehouse, tmp_path_factory):
    return _spec(warehouse, tmp_path_factory.mktemp("tun2022"), "TUN", 2022)


@pytest.fixture(scope="module")
def jor_2024(warehouse, tmp_path_factory):
    return _spec(warehouse, tmp_path_factory.mktemp("jor2024"), "JOR", 2024)


@pytest.fixture(scope="module")
def tun_2024(warehouse, tmp_path_factory):
    return _spec(warehouse, tmp_path_factory.mktemp("tun2024"), "TUN", 2024)


def _page(spec, page_id):
    return next(page for page in spec["pages"] if page["id"] == page_id)


def _fact_codes(spec):
    return {fact["code"] for fact in spec["facts"]}


def test_survey_year_without_data_marks_pages_unavailable(tun_2022):
    for page_id in ("inclusion", "exclusion"):
        page = _page(tun_2022, page_id)
        assert page["available"] is False
        assert "vagues" in page["unavailable_reason"]
        assert page["metrics"] == [] and page["charts"] == []
    overview = _page(tun_2022, "overview")
    assert overview["available"] is True
    assert any(notice["code"] == "survey_absent" for notice in overview["notices"])


def test_survey_year_keeps_the_rest_of_the_contract(tun_2022):
    assert _page(tun_2022, "access")["available"] is True
    assert _page(tun_2022, "pipeline")["available"] is True
    assert _page(tun_2022, "poverty")["available"] is True
    assert 2022 in tun_2022["years"]


def test_jordan_never_exposes_tunisian_references(jor_2024):
    codes = _fact_codes(jor_2024)
    assert not (codes & TUNISIA_ONLY_REFERENCES)
    macro = _page(jor_2024, "overview")["blocks"][0]
    assert {item["id"] for item in macro["items"]}.isdisjoint(TUNISIA_ONLY_REFERENCES)
    context = next(
        block for block in _page(jor_2024, "exclusion")["blocks"]
        if block["id"] == "exclusion_context"
    )
    assert {item["id"] for item in context["items"]}.isdisjoint(TUNISIA_ONLY_REFERENCES)
    assert _page(jor_2024, "poverty")["available"] is False


def test_tunisia_keeps_its_references(tun_2024):
    codes = _fact_codes(tun_2024)
    assert TUNISIA_ONLY_REFERENCES <= codes
    macro = _page(tun_2024, "overview")["blocks"][0]
    assert {"fx_tnd_usd_2024", "smig_2025"} <= {item["id"] for item in macro["items"]}
    assert _page(tun_2024, "poverty")["available"] is True


def test_api_exposes_survey_years(tmp_path):
    spec = {
        "schema_version": "2.0",
        "generated_at": "2026-10-30T09:00:00",
        "run_id": "scope_api",
        "country": {"iso3": "TUN", "name": "Tunisie"},
        "year": 2024,
        "years": [2021, 2024],
        "pages": [
            {"id": "overview", "title": "Vue d'ensemble", "metrics": [],
             "charts": [], "insights": [], "blocks": [], "notices": []},
        ],
        "facts": [],
        "notices": [],
        "publication_status": "not_evaluated",
    }
    spec_path = tmp_path / "finova.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    app = create_app(
        spec_path=spec_path, warehouse_path=tmp_path / "missing.duckdb",
        reports_dir=tmp_path / "reports", history_dir=tmp_path / "history",
        web_dist=tmp_path / "dist",
    )
    response = TestClient(app).get("/api/spec")
    assert response.status_code == 200
    assert response.json()["survey_years"] == []
