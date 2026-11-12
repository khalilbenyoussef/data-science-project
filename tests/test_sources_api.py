"""API « Mes données » : detect -> dry-run -> confirm -> job, liste, retrait, donnees, S6."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from biflow.tools.user_sources.jobs import JobManager
from biflow.utils.io import neutralize_formulas, write_csv
from dashboard_app.api.sources import create_sources_router

FIXTURES = Path(__file__).parent / "fixtures" / "user"
WIDE_FR = ("Pays;Indicateur;2021;2022;2023\n"
           "Tunisie;Clients (exemple fictif);120,5;131,25;140\n"
           "Maroc;Clients (exemple fictif);300;310,5;\n"
           "Algérie;Clients (exemple fictif);95;98,75;101\n"
           "Royaume de Nulle Part;Clients (exemple fictif);1;2;3\n")


class Runner:
    """Runner simule : termine tout de suite, ou attend un signal (job occupe)."""

    def __init__(self, status="success", wait=False):
        self.status, self.release, self.calls = status, threading.Event(), []
        if not wait:
            self.release.set()

    def __call__(self, job, update):
        self.calls.append((job["kind"], job["source"]))
        update(step="collector", run_id="user_test")
        self.release.wait(10)
        update(status=self.status, step=None, message="ok", reasons=["too_few_rows"] if self.status != "success" else [])


@pytest.fixture
def cfg(tmp_path):
    return {"uploads": {"dir": str(tmp_path / "uploads"), "mappings_dir": str(tmp_path / "sources"),
                        "pending_dir": str(tmp_path / "pending"), "jobs_dir": str(tmp_path / "jobs"),
                        "max_file_mb": 0.01, "job_timeout_min": 15},
            "paths": {"quality": str(tmp_path / "quality"), "reports": str(tmp_path / "reports")},
            "countries": {"name_to_iso3": {}}, "sources": {"findex": {"path": "data/raw/findex.csv"}},
            "quality": {"min_rows": 1}}


def make_client(cfg, tmp_path, runner=None, warehouse=None):
    app = FastAPI()
    router, jobs = create_sources_router(cfg, warehouse=warehouse or tmp_path / "missing.duckdb",
                                         runner=runner or Runner())
    app.include_router(router)
    return TestClient(app), jobs


def upload(client, content, filename="donnees.csv", content_type="text/csv"):
    data = content.encode("utf-8") if isinstance(content, str) else content
    return client.post("/api/sources/detect", files={"file": (filename, data, content_type)})


def wait_job(client, job_id):
    for _ in range(100):
        job = client.get(f"/api/sources/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job toujours actif")


def roles_of(detected):
    return {column["name"]: column["role"] for column in detected["columns"]}


# ----------------------------------------------------------------- detection
@pytest.mark.parametrize("fixture,layout", [("long_fr_semicolon.csv", "long"),
                                            ("wide_by_year_iso3.csv", "wide_by_year"),
                                            ("wide_by_indicator_en.csv", "wide_by_indicator")])
def test_detect_each_layout(cfg, tmp_path, fixture, layout):
    client, _ = make_client(cfg, tmp_path)
    body = upload(client, (FIXTURES / fixture).read_bytes(), fixture).json()
    assert body["layout"] == layout and body["upload_id"] and body["reusable"] == []
    assert sum(role == "country" for role in roles_of(body).values()) == 1
    assert not (tmp_path / "uploads").exists()  # zone d'attente seulement


def test_semicolon_decimal_comma_and_country_names(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    body = upload(client, WIDE_FR).json()
    assert (body["read"]["separator"], body["read"]["decimal"], body["layout"]) == (";", ",", "wide_by_year")
    assert body["country"]["column"] == "Pays" and body["country"]["kind"] == "name"
    assert roles_of(body) == {"Pays": "country", "Indicateur": "indicator", "2021": "year_column",
                              "2022": "year_column", "2023": "year_column"}


# ------------------------------------------------------------------- dry-run
def test_missing_unit_blocks_confirm_and_unknown_country_mapping(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    detected = upload(client, WIDE_FR).json()
    request = {"upload_id": detected["upload_id"], "name": "clients_demo",
               "mapping": {"roles": roles_of(detected)}}
    dry = client.post("/api/sources/dry-run", json=request).json()
    assert dry["missing_fields"] == [{"indicator": "clients_exemple_fictif", "label": "Clients (exemple fictif)",
                                      "field": "unit"}]
    assert "Royaume de Nulle Part" in dry["unmapped_countries"] and dry["year_range"] == [2021, 2023]
    assert dry["mapped"] == 8 and dry["empty_cells"] == 1 and len(dry["preview"]) == 8
    assert dry["preview"][0]["value"] == 120.5 and dry["preview"][0]["raw_value"] == "120,5"
    blocked = client.post("/api/sources/confirm", json=request)
    assert blocked.status_code == 400 and "Unité manquante" in blocked.json()["detail"]
    assert not (tmp_path / "sources").exists()

    request["mapping"].update(indicators={"clients_exemple_fictif": {"unit": "count", "label": "Clients"}},
                              country_names={"Royaume de Nulle Part": "MRT"})
    fixed = client.post("/api/sources/dry-run", json=request).json()
    assert fixed["missing_fields"] == [] and fixed["unmapped_countries"] == {} and fixed["mapped"] == 11
    assert fixed["indicators"][0] == {"code": "clients_exemple_fictif", "label": "Clients",
                                      "unit": "count", "transform": "none", "comparable_kpi": None}
    bad = dict(request, mapping={**request["mapping"], "country_names": {"Royaume de Nulle Part": "XYZ"}})
    assert client.post("/api/sources/dry-run", json=bad).status_code == 400


def test_units_are_never_guessed_and_transform_is_explicit(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    detected = upload(client, WIDE_FR).json()
    base = {"upload_id": detected["upload_id"], "name": "clients_demo"}
    for unit, transform, code in (("km", "none", 400), ("count", "percent_to_fraction", 400),
                                  ("percent", "percent_to_fraction", 200), ("currency:TND", "none", 200)):
        mapping = {"roles": roles_of(detected),
                   "indicators": {"clients_exemple_fictif": {"unit": unit, "transform": transform}}}
        response = client.post("/api/sources/dry-run", json={**base, "mapping": mapping})
        assert response.status_code == code, (unit, transform, response.json())
    converted = client.post("/api/sources/dry-run", json={**base, "mapping": {
        "roles": roles_of(detected),
        "indicators": {"clients_exemple_fictif": {"unit": "percent", "transform": "percent_to_fraction"}}}}).json()
    assert converted["preview"][0]["value"] == pytest.approx(1.205) and converted["preview"][0]["unit"] == "fraction"


# ------------------------------------------------------------- confirm + job
def confirm_demo(client, name="clients_demo", **extra):
    detected = upload(client, WIDE_FR).json()
    mapping = {"roles": roles_of(detected),
               "indicators": {"clients_exemple_fictif": {"unit": "count"}}, **extra}
    return detected, client.post("/api/sources/confirm",
                                 json={"upload_id": detected["upload_id"], "name": name, "mapping": mapping})


def test_confirm_registers_copies_and_starts_the_job(cfg, tmp_path):
    runner = Runner()
    client, _ = make_client(cfg, tmp_path, runner)
    detected, response = confirm_demo(client)
    assert response.status_code == 200, response.json()
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "success" and job["run_id"] == "user_test" and runner.calls == [("add", "clients_demo")]
    assert (tmp_path / "sources" / "clients_demo.yaml").is_file()
    copy = tmp_path / "uploads" / "clients_demo.csv"
    assert copy.read_bytes() == WIDE_FR.encode("utf-8")  # copie a l'identique
    assert not (tmp_path / "pending" / f"{detected['upload_id']}.csv").exists()
    # etat sur disque : relu par un nouveau gestionnaire (API redemarree)
    reread = JobManager(tmp_path / "jobs", timeout_s=900, runner=Runner())
    assert reread.get(job["job_id"])["status"] == "success"
    listed = client.get("/api/sources").json()["sources"]
    assert [(s["name"], s["status"], s["last_job"]["status"]) for s in listed] == [
        ("clients_demo", "pending", "success")]


def test_same_fingerprint_is_offered_and_reused(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    _, first = confirm_demo(client)
    wait_job(client, first.json()["job_id"])
    again = upload(client, WIDE_FR.replace("140", "141")).json()
    assert [item["name"] for item in again["reusable"]] == ["clients_demo"]
    dry = client.post("/api/sources/dry-run", json={"upload_id": again["upload_id"], "name": "clients_demo",
                                                    "mapping": {"reuse": "clients_demo"}}).json()
    assert dry["missing_fields"] == [] and dry["indicators"][0]["unit"] == "count"
    taken = client.post("/api/sources/confirm", json={"upload_id": again["upload_id"], "name": "clients_demo",
                                                      "mapping": {"reuse": "clients_demo"}})
    assert taken.status_code == 409 and "Remplacer le fichier" in taken.json()["detail"]
    replaced = client.post("/api/sources/confirm", json={"upload_id": again["upload_id"], "name": "clients_demo",
                                                         "mapping": {"reuse": "clients_demo", "replace": True}})
    assert replaced.status_code == 200 and replaced.json()["replaced"] is True


def test_job_busy_returns_409_and_delete_starts_a_job(cfg, tmp_path):
    runner = Runner(wait=True)
    client, _ = make_client(cfg, tmp_path, runner)
    _, first = confirm_demo(client)
    assert first.status_code == 200
    _, second = confirm_demo(client, name="autre_source")
    assert second.status_code == 409 and "déjà en cours" in second.json()["detail"]
    assert client.delete("/api/sources/clients_demo").status_code == 409
    runner.release.set()
    wait_job(client, first.json()["job_id"])
    deleted = client.delete("/api/sources/clients_demo")
    assert deleted.status_code == 200
    assert wait_job(client, deleted.json()["job_id"])["kind"] == "delete"
    assert not (tmp_path / "sources" / "clients_demo.yaml").exists()
    assert (tmp_path / "uploads" / "clients_demo.csv").is_file()  # copie conservee
    assert client.delete("/api/sources/clients_demo").status_code == 404


def test_timeout_and_orphan_jobs_end_in_error(tmp_path):
    from datetime import datetime, timedelta

    jobs = JobManager(tmp_path / "jobs", timeout_s=900, runner=Runner())
    old = (datetime.now() - timedelta(minutes=20)).isoformat(timespec="seconds")
    jobs._write({"job_id": "b" * 32, "kind": "add", "source": "lente", "status": "running",
                 "started_at": old, "heartbeat_at": datetime.now().isoformat(timespec="seconds")})
    stuck = jobs.get("b" * 32)
    assert stuck["status"] == "error" and "Délai dépassé (15 min)" in stuck["message"]
    assert jobs.active() is None  # un job clos ne bloque plus les suivants
    orphan = JobManager(tmp_path / "jobs2", timeout_s=900, runner=Runner())
    orphan._write({"job_id": "a" * 32, "kind": "add", "source": "x", "status": "running",
                   "started_at": (datetime.now() - timedelta(minutes=5)).isoformat(timespec="seconds"),
                   "heartbeat_at": (datetime.now() - timedelta(minutes=4)).isoformat(timespec="seconds")})
    assert "redémarrage" in orphan.get("a" * 32)["message"]


# --------------------------------------------------------------- refus
def test_oversized_wrong_extension_type_and_invalid_names(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    big = upload(client, "Pays;2021;2022\n" + "Tunisie;1;2\n" * 2000)
    assert big.status_code == 413 and "trop volumineux" in big.json()["detail"]
    assert upload(client, WIDE_FR, filename="donnees.xlsx").status_code == 400
    assert upload(client, WIDE_FR, content_type="application/pdf").status_code == 415
    detected = upload(client, WIDE_FR).json()
    for name in ("Clients", "../etc", "findex", "a", "x" * 50):
        response = client.post("/api/sources/dry-run", json={"upload_id": detected["upload_id"], "name": name,
                                                              "mapping": {"roles": roles_of(detected)}})
        assert response.status_code in (400, 422), name
    traversal = client.post("/api/sources/dry-run", json={"upload_id": "../../config", "name": "clients_demo",
                                                          "mapping": {}})
    assert traversal.status_code == 404
    assert client.get("/api/sources/Bad-Name/data").status_code == 400


# --------------------------------------------------------------- donnees
def test_data_view_reads_only_the_user_source(cfg, tmp_path):
    client, _ = make_client(cfg, tmp_path)
    _, done = confirm_demo(client)
    wait_job(client, done.json()["job_id"])
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE fact (iso3 VARCHAR, country VARCHAR, year BIGINT, source VARCHAR, "
                    "indicator_code VARCHAR, indicator_label VARCHAR, dimension VARCHAR, dimension_value VARCHAR, "
                    "value DOUBLE, unit VARCHAR)")
        con.executemany("INSERT INTO fact VALUES (?, NULL, ?, ?, ?, NULL, 'all', 'all', ?, ?)", [
            ("TUN", 2021, "user:clients_demo", "clients_demo.clients_exemple_fictif", 120.5, "count"),
            ("TUN", 2022, "user:clients_demo", "clients_demo.clients_exemple_fictif", 131.25, "count"),
            ("TUN", 2024, "findex", "account_t_d", 0.378, "fraction")])
    client, _ = make_client(cfg, tmp_path, warehouse=warehouse)
    data = client.get("/api/sources/clients_demo/data", params={"iso3": "TUN"}).json()
    assert data["chip"] == "Vos données" and data["provider"] == "user"
    assert [(v["year"], v["value"]) for v in data["values"]] == [(2021, 120.5), (2022, 131.25)]
    listed = client.get("/api/sources").json()["sources"][0]
    assert (listed["status"], listed["rows"], listed["years"], listed["countries"]) == (
        "included", 2, [2021, 2022], ["TUN"])
    assert client.get("/api/sources/inconnue/data").status_code == 404


# -------------------------------------------------------------------- S6
def test_csv_exports_neutralise_formula_cells(tmp_path):
    frame = pd.DataFrame({"=cmd|' /C calc'!A0": ["=1+1", "+33", "-2", "@SUM(A1)", "texte", None],
                          "value": [-1.5, 2.0, 3.0, 4.0, 5.0, 6.0]}, index=["=x", "b", "c", "d", "e", "f"])
    safe = neutralize_formulas(frame)
    assert list(safe.columns) == ["'=cmd|' /C calc'!A0", "value"]
    assert safe.iloc[:5, 0].tolist() == ["'=1+1", "'+33", "'-2", "'@SUM(A1)", "texte"]
    assert safe["value"].tolist() == [-1.5, 2.0, 3.0, 4.0, 5.0, 6.0]  # nombres inchanges
    text = write_csv(frame, tmp_path / "export.csv", index=True).read_text(encoding="utf-8-sig")
    assert "'=1+1" in text and "'=x" in text and "\n=" not in text and ",=" not in text


def test_job_file_survives_concurrent_status_reads(tmp_path):
    """Suivi (lectures) pendant les mises a jour du job : jamais d'acces refuse."""
    def runner(job, update):
        for index in range(200):
            update(step=f"etape {index}")
        update(status="success")

    jobs = JobManager(tmp_path / "jobs", timeout_s=900, runner=runner)
    job = jobs.start("add", "lecture")
    seen = set()
    for _ in range(2000):
        state = jobs.get(job["job_id"])
        seen.add(state["status"])
        if state["status"] == "success":
            break
    assert jobs.get(job["job_id"])["status"] == "success" and "error" not in seen
