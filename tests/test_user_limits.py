"""Limites et garde-fous des sources utilisateur (messages en francais)."""
from __future__ import annotations

import pytest

from biflow.agents.collector import CollectorAgent
from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.canonical import canonical
from biflow.tools.user_sources.detect import check_file, read_user_csv
from biflow.tools.user_sources.mapping import validate_mapping
from test_user_cli import Script, cfg, run  # noqa: F401 - fixture cfg reutilisee
from test_user_detect import LONG, write


def test_file_size_limit_from_config(tmp_path, cfg):
    path = write(tmp_path, "big.csv", LONG * 50)
    cfg["uploads"]["max_file_mb"] = 0.001
    with pytest.raises(UserSourceError, match=r"Fichier trop volumineux : 0\.0 Mo > 0\.001 Mo \(uploads\.max_file_mb\)"):
        run(path, "clients", cfg, Script())
    assert check_file(path, 200) == path  # limite par defaut : 200 Mo


@pytest.mark.parametrize("name,content,message", [
    ("data.xlsx", b"PK\x03\x04", "seuls les fichiers CSV"),
    ("data", b"a,b\n1,2\n", "sans extension"),
    ("data.csv", b"iso3,year\x00,value\n", "Contenu binaire"),
])
def test_only_text_csv_files_are_accepted(tmp_path, name, content, message):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(UserSourceError, match=message):
        check_file(path)


@pytest.mark.parametrize("text,message", [
    ("commentaire;note\nbon;1\nmauvais;2\n", "Structure non reconnue"),
    ("libelle,year,value\nfoo,2023,1\nbar,2024,2\n", "Aucune colonne pays detectable"),
    ("iso3,periode,valeur\nTUN,T1,1\nMAR,T2,2\n", "Structure non reconnue"),
])
def test_files_without_country_or_year_are_rejected(tmp_path, cfg, text, message):
    with pytest.raises(UserSourceError, match=message):
        run(write(tmp_path, "f.csv", text), "x_source", cfg, Script(), assume_yes=True)


def test_mapping_errors_are_reported_in_french():
    with pytest.raises(UserSourceError) as error:
        validate_mapping({"name": "ok_name", "layout": "long", "inconnu": 1})
    message = str(error.value)
    assert "fingerprint : champ obligatoire absent" in message
    assert "inconnu : champ inconnu (non autorise)" in message
    assert "Field required" not in message


def _mapping(unit, transform="none"):
    return validate_mapping({
        "name": "taux", "fingerprint": "0" * 64, "file": "f.csv",
        "read": {"encoding": "utf-8-sig", "separator": ";", "decimal": ",", "header_row": 0},
        "layout": "wide_by_indicator",
        "columns": {"country": {"column": "iso3", "kind": "iso3"}, "year": "annee",
                    "indicator_columns": {"taux": "taux"}},
        "indicators": {"taux": {"label": "Taux", "unit": unit, "transform": transform}}})


@pytest.mark.parametrize("unit,transform,value,stored_unit", [
    ("percent", "none", 45.25, "percent"),           # jamais de mise a l'echelle implicite
    ("fraction", "none", 45.25, "fraction"),         # meme si l'unite semble incoherente
    ("percent", "percent_to_fraction", 0.4525, "fraction"),  # conversion declaree explicitement
])
def test_values_are_unchanged_unless_conversion_is_declared(tmp_path, unit, transform, value, stored_unit):
    path = write(tmp_path, "t.csv", "iso3;annee;taux\nTUN;2024;45,25\n")
    frame, _ = canonical(_mapping(unit, transform), read_user_csv(path, _mapping(unit).read.model_dump()))
    assert frame.iloc[0]["value"] == pytest.approx(value) and frame.iloc[0]["unit"] == stored_unit
    assert frame.iloc[0]["raw_value"] == "45,25"


def test_oversized_registered_file_is_excluded_at_collection(tmp_path, cfg):
    path = write(tmp_path, "agents.csv", "iso3;annee;taux\nTUN;2024;45,25\n" * 100)
    mapping_file = tmp_path / "m.yaml"
    import yaml
    data = _mapping("percent").model_dump(mode="json")
    data["file"] = str(path)
    mapping_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    agent = CollectorAgent(cfg={"paths": {"reports": str(tmp_path)}, "uploads": {"max_file_mb": 0.0001}},
                           run_id="t")
    out = agent.execute({"sources": {"taux": {"type": "user", "path": str(path), "mapping": str(mapping_file)}}})
    excluded, = out["excluded_sources"]
    assert excluded["step"] == "collector" and "Fichier trop volumineux" in excluded["reason"]
    assert "taux" not in out["raw_paths"]
