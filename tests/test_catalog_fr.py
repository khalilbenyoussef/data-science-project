"""Catalogue 1.8.0 : définition et dénominateur en français pour chaque KPI officiel
(traduction de la source anglaise, conservée) ; libellés seulement, aucun contrat modifié."""
from __future__ import annotations

import copy
import re
import subprocess

import pytest
import yaml

from biflow.config import ROOT
from biflow.tools import deliverables as dl
from biflow.tools.kpi import CatalogError, _validate_catalog, load_catalog
from biflow.tools.user_sources.comparisons import official_kpis

PATH = ROOT / "config/kpi_catalog.v1.yaml"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(PATH)


def test_every_official_kpi_has_french_definition_and_denominator(catalog):
    kpis = catalog["kpis"]
    assert catalog["catalog_version"] == "1.8.0" and len(kpis) == 44
    for kpi_id, kpi in kpis.items():
        assert kpi["definition_fr"].strip() and kpi["denominator_fr"].strip(), kpi_id
        assert kpi["definition_fr"] != kpi["definition"], kpi_id  # traduit, pas recopie
        assert kpi["definition"].strip(), kpi_id  # la source anglaise reste dans le catalogue


def test_translations_keep_the_key_facts_of_the_english_source(catalog):
    for kpi_id, kpi in catalog["kpis"].items():
        en, fr = kpi["definition"], kpi["definition_fr"]
        for figure in ("100000", "1000", "30", "15+", "60%", "40%"):
            if re.search(rf"(?<!\d){re.escape(figure)}(?!\d)", en):
                expected = {"100000": "100 000", "1000": "1 000", "15+": "15", "60%": "60 %", "40%": "40 %"}.get(
                    figure, figure)
                assert expected in fr, (kpi_id, figure)
        assert ("FAS" in en) == ("FAS" in fr), kpi_id
        assert ("percentage points" in en) == ("points de pourcentage" in fr), kpi_id
        assert ("not only adults without an account" in en) == ("pas seulement les adultes sans compte" in fr), kpi_id


def test_validator_requires_the_french_fields_for_official_kpis(catalog):
    for field in ("definition_fr", "denominator_fr"):
        broken = copy.deepcopy(catalog)
        del broken["kpis"]["account_ownership"][field]
        with pytest.raises(CatalogError, match=field):
            _validate_catalog(broken)


def test_only_labels_changed_since_catalog_1_7_0():
    """Hors libellés français et métadonnées de version, le catalogue est identique à 1.7.0."""
    try:
        old_text = subprocess.run(["git", "show", "4244fdd:config/kpi_catalog.v1.yaml"], cwd=ROOT, check=True,
                                  capture_output=True, text=True, encoding="utf-8").stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("historique git indisponible")
    old, new = yaml.safe_load(old_text), yaml.safe_load(PATH.read_text(encoding="utf-8"))
    assert old["catalog_version"] == "1.7.0"
    for meta in ("catalog_version", "updated_on"):
        old.pop(meta), new.pop(meta)
    for kpi in new["kpis"].values():
        kpi.pop("definition_fr"), kpi.pop("denominator_fr")
    assert new == old


def test_french_definitions_reach_the_comparison_block_and_the_catalog_document(catalog):
    atm = official_kpis()["atm_density"]
    assert atm["definition"] == catalog["kpis"]["atm_density"]["definition_fr"]
    assert atm["definition_en"] == catalog["kpis"]["atm_density"]["definition"]
    assert atm["denominator"] == catalog["kpis"]["atm_density"]["denominator_fr"]
    text = dl.render_kpi_catalog(dl.load_context())
    assert f"- **Définition** : {catalog['kpis']['account_ownership']['definition_fr']}" in text
    assert f"<sub>Source (EN) : {catalog['kpis']['account_ownership']['definition']}</sub>" in text
    assert f"- **Dénominateur** : {catalog['kpis']['account_ownership']['denominator_fr']}" in text
