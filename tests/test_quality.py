from __future__ import annotations

import pandas as pd
import pytest

from biflow.agents.quality import KEY_COLUMNS, REQUIRED_COLUMNS, build_report, check_frame


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


def _mandatory_frames():
    return {
        "findex": pd.DataFrame({
            "codewb": ["MAR"] * 100, "year": range(1900, 2000),
            "group": ["all"] * 100, "group2": ["all"] * 100,
            "account_t_d": [0.5] * 100,
        }),
        "fas": pd.DataFrame({
            "SERIES_CODE": [f"MAR.FA{i}.NUM.A" for i in range(100)],
            "2020": [10.0] * 100,
        }),
        "gdp": pd.DataFrame({
            "iso3": ["MAR"] * 100, "year": range(1900, 2000),
            "indicator_code": ["NY.GDP.MKTP.CD"] * 100, "value": [100.0] * 100,
        }),
    }


@pytest.mark.parametrize("failed_sources", [
    (), ("findex",), ("fas",), ("gdp",),
    ("findex", "fas"), ("findex", "gdp"), ("fas", "gdp"),
    ("findex", "fas", "gdp"),
])
def test_every_mandatory_gate_must_pass(failed_sources):
    frames = _mandatory_frames()
    for name in failed_sources:
        frames[name] = frames[name].head(1)
    report = build_report(frames, {"min_rows": 10, "score_threshold": 0.9})

    assert report["critical_issues"] == 0
    for name, check in report["checks"].items():
        assert check["gate"] is (name not in failed_sources)
    expected_score = sum(c["score"] * c["rows"] for c in report["checks"].values()) / sum(
        c["rows"] for c in report["checks"].values()
    )
    assert report["overall_score"] == round(expected_score, 4)
    if len(failed_sources) < 3:
        assert report["overall_score"] >= 0.9
    assert report["passed"] is (not failed_sources)


@pytest.mark.parametrize("source", ["findex", "fas", "gdp"])
@pytest.mark.parametrize("missing", [False, True], ids=["empty", "absent"])
def test_empty_or_absent_mandatory_source_blocks_quality(source, missing):
    frames = _mandatory_frames()
    if missing:
        del frames[source]
    else:
        frames[source] = frames[source].iloc[:0]
    report = build_report(frames, {"min_rows": 10, "score_threshold": 0.9})

    assert report["overall_score"] == 1.0
    assert report["checks"][source]["gate"] is False
    assert report["checks"][source]["issues"][0]["code"] == "empty_source"
    assert report["passed"] is False


@pytest.mark.parametrize("backend", ["sequential", "langgraph"])
@pytest.mark.parametrize("failed_source,failure", [(None, "valid")] + [
    (source, failure) for source in ("findex", "fas", "gdp")
    for failure in ("row_count", "missing_column", "missing_key", "coverage")
])
def test_pipeline_only_reaches_etl_when_all_sources_pass(
    tmp_path, monkeypatch, backend, failed_source, failure,
):
    from biflow import graph

    if backend == "langgraph" and not graph.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph unavailable")
    monkeypatch.setattr(graph, "LANGGRAPH_AVAILABLE", backend == "langgraph")
    frames = _mandatory_frames()
    if failure == "row_count":
        frames[failed_source] = frames[failed_source].head(1)
    elif failure == "missing_column":
        frames[failed_source] = frames[failed_source].drop(columns=[REQUIRED_COLUMNS[failed_source][0]])
    elif failure == "missing_key":
        frames[failed_source].iloc[0, 0] = None
    elif failure == "coverage":
        if failed_source == "findex":
            frames[failed_source] = frames[failed_source].drop(columns=["account_t_d"])
        elif failed_source == "fas":
            frames[failed_source]["SERIES_CODE"] = [f"MAR.OTHER{i}.NUM.A" for i in range(100)]
        else:
            frames[failed_source]["indicator_code"] = "OTHER.VALUE"
    sources = {}
    for name, frame in frames.items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        sources[name] = {"type": "csv", "path": str(path)}
    sources["findex"]["indicators"] = ["account_t_d"]
    sources["fas"]["series"] = {"test": "FA0.NUM"}
    sources["gdp"]["indicators"] = ["NY.GDP.MKTP.CD"]

    etl_calls = []

    class RecordingEtl:
        name = "etl"

        def __init__(self, **kwargs):
            pass

        def run(self, state):
            etl_calls.append(state["run_id"])
            return {"status": "success", "outputs": {}}

    monkeypatch.setitem(graph.AGENT_CLASSES, "etl", RecordingEtl)
    cfg = {
        "sources": sources,
        "paths": {
            "reports": str(tmp_path / "reports"),
            "quality": str(tmp_path / "quality"),
            "processed": str(tmp_path / "processed"),
        },
        "quality": {"min_rows": 10, "score_threshold": 0.9},
    }
    state = graph.run_pipeline(
        start="quality", stop="etl", cfg=cfg, run_id="gate_test", use_llm=False,
    )

    if failure in ("valid", "row_count"):
        assert state["quality"]["overall_score"] >= 0.9
    else:
        assert state["quality"]["critical_issues"] > 0
    assert state["quality"]["passed"] is (failed_source is None)
    assert state["status"] == ("quality_failed" if failed_source else "success")
    assert etl_calls == ([] if failed_source else ["gate_test"])
    assert not (tmp_path / "processed").exists()


