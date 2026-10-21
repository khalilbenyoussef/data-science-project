from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from biflow.config import ROOT, load_config
from biflow.utils.io import (
    load_source,
    read_csv_smart,
    save_json,
    sha256_file,
)


def test_read_csv_smart_double_header(tmp_path):
    path = tmp_path / "fas_sample.csv"
    path.write_text(
        "Column1;Column2;Column3\n"
        "DATASET;SERIES_CODE;2004\n"
        "IMF.STA:FAS(5.0.0);BRA.LOANACC_DTMFI.NUM.A;12.5\n",
        encoding="utf-8",
    )

    df = read_csv_smart(path, header_marker="SERIES_CODE")

    assert list(df.columns) == ["DATASET", "SERIES_CODE", "2004"]
    assert df.loc[0, "SERIES_CODE"] == "BRA.LOANACC_DTMFI.NUM.A"
    assert df.loc[0, "2004"] == 12.5


def test_read_csv_smart_missing_marker(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="En-tete introuvable"):
        read_csv_smart(path, header_marker="SERIES_CODE")


def test_read_csv_smart_comma_default(tmp_path):
    path = tmp_path / "plain.csv"
    path.write_text("country,year,value\nTUN,2020,3.5\n", encoding="utf-8")

    df = read_csv_smart(path)

    assert list(df.columns) == ["country", "year", "value"]
    assert df.loc[0, "country"] == "TUN"


def test_load_source_reads_real_fas():
    cfg = load_config()
    source = cfg["sources"]["fas"]
    path = ROOT / source["path"]
    if not path.exists():
        pytest.skip("data/raw/fas.csv absent")

    df = load_source(source, nrows=200)

    assert "SERIES_CODE" in df.columns
    assert "Column1" not in df.columns
    assert "2004" in df.columns
    assert "2025" in df.columns
    assert len(df) == 200


def test_sha256_file(tmp_path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"abc")

    assert sha256_file(path) == hashlib.sha256(b"abc").hexdigest()


def test_save_json_handles_numpy(tmp_path):
    path = tmp_path / "out.json"
    save_json(
        {
            "entier": np.int64(3),
            "flottant": np.float64(1.5),
            "booleen": np.bool_(True),
            "tableau": np.array([1, 2, 3]),
            "manquant": float("nan"),
        },
        path,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["entier"] == 3
    assert data["flottant"] == 1.5
    assert data["booleen"] is True
    assert data["tableau"] == [1, 2, 3]
    assert data["manquant"] is None


def test_load_source_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_source({"type": "csv", "path": tmp_path / "absent.csv"})
