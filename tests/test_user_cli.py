"""add-source / remove-source : dry-run, confirmation, reutilisation par empreinte."""
from __future__ import annotations

import pytest
import yaml

from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.cli import add_source, remove_source
from biflow.tools.user_sources.registry import list_mappings
from test_user_detect import LONG, WIDE_IND, write


@pytest.fixture
def cfg(tmp_path):
    return {"uploads": {"dir": str(tmp_path / "uploads"), "mappings_dir": str(tmp_path / "sources")},
            "countries": {"name_to_iso3": {}}, "sources": {}}


class Script:
    """Reponses scriptees aux questions ; enregistre aussi les sorties."""

    def __init__(self, *answers):
        self.answers, self.questions, self.lines = list(answers), [], []

    def ask(self, question):
        self.questions.append(question)
        if not self.answers:
            raise AssertionError(f"question inattendue : {question}")
        return self.answers.pop(0)

    def out(self, line):
        self.lines.append(line)

    @property
    def text(self):
        return "\n".join(self.lines)


def run(path, name, cfg, script, **kwargs):
    return add_source(path, name, cfg=cfg, ask=script.ask, out=script.out, **kwargs)


def test_dry_run_reports_and_writes_nothing(tmp_path, cfg):
    path = write(tmp_path, "clients.csv", LONG)
    script = Script()
    result = run(path, "clients", cfg, script, dry_run=True, assume_yes=True)
    report = result["report"]
    assert result["registered"] is False and report["units_missing"] == ["clients"]
    assert report["mapped"] == 3 and report["mapped_pct"] == 100.0 and report["year_range"] == [2023, 2024]
    assert report["countries"] == ["MAR", "TUN"]
    assert report["preview"][0]["raw_value"] == "1 234,5" and report["preview"][0]["value"] == 1234.5
    assert "Dry-run : rien n'est enregistre." in script.text and "Apercu" in script.text
    assert not (tmp_path / "uploads").exists() and not (tmp_path / "sources").exists()


def test_interactive_flow_asks_unit_and_unknown_country(tmp_path, cfg):
    path = write(tmp_path, "agents.csv", WIDE_IND + "Atlantide,2023,7,8\nJordanie (Amman),2023,1,1\n")
    script = Script("", "count", "count", "", "JOR", "o")  # roles ok, 2 unites, Atlantide exclu, alias, confirmer
    result = run(path, "agents", cfg, script)
    assert result["registered"]
    assert any("jamais devinee" in q for q in script.questions)
    mapping = list_mappings(cfg)["agents"]
    assert mapping.country_names == {"Jordanie (Amman)": "JOR"}
    assert {code: spec.unit for code, spec in mapping.indicators.items()} == {"agents": "count", "branches": "count"}
    assert mapping.file.endswith("uploads/agents.csv") and mapping.confirmed_at
    assert (tmp_path / "uploads" / "agents.csv").read_text(encoding="utf-8") == path.read_text(encoding="utf-8")
    assert "'Atlantide' x2" in script.text


def test_role_can_be_edited_interactively(tmp_path, cfg):
    text = "c1;c2;c3;c4;c5\nTunisie;2023;Clients;5;INS\nMaroc;2023;Clients;6;INS\nMaroc;2024;Clients;8;INS\n"
    script = Script("indicateur", "c3", "", "count", "o")
    result = run(write(tmp_path, "c.csv", text), "opaque", cfg, script)
    assert result["mapping"]["columns"]["indicator"] == "c3" and result["registered"]


def test_cancel_writes_nothing(tmp_path, cfg):
    result = run(write(tmp_path, "c.csv", LONG), "clients", cfg, Script("", "count", "n"))
    assert result["status"] == "cancelled" and not list_mappings(cfg)