def _schema_fixture(source):
    frame = _mandatory_frames()[source].head(4).copy()
    config = {
        "findex": {"indicators": ["account_t_d", "dig_acc"]},
        "fas": {"series": {"branches": "FA0.NUM", "atm": "FA1.NUM"}},
        "gdp": {"indicators": ["NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD"]},
    }[source]
    return frame, config


@pytest.mark.parametrize("source,column", [
    (source, column) for source, columns in REQUIRED_COLUMNS.items() for column in columns
])
def test_missing_etl_required_column_is_critical(source, column):
    frame, source_cfg = _schema_fixture(source)
    check = check_frame(source, frame.drop(columns=[column]), {"min_rows": 1}, source_cfg)
    assert check["gate"] is False
    issue = next(i for i in check["issues"] if i["code"] == "missing_required_columns")
    assert issue["severity"] == "critical"
    assert column in check["metrics"]["schema"]["missing_required_columns"]


@pytest.mark.parametrize("source,column", [
    (source, column) for source, columns in KEY_COLUMNS.items() for column in columns
])
@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA, "", " \t"])
def test_missing_key_fields_are_critical(source, column, missing):
    frame, source_cfg = _schema_fixture(source)
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = missing
    check = check_frame(source, frame, {"min_rows": 1}, source_cfg)
    assert check["gate"] is False
    issue = next(i for i in check["issues"] if i["code"] == "missing_key" and i["column"] == column)
    assert issue["count"] == 1
    assert issue["severity"] == "critical"


@pytest.mark.parametrize("source,column,value", [
    ("findex", "codewb", "M"), ("gdp", "iso3", "12A"),
    ("findex", "year", "not-a-year"), ("gdp", "year", 2024.5),
    ("findex", "year", float("inf")), ("gdp", "year", float("-inf")),
    ("findex", "group", 123), ("findex", "group2", 123),
    ("fas", "SERIES_CODE", "MAR"), ("fas", "SERIES_CODE", "MAR.FA0.NUM.M"),
    ("fas", "SERIES_CODE", "NAN.FA0.NUM.A"),
    ("gdp", "indicator_code", "???"),
])
def test_invalid_key_fields_are_critical(source, column, value):
    frame, source_cfg = _schema_fixture(source)
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = value
    check = check_frame(source, frame, {"min_rows": 1}, source_cfg)
    assert check["gate"] is False
    assert any(i["code"] == "invalid_key" and i["column"] == column
               and i["severity"] == "critical" for i in check["issues"])


def test_fas_requires_a_four_digit_year_column():
    frame, source_cfg = _schema_fixture("fas")
    check = check_frame("fas", frame.rename(columns={"2020": "FY2020"}), {"min_rows": 1}, source_cfg)
    assert check["gate"] is False
    assert any(i["code"] == "missing_year_columns" for i in check["issues"])


@pytest.mark.parametrize("source", ["findex", "fas", "gdp"])
def test_unrelated_indicators_do_not_satisfy_configured_coverage(source):
    frame, source_cfg = _schema_fixture(source)
    if source == "findex":
        frame = frame.rename(columns={"account_t_d": "unrelated"})
    elif source == "fas":
        frame["SERIES_CODE"] = [f"MAR.UNRELATED{i}.NUM.A" for i in range(4)]
    else:
        frame["indicator_code"] = "UNRELATED.VALUE"
    check = check_frame(source, frame, {"min_rows": 1}, source_cfg)
    assert check["gate"] is False
    assert any(i["code"] == "missing_indicator_coverage" for i in check["issues"])


@pytest.mark.parametrize("source", ["findex", "fas", "gdp"])
@pytest.mark.parametrize("all_missing", [False, True])
def test_sparse_observations_and_unavailable_years_are_not_schema_failures(source, all_missing):
    frame, source_cfg = _schema_fixture(source)
    if source == "findex":
        frame["year"] = [2011, 2014, 2021, 2024]
        frame["account_t_d"] = [None, 0.4, None, 0.0]
        frame["codewb"] = ["KOS", "WBG", "WLD", "MAR"]
    elif source == "fas":
        frame["SERIES_CODE"] = ["KOS.FA0.NUM.A", "WBG.FA0.NUM.A", "WLD.FA0.NUM.A", "MAR.FA0.NUM.A"]
        frame = frame.rename(columns={"2020": "2024"})
        frame["2024"] = [None, 10.0, None, 0.0]
    else:
        frame["year"] = [2011, 2014, 2021, 2024]
        frame["iso3"] = ["KOS", "WBG", "WLD", "MAR"]
        frame["value"] = [None, 100.0, None, 0.0]
    if all_missing:
        frame[{"findex": "account_t_d", "fas": "2024", "gdp": "value"}[source]] = None
    check = check_frame(source, frame, {"min_rows": 1}, source_cfg)
    assert check["gate"] is True
    assert check["issue_counts"].get("critical", 0) == 0
    assert check["metrics"]["schema"]["available_indicators"]
    assert check["metrics"]["schema"]["missing_configured_indicators"]


@pytest.mark.parametrize("source,key", [("findex", "indicators"), ("fas", "series")])
@pytest.mark.parametrize("empty", [False, True])
def test_missing_indicator_configuration_cannot_pass_source_coverage(source, key, empty):
    frame, _ = _schema_fixture(source)
    source_cfg = {"type": "csv"}
    if empty:
        source_cfg[key] = [] if key == "indicators" else {}
    check = check_frame(source, frame, {"min_rows": 1}, source_cfg)
    assert check["gate"] is False
    assert any(i["code"] == "missing_indicator_coverage" for i in check["issues"])
