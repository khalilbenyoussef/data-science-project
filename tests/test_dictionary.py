"""Libelles Findex verifies dans le glossaire Global Findex 2025 (aucun reseau)."""
from __future__ import annotations

import pytest
import yaml

from biflow.config import ROOT
from biflow.tools import dictionary
from biflow.tools.dictionary import (
    FINDEX_GLOSSARY_ROWS, FINDEX_LABELS, FINDEX_UNVERIFIED, UNITS, label_for,
)
from biflow.tools.kpi import CatalogError, load_catalog

FIN24 = ["fin24aP", "fin24aN", "fin24aSD_ND", "fin24sav", "fin24fam", "fin24work",
         "fin24bor", "fin24sell", "fin24other"]
FIN11 = ["fin11a", "fin11b", "fin11c", "fin11d", "fin11e", "fin11f"]


@pytest.mark.parametrize("code", FIN24)
def test_fin24_codes_are_emergency_funds_not_payment_saving_or_borrowing(code):
    label = FINDEX_LABELS[code]
    assert "Fonds d'urgence" in label or "fonds d'urgence" in label
    assert "Paiement" not in label and "vague 2024" not in label
    assert UNITS[code] == "fraction"
    assert code in FINDEX_GLOSSARY_ROWS


@pytest.mark.parametrize("code", FIN11)
def test_fin11_codes_are_barriers_to_account_ownership(code):
    assert FINDEX_LABELS[code].startswith("Sans compte : ")
    assert UNITS[code] == "fraction" and code in FINDEX_GLOSSARY_ROWS


def test_glossary_rows_match_verified_positions():
    assert FINDEX_GLOSSARY_ROWS["fin24aP"] == 44 and FINDEX_GLOSSARY_ROWS["fin24sav"] == 34
    assert FINDEX_GLOSSARY_ROWS["fin24bor"] == 37 and FINDEX_GLOSSARY_ROWS["fin17a"] == 24
    assert FINDEX_GLOSSARY_ROWS["fin22a"] == 31
    assert set(FINDEX_GLOSSARY_ROWS) <= set(FINDEX_LABELS)
    assert len(set(FINDEX_GLOSSARY_ROWS.values())) == len(FINDEX_GLOSSARY_ROWS)


def test_catalog_uses_only_the_requested_emergency_fund_codes():
    used = {k["warehouse"]["indicator_code"] for k in load_catalog()["kpis"].values()}
    # catalogue 1.4.0 (REQUEST_CATALOG) : fin24aP, fin24sav, fin24bor seulement
    assert used & set(FIN24 + FIN11) == {"fin24aP", "fin24sav", "fin24bor"}
    findex_used = {k["warehouse"]["indicator_code"] for k in load_catalog()["kpis"].values()
                   if k["warehouse"]["source"] == "findex"}
    assert findex_used <= set(FINDEX_GLOSSARY_ROWS)
    assert findex_used.isdisjoint(FINDEX_UNVERIFIED)


def test_unverified_codes_are_labelled_and_blocked_from_kpis(monkeypatch, tmp_path):
    monkeypatch.setattr(dictionary, "FINDEX_UNVERIFIED", frozenset({"fin17a"}))
    assert label_for("fin17a").endswith("(unverified)")
    monkeypatch.setattr("biflow.tools.kpi.FINDEX_UNVERIFIED", frozenset({"fin17a"}))
    path = tmp_path / "catalog.yaml"
    path.write_text((ROOT / "config/kpi_catalog.v1.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(CatalogError, match="Unverified"):
        load_catalog(path)
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["kpis"]["formal_saving_rate"]
