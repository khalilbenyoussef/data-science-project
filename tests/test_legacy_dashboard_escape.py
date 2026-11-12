"""Dashboard historique (legacy/dashboard/, retire du service, remplace par FinOVA) :
S4 infobulles echappees, S5 validation imbriquee (tests Node).

Le front n'est plus construit ni servi ; ces tests restent executables tant que le
code est conserve dans le depot (lecture du source, Node pour les tests .ts)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy" / "dashboard"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node absent : tests Node du dashboard historique (retire du service) ignores")
    major, minor = (int(part) for part in re.findall(r"\d+", subprocess.run(
        [node, "--version"], capture_output=True, text=True).stdout)[:2])
    if (major, minor) < (22, 6):
        pytest.skip("Node >= 22.6 requis pour executer un fichier .ts (dashboard historique)")
    return node


@pytest.mark.parametrize("script", ["escape.test.ts", "validate.test.ts"])
def test_node_tests_pass(script):
    result = subprocess.run([_node(), "--test", f"tests/{script}"], cwd=LEGACY,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("component", ["BarComparison.tsx", "TrendChart.tsx"])
def test_tooltip_formatters_escape_every_data_label(component):
    source = (LEGACY / "src" / "components" / component).read_text(encoding="utf-8")
    tooltip = source[source.index("tooltip:"):source.index("},\n      ", source.index("tooltip:"))]
    interpolations = re.findall(r"\$\{([^}]*)\}", tooltip)
    data_parts = [part for part in interpolations if "requires_review" not in part]
    assert data_parts and all(part.strip().startswith("escapeHtml(") for part in data_parts), data_parts


def test_legacy_dashboard_is_not_served_or_fed():
    """N1 : l'API ne sert que dashboard_app ; la Route 1 n'ecrit plus dans le front historique."""
    app = (ROOT / "dashboard_app" / "api" / "app.py").read_text(encoding="utf-8")
    assert "legacy" not in app
    config = (ROOT / "config" / "config.yaml").read_text(encoding="utf-8")
    assert "data_output: outputs/dashboard/dashboard.json" in config
    assert not (ROOT / "dashboard").exists() or not any((ROOT / "dashboard").glob("package.json"))
