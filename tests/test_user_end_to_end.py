"""Sources utilisateur : une fixture par disposition, puis bout en bout ETL + KPI + audit."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
import yaml

from biflow import graph
from biflow.tools.kpi import CatalogError, load_catalog
from biflow.tools.user_sources.cli import add_source
from biflow.tools.user_sources.detect import detect
from test_user_cli import Script
from test_user_integration import add_user_source, full_cfg

FIXTURES = Path(__file__).parent / "fixtures" / "user"


@pytest.fixture
def cfg(tmp_path):
    return {"uploads": {"dir": str(tmp_path / "uploads"), "mappings_dir": str(tmp_path / "sources")},
            "countries": {"name_to_iso3": {}}, "sources": {}, "quality": {"min_rows": 1}}


def dry(cfg, fixture, name, *answers, **kwargs):
    script = Script(*answers)
    result = add_source(FIXTURES / fixture, name, cfg=cfg, ask=script.ask, out=script.out,
                        dry_run=True, **kwargs)
    return result["report"], script


# --------------------------------------------------------------------------- une fixture par disposition
def test_long_semicolon_decimal_comma_and_french_names(cfg):
    detection = detect(FIXTURES / "long_fr_semicolon.csv")
    assert detection["layout"] == "long"
    assert detection["read"] == {"encoding": "utf-8-sig", "separator": ";", "header_row": 0, "decimal": ","}
    report, script = dry(cfg, "long_fr_semicolon.csv", "microfinance", "", "milliers_clients", "")
    assert report["countries"] == ["DZA", "MAR", "TUN"]  # Tunisie, Maroc, Algerie (noms francais)
    assert report["unmapped_countries"] == {"Atlantide": {"rows": 1, "reason": "nom de pays inconnu 'Atlantide'"}}
    assert report["non_numeric"]["count"] == 1 and report["non_numeric"]["examples"][0]["text"] == "n/d"
    assert report["mapped"] == 4 and report["mapped_pct"] == 66.7 and report["year_range"] == [2021, 2024]
    first = report["preview"][0]
    assert (first["raw_value"], first["value"], first["unit"]) == ("1 012,5", 1012.5, "milliers_clients")
    assert first["indicator_code"] == "microfinance.clients_microfinance_milliers"
    assert any("Unite de l'indicateur" in q for q in script.questions)


def test_wide_by_year_iso3_codes_and_aggregate_listed(cfg):
    assert detect(FIXTURES / "wide_by_year_iso3.csv")["layout"] == "wide_by_year"
    report, script = dry(cfg, "wide_by_year_iso3.csv", "mobile", "", "percent", "")  # WLD : Entree = exclure
    assert any("Pays non reconnu 'WLD'" in q for q in script.questions)
    assert report["countries"] == ["EGY", "MAR", "TUN"]
    assert report["unmapped_countries"]["WLD"]["reason"] == "agregat WLD (pas un pays)"
    assert report["empty_cells"] == 1 and report["mapped"] == 11  # MAR 2022 vide : jamais 0
    assert report["year_range"] == [2021, 2024]


def test_wide_by_indicator_english_names_and_unknown_country(cfg):
    assert detect(FIXTURES / "wide_by_indicator_en.csv")["layout"] == "wide_by_indicator"
    report, _ = dry(cfg, "wide_by_indicator_en.csv", "network", "", "count", "count", "")
    assert report["countries"] == ["DZA", "EGY", "JOR", "TUN"]
    assert list(report["unmapped_countries"]) == ["Atlantis"]
    assert set(report["indicators"]) == {"bank_agents", "atm_count"}


def test_missing_unit_is_asked_never_guessed(cfg):
    report, script = dry(cfg, "wide_by_indicator_en.csv", "network", assume_yes=True)
    assert report["units_missing"] == ["bank_agents", "atm_count"]
    assert {i["unit"] for i in report["indicators"].values()} == {"A_DECLARER"}
    assert "? Unité de l'indicateur 'bank_agents' (bank_agents) ? (ex. percent, fraction, count, usd) - jamais devinée" \
        in script.lines


def test_same_fingerprint_reused_and_changed_columns_ask_again(tmp_path, cfg):
    script = Script("", "count", "count", "", "o")
    add_source(FIXTURES / "wide_by_indicator_en.csv", "network", cfg=cfg, ask=script.ask, out=script.out)
    shuffled = tmp_path / "next_delivery.csv"
    shuffled.write_text("ATM_COUNT,Country,YEAR,bank_agents\n2200,Tunisia,2024,1250\n", encoding="utf-8")
    quiet = Script()
    result = add_source(shuffled, "network", cfg=cfg, ask=quiet.ask, out=quiet.out)
    assert result["status"] == "reused" and result["report"]["mapped"] == 2
    renamed = tmp_path / "renamed.csv"
    renamed.write_text("country,year,agents_bancaires,atm_count\nTunisia,2024,1250,2200\n", encoding="utf-8")
    again = Script("", "count", "count", "o")
    add_source(renamed, "network", cfg=cfg, ask=again.ask, out=again.out)
    assert "Structure differente du mapping enregistre pour cette source" in again.text


# --------------------------------------------------------------------------- catalogue utilisateur
def user_catalog(path: Path, **overrides) -> Path:
    kpi = {
        "definition_version": "1.0.0", "name": "Agents bancaires (source utilisateur)",
        "business_objective": "financial_inclusion",
        "definition": "Nombre d'agents bancaires declare par l'utilisateur.",
        "verification": {"status": "user_declared", "evidence": ["user_upload_agents"],
                         "uncertainties": ["Source fournie par l'utilisateur, non verifiee par BIFlow."]},
        "source": {"dataset": "user:agents", "indicator": "agents.agents", "official_indicator": None},
        "warehouse": {"fact_table": "fact", "indicator_code": "agents.agents", "source": "user:agents",
                      "input_unit": "count", "dimension": "all", "dimension_value": "all"},
        "formula": {"from_fact": "value"}, "unit": "count",
        "denominator": {"population": "non applicable", "basis": "user_declared"},
        "subgroup": "total_population", "reference_period": "annee declaree",
        "valid_years": [2023, 2024], "year_evidence": "user_upload_agents",
        "aggregation": {"country_year": "unique_observation", "over_time": "none", "subgroup_rollup": "none"},
        "missing_data_policy": "preserve_missing_v1", "aggregation_policy": "compatible_denominators_v1",
        "traceability_policy": "retain_input_lineage_v1",
        "publication_review_policy": "review_flagged_dependencies_v1", "dependencies": [],
    }
    for key, value in overrides.items():
        kpi[key] = value
    data = {"catalog_id": "biflow_user_kpis",
            "references": {"user_upload_agents": {"path": "data/uploads/agents.csv",
                                                  "locator": "config/sources/agents.yaml, colonne agents",
                                                  "evidence": "fichier depose, unite declaree count"}},
            "kpis": {overrides.pop("kpi_id", "agents_count"): kpi}}
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_user_catalog_is_merged_without_touching_official_identity(tmp_path, monkeypatch):
    official = load_catalog()
    monkeypatch.setenv("BIFLOW_USER_CATALOG", str(user_catalog(tmp_path / "u.yaml")))
    merged = load_catalog()
    assert merged["catalog_version"] == official["catalog_version"]
    assert set(merged["kpis"]) == set(official["kpis"]) | {"agents_count"}


@pytest.mark.parametrize("override,message", [
    ({"verification": {"status": "verified", "evidence": ["user_upload_agents"]}}, "Unsupported calculation contract"),
    ({"formula": {"from_fact": "100 * value"}}, "Unsupported calculation contract"),
    ({"warehouse": {"fact_table": "fact", "indicator_code": "account_t_d", "source": "findex", "input_unit": "fraction",
                    "dimension": "all", "dimension_value": "all"}}, "Unsupported calculation contract"),
])
def test_user_catalog_contract_is_restricted(tmp_path, monkeypatch, override, message):
    monkeypatch.setenv("BIFLOW_USER_CATALOG", str(user_catalog(tmp_path / "u.yaml", **override)))
    with pytest.raises(CatalogError, match=message):
        load_catalog()


def test_user_catalog_cannot_redefine_official_kpi(tmp_path, monkeypatch):
    path = user_catalog(tmp_path / "u.yaml")
    path.write_text(path.read_text(encoding="utf-8").replace("agents_count:", "account_ownership:"), encoding="utf-8")
    monkeypatch.setenv("BIFLOW_USER_CATALOG", str(path))
    with pytest.raises(CatalogError, match="redefines official identifiers"):
        load_catalog()


# --------------------------------------------------------------------------- bout en bout
def test_end_to_end_user_indicator_through_etl_kpi_and_audit(tmp_path, monkeypatch):
    (tmp_path / "raw").mkdir()
    cfg = full_cfg(tmp_path)
    add_user_source(tmp_path, cfg, monkeypatch, text="pays;annee;agents;succursales\n"
                    "Tunisie;2023;1 200,5;45\nMaroc;2023;980;30\nTunisie;2024;1 310;47\nAlgerie;2024;640,25;20\n")
    catalog = user_catalog(tmp_path / "kpi_catalog.user.yaml")
    monkeypatch.setenv("BIFLOW_USER_CATALOG", str(catalog))
    state = graph.run_pipeline(cfg=cfg, run_id="e2e", use_llm=False)
    assert state["status"] == "success" and state["snapshot"]["status"] == "published"
    audit = state["audit"]
    assert audit["verdict"] != "fail", [c for c in audit["checks"] if c["result"] == "fail"]
    with duckdb.connect(str(tmp_path / "processed" / "warehouse.duckdb"), read_only=True) as con:
        rows = {(i, y): (v, s, list(r), u) for i, y, v, s, r, u in con.execute(
            "SELECT iso3, year, value, publication_status, review_reasons, user_catalog_sha256 FROM kpi_values "
            "WHERE kpi_id = 'agents_count'").fetchall()}
        explanation = json.loads(con.execute(
            "SELECT explanation FROM kpi_explanations WHERE kpi_id='agents_count' AND iso3='TUN' AND year=2023"
        ).fetchone()[0])
    value, status, reasons, user_sha = rows[("TUN", 2023)]
    assert value == 1200.5 and status == "approved_with_review_note"  # valeur du fichier, sans x100
    assert "user_provided_source" in reasons and len(user_sha) == 64
    assert rows[("MAR", 2023)][0] == 980.0 and rows[("EGY", 2023)][0] is None  # absent : NULL
    assert rows[("PEERS", 2024)][0] == 640.25  # moyenne simple des pairs disponibles (DZA)
    raw = explanation["inputs"][0]["raw"]
    assert raw["source"] == "user:agents" and raw["raw_value_text"] == "1 200,5"
    assert raw["record_key"] == {"line": 2, "column": "agents", "country": "Tunisie"}
    checks = {c["check_id"]: c for c in audit["checks"]}
    assert checks["A5_raw_to_fact"]["result"] == "pass" and checks["A6_user_source_facts"]["result"] == "pass"
    assert checks["B8_catalog_definitions"]["result"] == "pass"


def test_tampered_user_fact_is_caught_by_the_audit(tmp_path, monkeypatch):
    (tmp_path / "raw").mkdir()
    cfg = full_cfg(tmp_path)
    add_user_source(tmp_path, cfg, monkeypatch)
    monkeypatch.setenv("BIFLOW_USER_CATALOG", str(user_catalog(tmp_path / "kpi_catalog.user.yaml")))
    state = graph.run_pipeline(cfg=cfg, run_id="clean", use_llm=False, stop="semantic_kpi")
    with duckdb.connect(str(tmp_path / "processed" / "warehouse.duckdb")) as con:
        con.execute("UPDATE fact SET value = value * 100 WHERE source = 'user:agents' AND iso3 = 'MAR'")
    from biflow.agents.auditor import AuditorAgent
    audit = AuditorAgent(cfg=cfg, run_id="clean").execute(state)["audit"]
    failing = {c["check_id"] for c in audit["checks"] if c["result"] == "fail"}
    assert {"A6_user_source_facts", "B7_warehouse_content_digest"} <= failing