def test_non_interactive_missing_unit_asks_via_draft(tmp_path, cfg):
    draft = tmp_path / "draft.yaml"
    with pytest.raises(UserSourceError, match="Reponses requises \\(unite de : clients\\)"):
        run(write(tmp_path, "c.csv", LONG), "clients", cfg, Script(), assume_yes=True, draft_path=draft)
    data = yaml.safe_load(draft.read_text(encoding="utf-8"))
    assert data["indicators"]["clients"]["unit"] is None and not list_mappings(cfg)
    data["indicators"]["clients"]["unit"] = "count"
    draft.write_text(yaml.safe_dump(data), encoding="utf-8")
    result = run(tmp_path / "c.csv", "clients", cfg, Script(), mapping_file=draft)
    assert result["registered"] and result["status"] == "provided"


def test_same_fingerprint_reuses_mapping_without_questions(tmp_path, cfg):
    first = write(tmp_path, "v1.csv", LONG)
    run(first, "clients", cfg, Script("", "count", "o"))
    # Nouvelle livraison : memes colonnes (ordre et casse differents), autres valeurs
    later = write(tmp_path, "v2.csv", "valeur;ANNEE;indicateur;pays\n1500;2025;Clients;Tunisie\n")
    script = Script()  # aucune reponse : toute question ferait echouer le test
    result = run(later, "clients", cfg, script)
    assert result["status"] == "reused" and result["registered"]
    assert "Mapping existant reutilise (meme source)" in script.text
    assert result["report"]["year_range"] == [2025, 2025]


def test_same_structure_under_another_name_is_a_template(tmp_path, cfg):
    run(write(tmp_path, "a.csv", LONG), "clients", cfg, Script("", "count", "o"))
    script = Script("o")
    result = run(write(tmp_path, "b.csv", LONG), "clients_bis", cfg, script)
    assert result["status"] == "template" and "meme structure : clients" in script.text


def test_changed_columns_ask_again(tmp_path, cfg):
    run(write(tmp_path, "a.csv", LONG), "clients", cfg, Script("", "count", "o"))
    changed = write(tmp_path, "b.csv", LONG.replace("Valeur", "Montant"))
    script = Script("", "usd", "o")
    result = run(changed, "clients", cfg, script)
    assert "Structure differente du mapping enregistre" in script.text
    assert result["registered"] and list_mappings(cfg)["clients"].indicators["clients"].unit == "usd"


def test_provided_mapping_for_other_structure_is_refused(tmp_path, cfg):
    run(write(tmp_path, "a.csv", LONG), "clients", cfg, Script("", "count", "o"))
    other = write(tmp_path, "b.csv", WIDE_IND)
    with pytest.raises(UserSourceError, match="autre structure"):
        run(other, "clients", cfg, Script(), mapping_file=tmp_path / "sources" / "clients.yaml")


def test_conflicting_duplicates_are_refused(tmp_path, cfg):
    text = LONG + "Tunisie;2024;Clients;9\n"
    with pytest.raises(UserSourceError, match="en double avec des valeurs differentes"):
        run(write(tmp_path, "d.csv", text), "clients", cfg, Script("", "count"))
    assert not list_mappings(cfg)


def test_official_names_are_refused(tmp_path, cfg):
    with pytest.raises(UserSourceError, match="source officielle"):
        run(write(tmp_path, "f.csv", LONG), "findex", cfg, Script("", "count"))


def test_remove_source_keeps_the_uploaded_copy(tmp_path, cfg):
    run(write(tmp_path, "a.csv", LONG), "clients", cfg, Script("", "count", "o"))
    lines = []
    assert remove_source("clients", cfg, out=lines.append) and not list_mappings(cfg)
    assert (tmp_path / "uploads" / "clients.csv").exists() and "retiree" in lines[0]
    assert remove_source("clients", cfg, out=lines.append) is False


def test_main_add_source_reports_french_errors(tmp_path, monkeypatch, capsys):
    import sys
    import main as cli
    monkeypatch.setattr(sys, "argv", ["main.py", "add-source", "--file", str(tmp_path / "absent.csv"),
                                      "--name", "x_source", "--no-llm"])
    assert cli.main() == 1
    assert "Erreur : Fichier introuvable" in capsys.readouterr().out
