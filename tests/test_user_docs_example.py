"""L'exemple de mapping documente fonctionne tel quel (mode --mapping)."""
from __future__ import annotations

from biflow.config import ROOT
from biflow.tools.user_sources.cli import add_source
from biflow.tools.user_sources.registry import load_mapping
from test_user_cli import Script, cfg  # noqa: F401 - fixture reutilisee

EXAMPLE = ROOT / "docs" / "examples" / "microfinance_mapping.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "user" / "long_fr_semicolon.csv"


def test_documented_example_mapping_is_valid_and_non_interactive(cfg):
    mapping = load_mapping(EXAMPLE)
    assert mapping.name == "microfinance" and mapping.layout == "long"
    script = Script()  # aucune question en mode --mapping
    result = add_source(FIXTURE, "microfinance", mapping_file=EXAMPLE, cfg=cfg, ask=script.ask, out=script.out)
    assert result["registered"] and result["status"] == "provided"
    assert result["report"]["countries"] == ["DZA", "MAR", "TUN"]
    assert "Controle qualite de la source : PASS" in script.text
