"""« Vos indicateurs face aux données officielles » : KPI comparable déclaré à l'étape
« Indicateurs » (même unité, même définition cochée) et comparaison en lecture seule."""
from __future__ import annotations

import duckdb
import pytest
import yaml

from biflow.tools.user_sources.comparisons import (
    INDICATIVE, UNIT_MISMATCH, YEARS_DIFFER, comparisons, official_kpis,
)
from biflow.tools.user_sources.data import USER_CHIP, UserData
from tests.test_sources_api import Runner, cfg, make_client, roles_of, upload  # noqa: F401

WIDE = ("Pays;Année;Distributeurs pour 100 000 adultes (exemple fictif);Taux d'usage (exemple fictif)\n"
        "Tunisie;2023;31,5;40\n"
        "Tunisie;2024;33,25;42\n")
ATM = "distributeurs_pour_100_000_adultes_exemple_fictif"
RATE = "taux_d_usage_exemple_fictif"


def dry(client, detected, indicators):
    return client.post("/api/sources/dry-run", json={
        "upload_id": detected["upload_id"], "name": "banque",
        "mapping": {"roles": roles_of(detected), "indicators": indicators}})


# ----------------------------------------------------------- declaration (etape 3)
def test_official_kpis_exclude_user_declared_and_carry_definition():
    kpis = official_kpis()
    assert kpis["atm_density"]["unit"] == "per_100k_adults" and kpis["atm_density"]["definition"]
    assert kpis["account_ownership"]["denominator"]
    assert all(not str(kpi["id"]).startswith("user") for kpi in kpis.values())


