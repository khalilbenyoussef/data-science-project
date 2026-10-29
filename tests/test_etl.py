from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from biflow.agents.base import AgentError
from biflow.config import load_config
from biflow.agents.etl import (
    EtlAgent,
    build_country_dim,
    fas_long,
    findex_long,
    gdp_long,
)
from biflow.tools.dictionary import FAS_LABELS, FINDEX_LABELS


def _write_inputs(tmp_path):
    findex = pd.DataFrame(
        {
            "countrynewwb": ["Morocco", "France", "Morocco", "France"],
            "codewb": ["MAR", "FRA", "MAR", "FRA"],
            "regionwb24_hi": ["MENA", "Europe", "MENA", "Europe"],
            "incomegroupwb24": ["Lower middle", "High", "Lower middle", "High"],
            "year": [2020, 2020, 2021, 2021],
            "pop_adult": [20_000_000, 50_000_000, 20_100_000, 50_100_000],
            "group": ["all"] * 4,
            "group2": ["all"] * 4,
            "account_t_d": [0.5, 0.9, 0.55, 0.91],
            "mobileaccount_t_d": [0.2, 0.3, 0.25, 0.32],
        }
    )
    fas = pd.DataFrame(
        {
            "SERIES_CODE": ["MAR.FA26N.PHTADLT_NUM.A", "FRA.FA26N.PHTADLT_NUM.A"],
            "COUNTRY": ["Morocco", "France"],
            "INDICATOR": ["Number of commercial bank branches"] * 2,
            "UNIT": ["Number"] * 2,
            "2020": [10.0, 30.0],
            "2021": [10.5, 29.5],
        }
    )
    gdp = pd.DataFrame(
        {
            "iso3": ["MAR", "FRA", "MAR", "FRA"],
            "country": ["Morocco", "France", "Morocco", "France"],
            "indicator_code": ["NY.GDP.PCAP.CD"] * 4,
            "indicator_name": ["GDP per capita"] * 4,
            "year": [2020, 2020, 2021, 2021],
            "value": [3000.0, 40000.0, 3100.0, 41000.0],
        }
    )
    paths = {}
    for name, frame in (("findex", findex), ("fas", fas), ("gdp", gdp)):
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = str(path)
    return paths


def _cfg(tmp_path, paths):
    return {
        "paths": {"processed": str(tmp_path / "processed")},
        "etl": {"min_year": 2011, "max_year": 2024, "write_csv_copy": True},
        "sources": {
            "findex": {
                "path": paths["findex"],
                "type": "csv",
                "indicators": ["account_t_d", "mobileaccount_t_d"],
            },
            "fas": {
                "path": paths["fas"],
                "type": "csv",
                "series": {"branch_density": "FA26N.PHTADLT_NUM"},
            },
            "gdp": {"path": paths["gdp"], "type": "csv"},
        },
    }


def _run_agent(tmp_path, paths=None):
    paths = paths or _write_inputs(tmp_path)
    cfg = _cfg(tmp_path, paths)
    out = EtlAgent(cfg=cfg, run_id="test").execute(
        {"sources": cfg["sources"], "raw_paths": paths}
    )
    return out, tmp_path / "processed"


