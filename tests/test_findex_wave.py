"""Annees sans enquete Findex : derniere vague anterieure, FAS a l'annee choisie."""
import duckdb
import pytest

from biflow.tools.analysis import (
    AnalysisRequest, AnalysisService, build_with_findex_wave, findex_wave,
)
from biflow.tools.dashboard_spec import SPEC_KPIS, build_finova_spec, load_reference
from biflow.tools.warehouse_reader import WarehouseReader

CODES = ("TUN", "DZA", "EGY", "JOR", "MAR")


def _row(iso3, year, source, indicator, dimension, value, unit="fraction", dimension_value=None):
    return (iso3, year, source, indicator, dimension,
            dimension_value if dimension_value is not None else dimension, value, unit)


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    path = tmp_path_factory.mktemp("wave") / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE country_dim (iso3 VARCHAR, country VARCHAR, region VARCHAR, "
                    "income_group VARCHAR, is_country BOOLEAN, is_aggregate BOOLEAN)")
        con.executemany("INSERT INTO country_dim VALUES (?, ?, 'MENA', 'LMIC', true, false)",
                        [(code, code.title()) for code in CODES])
        con.execute("CREATE TABLE country_year (iso3 VARCHAR, year INTEGER, gdp_pc DOUBLE)")
        con.execute("CREATE TABLE fact (iso3 VARCHAR, year INTEGER, source VARCHAR, "
                    "indicator_code VARCHAR, dimension VARCHAR, dimension_value VARCHAR, "
                    "value DOUBLE, unit VARCHAR)")
        rows = [
            # DZA : vagues 2011, 2017, 2021 ; TUN : premiere vague 2014
            _row("DZA", 2011, "findex", "account_t_d", "all", 0.333, dimension_value="all"),
            _row("DZA", 2017, "findex", "account_t_d", "all", 0.429, dimension_value="all"),
            _row("DZA", 2021, "findex", "account_t_d", "all", 0.441, dimension_value="all"),
            _row("DZA", 2021, "findex", "fin24aP", "all", 0.874, dimension_value="all"),
            _row("EGY", 2011, "findex", "account_t_d", "all", 0.097, dimension_value="all"),
            _row("TUN", 2014, "findex", "account_t_d", "all", 0.271, dimension_value="all"),
            *[_row("DZA", year, "fas", "atm_density", "bank_type", value,
                   "per_100k_adults", "commercial_banks")
              for year, value in ((2012, 6.17), (2021, 11.5), (2023, 12.02))],
            _row("TUN", 2012, "fas", "atm_density", "bank_type", 22.18,
                 "per_100k_adults", "commercial_banks"),
        ]
        for year, women, men in ((2011, 0.204, 0.461), (2017, 0.29, 0.56), (2021, 0.31, 0.58)):
            rows += [_row("DZA", year, "findex", "account_t_d", "gender", women, dimension_value="women"),
                     _row("DZA", year, "findex", "account_t_d", "gender", men, dimension_value="men")]
        con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return path


def _spec(warehouse, tmp_path, iso3, year):
    service = AnalysisService(warehouse, lineage_path=tmp_path / "lineage.json",
                              quality_report_path=tmp_path / "quality_report.json")
    request = AnalysisRequest(iso3=(iso3, *(c for c in CODES if c != iso3)), mode="year",
                              year=year, kpi_ids=SPEC_KPIS, series_iso3=(iso3,),
                              include_trends=False, include_rankings=False,
                              include_comparisons=False)
    dataset = build_with_findex_wave(service, request)
    return build_finova_spec(dataset, run_id="wave_test", iso3=iso3, year=year,
                             reader=WarehouseReader(warehouse), reference=load_reference())


def test_wave_is_the_latest_at_or_before_the_year():
    assert findex_wave([2011, 2014, 2017, 2021, 2024], 2012) == 2011
    assert findex_wave([2011, 2014, 2017, 2021, 2024], 2023) == 2021
    assert findex_wave([2011, 2014, 2017, 2021, 2024], 2024) == 2024
    assert findex_wave([2014, 2017], 2013) is None


