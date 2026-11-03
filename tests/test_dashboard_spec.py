"""Finova contract v2.0: deterministic values, fail-closed validation, history."""
import json

import duckdb
import pytest
from pydantic import ValidationError

from biflow.tools.analysis import AnalysisRequest, AnalysisService
from biflow.tools.dashboard_spec import (
    PAGE_IDS, SCHEMA_VERSION, SPEC_KPIS, build_finova_spec, diff_snapshots, format_value,
    load_reference, snapshot_from_spec, validate_spec,
)
from biflow.tools.warehouse_reader import WarehouseReader

PEERS = {
    "TUN": 0.3784, "DZA": 0.353, "EGY": 0.431, "JOR": 0.465, "MAR": 0.444,
}


def _row(iso3, year, source, indicator, dimension, value, unit="fraction",
         dimension_value=None):
    return (
        iso3, year, source, indicator, dimension,
        dimension_value if dimension_value is not None else dimension, value, unit,
    )


@pytest.fixture(scope="module")
def finova_warehouse(tmp_path_factory):
    path = tmp_path_factory.mktemp("finova") / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE country_dim (iso3 VARCHAR, country VARCHAR, region VARCHAR, "
            "income_group VARCHAR, is_country BOOLEAN, is_aggregate BOOLEAN)"
        )
        con.executemany(
            "INSERT INTO country_dim VALUES (?, ?, ?, ?, true, false)",
            [(code, code.title(), "MENA", "LMIC") if code != "TUN"
             else ("TUN", "Tunisia", "MENA", "LMIC") for code in PEERS],
        )
        con.execute("CREATE TABLE country_year (iso3 VARCHAR, year INTEGER, gdp_pc DOUBLE)")
        con.execute("INSERT INTO country_year VALUES ('TUN', 2024, 4213.0)")
        con.execute(
            "CREATE TABLE fact (iso3 VARCHAR, year INTEGER, source VARCHAR, "
            "indicator_code VARCHAR, dimension VARCHAR, dimension_value VARCHAR, "
            "value DOUBLE, unit VARCHAR)"
        )
        rows = []
        for code, value in PEERS.items():
            rows.append(_row(code, 2024, "findex", "account_t_d", "all", value,
                             dimension_value="all"))
        rows += [
            _row("TUN", 2021, "findex", "account_t_d", "all", 0.3691, dimension_value="all"),
            _row("TUN", 2017, "findex", "account_t_d", "all", 0.3691, dimension_value="all"),
            _row("TUN", 2024, "findex", "g20_any", "all", 0.2368, dimension_value="all"),
            _row("TUN", 2024, "findex", "save_any_t_d", "all", 0.216, dimension_value="all"),
            _row("TUN", 2024, "findex", "borrow_any_t_d", "all", 0.035, dimension_value="all"),
            _row("TUN", 2024, "findex", "fin17a", "all", 0.216, dimension_value="all"),
            _row("TUN", 2024, "findex", "fin22a", "all", 0.035, dimension_value="all"),
            _row("TUN", 2024, "findex", "fin24aP", "all", 0.8839, dimension_value="all"),
            _row("TUN", 2024, "fas", "branch_density", "bank_type", 22.37,
                 "per_100k_adults", "commercial_banks"),
            _row("TUN", 2017, "fas", "atm_density", "bank_type", 30.0,
                 "per_100k_adults", "commercial_banks"),
            _row("TUN", 2024, "fas", "atm_density", "bank_type", 35.44,
                 "per_100k_adults", "commercial_banks"),
            _row("TUN", 2018, "fas", "depositors_per_1k", "bank_type", 1063.3,
                 "per_1k_adults", "commercial_banks"),
            _row("TUN", 2024, "fas", "borrowers_per_1k", "bank_type", 82.1,
                 "per_1k_adults", "commercial_banks"),
            _row("TUN", 2024, "fas", "loans_pct_gdp", "bank_type", 67.8,
                 "percent_of_gdp", "commercial_banks"),
            _row("TUN", 2024, "fas", "deposits_pct_gdp", "bank_type", 58.2,
                 "percent_of_gdp", "commercial_banks"),
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
        con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return path


def _service(warehouse, tmp_path):
    return AnalysisService(
        warehouse,
        lineage_path=tmp_path / "lineage.json",
        quality_report_path=tmp_path / "quality_report.json",
    )


@pytest.fixture(scope="module")
def dataset(finova_warehouse, tmp_path_factory):
    request = AnalysisRequest(
        iso3=("TUN", "DZA", "EGY", "JOR", "MAR"), mode="year", year=2024,
        kpi_ids=SPEC_KPIS,
    )
    return _service(finova_warehouse, tmp_path_factory.mktemp("finova_prov")).build(request)


@pytest.fixture(scope="module")
def spec(dataset, finova_warehouse):
    reader = WarehouseReader(finova_warehouse)
    return build_finova_spec(
        dataset, run_id="spec_test", reader=reader, reference=load_reference(),
    )


def test_spec_exposes_six_pages_and_never_approves(spec):
    assert spec.schema_version == SCHEMA_VERSION == "2.0"
    assert tuple(page.id for page in spec.pages) == PAGE_IDS
    assert spec.publication_status == "not_evaluated"
    assert spec.country.iso3 == "TUN" and spec.country.name == "Tunisie"
    assert spec.page("poverty").available is True
    assert any(notice.code == "publication_not_evaluated" for notice in spec.notices)


def test_catalog_values_deltas_and_review_flags(spec):
    account = spec.metric("account_ownership")
    assert account.value == pytest.approx(37.84)
    assert account.display == "37.8 %"
    assert account.provider == "semantic"
    assert account.delta is not None
    assert account.delta.unit == "percentage_points"
    assert account.delta.from_year == 2021 and account.delta.to_year == 2024
    assert account.delta.value == pytest.approx(0.93, abs=1e-9)

    saving = spec.metric("saving_rate")
    assert saving.chip.requires_review is True  # provenance absente dans cette fixture
    assert "provisional_definition" not in saving.chip.review_reasons  # catalogue 1.3.0 : verifie
    assert saving.label == "Épargne (toute forme)"
    assert saving.chip.note == "Définition catalogue v1.4.0 appliquée au warehouse."

    emergency = spec.metric("emergency_money")
    # catalogue 1.4.0 : KPI emergency_funds (fin24aP), identifiant du widget inchange
    assert emergency.provider == "semantic" and emergency.chip.provider == "semantic"
    assert emergency.evidence_ids == ("EV-emergency_funds-TUN-2024",)
    assert emergency.value == pytest.approx(88.39)
    # libelle du dictionnaire corrige (glossaire Findex 2025) : plus de signalement d'ecart
    assert emergency.label == "Fonds d'urgence en 30 jours : possible"
    assert "dictionary_label_mismatch" not in emergency.chip.review_reasons
    codes = {notice.code for notice in spec.notices}
    assert "fin24aP_definition" not in codes
    # toutes les series affichees sont au catalogue : plus de notice « hors catalogue »
    assert "warehouse_not_in_catalog" not in codes


def test_warehouse_series_keep_their_observed_year(spec):
    atm = spec.metric("atm_per_100k")
    assert atm.value == pytest.approx(35.44) and atm.year == 2024
    depositors = spec.metric("depositors_per_1k")
    assert depositors.value == pytest.approx(1063.3) and depositors.year == 2018
    assert "série arrêtée" in (depositors.caveat or "")
    assert depositors.evidence_ids == ("EV-depositors_per_1k-TUN-2018",)
    loans = spec.metric("loans_pct_gdp")
    assert loans.value == pytest.approx(67.8) and loans.year == 2024
    assert any(notice.code == "loans_pct_gdp_now_available" for notice in spec.notices)
    # catalogue 1.4.0 : memes widgets, valeurs lues via les KPI (chip du catalogue)
    access = spec.page("access")
    assert {m.id: m.provider for m in access.metrics} == {
        "atm_per_100k": "semantic", "branch_density": "semantic", "depositors_per_1k": "semantic",
        "borrowers_per_1k": "semantic", "loans_pct_gdp": "semantic", "deposits_pct_gdp": "semantic"}
    charts = {chart.id: chart for chart in access.charts}
    assert all(series.provider == "semantic" for series in charts["physical_network"].series)
    assert {bar.provider for bar in charts["atm_peers"].bars} == {"semantic"}
    assert all(m.chip.label.startswith("KPI catalog") for m in access.metrics)


def test_subgroups_and_gaps_come_from_catalog_kpis(spec):
    inclusion = spec.page("inclusion")
    dumbbell = next(chart for chart in inclusion.charts if chart.id == "account_ownership_groups")
    gender = next(group for group in dumbbell.groups if group.dimension == "gender").rows[0]
    assert gender.provider == "semantic"
    assert (gender.left.value, gender.right.value) == (pytest.approx(26.6), pytest.approx(49.6))
    assert gender.gap_pp == pytest.approx(23.0)  # lu dans gender_gap
    assert gender.evidence_ids == ("EV-account_ownership_women-TUN-2024",
                                   "EV-account_ownership_men-TUN-2024", "EV-gender_gap-TUN-2024")
    facts = {fact.id: fact for fact in spec.facts}
    assert facts["F-gap-gender-TUN-2024"].provider == "semantic"
    assert facts["F-gap-gender-TUN-2024"].evidence_ids == ("EV-gender_gap-TUN-2024",)
    assert facts["F-gender-femmes-TUN-2024"].evidence_ids == ("EV-account_ownership_women-TUN-2024",)
    exclusion = spec.page("exclusion")
    rural = next(metric for metric in exclusion.metrics if metric.id == "rural_account")
    assert rural.provider == "semantic" and rural.value == pytest.approx(30.2)
    assert rural.evidence_ids == ("EV-account_ownership_rural-TUN-2024",)


def test_peers_reference_lines_and_placeholders(spec):
    peers = spec.page("overview").charts[1]
    values = {bar.iso3: bar.value for bar in peers.bars}
    assert values["MAR"] == pytest.approx(44.4)
    assert values["DZA"] == pytest.approx(35.3)
    assert "Écart calculé Maroc − Tunisie" in " ".join(peers.notes)

    history = spec.page("overview").charts[0]
    assert [line.value for line in history.reference_lines] == pytest.approx([
        52.9089186737193, 70.38717, 78.74240,
    ])
    heatmap = spec.page("exclusion").charts[0]
    assert heatmap.kind == "heatmap"
    assert {cell.display for cell in heatmap.cells} == {"To load"}


def test_facts_are_unique_and_numbered(spec):
    ids = [fact.id for fact in spec.facts]
    assert len(ids) == len(set(ids))
    codes = {fact.code for fact in spec.facts}
    assert {"gender_femmes", "gap_gender", "gap_change_gender"} <= codes
    rural_poverty = next(fact for fact in spec.facts if fact.code == "poverty_rate_rural_2021")
    assert rural_poverty.value == pytest.approx(24.8)


def test_formal_saving_and_borrowing_come_from_the_catalog_with_stable_widget_ids(spec):
    inclusion = spec.page("inclusion")
    charts = {chart.id: chart for chart in inclusion.charts}
    steps = {step.id: step for step in charts["inclusion_funnel"].steps}
    bars = {bar.id: bar for bar in charts["formal_vs_any"].bars}
    for widget, kpi, value in (("formal_saving", "formal_saving_rate", 21.6),
                               ("formal_borrowing", "formal_borrowing_rate", 3.5)):
        for item in (steps[widget], bars[widget]):
            assert item.provider == "semantic" and item.chip.provider == "semantic"
            assert item.value == pytest.approx(value)
            assert item.evidence_ids == (f"EV-{kpi}-TUN-2024",)
    # seules les mesures « toute forme » restent mises en avant
    assert [bar.id for bar in charts["formal_vs_any"].bars if bar.highlight] == ["saving_rate", "borrowing_rate"]


def test_delta_fact_cites_both_years_and_the_baseline_is_a_fact(spec):
    delta = next(fact for fact in spec.facts if fact.code == "account_ownership_delta")
    assert delta.evidence_ids == ("EV-account_ownership-TUN-2024", "EV-account_ownership-TUN-2021")
    baseline = next(fact for fact in spec.facts if fact.id == "F-account_ownership-TUN-2021")
    assert baseline.provider == "semantic" and baseline.year == 2021
    assert baseline.value == pytest.approx(36.91)  # lu dans la serie, aucun calcul
    assert baseline.evidence_ids == ("EV-account_ownership-TUN-2021",)


def test_history_diff_is_stable_then_changed(spec):
    snapshot = snapshot_from_spec(spec)
    stable = diff_snapshots(spec, snapshot)
    assert stable.available is True
    assert all(item.status == "stable" for item in stable.items)
    modified = json.loads(json.dumps(snapshot))
    modified["metrics"]["account_ownership"]["value"] += 1.0
    changed = diff_snapshots(spec, modified)
    item = next(item for item in changed.items if item.metric_id == "account_ownership")
    assert item.status == "changed" and item.delta == pytest.approx(-1.0)
    assert diff_snapshots(spec, {**snapshot, "iso3": "MAR"}).available is False


def test_unknown_fact_reference_fails_closed(spec):
    payload = spec.model_dump(mode="json")
    payload["pages"][0]["insights"] = [{
        "id": "bad", "code": "bad", "statement": "Un constat non verifie.",
        "severity": "info", "kind": "auto", "evidence_ids": ["F-does-not-exist"],
    }]
    with pytest.raises(ValidationError):
        validate_spec(payload)


@pytest.mark.parametrize("value,unit,expected", [
    (37.84, "percent", "37.8 %"),
    (1.04, "percentage_points", "+1.0 pt"),
    (35.44, "per_100k_adults", "35.44 / 100k adultes"),
    (3.107, "TND_per_USD", "3.107 TND/USD"),
    (119.0, "index_2017_100", "119.0"),
    (None, "percent", "Indisponible"),
])
def test_format_value(value, unit, expected):
    assert format_value(value, unit) == expected