def test_comparable_kpi_is_saved_only_with_the_same_definition_tick(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    detected = upload(client, WIDE).json()
    roles = roles_of(detected)
    assert set(roles.values()) >= {"country", "year", "indicator_column"}
    ticked = dry(client, detected, {
        ATM: {"unit": "per_100k_adults", "comparable_kpi": "atm_density", "same_definition": True},
        RATE: {"unit": "percent"}}).json()
    assert {i["code"]: i["comparable_kpi"] for i in ticked["indicators"]} == {ATM: "atm_density", RATE: None}
    unticked = dry(client, detected, {
        ATM: {"unit": "per_100k_adults", "comparable_kpi": "atm_density"}, RATE: {"unit": "percent"}}).json()
    assert {i["code"]: i["comparable_kpi"] for i in unticked["indicators"]} == {ATM: None, RATE: None}


@pytest.mark.parametrize("spec,message", [
    ({"unit": "per_100k_adults", "comparable_kpi": "account_ownership"}, "même unité"),
    ({"unit": "percent", "transform": "percent_to_fraction", "comparable_kpi": "account_ownership"}, "même unité"),
    ({"unit": "per_100k_adults", "comparable_kpi": "kpi_inexistant"}, "KPI officiel inconnu"),
])
def test_comparable_kpi_requires_an_official_kpi_with_the_same_unit(cfg, tmp_path, spec, message):
    client, _ = make_client(cfg, tmp_path)
    detected = upload(client, WIDE).json()
    response = dry(client, detected, {ATM: {**spec, "same_definition": True}, RATE: {"unit": "percent"}})
    assert response.status_code == 400 and message in response.json()["detail"]


def test_confirmed_mapping_keeps_the_comparable_kpi_and_omits_empty_ones(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    detected = upload(client, WIDE).json()
    response = client.post("/api/sources/confirm", json={
        "upload_id": detected["upload_id"], "name": "banque", "mapping": {"roles": roles_of(detected), "indicators": {
            ATM: {"unit": "per_100k_adults", "comparable_kpi": "atm_density", "same_definition": True},
            RATE: {"unit": "percent"}}}})
    assert response.status_code == 200, response.json()
    saved = yaml.safe_load((tmp_path / "sources" / "banque.yaml").read_text(encoding="utf-8"))
    assert saved["indicators"][ATM]["comparable_kpi"] == "atm_density"
    assert "comparable_kpi" not in saved["indicators"][RATE]


# ------------------------------------------------------------- comparaison
@pytest.fixture
def setup(cfg, tmp_path):
    folder = tmp_path / "sources"
    folder.mkdir()
    mapping = {
        "schema_version": 1, "name": "banque", "fingerprint": "b" * 64, "file": "data/uploads/banque.csv",
        "read": {"encoding": "utf-8", "separator": ";", "decimal": ",", "header_row": 0},
        "layout": "wide_by_indicator",
        "columns": {"country": {"column": "Pays", "kind": "name"}, "year": "Année",
                    "indicator_columns": {"a": "atm", "b": "agences", "c": "taux", "d": "sans"}},
        "indicators": {
            "atm": {"label": "Distributeurs (exemple fictif)", "unit": "per_100k_adults", "comparable_kpi": "atm_density"},
            "agences": {"label": "Agences (exemple fictif)", "unit": "per_100k_adults", "comparable_kpi": "branch_density"},
            "taux": {"label": "Taux (exemple fictif)", "unit": "percent", "comparable_kpi": "account_ownership"},
            "sans": {"label": "Sans comparable (exemple fictif)", "unit": "percent"}},
    }
    (folder / "banque.yaml").write_text(yaml.safe_dump(mapping, allow_unicode=True), encoding="utf-8")
    warehouse = tmp_path / "w.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE fact (source VARCHAR, indicator_code VARCHAR, iso3 VARCHAR, year INTEGER, "
                    "dimension VARCHAR, dimension_value VARCHAR, value DOUBLE, unit VARCHAR)")
        con.executemany("INSERT INTO fact VALUES ('user:banque', ?, 'TUN', ?, 'all', 'all', ?, ?)", [
            ("banque.atm", 2024, 33.25, "per_100k_adults"), ("banque.agences", 2023, 21.5, "per_100k_adults"),
            ("banque.taux", 2024, 45.0, "percent"), ("banque.sans", 2024, 12.0, "percent")])
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, value DOUBLE, "
                    "unit VARCHAR, publication_status VARCHAR)")
        con.executemany("INSERT INTO kpi_values VALUES (?, 'TUN', ?, ?, ?, ?)", [
            ("atm_density", 2024, 30.1, "per_100k_adults", "approved"),
            ("branch_density", 2024, 18.2, "per_100k_adults", "approved"),
            ("account_ownership", 2022, 36.9, "percent", "approved_with_review_note"),
            ("account_ownership", 2024, 99.0, "percent", "blocked"),  # jamais citee
        ])
    return UserData({"uploads": {"mappings_dir": str(folder)}}, warehouse), warehouse


def test_same_year_comparison_with_chip_and_definition(setup):
    data, warehouse = setup
    result = comparisons(data, warehouse, "TUN", 2024, official_kpis())
    assert result["note"] == INDICATIVE and result["chip"] == USER_CHIP
    rows = {r["kpi_id"]: r for r in result["rows"]}
    assert set(rows) == {"atm_density", "branch_density", "account_ownership"}  # « sans » : aucun bloc
    atm = rows["atm_density"]
    assert atm["status"] == "ok" and atm["same_year"] and atm["notes"] == []
    assert atm["user"] == {"value": 33.25, "display": "33,25 pour 100 000 adultes", "year": 2024,
                           "unit": "per_100k_adults", "chip": USER_CHIP}
    assert atm["official"]["value"] == 30.1 and atm["official"]["year"] == 2024
    assert atm["definition"] and atm["denominator"]


def test_different_years_are_both_shown_and_labelled(setup):
    data, warehouse = setup
    rows = {r["kpi_id"]: r for r in comparisons(data, warehouse, "TUN", 2024, official_kpis())["rows"]}
    branch = rows["branch_density"]  # utilisateur 2023 (derniere annee anterieure), officiel 2024
    assert (branch["user"]["year"], branch["official"]["year"]) == (2023, 2024)
    assert not branch["same_year"] and branch["notes"] == [YEARS_DIFFER]
    survey = rows["account_ownership"]  # vague 2022 ; la ligne 2024 bloquee n'est jamais lue
    assert survey["official"]["year"] == 2022 and survey["official"]["value"] == 36.9
    assert survey["notes"] == [YEARS_DIFFER]