def test_dza_2012_reads_the_2011_wave(warehouse, tmp_path):
    spec = _spec(warehouse, tmp_path, "DZA", 2012)
    assert spec.year == 2012
    assert (spec.findex_wave.year_requested, spec.findex_wave.year_used) == (2012, 2011)
    account = spec.metric("account_ownership")
    assert account.value == pytest.approx(33.3)
    assert (account.year, account.year_requested, account.year_basis) == (2011, 2012, "survey_wave")
    assert account.evidence_ids == ("EV-account_ownership-DZA-2011",)
    assert account.chip.provider == "semantic"
    assert spec.page("inclusion").available and spec.page("exclusion").available
    row = spec.page("inclusion").charts[[c.id for c in spec.page("inclusion").charts]
                                       .index("account_ownership_groups")].groups[0].rows[0]
    assert (row.year, row.year_requested) == (2011, 2012)
    facts = {fact.id: fact for fact in spec.facts}
    assert facts["F-account_ownership-DZA-2011"].year_requested == 2012
    # aucune valeur d'enquete posterieure a l'annee demandee
    assert all(fact.year <= 2012 for fact in spec.facts
               if fact.provider == "semantic" and fact.year is not None)
    peers = next(c for c in spec.page("overview").charts if c.id == "account_ownership_peers")
    assert peers.notes[0] == ("Comparaison des détentions de compte à l'enquête 2011 "
                              "(pas d'enquête Findex en 2012).")
    # deux vagues anterieures manquent : pas de graphique d'evolution des ecarts
    assert "gap_change" not in {chart.id for chart in spec.page("inclusion").charts}


def test_fas_cards_keep_the_selected_year(warehouse, tmp_path):
    for year, value in ((2012, 6.17), (2023, 12.02)):
        atm = _spec(warehouse, tmp_path, "DZA", year).metric("atm_per_100k")
        assert (atm.value, atm.year, atm.year_requested, atm.year_basis) == (
            pytest.approx(value), year, year, "selected")


def test_dza_2023_reads_the_2021_wave(warehouse, tmp_path):
    spec = _spec(warehouse, tmp_path, "DZA", 2023)
    assert spec.findex_wave.year_used == 2021
    account = spec.metric("account_ownership")
    assert (account.value, account.year, account.year_basis) == (
        pytest.approx(44.1), 2021, "survey_wave")
    gap = next(chart for chart in spec.page("inclusion").charts if chart.id == "gap_change")
    point = next(p for p in gap.gap_points if p.id == "gap-gender")
    assert (point.from_year, point.to_year) == (2017, 2021)


def test_no_earlier_wave_stays_unavailable(warehouse, tmp_path):
    spec = _spec(warehouse, tmp_path, "TUN", 2012)
    assert (spec.findex_wave.year_requested, spec.findex_wave.year_used) == (2012, None)
    account = spec.metric("account_ownership")
    assert account.value is None and account.display == "Indisponible"
    assert (account.year, account.year_basis) == (2012, "selected")
    assert not spec.page("inclusion").available and not spec.page("exclusion").available
    assert spec.metric("atm_per_100k").value == pytest.approx(22.18)


def test_unavailable_emergency_card_shows_the_requested_year(warehouse, tmp_path):
    emergency = _spec(warehouse, tmp_path, "TUN", 2012).metric("emergency_money")
    assert emergency.value is None and emergency.year == 2012


def test_no_earlier_wave_gives_the_specific_reason(warehouse, tmp_path):
    spec = _spec(warehouse, tmp_path, "TUN", 2012)
    for page_id in ("inclusion", "exclusion"):
        assert spec.page(page_id).unavailable_reason == (
            "Aucune enquête Findex en 2012 ni avant pour ce pays (Tunisie) : la première "
            "enquête observée date de 2014. Les indicateurs bancaires annuels restent "
            "disponibles sur la page Accès et crédit.")


def test_poverty_page_is_out_of_scope_by_design_outside_tunisia(warehouse, tmp_path):
    spec = _spec(warehouse, tmp_path, "DZA", 2012)
    poverty = spec.page("poverty")
    assert not poverty.available
    assert poverty.unavailable_reason == (
        "Hors périmètre par conception : les références SMIG et pauvreté INS sont propres "
        "à la Tunisie ; aucune valeur n'est affichée pour ce pays (Algérie).")
    # une annee sans enquete avec vague anterieure n'est jamais « non disponible »
    assert spec.page("inclusion").available and spec.page("exclusion").available


def test_account_history_stops_at_the_wave_used(warehouse, tmp_path):
    for year, last, refs in ((2012, 2011, 0), (2023, 2021, 0)):
        spec = _spec(warehouse, tmp_path, "DZA", year)
        history = next(c for c in spec.page("overview").charts if c.id == "account_ownership_history")
        years = [point.year for point in history.series[0].points]
        assert years and max(years) == last, (year, years)
        assert all(e.endswith(tuple(f"-{y}" for y in range(2000, last + 1))) for e in history.series[0].evidence_ids)
        assert len(history.reference_lines) == refs and "postérieurs à l'enquête" in history.notes[0]
