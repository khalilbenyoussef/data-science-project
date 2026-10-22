from __future__ import annotations

import pandas as pd

from biflow.agents.collector import CollectorAgent, parse_payload, serialize, to_frame


def test_parse_payload_normalizes_records():
    payload = [
        {"pages": 1},
        [
            {
                "countryiso3code": "MAR",
                "country": {"value": "Morocco"},
                "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita"},
                "date": "2023",
                "value": 3672.5,
            },
            {
                "countryiso3code": "FRA",
                "country": {"value": "France"},
                "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita"},
                "date": "2023",
                "value": None,
            },
        ],
    ]
    rows = parse_payload(payload)
    assert len(rows) == 2
    assert rows[0]["iso3"] == "MAR"
    assert rows[0]["year"] == 2023
    frame = to_frame(rows)
    assert str(frame["year"].dtype) == "Int64"
    assert frame.loc[0, "value"] == 3672.5


def test_parse_payload_handles_api_error():
    assert parse_payload([{"message": [{"id": "120", "value": "Invalid"}]}]) == []
    assert parse_payload("not a list") == []


def test_serialize_is_deterministic():
    rows = [
        {"iso3": "FRA", "country": "France", "indicator_code": "A", "indicator_name": "A",
         "year": 2020, "value": 1.0},
        {"iso3": "MAR", "country": "Morocco", "indicator_code": "A", "indicator_name": "A",
         "year": 2020, "value": 2.0},
    ]
    first = serialize(to_frame(rows))
    second = serialize(to_frame(list(reversed(rows))))
    assert first == second


def test_static_source_is_hashed(tmp_path):
    path = tmp_path / "source.csv"
    pd.DataFrame({"code": ["MAR", "FRA"], "year": [2020, 2021]}).to_csv(path, index=False)
    cfg = {
        "paths": {"reports": str(tmp_path / "reports")},
        "collector": {"timeout": 5, "retries": 1},
        "sources": {
            "mini": {"static": True, "type": "csv", "path": str(path)},
        },
    }
    agent = CollectorAgent(cfg=cfg, run_id="test")
    out = agent.execute({"sources": cfg["sources"]})

    meta = out["raw_meta"]["mini"]
    assert meta["static"] is True
    assert meta["columns"] == 2
    assert len(meta["sha256"]) == 64
    assert out["raw_paths"]["mini"] == str(path)


def test_diagnose_is_deterministic():
    agent = CollectorAgent(cfg={"collector": {}}, run_id="test")

    diagnosis = agent._diagnose(TimeoutError("timed out"))

    assert diagnosis["cause"].startswith("TimeoutError")
    assert diagnosis["action"].startswith("augmenter collector.timeout")
    assert agent.llm_usage() == {}
