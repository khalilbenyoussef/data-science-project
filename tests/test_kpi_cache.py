"""Cache du catalogue / de la config et connexion partagee de l'etape KPI."""
from __future__ import annotations

from dataclasses import asdict
import shutil

import duckdb
import pytest

from biflow.config import ROOT
from biflow.tools import kpi, kpi_provenance
from biflow.tools.kpi import KpiCalculator, load_catalog, shared_read_only_connection
from test_kpi import warehouse  # noqa: F401 - fixture reutilisee


@pytest.fixture
def parses(monkeypatch):
    monkeypatch.setattr(kpi, "_CATALOG_CACHE", {})
    monkeypatch.setattr(kpi_provenance, "_FAS_SERIES_CACHE", {})
    calls = {"catalog": 0, "config": 0}
    original_yaml, original_config = kpi.yaml.safe_load, kpi_provenance.load_config

    def counting_yaml(content):
        # Le catalogue est lu en octets ; load_config passe un fichier (meme module yaml)
        calls["catalog"] += isinstance(content, bytes)
        return original_yaml(content)

    def counting_config(*args, **kwargs):
        calls["config"] += 1
        return original_config(*args, **kwargs)

    monkeypatch.setattr(kpi.yaml, "safe_load", counting_yaml)
    monkeypatch.setattr(kpi_provenance, "load_config", counting_config)
    return calls


def test_catalog_and_config_parsed_once_for_many_lookups(warehouse, parses):
    for kpi_id in ("account_ownership", "branch_density", "unbanked_share", "gender_gap"):
        for year in (2021, 2024):
            KpiCalculator(warehouse).calculate("TUN", year, kpi_id)
    assert parses == {"catalog": 1, "config": 1}


def test_edited_catalog_is_reparsed(tmp_path, warehouse, parses):
    path = tmp_path / "catalog.yaml"
    shutil.copyfile(ROOT / "config" / "kpi_catalog.v1.yaml", path)
    first = KpiCalculator(warehouse, path)._catalog_sha256
    path.write_text(path.read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
    second = KpiCalculator(warehouse, path)._catalog_sha256
    assert first != second and parses["catalog"] == 2


def test_load_catalog_returns_independent_copies(parses):
    catalog = load_catalog()
    catalog["kpis"]["saving_rate"]["verification"]["status"] = "provisional"
    assert load_catalog()["kpis"]["saving_rate"]["verification"]["status"] == "verified"
    assert parses["catalog"] == 1


def test_shared_connection_is_reused_and_closed(warehouse, monkeypatch):
    expected = [KpiCalculator(warehouse).calculate("TUN", 2024, k)
                for k in ("account_ownership", "gender_gap", "branch_density")]
    with shared_read_only_connection(warehouse):
        opened = []
        original = duckdb.connect
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: opened.append(kw) or original(*a, **kw))
        results = [KpiCalculator(warehouse).calculate("TUN", 2024, k)
                   for k in ("account_ownership", "gender_gap", "branch_density")]
        assert opened == []  # aucune nouvelle connexion par lookup
        monkeypatch.undo()
    assert [asdict(r) for r in results] == [asdict(r) for r in expected]
    assert not kpi._SHARED_CONNECTIONS
    with duckdb.connect(str(warehouse)) as con:  # ecriture possible apres le bloc
        con.execute("CREATE TABLE after_block AS SELECT 1 AS x")
