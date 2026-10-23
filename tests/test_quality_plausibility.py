from __future__ import annotations

import json

import pandas as pd
import pytest

from biflow.agents.quality import QualityAgent, build_report, check_frame
from biflow.config import load_config


def _known_fas_cases():
    # Exact numeric examples found during the offline real-data validation.
    cases = {
        "VEN.OUTD_COMBANK.POGDP.A": {
            2011: 2978174729587.812, 2012: 3783782846704.122,
            2013: 5107645317147.158, 2014: 4320208084329.587,
            2015: 3775626464786.702,
        },
        "VEN.OUTL_COMBANK.POGDP.A": {
            2011: 1937666098956.602, 2012: 2274087909760.234,
            2013: 2619297008161.338, 2014: 2389523830416.893,
            2015: 2295911493352.053,
        },
        "NAM.OUTL_COMBANK.POGDP.A": {2023: 2818.673334324055, 2024: 3752.32452302587},
        "PNG.OUTL_COMBANK.POGDP.A": {2023: 20054.39782530197},
    }
    names = {"VEN": "Venezuela", "NAM": "Namibia", "PNG": "Papua New Guinea"}
    frame = pd.DataFrame([
        {"SERIES_CODE": code, "COUNTRY": names[code[:3]],
         **{str(year): value for year, value in observations.items()}}
        for code, observations in cases.items()
    ])
    return frame, cases


@pytest.mark.parametrize("threshold,expected", [(1000.0, 13), (5000.0, 11), (1e13, 0)])
def test_known_cases_and_configurable_threshold_preserve_values(threshold, expected):
    frame, cases = _known_fas_cases()
    original = frame.copy(deep=True)
    check = check_frame("fas", frame, {"min_rows": 1, "fas_pct_gdp_threshold": threshold})
    assert len(check["diagnostics"]) == expected
    assert check["issue_counts"].get("critical", 0) == 0
    for diagnostic in check["diagnostics"]:
        code, year = diagnostic["series_code"], diagnostic["year"]
        assert diagnostic["original_value"] == cases[code][year]
        assert diagnostic["value"] == cases[code][year]
        assert diagnostic["iso3"] == code[:3]
        assert diagnostic["country"] in {"Venezuela", "Namibia", "Papua New Guinea"}
        assert diagnostic["indicator_code"] == (
            "deposits_pct_gdp" if ".OUTD_" in code else "loans_pct_gdp"
        )
        assert diagnostic["unit"] == "percent_of_gdp"
        assert diagnostic["threshold"] == threshold
        assert "review" in diagnostic["reason"]
    pd.testing.assert_frame_equal(frame, original)


def test_threshold_is_strict_and_only_targets_the_two_percentage_series():
    frame = pd.DataFrame({
        "SERIES_CODE": ["VEN.OUTD_COMBANK.POGDP.A", "VEN.FA30N_COMBANK.PTADLT_NUM.A",
                        "VEN.OUTD_COMBANK_S14.POGDP.A", "VEN.OUTD_COMBANK.XDC.A"],
        "2011": [0.0, 5000.0, 5000.0, 5000.0],
        "2012": [125.5, None, None, None], "2013": [1000.0, None, None, None],
        "2014": ["1000.01", None, None, None], "2015": [None] * 4,
        "2016": ["not-a-number", None, None, None], "2017": [float("inf"), None, None, None],
    })
    check = check_frame("fas", frame, {"min_rows": 1})
    assert len(check["diagnostics"]) == 1
    diagnostic = check["diagnostics"][0]
    assert diagnostic["year"] == 2014
    assert diagnostic["original_value"] == "1000.01"
    assert diagnostic["value"] == 1000.01
    assert diagnostic["country"] == "VEN"


def test_diagnostics_do_not_change_scores_issues_or_gate_decisions():
    fas, _ = _known_fas_cases()
    frames = {
        "fas": fas,
        "findex": pd.DataFrame({"codewb": ["VEN"], "year": [2024], "group": ["all"],
                                "group2": ["all"], "account_t_d": [0.5]}),
        "gdp": pd.DataFrame({"iso3": ["VEN"], "year": [2024],
                             "indicator_code": ["NY.GDP.MKTP.CD"], "value": [100.0]}),
    }
    flagged = build_report(frames, {"min_rows": 1})
    unflagged = build_report(frames, {"min_rows": 1, "fas_pct_gdp_threshold": 1e13})
    assert flagged["passed"] is True
    assert len(flagged["diagnostics"]) == 13
    assert unflagged["diagnostics"] == []
    for key in ("overall_score", "passed", "critical_issues", "issue_counts", "issues"):
        assert flagged[key] == unflagged[key]
    assert flagged["checks"]["fas"]["score"] == unflagged["checks"]["fas"]["score"]
    frames["gdp"] = frames["gdp"].drop(columns=["value"])
    failed = build_report(frames, {"min_rows": 1})
    assert failed["passed"] is False
    assert failed["critical_issues"] > 0
    assert len(failed["diagnostics"]) == 13


def test_quality_agent_exports_separate_diagnostics(tmp_path):
    frame, _ = _known_fas_cases()
    path = tmp_path / "fas.csv"
    frame.to_csv(path, index=False)
    before = path.read_bytes()
    cfg = {"llm": {"enabled": False}, "quality": {"min_rows": 1},
           "sources": {"fas": {"type": "csv", "path": str(path)}},
           "paths": {"quality": str(tmp_path / "quality")}}
    out = QualityAgent(cfg=cfg).execute({})
    report = json.loads((tmp_path / "quality/quality_report.json").read_text(encoding="utf-8"))
    csv = pd.read_csv(out["quality_paths"]["diagnostics_csv"])
    assert len(report["diagnostics"]) == len(csv) == 13
    assert set(csv["iso3"]) == {"VEN", "NAM", "PNG"}
    assert {"country", "year", "series_code", "original_value", "reason"} <= set(csv.columns)
    assert all(i["code"] != "fas_pct_gdp_plausibility" for i in report["issues"])
    markdown = (tmp_path / "quality/quality_report.md").read_text(encoding="utf-8")
    assert "Plausibility diagnostics (review only)" in markdown
    assert "Venezuela" in markdown and "Papua New Guinea" in markdown
    assert "5107645317147.158" in markdown
    assert path.read_bytes() == before


@pytest.mark.parametrize("threshold", [0, -1, float("nan"), float("inf")])
def test_invalid_diagnostic_threshold_is_a_configuration_error(threshold):
    frame, _ = _known_fas_cases()
    with pytest.raises(ValueError, match="finite and positive"):
        check_frame("fas", frame, {"fas_pct_gdp_threshold": threshold})


def test_config_declares_the_default_diagnostic_threshold():
    assert load_config()["quality"]["fas_pct_gdp_threshold"] == 1000.0