def test_unit_change_in_the_catalog_shows_no_values(setup):
    data, warehouse = setup
    kpis = official_kpis()
    kpis["atm_density"] = {**kpis["atm_density"], "unit": "count"}
    row = next(r for r in comparisons(data, warehouse, "TUN", 2024, kpis)["rows"] if r["kpi_id"] == "atm_density")
    assert row["status"] == "unit_mismatch" and row["user"] is None and row["official"] is None
    assert row["notes"] == [UNIT_MISMATCH]


def test_missing_values_are_reported_not_estimated(setup):
    data, warehouse = setup
    rows = comparisons(data, warehouse, "TUN", 2023, official_kpis())["rows"]
    by_kpi = {r["kpi_id"]: r for r in rows}
    assert by_kpi["atm_density"]["status"] == "no_user_value" and by_kpi["atm_density"]["user"] is None
    assert by_kpi["branch_density"]["status"] == "no_official_value"


def test_api_endpoints(cfg, tmp_path, setup):
    data, warehouse = setup
    client, _ = make_client({**cfg, "uploads": {**cfg["uploads"], "mappings_dir": str(tmp_path / "sources")}},
                            tmp_path, warehouse=warehouse)
    kpis = client.get("/api/sources/comparable-kpis").json()["kpis"]
    assert {"id", "name_fr", "unit", "definition", "denominator"} <= set(kpis[0])
    body = client.get("/api/sources/comparisons", params={"iso3": "tun", "year": 2024}).json()
    assert body["iso3"] == "TUN" and len(body["rows"]) == 3
    assert client.get("/api/sources/comparisons", params={"iso3": "../x", "year": 2024}).status_code == 422


def test_documented_bank_example_declares_both_comparable_kpis(cfg, tmp_path):
    """docs/examples/banque_fictive_exemple.csv : données fictives, deux indicateurs
    comparables (atm_density, branch_density) et un indicateur en % sans comparable."""
    from biflow.config import ROOT

    content = (ROOT / "docs" / "examples" / "banque_fictive_exemple.csv").read_text(encoding="utf-8")
    assert "FICTIVES" in content.splitlines()[0]
    client, _ = make_client({**cfg, "uploads": {**cfg["uploads"], "max_file_mb": 1}}, tmp_path)
    detected = upload(client, content, filename="banque_fictive_exemple.csv").json()
    labels = [c["name"] for c in detected["columns"] if c["role"] == "indicator_column"]
    assert len(labels) == 3 and all("(exemple fictif)" in label for label in labels)
    codes = {label: label for label in labels}
    first = client.post("/api/sources/dry-run", json={
        "upload_id": detected["upload_id"], "name": "banque_fictive",
        "mapping": {"roles": roles_of(detected)}}).json()
    assert "indicators" in first, first
    by_label = {i["label"]: i["code"] for i in first["indicators"]}
    assert set(by_label) == set(codes)
    atm = next(code for label, code in by_label.items() if label.startswith("Distributeurs"))
    branches = next(code for label, code in by_label.items() if label.startswith("Agences"))
    mobile = next(code for label, code in by_label.items() if label.startswith("Clients"))
    result = client.post("/api/sources/dry-run", json={
        "upload_id": detected["upload_id"], "name": "banque_fictive", "mapping": {
            "roles": roles_of(detected), "indicators": {
                atm: {"unit": "per_100k_adults", "comparable_kpi": "atm_density", "same_definition": True},
                branches: {"unit": "per_100k_adults", "comparable_kpi": "branch_density", "same_definition": True},
                mobile: {"unit": "percent"}}}}).json()
    assert result["blocking"] == [] and result["countries"] == ["MAR", "TUN"]
    assert {i["code"]: i["comparable_kpi"] for i in result["indicators"]} == {
        atm: "atm_density", branches: "branch_density", mobile: None}
