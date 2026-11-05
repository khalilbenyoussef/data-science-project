"""Pistes de recommandation : regles deterministes, seuils, formulation, audit."""
from __future__ import annotations

import copy

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from biflow.tools.kpi import load_catalog
from biflow.tools.recommendations import RULES_PATH, RulesError, evaluate, load_rules

KPIS = load_catalog()["kpis"]
RULES = load_rules()
YEAR = 2024


def row(kpi_id, iso3, value, unit="percent", status="approved", **extra):
    return {"kpi_id": kpi_id, "iso3": iso3, "year": YEAR, "value": value, "unit": unit,
            "publication_status": status, "review_reasons": extra.pop("review_reasons", []),
            "peer_status": extra.pop("peer_status", None), "peers_included": extra.pop("peers_included", None),
            "missing_peers": extra.pop("missing_peers", None)}


def peers(kpi_id, value, unit="percent", partial=False, included=("DZA", "EGY", "JOR", "MAR")):
    return row(kpi_id, "PEERS", value, unit,
               status="approved_with_review_note" if partial else "approved",
               peer_status="partial" if partial else "complete",
               missing_peers=["DZA"] if partial else [], peers_included=[c for c in included if not partial or c != "DZA"])


def run(rows, iso3="TUN", rules=RULES):
    return evaluate(rows, iso3, YEAR, rules, KPIS)


def ids(result):
    return [(r["rule_id"], r["kpi_id"]) for r in result["recommendations"]]


def test_config_thresholds_are_the_agreed_ones():
    by_id = {r["id"]: r for r in RULES["rules"]}
    assert by_id["subgroup_gap"]["threshold_pp"] == 10
    assert set(by_id["subgroup_gap"]["kpis"]) == {"gender_gap", "income_gap", "education_gap", "laborforce_gap",
                                                  "age_gap", "urban_gap"}
    assert by_id["barrier_above_peers"]["threshold_pp"] == 5
    assert all(k.startswith("barrier_") for k in by_id["barrier_above_peers"]["kpis"])
    assert by_id["usage_below_peers"]["threshold_pp"] == 5
    assert set(by_id["usage_below_peers"]["kpis"]) == {"digital_payment_rate", "account_ownership",
                                                       "formal_saving_rate"}
    assert by_id["network_below_peers"]["threshold_pct"] == 10
    assert set(by_id["network_below_peers"]["kpis"]) == {"branch_density", "atm_density"}
    assert RULES["publication_statuses"] == ["approved", "approved_with_review_note"]
    assert all(k in KPIS for r in RULES["rules"] if "kpis" in r for k in r["kpis"])
    assert (by_id["user_vs_official"]["threshold_pp"], by_id["user_vs_official"]["threshold_pct"]) == (5, 10)


def test_subgroup_gap_threshold_is_inclusive():
    assert ids(run([row("gender_gap", "TUN", 10.0, "percentage_points")])) == [("subgroup_gap", "gender_gap")]
    assert ids(run([row("gender_gap", "TUN", 9.99, "percentage_points")])) == []


def test_subgroup_gap_cites_both_groups_and_names_target():
    result = run([row("gender_gap", "TUN", 22.96, "percentage_points"),
                  row("account_ownership_men", "TUN", 49.6), row("account_ownership_women", "TUN", 26.64)])
    rec = result["recommendations"][0]
    assert rec["target_group"] == "femmes"
    assert "23.0 pts (49.6 % contre 26.6 %)" in rec["text"]
    assert [e["kpi_id"] for e in rec["evidence"]] == ["gender_gap", "account_ownership_men",
                                                      "account_ownership_women"]
    assert rec["audit"]["accepted"] is True


def test_negative_gap_swaps_target_group():
    rec = run([row("urban_gap", "TUN", -12.0, "percentage_points")])["recommendations"][0]
    assert rec["target_group"] == "adultes urbains"
    assert "12.0 pts" in rec["text"]


def test_barrier_above_peers_threshold_and_partial_average():
    rows = [row("barrier_no_trust", "TUN", 15.5), peers("barrier_no_trust", 10.5, partial=True)]
    rec = run(rows)["recommendations"][0]
    assert rec["rule_id"] == "barrier_above_peers"
    assert "moyenne partielle, sans Algérie" in rec["text"] and "5.0 pts de plus" in rec["text"]
    assert rec["review_note"] is True
    assert ids(run([row("barrier_no_trust", "TUN", 15.4), peers("barrier_no_trust", 10.5)])) == []


def test_usage_below_peers_and_network_relative_threshold():
    rows = [row("digital_payment_rate", "TUN", 23.7), peers("digital_payment_rate", 29.9),
            row("account_ownership", "TUN", 40.0), peers("account_ownership", 44.0)]
    assert ids(run(rows)) == [("usage_below_peers", "digital_payment_rate")]
    unit = "per_100k_adults"
    hit = run([row("branch_density", "TUN", 18.0, unit), peers("branch_density", 20.0, unit)])
    assert ids(hit) == [("network_below_peers", "branch_density")]
    assert "18.0 pour 100 000 adultes en Tunisie, contre 20.0" in hit["recommendations"][0]["text"]
    assert hit["recommendations"][0]["audit"]["accepted"] is True
    assert ids(run([row("branch_density", "TUN", 18.1, unit), peers("branch_density", 20.0, unit)])) == []


