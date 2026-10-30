"""Proposition et validation du mapping des sources utilisateur (LLM simule)."""
from __future__ import annotations

import pytest

from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.detect import detect, read_user_csv
from biflow.tools.user_sources.mapping import (
    fingerprint, llm_role_suggester, propose_mapping, slug, validate_mapping,
)
from test_user_detect import LONG, WIDE_IND, WIDE_YEAR, write


def propose(tmp_path, text, name="demo", **kwargs):
    path = write(tmp_path, "f.csv", text)
    detection = detect(path)
    df = read_user_csv(path, detection["read"])
    return propose_mapping(name, str(path), df, detection, **kwargs), df


def complete(proposal, unit="count"):
    mapping = proposal["mapping"]
    for spec in mapping["indicators"].values():
        spec["unit"] = unit
    return mapping


def test_long_proposal_uses_synonyms_and_asks_for_unit(tmp_path):
    proposal, df = propose(tmp_path, LONG)
    mapping = proposal["mapping"]
    assert mapping["layout"] == "long"
    assert mapping["columns"] == {"country": {"column": "Pays", "kind": "name"}, "year": "Annee",
                                  "value": "Valeur", "indicator": "Indicateur"}
    assert mapping["indicators"] == {"clients": {"label": "Clients", "unit": None, "transform": "none"}}
    assert mapping["indicator_values"] == {"Clients": "clients"}
    assert proposal["origins"]["country"] == "regle : synonyme de nom de colonne"
    assert any("Unite de l'indicateur 'Clients'" in q and "jamais devinee" in q for q in proposal["questions"])
    with pytest.raises(UserSourceError, match="unit"):
        validate_mapping(mapping, df)  # unite manquante : refuse
    assert validate_mapping(complete(proposal), df).indicators["clients"].unit == "count"


def test_wide_by_year_proposal(tmp_path):
    proposal, df = propose(tmp_path, WIDE_YEAR)
    mapping = proposal["mapping"]
    assert mapping["columns"]["year_columns"] == ["2019", "2020", "2021"]
    assert mapping["columns"]["country"] == {"column": "iso3", "kind": "iso3"}
    assert mapping["indicator_values"] == {"mobile_users": "mobile_users"}
    validate_mapping(complete(proposal, "percent"), df)


def test_wide_by_indicator_proposal_lists_unknown_countries(tmp_path):
    text = WIDE_IND + "Atlantis,2023,1,2\n"
    proposal, df = propose(tmp_path, text)
    mapping = proposal["mapping"]
    assert mapping["columns"]["indicator_columns"] == {"agents": "agents", "branches": "branches"}
    assert set(mapping["indicators"]) == {"agents", "branches"}
    assert proposal["unresolved_countries"] == {"Atlantis": "nom de pays inconnu 'Atlantis'"}
    assert any("Pays non reconnu : 'Atlantis'" in q for q in proposal["questions"])
    validate_mapping(complete(proposal), df)


def test_single_numeric_column_is_one_indicator(tmp_path):
    proposal, _ = propose(tmp_path, "iso3,year,agents\nTUN,2023,120\nMAR,2023,80\n")
    assert proposal["mapping"]["columns"]["indicator_columns"] == {"agents": "agents"}


@pytest.mark.parametrize("text,message", [
    ("note,commentaire\nabc,def\nghi,jkl\n", "Structure non reconnue"),
    ("libelle,year,value\nfoo,2023,1\nbar,2024,2\n", "Aucune colonne pays"),
])
def test_files_without_country_or_year_are_rejected(tmp_path, text, message):
    with pytest.raises(UserSourceError, match=message):
        propose(tmp_path, text)


def test_llm_is_only_asked_for_missing_roles_and_revalidated(tmp_path):
    # colonnes aux noms opaques : la regle trouve pays/annee par les valeurs, pas l'indicateur
    text = ("c1;c2;c3;c4;c5\nTunisie;2023;Clients;5;INS\nMaroc;2023;Clients;6;INS\n"
            "Maroc;2024;Clients;8;INS\nTunisie;2024;Clients;7;INS\n")  # deux colonnes texte : indicateur ambigu
    calls = []

    def suggest(context):
        calls.append(context)
        return {"indicator": "c3", "value": "c1"}  # c1 deja utilisee (pays)

    proposal, _ = propose(tmp_path, text, llm_suggest=suggest)
    mapping = proposal["mapping"]
    assert mapping["columns"]["indicator"] == "c3" and mapping["columns"]["value"] == "c4"
    assert proposal["origins"]["indicator"] == "LLM (valide par regles)"
    assert calls and calls[0]["missing_roles"] == ["indicator"]


def test_llm_suggestion_failing_rules_is_rejected(tmp_path):
    text = ("c1;c2;c3;c4;c5\nTunisie;2023;Clients;5;INS\nMaroc;2023;Clients;6;INS\n"
            "Maroc;2024;Clients;8;INS\nTunisie;2024;Clients;7;INS\n")
    detection = detect(write(tmp_path, "f.csv", text))
    detection["candidates"]["value"] = []  # force un role manquant
    df = read_user_csv(tmp_path / "f.csv", detection["read"])
    proposal = propose_mapping("demo", "f.csv", df, detection,
                               llm_suggest=lambda ctx: {"value": "c5", "indicator": "c1"})
    assert proposal["mapping"]["columns"]["value"] is None
    assert proposal["origins"]["value"] == "suggestion LLM rejetee : 'c5' : 0% de valeurs numeriques"
    assert proposal["origins"]["indicator"] == "suggestion LLM rejetee : colonne 'c1' deja utilisee"


def test_llm_role_suggester_never_returns_units():
    suggest = llm_role_suggester(lambda prompt, system, fallback: {"value": "v", "unit": "percent", "year": 3})
    assert suggest({"missing_roles": ["value"], "columns": ["v"], "sample": []}) == {"value": "v"}


@pytest.mark.parametrize("change,message", [
    (lambda m: m.update(name="findex"), "source officielle"),
    (lambda m: m.update(name="Bad Name"), "nom de source"),
    (lambda m: m["indicators"]["clients"].update(transform="percent_to_fraction"), "exige unit: percent"),
    (lambda m: m["columns"].update(value="Absente"), "absentes du fichier"),
    (lambda m: m.update(indicator_values={}), "sans correspondance"),
    (lambda m: m.update(layout="wide_by_year"), "year_columns requis"),
    (lambda m: m.update(extra=1), "extra"),
])
def test_invalid_mappings_are_rejected(tmp_path, change, message):
    proposal, df = propose(tmp_path, LONG)
    mapping = complete(proposal)
    change(mapping)
    with pytest.raises(UserSourceError, match=message):
        validate_mapping(mapping, df)


def test_explicit_percent_to_fraction_is_allowed():
    from biflow.tools.user_sources.mapping import IndicatorSpec
    spec = IndicatorSpec(label="Taux", unit="percent", transform="percent_to_fraction")
    assert spec.stored_unit == "fraction"
    assert IndicatorSpec(label="Taux", unit="percent").stored_unit == "percent"


def test_fingerprint_ignores_order_and_case_but_not_names():
    assert fingerprint(["Pays", "Annee", "Valeur"]) == fingerprint(["valeur", "PAYS", "Année", "_line"])
    assert fingerprint(["Pays", "Annee", "Valeur"]) != fingerprint(["Pays", "Annee", "Montant"])
    assert slug("Clients microfinance (milliers)") == "clients_microfinance_milliers" and slug("2024") == "i_2024"
