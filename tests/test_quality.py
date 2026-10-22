from __future__ import annotations

import pandas as pd

from biflow.agents.quality import build_report, check_frame


def _clean() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "codewb": ["MAR", "FRA", "MAR", "FRA"],
            "year": [2011, 2011, 2014, 2014],
            "group": ["all", "all", "all", "all"],
            "group2": ["all", "all", "all", "all"],
            "account_t_d": [0.3, 0.9, 0.4, 0.92],
        }
    )


def test_clean_source_passes():
    check = check_frame("findex", _clean(), {"min_rows": 1})
    assert check["score"] == 1.0
    assert check["gate"] is True
    assert check["issues"] == []


def test_duplicate_key_and_out_of_range_are_flagged():
    df = _clean()
    df.loc[1, "codewb"] = "MAR"
    df.loc[0, "account_t_d"] = 1.5
    check = check_frame("findex", df, {"min_rows": 1})

    codes = {issue["code"] for issue in check["issues"]}
    assert "duplicate_key" in codes
    assert "rate_out_of_range" in codes
    assert check["gate"] is False


def test_report_aggregates_sources():
    report = build_report(
        {"findex": _clean(), "gdp": pd.DataFrame({"iso3": ["MAR"], "value": [1]})},
        {"min_rows": 1, "score_threshold": 0.5},
    )
    assert report["overall_score"] > 0
    assert "checks" in report
    assert isinstance(report["issues"], list)
