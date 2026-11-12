"""Detection de structure des CSV utilisateur (fichiers temporaires)."""
from __future__ import annotations

import pytest

from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.countries import CountryResolver, normalize_name
from biflow.tools.user_sources.detect import (
    detect, detect_read_params, parse_number, read_user_csv,
)


def write(tmp_path, name, text, encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


LONG = "Pays;Annee;Indicateur;Valeur\nTunisie;2023;Clients;1 234,5\nTunisie;2024;Clients;1300,25\nMaroc;2024;Clients;2100,5\n"
WIDE_YEAR = "iso3,indicator,2019,2020,2021\nTUN,mobile_users,10.5,11.2,12.0\nMAR,mobile_users,9.1,,10.3\n"
WIDE_IND = "country,year,agents,branches\nTunisia,2023,120,45\nAlgeria,2023,80,30\nEgypt,2023,1,2\n"


@pytest.mark.parametrize("text,layout,read", [
    (LONG, "long", {"separator": ";", "decimal": ",", "header_row": 0}),
    (WIDE_YEAR, "wide_by_year", {"separator": ",", "decimal": ".", "header_row": 0}),
    (WIDE_IND, "wide_by_indicator", {"separator": ",", "decimal": ".", "header_row": 0}),
    (WIDE_IND.replace(",", "\t"), "wide_by_indicator", {"separator": "\t", "decimal": ".", "header_row": 0}),
])
def test_layouts_and_read_parameters(tmp_path, text, layout, read):
    result = detect(write(tmp_path, "f.csv", text))
    assert result["layout"] == layout, result["evidence"]
    assert {k: result["read"][k] for k in read} == read


def test_candidates_have_evidence(tmp_path):
    long = detect(write(tmp_path, "l.csv", LONG))["candidates"]
    assert long["country"] == [{"column": "Pays", "kind": "name", "share": 1.0}]
    assert long["year"][0]["column"] == "Annee" and long["indicator"][0]["column"] == "Indicateur"
    assert long["value"][0]["column"] == "Valeur"
    wide = detect(write(tmp_path, "w.csv", WIDE_YEAR))
    assert wide["candidates"]["country"][0] == {"column": "iso3", "kind": "iso3", "share": 1.0}
    assert wide["year_columns"] == ["2019", "2020", "2021"]


def test_title_line_above_header_is_skipped(tmp_path):
    path = write(tmp_path, "t.csv", "Source : ministere des finances\n" + WIDE_IND)
    assert detect_read_params(path)["header_row"] == 1
    assert detect(path)["layout"] == "wide_by_indicator"


def test_encoding_is_checked_on_the_whole_file(tmp_path):
    # Debut ASCII (> 64 Ko), accent cp1252 a la fin : utf-8 ne decode pas le fichier entier
    filler = "".join(f"TUN,{2000 + i % 20},1\n" for i in range(8000))
    path = tmp_path / "late.csv"
    path.write_bytes(("iso3,year,value\n" + filler).encode("ascii") + "CIV,2020,1\nCôte,2021,2\n".encode("cp1252"))
    read = detect_read_params(path)
    assert read["encoding"] == "cp1252"
    assert read_user_csv(path, read).iloc[-1]["iso3"] == "Côte"


def test_raw_text_and_physical_line_numbers_are_kept(tmp_path):
    path = write(tmp_path, "q.csv", 'iso3;year;note;value\nTUN;2024;"ligne 1\nligne 2";12,50\nMAR;2024;x;7\n')
    df = read_user_csv(path, detect_read_params(path))
    assert df["value"].tolist() == ["12,50", "7"]  # texte brut, rien n'est converti
    assert df["_line"].tolist() == [2, 4]


@pytest.mark.parametrize("text,message", [
    ("a,b\n1,2,3\n", r"3 champ\(s\) au lieu de 2"),
    ("a,a\n1,2\n", "En-tetes en double"),
])
def test_malformed_files_raise_french_errors(tmp_path, text, message):
    path = write(tmp_path, "bad.csv", text)
    with pytest.raises(UserSourceError, match=message):
        read_user_csv(path, {"encoding": "utf-8-sig", "separator": ",", "header_row": 0})


def test_empty_file_is_rejected(tmp_path):
    with pytest.raises(UserSourceError, match="Fichier vide"):
        detect(write(tmp_path, "e.csv", "  \n"))


@pytest.mark.parametrize("text,decimal,expected", [
    ("12,5", ",", 12.5), ("1 234,5", ",", 1234.5), ("1 234,5", ",", 1234.5), ("-0,25", ",", -0.25),
    ("12.5", ".", 12.5), ("12 345 678", ".", 12345678.0), ("1e3", ".", 1000.0), ("", ".", None),
])
def test_parse_number(text, decimal, expected):
    assert parse_number(text, decimal) == expected


@pytest.mark.parametrize("text,decimal", [("12.5", ","), ("12,5", "."), ("1 234.5", ","), ("12 34", "."),
                                          ("n/a", "."), ("12%", ".")])
def test_non_numeric_is_never_coerced(text, decimal):
    with pytest.raises(ValueError):
        parse_number(text, decimal)


@pytest.mark.parametrize("value,expected", [
    ("Tunisie", "TUN"), ("TUNISIA", "TUN"), ("Algérie", "DZA"), ("Algerie", "DZA"), ("Égypte", "EGY"),
    ("Kingdom of Morocco", "MAR"), ("Royaume du Maroc", "MAR"), ("تونس", "TUN"), ("Côte d'Ivoire", "CIV"),
    ("Cote d Ivoire", "CIV"), ("tun", "TUN"), ("KOS", "XKX"), ("Kosovo", "XKX"),
])
def test_country_names_resolve_exactly(value, expected):
    assert CountryResolver().resolve(value) == (expected, None)


@pytest.mark.parametrize("value,reason", [
    ("Atlantis", "nom de pays inconnu"), ("Tunisi", "nom de pays inconnu"), ("WLD", "agregat"),
    ("", "pays manquant"),
])
def test_unknown_names_are_never_guessed(value, reason):
    code, why = CountryResolver().resolve(value)
    assert code is None and reason in why


def test_aliases_from_config_or_mapping():
    resolver = CountryResolver({"Tunisie (centre)": "TUN"})
    assert resolver.resolve("tunisie centre") == ("TUN", None)
    resolved, unresolved = resolver.resolve_all(["Tunisie (centre)", "Maroc", "Atlantis", "Maroc"])
    assert resolved == {"Tunisie (centre)": "TUN", "Maroc": "MAR"} and list(unresolved) == ["Atlantis"]
    assert CountryResolver().resolve("TUN", "name")[0] is None  # un code n'est pas un nom
    assert normalize_name("  Côte-d'Ivoire ") == "cote d ivoire"