def test_only_approved_rows_are_used():
    assert ids(run([row("gender_gap", "TUN", 30.0, "percentage_points", status="blocked")])) == []
    assert ids(run([row("barrier_no_trust", "TUN", 30.0), {**peers("barrier_no_trust", 5.0),
                                                             "publication_status": "blocked"}])) == []


def test_rules_apply_to_the_selected_country():
    rows = [row("gender_gap", "MAR", 19.9, "percentage_points"), row("gender_gap", "TUN", 30.0, "percentage_points")]
    result = run(rows, iso3="MAR")
    assert result["country"] == "Maroc"
    rec = result["recommendations"][0]
    assert rec["iso3"] == "MAR" and "au Maroc" in rec["text"] and "19.9" in rec["text"]
    rec = run([row("barrier_no_trust", "MAR", 20.0), peers("barrier_no_trust", 10.0)], iso3="MAR")
    assert "moyenne incluant Maroc" in rec["recommendations"][0]["text"]


def test_wording_is_a_piste_without_causal_claim():
    rows = [row(k, "TUN", 30.0, "percentage_points") for k in
            ("gender_gap", "income_gap", "education_gap", "laborforce_gap", "age_gap", "urban_gap")]
    rows += [row(k, "TUN", 30.0) for k in RULES["rules"][1]["kpis"]] + [peers(k, 10.0) for k in RULES["rules"][1]["kpis"]]
    result = run(rows)
    assert len(result["recommendations"]) == 12 and not result["rejected"]
    for rec in result["recommendations"]:
        assert rec["text"].startswith("Piste à explorer : ")
        assert rec["text"].endswith("Association, pas causalité.")
        assert "il faut" not in rec["text"].lower() and rec["target_group"] in rec["text"]


def test_unjustified_number_or_forbidden_phrase_is_rejected():
    rules = copy.deepcopy(RULES)
    rules["rules"][0]["kpis"]["gender_gap"]["piste"] = "lancer 3 programmes pour les {target}"
    result = run([row("gender_gap", "TUN", 22.0, "percentage_points")], rules=rules)
    assert result["recommendations"] == []
    assert "nombre '3' du texte non justifie par un claim" in result["rejected"][0]["audit"]["reasons"]
    rules["rules"][0]["kpis"]["gender_gap"]["piste"] = "il faut cibler les {target}"
    result = run([row("gender_gap", "TUN", 22.0, "percentage_points")], rules=rules)
    assert result["rejected"][0]["audit"]["reasons"] == ["formulation interdite : il faut"]


def test_invalid_rules_file(tmp_path):
    bad = tmp_path / "r.yaml"
    bad.write_text("rules:\n  - {id: x, kind: subgroup_gap, threshold_pp: 0, kpis: {gender_gap: {}}}\n",
                   encoding="utf-8")
    with pytest.raises(RulesError):
        load_rules(bad)
    assert load_rules(RULES_PATH)["version"] == 1


@pytest.fixture
def client(tmp_path):
    from dashboard_app.api.reports import create_reports_router

    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, value DOUBLE, unit VARCHAR, "
                    "publication_status VARCHAR, review_reasons VARCHAR[], peer_status VARCHAR, "
                    "peers_included VARCHAR[], missing_peers VARCHAR[])")
        con.executemany("INSERT INTO kpi_values VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ("gender_gap", "TUN", 2024, 22.96, "percentage_points", "approved", [], None, None, None),
            ("gender_gap", "TUN", 2021, 16.4, "percentage_points", "approved", [], None, None, None),
            ("barrier_no_trust", "TUN", 2024, 15.53, "percent", "approved", [], None, None, None),
            ("barrier_no_trust", "PEERS", 2024, 7.54, "percent", "approved_with_review_note",
             ["partial_peer_coverage"], "partial", ["EGY", "JOR", "MAR"], ["DZA"]),
        ])
    app = FastAPI()
    app.include_router(create_reports_router(warehouse=warehouse, audit_dir=tmp_path / "audit",
                                             spec_file=tmp_path / "finova.json"))
    return TestClient(app)


def test_api_returns_audited_recommendations_for_the_scope(client):
    body = client.get("/api/recommendations", params={"iso3": "tun", "year": 2024}).json()
    assert (body["iso3"], body["year"], body["country"]) == ("TUN", 2024, "Tunisie")
    assert [r["kpi_id"] for r in body["recommendations"]] == ["gender_gap", "barrier_no_trust"]
    trust = body["recommendations"][1]
    assert "15.5 %" in trust["text"] and "7.5 %" in trust["text"] and "8.0 pts" in trust["text"]
    assert [e["id"] for e in trust["evidence"]] == ["EV-barrier_no_trust-TUN-2024", "EV-barrier_no_trust-PEERS-2024"]
    assert body["rejected"] == 0
    assert [r["kpi_id"] for r in client.get("/api/recommendations?iso3=TUN&year=2021").json()["recommendations"]] \
        == ["gender_gap"]


@pytest.mark.parametrize("query", ["iso3=TU&year=2024", "iso3=TUN1&year=2024", "iso3=T%27N&year=2024",
                                   "iso3=TUN&year=1999", "iso3=TUN"])
def test_api_validates_parameters(client, query):
    assert client.get(f"/api/recommendations?{query}").status_code in (400, 422)
