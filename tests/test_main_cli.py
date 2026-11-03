"""CLI Route 2 : lecture des options --country et --kpis."""
import argparse

import main as cli


def _args(*argv):
    parser = argparse.ArgumentParser()
    cli._add_analysis_args(parser)
    return parser.parse_args(list(argv))


def test_kpis_option_is_split_on_commas_not_characters():
    request = cli._analysis_request(
        _args("--kpis", "account_ownership, saving_rate", "--country", "TUN,MAR"), {})
    assert request["kpi_ids"] == ["account_ownership", "saving_rate"]
    assert request["iso3"] == ["TUN", "MAR"]


def test_missing_kpis_option_falls_back_to_config_defaults():
    cfg = {"analyst": {"default_kpis": ["branch_density"], "default_countries": ["TUN"]}}
    request = cli._analysis_request(_args(), cfg)
    assert request["kpi_ids"] == ["branch_density"]
    assert request["iso3"] == ["TUN"]
