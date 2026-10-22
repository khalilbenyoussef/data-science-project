from __future__ import annotations

import pandas as pd

from biflow.agents.profiler import profile, to_markdown


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "iso3": ["MAR", "FRA", "IND", "MAR", "FRA", "IND"],
            "year": [2011, 2011, 2011, 2014, 2014, 2014],
            "account": [0.3, 0.9, 0.6, 0.4, 0.92, 0.62],
            "extra": [None, None, None, 1.0, None, None],
        }
    )


def test_profile_detects_format_and_missing():
    prof = profile(_frame(), "mini", {"enable_isolation_forest": False})

    assert prof["format"] == "tabular"
    assert prof["rows"] == 6
    assert prof["overview"]["columns_fully_empty"] == []
    assert "extra" in prof["high_missing_columns"]
    assert prof["overview"]["n_countries"] == 3
    assert "extra" in prof["sparse_columns"]
    assert prof["recommendations"]


def test_to_markdown_contains_tables():
    prof = profile(_frame(), "mini", {"enable_isolation_forest": False})
    text = to_markdown(prof)
    assert "# Profil de la source : mini" in text
    assert "## Recommandations" in text
