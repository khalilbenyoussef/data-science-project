"""Scripts d'evaluation : approche de reference et controle en direct d'Ask Finova."""
from __future__ import annotations

import sys

from biflow.config import ROOT, load_config

sys.path.insert(0, str(ROOT / "scripts"))
import baseline_reference  # noqa: E402
import evaluate_agents  # noqa: E402

FINDEX = """codewb,year,group,group2,account_t_d,g20_any
TUN,2024,all,all,0.378,0.237
TUN,2024,gender,men,0.496,0.349
TUN,2024,gender,women,0.266,0.130
"""
FAS = ("x;y;z\nSERIES_CODE;SERIES_NAME;2023;2024\n"
       "TUN.FA26N.PHTADLT_NUM.A;branches;22.4;22.3\nMAR.FA26N.PHTADLT_NUM.A;branches;;24.0\n")


def test_naive_recalculation_matches_published_values(tmp_path):
    (tmp_path / "findex.csv").write_text(FINDEX, encoding="utf-8")
    (tmp_path / "fas.csv").write_text(FAS, encoding="utf-8")
    naive = baseline_reference.naive_values(tmp_path / "findex.csv", tmp_path / "fas.csv", ["TUN", "MAR"])
    values = {(r["kpi_id"], r["iso3"], r["year"]): r["value"] for r in naive}
    assert values[("account_ownership", "TUN", 2024)] == 100 * 0.378
    assert abs(values[("gender_gap", "TUN", 2024)] - 23.0) < 1e-9
    assert values[("branch_density", "MAR", 2024)] == 24.0 and ("branch_density", "MAR", 2023) not in values
    published = {("account_ownership", "TUN", 2024): 37.8, ("gender_gap", "TUN", 2024): 23.0,
                 ("branch_density", "TUN", 2023): 22.4, ("digital_payment_rate", "TUN", 2021): None}
    result = baseline_reference.compare(naive, published, 1e-9)
    assert (result["compared"], result["matched"], result["mismatched"]) == (3, 3, [])
    wrong = baseline_reference.compare(naive, {("branch_density", "TUN", 2024): 30.0}, 1e-9)
    assert wrong["matched"] == 0 and wrong["mismatched"][0]["naive"] == 22.3
    missing = baseline_reference.compare(naive, {("branch_density", "JOR", 2024): 1.0}, 1e-9)
    assert missing["missing_in_naive"][0]["iso3"] == "JOR"


def test_live_ask_check_is_not_measured_without_key(monkeypatch):
    cfg = load_config()
    for name, spec in (cfg["llm"]["providers"]).items():
        from biflow.llm import provider_env_var

        monkeypatch.setenv(provider_env_var(name, spec), "")
    assert evaluate_agents.configured_model(cfg) is None
    assert evaluate_agents.ask_live(cfg) == {"status": "non mesuré",
                                             "reason": "aucune clé LLM valide pour llm.routing.ask"}