def test_long_transforms_are_canonical(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"])
    fas = pd.read_csv(paths["fas"])
    gdp = pd.read_csv(paths["gdp"])

    fact_findex, population = findex_long(
        findex,
        {"indicators": ["account_t_d", "mobileaccount_t_d"]},
        2011,
        2024,
    )
    fact_fas = fas_long(fas, {"branch_density": "FA26N.PHTADLT_NUM"}, 2011, 2024)
    fact_gdp = gdp_long(gdp, 2011, 2024)

    assert set(fact_findex["indicator_code"]) == {"account_t_d", "mobileaccount_t_d"}
    assert fact_findex["value"].between(0, 1).all()
    assert len(population) == 4
    assert set(fact_fas["indicator_code"]) == {"branch_density"}
    assert fact_fas["unit"].iloc[0] == "per_100k_adults"
    assert set(fact_gdp["source"]) == {"gdp"}


def _fas_percentage_inputs():
    # Include all six existing indicators plus zero and >100% GDP observations.
    specs = {
        "branch_density": ("FA26N.PHTADLT_NUM", "per_100k_adults", 10.0, 10.5),
        "atm_density": ("FA18N.PHTADLT_NUM", "per_100k_adults", 30.0, 31.0),
        "depositors_per_1k": ("FA29N_COMBANK.PTADLT_NUM", "per_1k_adults", 1000.0, 1100.0),
        "borrowers_per_1k": ("FA21N_COMBANK.PTADLT_NUM", "per_1k_adults", 200.0, 250.0),
        "loan_accounts_per_1k": ("LOANACCN_COMBANK.PTADLT_NUM", "per_1k_adults", 500.0, 550.0),
        "deposit_accounts_per_1k": ("FA30N_COMBANK.PTADLT_NUM", "per_1k_adults", 1500.0, 1600.0),
        "deposits_pct_gdp": ("OUTD_COMBANK.POGDP", "percent_of_gdp", 0.0, 125.5),
        "loans_pct_gdp": ("OUTL_COMBANK.POGDP", "percent_of_gdp", 42.75, 110.25),
    }
    rows = [
        {"SERIES_CODE": f"MAR.{series}.A", "COUNTRY": "Morocco",
         "INDICATOR": code, "2020": first, "2021": second}
        for code, (series, unit, first, second) in specs.items()
    ]
    # An unmapped household series must not be mistaken for the total-bank series.
    rows.append({"SERIES_CODE": "MAR.OUTD_COMBANK_S14.POGDP.A", "COUNTRY": "Morocco",
                 "INDICATOR": "Household deposits", "2020": 500.0, "2021": 600.0})
    return pd.DataFrame(rows), specs


def test_fas_gdp_percentage_mappings_preserve_all_indicator_values_and_units():
    raw, specs = _fas_percentage_inputs()
    mapping = load_config()["sources"]["fas"]["series"]
    assert mapping == {code: spec[0] for code, spec in specs.items()}

    fact = fas_long(raw, mapping, 2011, 2024)
    assert len(fact) == 16
    assert set(fact["indicator_code"]) == set(specs)
    assert set(fact["source"]) == {"fas"}
    assert set(fact["dimension_value"]) == {"commercial_banks"}
    for code, (series, unit, first, second) in specs.items():
        rows = fact[fact["indicator_code"] == code].sort_values("year")
        assert rows["year"].tolist() == [2020, 2021]
        assert rows["value"].tolist() == pytest.approx([first, second])
        assert rows["unit"].tolist() == [unit, unit]
        assert rows["indicator_label"].tolist() == [FAS_LABELS[code]] * 2


def test_fas_gdp_percentages_reach_warehouse_fact_and_indicator_dim(tmp_path):
    paths = _write_inputs(tmp_path)
    raw, specs = _fas_percentage_inputs()
    raw.to_csv(paths["fas"], index=False)
    cfg = _cfg(tmp_path, paths)
    cfg["sources"]["fas"]["series"] = load_config()["sources"]["fas"]["series"]
    out = EtlAgent(cfg=cfg, run_id="percent_test").execute(
        {"sources": cfg["sources"], "raw_paths": paths}
    )

    con = duckdb.connect(out["warehouse_path"], read_only=True)
    try:
        fact = con.execute("SELECT * FROM fact WHERE source = 'fas'").df()
        dim = con.execute("SELECT * FROM indicator_dim WHERE source = 'fas'").df()
        branch = con.execute(
            "SELECT brch_per_100k FROM country_year WHERE iso3 = 'MAR' AND year = 2021"
        ).fetchone()[0]
    finally:
        con.close()
    assert branch == 10.5
    assert set(dim["indicator_code"]) == set(specs)
    parquet = pd.read_parquet(tmp_path / "processed" / "fact_inclusion.parquet")
    for frame in (fact, parquet[parquet["source"] == "fas"]):
        assert len(frame) == 16
        for code, (series, unit, first, second) in specs.items():
            rows = frame[frame["indicator_code"] == code].sort_values("year")
            assert rows["value"].tolist() == pytest.approx([first, second])
            assert rows["unit"].tolist() == [unit, unit]
    for code in ("deposits_pct_gdp", "loans_pct_gdp"):
        row = dim[dim["indicator_code"] == code].iloc[0]
        assert row["unit"] == "percent_of_gdp"
        assert row["indicator_label"] == FAS_LABELS[code]
        assert row["dimension"] == "bank_type"


def test_etl_agent_builds_star_schema(tmp_path):
    out, processed = _run_agent(tmp_path)
    assert (processed / "fact_inclusion.parquet").exists()
    assert (processed / "warehouse.duckdb").exists()
    year = pd.read_parquet(processed / "country_year.parquet")

    assert set(year["iso3"]) == {"MAR", "FRA"}
    maroc = year[(year["iso3"] == "MAR") & (year["year"] == 2021)].iloc[0]
    assert round(maroc["account_own"], 2) == 55.0
    assert round(maroc["brch_per_100k"], 2) == 10.5
    assert round(maroc["gdp_pc"], 1) == 3100.0
    assert out["warehouse_path"].endswith("warehouse.duckdb")
    assert (processed / "country_year.csv").exists()
    assert (processed / "population.parquet").exists()
    assert (processed / "lineage.json").exists()


@pytest.mark.parametrize("digital_account,payment", [
    (0.2, 0.7), (None, 0.7), (0.2, None), (0.0, 1.0),
])
def test_findex_digital_accounts_and_payments_have_distinct_mappings(
    tmp_path, digital_account, payment,
):
    paths = _write_inputs(tmp_path)
    raw = pd.read_csv(paths["findex"])
    raw["dig_acc"] = digital_account
    raw["g20_any"] = payment
    raw.to_csv(paths["findex"], index=False)
    cfg = _cfg(tmp_path, paths)
    cfg["sources"]["findex"]["indicators"] += ["dig_acc", "g20_any"]
    assert {"dig_acc", "g20_any"} <= set(load_config()["sources"]["findex"]["indicators"])
    assert FINDEX_LABELS["dig_acc"] == "Detention d'un compte permettant des paiements numeriques"
    assert FINDEX_LABELS["g20_any"] == "Paiement numerique effectue ou recu dans l'annee"

    out = EtlAgent(cfg=cfg, run_id="digital_test").execute(
        {"sources": cfg["sources"], "raw_paths": paths}
    )
    con = duckdb.connect(out["warehouse_path"], read_only=True)
    try:
        fact = con.execute("SELECT * FROM fact WHERE source = 'findex'").df()
        year = con.execute("SELECT * FROM country_year").df()
        dim = con.execute("SELECT * FROM indicator_dim WHERE source = 'findex'").df()
    finally:
        con.close()
    assert "remittance_use" not in year.columns
    for code, column, value in [
        ("dig_acc", "digitally_enabled_account", digital_account),
        ("g20_any", "digital_payment", payment),
    ]:
        observations = fact[fact["indicator_code"] == code]
        if value is None:
            assert observations.empty
            assert year[column].isna().all()
        else:
            assert observations["value"].tolist() == pytest.approx([value] * 4)
            assert set(observations["unit"]) == {"fraction"}
            assert set(observations["indicator_label"]) == {FINDEX_LABELS[code]}
            assert year[column].tolist() == pytest.approx([100 * value] * 4)
            metadata = dim[dim["indicator_code"] == code]
            assert set(metadata["indicator_label"]) == {FINDEX_LABELS[code]}
            assert set(metadata["unit"]) == {"fraction"}
    maroc = year[(year["iso3"] == "MAR") & (year["year"] == 2021)].iloc[0]
    assert maroc["account_own"] == pytest.approx(55.0)
    exported = pd.read_parquet(tmp_path / "processed" / "country_year.parquet")
    pd.testing.assert_frame_equal(
        year.sort_values(["iso3", "year"]).reset_index(drop=True),
        exported.sort_values(["iso3", "year"]).reset_index(drop=True),
    )


def test_formal_saving_and_borrowing_are_pivoted_separately_from_any(tmp_path):
    paths = _write_inputs(tmp_path)
    raw = pd.read_csv(paths["findex"])
    raw["save_any_t_d"] = 0.6
    raw["fin17a"] = 0.2
    raw["borrow_any_t_d"] = 0.5
    raw["fin22a"] = [0.04, None, 0.05, None]
    raw.to_csv(paths["findex"], index=False)
    cfg = _cfg(tmp_path, paths)
    cfg["sources"]["findex"]["indicators"] += ["save_any_t_d", "fin17a", "borrow_any_t_d", "fin22a"]
    EtlAgent(cfg=cfg, run_id="formal").execute({"sources": cfg["sources"], "raw_paths": paths})
    year = pd.read_parquet(tmp_path / "processed" / "country_year.parquet").set_index(["iso3", "year"])
    assert year.loc[("MAR", 2021), "savings"] == pytest.approx(60.0)
    assert year.loc[("MAR", 2021), "formal_saving"] == pytest.approx(20.0)
    assert year.loc[("MAR", 2021), "borrowing"] == pytest.approx(50.0)
    assert year.loc[("MAR", 2021), "formal_borrowing"] == pytest.approx(5.0)
    assert pd.isna(year.loc[("FRA", 2021), "formal_borrowing"])


def test_indicator_dim_table_is_created_and_matches_parquet(tmp_path):
    _, processed = _run_agent(tmp_path)
    con = duckdb.connect(str(processed / "warehouse.duckdb"), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert "indicator_dim" in tables
        rows = con.execute("SELECT count(*) FROM indicator_dim").fetchone()[0]
        columns = [row[0] for row in con.execute("DESCRIBE indicator_dim").fetchall()]
    finally:
        con.close()
    parquet = pd.read_parquet(processed / "indicator_dim.parquet")
    assert rows == len(parquet)
    assert columns == list(parquet.columns)
    assert {"source", "indicator_code", "indicator_label", "unit", "dimension"} <= set(
        columns
    )


def test_missing_required_columns_raise(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"])
    fas = pd.read_csv(paths["fas"])
    gdp = pd.read_csv(paths["gdp"])

    with pytest.raises(AgentError, match="colonnes obligatoires"):
        findex_long(
            findex.drop(columns=["codewb"]),
            {"indicators": ["account_t_d"]},
            2011,
            2024,
        )
    with pytest.raises(AgentError, match="colonnes obligatoires"):
        fas_long(fas.drop(columns=["SERIES_CODE"]), {"branch_density": "FA26N.PHTADLT_NUM"}, 2011, 2024)
    with pytest.raises(AgentError, match="colonnes obligatoires"):
        gdp_long(gdp.drop(columns=["iso3"]), 2011, 2024)


def test_optional_columns_have_safe_fallbacks(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"]).drop(
        columns=["pop_adult", "countrynewwb"]
    )
    fas = pd.read_csv(paths["fas"]).drop(columns=["COUNTRY", "INDICATOR", "UNIT"])
    gdp = pd.read_csv(paths["gdp"]).drop(columns=["country", "indicator_name"])

    fact_findex, population = findex_long(
        findex, {"indicators": ["account_t_d"]}, 2011, 2024
    )
    fact_fas = fas_long(fas, {"branch_density": "FA26N.PHTADLT_NUM"}, 2011, 2024)
    fact_gdp = gdp_long(gdp, 2011, 2024)

    assert list(population.columns) == ["iso3", "year", "pop_adult"]
    assert population.empty
    assert fact_findex["country"].isna().all()
    assert fact_fas["indicator_label"].iloc[0] == FAS_LABELS["branch_density"]
    assert fact_fas["unit"].iloc[0] == "per_100k_adults"
    assert fact_gdp["indicator_label"].notna().all()
    assert fact_gdp["country"].isna().all()


def test_invalid_year_and_value_are_counted(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"])
    findex["year"] = findex["year"].astype(object)
    findex["account_t_d"] = findex["account_t_d"].astype(object)
    findex.loc[0, "year"] = "not-a-year"
    findex.loc[1, "account_t_d"] = "not-a-number"
    report = {}

    fact, population = findex_long(
        findex, {"indicators": ["account_t_d"]}, 2011, 2024, report=report
    )

    assert "not-a-year" not in set(fact["year"].astype(str))
    assert report["rejected"]["findex"]["year_non_numeric"] == 1
    assert report["rejected"]["findex"]["value_non_numeric"] == 1
    assert population["pop_adult"].notna().all()


def test_invalid_and_unknown_iso3_are_traced(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"])
    findex.loc[0, "codewb"] = "M"
    findex.loc[1, "codewb"] = "XYZ"
    report = {}

    fact, _ = findex_long(
        findex, {"indicators": ["account_t_d"]}, 2011, 2024, report=report
    )
    country_dim = build_country_dim(findex, pd.read_csv(paths["fas"]), pd.read_csv(paths["gdp"]))

    assert "M" not in set(fact["iso3"])
    assert "XYZ" in set(fact["iso3"])
    assert report["rejected"]["findex"]["iso3_invalid"] == 1
    row = country_dim[country_dim["iso3"] == "XYZ"].iloc[0]
    assert not bool(row["is_country"])
    assert not bool(row["is_aggregate"])


def test_missing_country_codes_never_reach_warehouse(tmp_path):
    paths = _write_inputs(tmp_path)
    frames = {name: pd.read_csv(path) for name, path in paths.items()}
    missing_codes = [None, float("nan"), pd.NA, "", " \t", "nan", "<NA>"]
    malformed_codes = ["M", "12A", "TOOLONG"]
    for name, frame in frames.items():
        column = {"findex": "codewb", "fas": "SERIES_CODE", "gdp": "iso3"}[name]
        extra = []
        for code in missing_codes + malformed_codes + [" kos ", "wbg"]:
            row = frame.iloc[0].to_dict()
            # FAS has both missing SERIES_CODE cells and missing/malformed prefixes.
            row[column] = (
                f"{code}.FA26N.PHTADLT_NUM.A"
                if name == "fas" and isinstance(code, str)
                else code
            )
            extra.append(row)
        frames[name] = pd.concat([frame, pd.DataFrame(extra)], ignore_index=True)

    report = {}
    findex, population = findex_long(
        frames["findex"], {"indicators": ["account_t_d", "mobileaccount_t_d"]},
        2011, 2024, report=report,
    )
    fas = fas_long(frames["fas"], {"branch_density": "FA26N.PHTADLT_NUM"}, 2011, 2024)
    gdp = gdp_long(frames["gdp"], 2011, 2024)
    dim = build_country_dim(frames["findex"], frames["fas"], frames["gdp"])
    expected = {"MAR", "FRA", "XKX", "PSE"}
    for frame in (findex, population, fas, gdp, dim):
        assert set(frame["iso3"]) == expected
        assert frame["iso3"].notna().all()
    assert report["rejected"]["findex"]["iso3_missing"] == len(missing_codes)
    assert report["rejected"]["findex"]["iso3_invalid"] == len(malformed_codes)

    # Only synthetic inputs and warehouse outputs under pytest's temporary directory.
    for name, frame in frames.items():
        frame.to_csv(paths[name], index=False)
    _, processed = _run_agent(tmp_path, paths)
    con = duckdb.connect(str(processed / "warehouse.duckdb"), read_only=True)
    try:
        for table in ("fact", "country_dim", "population", "country_year"):
            codes = con.execute(f"SELECT DISTINCT iso3 FROM {table}").fetchall()
            assert {row[0] for row in codes} == expected
    finally:
        con.close()
    for filename in ("fact_inclusion", "country_dim", "population", "country_year"):
        assert set(pd.read_parquet(processed / f"{filename}.parquet")["iso3"]) == expected


def test_exact_duplicates_are_removed_but_conflicts_are_rejected(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"])
    duplicate = findex.iloc[[0]].copy()
    report = {}

    fact, _ = findex_long(
        pd.concat([findex, duplicate], ignore_index=True),
        {"indicators": ["account_t_d"]},
        2011,
        2024,
        report=report,
    )
    assert report["rejected"]["findex"]["exact_duplicates_removed"] == 1
    assert len(fact) == 4

    conflicting = duplicate.copy()
    conflicting.loc[:, "account_t_d"] = 0.6
    with pytest.raises(AgentError, match="doublons conflictuels"):
        findex_long(
            pd.concat([findex, conflicting], ignore_index=True),
            {"indicators": ["account_t_d"]},
            2011,
            2024,
        )


def test_findex_fraction_and_percent_inputs_give_same_percent_output(tmp_path):
    paths = _write_inputs(tmp_path)
    fraction = pd.read_csv(paths["findex"])
    percent = fraction.copy()
    percent["account_t_d"] = percent["account_t_d"] * 100

    report = {}
    fact_fraction, _ = findex_long(
        fraction, {"indicators": ["account_t_d"]}, 2011, 2024
    )
    fact_percent, _ = findex_long(
        percent, {"indicators": ["account_t_d"]}, 2011, 2024, report=report
    )

    assert fact_fraction["value"].between(0, 1).all()
    assert fact_percent["value"].between(0, 1).all()
    assert fact_fraction["value"].tolist() == pytest.approx(
        fact_percent["value"].tolist()
    )
    assert any("pourcentage" in message for message in report["warnings"])

    paths_percent = dict(paths)
    percent.to_csv(paths_percent["findex"], index=False)
    _, processed = _run_agent(tmp_path, paths_percent)
    year = pd.read_parquet(processed / "country_year.parquet")
    maroc = year[(year["iso3"] == "MAR") & (year["year"] == 2021)].iloc[0]
    assert round(maroc["account_own"], 2) == 55.0


def test_findex_all_men_women_dimensions_are_pivoted(tmp_path):
    paths = _write_inputs(tmp_path)
    findex = pd.read_csv(paths["findex"])
    extra = []
    for _, row in findex.iterrows():
        for group2, value in (("men", 0.45), ("women", 0.65)):
            item = row.to_dict()
            item["group"] = "gender"
            item["group2"] = group2
            item["account_t_d"] = value
            extra.append(item)
    findex = pd.concat([findex, pd.DataFrame(extra)], ignore_index=True)
    findex.to_csv(paths["findex"], index=False)

    _, processed = _run_agent(tmp_path, paths)
    year = pd.read_parquet(processed / "country_year.parquet")
    maroc = year[(year["iso3"] == "MAR") & (year["year"] == 2021)].iloc[0]

    assert round(maroc["account_own"], 2) == 55.0
    assert round(maroc["account_male"], 2) == 45.0
    assert round(maroc["account_female"], 2) == 65.0
    assert round(maroc["gender_gap_pp"], 2) == -20.0


def _with_subgroups(paths, groups):
    findex = pd.read_csv(paths["findex"])
    extra = []
    for _, row in findex.iterrows():
        for group, group2, value in groups:
            item = row.to_dict()
            item.update(group=group, group2=group2, account_t_d=value)
            extra.append(item)
    findex = pd.concat([findex, pd.DataFrame(extra)], ignore_index=True)
    findex.to_csv(paths["findex"], index=False)


def test_income_and_age_dimensions_are_pivoted_with_gaps(tmp_path):
    paths = _write_inputs(tmp_path)
    _with_subgroups(paths, [
        ("gender", "men", 0.4957), ("gender", "women", 0.2661),
        ("income", "richest 60%", 0.4862), ("income", "poorest 40%", 0.2166),
        ("age_cat", "age 25+", 0.4548), ("age_cat", "ages 15-24", 0.1166),
        # Autres groupes : ne doivent jamais alimenter les colonnes revenu/age
        ("education", "prim edu or less", 0.9), ("urbanicity", "rural", 0.8),
    ])
    out, processed = _run_agent(tmp_path, paths)
    year = pd.read_parquet(processed / "country_year.parquet")
    row = year[(year["iso3"] == "MAR") & (year["year"] == 2021)].iloc[0]
    assert row["account_richest_60"] == pytest.approx(48.62)
    assert row["account_poorest_40"] == pytest.approx(21.66)
    assert row["account_age_25_plus"] == pytest.approx(45.48)
    assert row["account_age_15_24"] == pytest.approx(11.66)
    assert row["gender_gap_pp"] == pytest.approx(22.96)
    assert row["income_gap_pp"] == pytest.approx(26.96)
    assert row["age_gap_pp"] == pytest.approx(33.82)
    lineage = json.loads((processed / "lineage.json").read_text(encoding="utf-8"))
    assert all(lineage["checks"]["findex_income_age"].values())


def test_gap_is_null_when_one_subgroup_is_missing(tmp_path):
    paths = _write_inputs(tmp_path)
    _with_subgroups(paths, [("income", "richest 60%", 0.6), ("age_cat", "ages 15-24", 0.2)])
    _, processed = _run_agent(tmp_path, paths)
    year = pd.read_parquet(processed / "country_year.parquet")
    assert year["account_richest_60"].notna().all() and year["account_poorest_40"].isna().all()
    assert year["income_gap_pp"].isna().all() and year["age_gap_pp"].isna().all()


def test_same_subgroup_label_in_two_groups_is_rejected_before_pivot(tmp_path):
    paths = _write_inputs(tmp_path)
    _with_subgroups(paths, [("income", "poorest 40%", 0.2), ("education", "poorest 40%", 0.7)])
    with pytest.raises(AgentError, match="collision"):
        _run_agent(tmp_path, paths)


def test_gdp_growth_requires_consecutive_positive_years(tmp_path):
    paths = _write_inputs(tmp_path)
    gdp = pd.read_csv(paths["gdp"])
    total = pd.DataFrame(
        {
            "iso3": ["MAR"] * 5,
            "country": ["Morocco"] * 5,
            "indicator_code": ["NY.GDP.MKTP.CD"] * 5,
            "indicator_name": ["GDP"] * 5,
            "year": [2019, 2021, 2022, 2023, 2024],
            "value": [100.0, 110.0, 0.0, 120.0, 132.0],
        }
    )
    pd.concat([gdp, total], ignore_index=True).to_csv(paths["gdp"], index=False)

    _, processed = _run_agent(tmp_path, paths)
    year = pd.read_parquet(processed / "country_year.parquet")
    growth = year[year["iso3"] == "MAR"].set_index("year")["gdp_growth_pct"]

    assert pd.isna(growth.loc[2019])
    assert pd.isna(growth.loc[2021])
    assert pd.isna(growth.loc[2022])
    assert pd.isna(growth.loc[2023])
    assert round(float(growth.loc[2024]), 2) == 10.0


def test_star_schema_uniqueness_and_country_year_contract(tmp_path):
    _, processed = _run_agent(tmp_path)
    fact = pd.read_parquet(processed / "fact_inclusion.parquet")
    year = pd.read_parquet(processed / "country_year.parquet")
    country_dim = pd.read_parquet(processed / "country_dim.parquet")
    indicator_dim = pd.read_parquet(processed / "indicator_dim.parquet")

    assert not fact.duplicated(
        ["iso3", "year", "indicator_code", "dimension", "dimension_value"]
    ).any()
    assert not country_dim.duplicated(["iso3"]).any()
    assert not indicator_dim.duplicated(
        ["source", "indicator_code", "dimension"]
    ).any()
    assert not year.duplicated(["iso3", "year"]).any()
    required = {
        "account_own",
        "account_male",
        "account_female",
        "gender_gap_pp",
        "gdp_pc",
        "gdp_usd",
        "gdp_growth_pct",
        "region",
        "income_group",
        "is_country",
        "is_aggregate",
    }
    assert required <= set(year.columns)


def test_missing_source_file_fails_before_outputs(tmp_path):
    paths = _write_inputs(tmp_path)
    cfg = _cfg(tmp_path, paths)
    missing = tmp_path / "missing.csv"
    cfg["sources"]["findex"]["path"] = str(missing)
    agent = EtlAgent(cfg=cfg, run_id="test")

    with pytest.raises(FileNotFoundError):
        agent.execute({"sources": cfg["sources"], "raw_paths": {}})
    assert not (tmp_path / "processed").exists()


def test_lineage_contains_rejections_and_checks(tmp_path):
    _, processed = _run_agent(tmp_path)
    lineage = json.loads((processed / "lineage.json").read_text(encoding="utf-8"))

    assert lineage["period"] == {"min_year": 2011, "max_year": 2024}
    assert set(lineage["inputs"]) == {"findex", "fas", "gdp"}
    assert lineage["inputs"]["findex"]["rows"] == 4
    assert "rejected" in lineage
    assert lineage["checks"]["fact_unique"] is True
    assert lineage["checks"]["country_year_unique"] is True
    assert "all" in lineage["checks"]["findex_dimensions"]
    assert lineage["checks"]["findex_all_men_women"] == {
        "all": True,
        "men": False,
        "women": False,
    }
