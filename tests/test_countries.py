from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from biflow.utils.countries import (
    country_name,
    invalid_iso3,
    is_aggregate,
    is_country,
    normalize_iso3,
)


@pytest.mark.parametrize(
    "code",
    [None, float("nan"), np.float64("nan"), pd.NA, "", " \t\n", "nan", " NAN ",
     "<NA>", "None", "null", "NaT"],
)
def test_missing_country_codes_are_not_stringified(code):
    assert normalize_iso3(code) is None
    assert is_country(code) is False
    assert is_aggregate(code) is False
    assert country_name(code, "fallback") == "fallback"
    assert invalid_iso3([code]) == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [("TUN", "TUN"), (" fra ", "FRA"), (" kos ", "XKX"),
     ("wbg", "PSE"), ("XKX", "XKX"), ("PSE", "PSE"), (" wld ", "WLD")],
)
def test_valid_codes_aliases_and_aggregates_are_preserved(code, expected):
    assert normalize_iso3(code) == expected


def test_country_and_aggregate_classification_preserves_aliases():
    assert is_country("KOS") is True
    assert is_aggregate(" wld ") is True
    assert is_country("WLD") is False
