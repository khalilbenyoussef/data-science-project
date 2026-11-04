"""Dashboard historique (dashboard/) : S4 infobulles echappees, S5 validation imbriquee (tests Node)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node absent")
    major, minor = (int(part) for part in re.findall(r"\d+", subprocess.run(
        [node, "--version"], capture_output=True, text=True).stdout)[:2])
    if (major, minor) < (22, 6):
        pytest.skip("Node >= 22.6 requis pour executer un fichier .ts")
    return node


@pytest.mark.parametrize("script", ["escape.test.ts", "validate.test.ts"])
def test_node_tests_pass(script):
    result = subprocess.run([_node(), "--test", f"dashboard/tests/{script}"], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("component", ["BarComparison.tsx", "TrendChart.tsx"])
def test_tooltip_formatters_escape_every_data_label(component):
    source = (ROOT / "dashboard" / "src" / "components" / component).read_text(encoding="utf-8")
    tooltip = source[source.index("tooltip:"):source.index("},\n      ", source.index("tooltip:"))]
    interpolations = re.findall(r"\$\{([^}]*)\}", tooltip)
    data_parts = [part for part in interpolations if "requires_review" not in part]
    assert data_parts and all(part.strip().startswith("escapeHtml(") for part in data_parts), data_parts
