"""Evaluation de chaque agent a partir de resultats mesures.

    python scripts/evaluate_agents.py [--with-fault-injection] [--ask-live]

- Par agent : duree, lignes en entree et en sortie, score, controles, appels LLM,
  lus dans les rapports du dernier run (Route 1 et Route 2).
- Auditor : injection de fautes (data/audit/evaluation.json ; --with-fault-injection
  la relance via scripts/evaluate_auditor.py, sur une copie des donnees).
- Analyst : audit des constats consigne dans le rapport d'audit.
- Ask Finova : tests unitaires (LLM simule) de tests/test_ask_chat.py ; avec
  --ask-live et une cle LLM, 10 questions fixes (config/ask_eval_questions.yaml)
  envoyees a POST /api/ask, en comptant les reponses dont tous les nombres sont fondes.
  Sans cle : « non mesure ».

Sorties : outputs/evaluation/agents.json (et ask_live.json). Aucune donnee modifiee.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from biflow.tools.audit_text import UNIT_LABELS, extract_numbers  # noqa: E402
from biflow.tools.deliverables import EVALUATION_DIR, agent_summaries, load_context  # noqa: E402

QUESTIONS = ROOT / "config" / "ask_eval_questions.yaml"
ASK_TESTS = "tests/test_ask_chat.py"


def run_fault_injection() -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "evaluate_auditor.py")], cwd=ROOT)


def ask_unit_tests() -> dict:
    """Tests unitaires d'Ask Finova (LLM simule) : comptes par test, lus dans le rapport JUnit."""
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "ask.xml"
        started = datetime.now()
        code = subprocess.call([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", ASK_TESTS,
                                f"--junitxml={xml_path}"], cwd=ROOT, stdout=subprocess.DEVNULL)
        if not xml_path.is_file():
            return {"label": "tests unitaires (LLM simulé)", "status": "non mesuré", "exit_code": code}
        cases = list(ET.parse(xml_path).getroot().iter("testcase"))
    failed = [c.get("name") for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c.get("name") for c in cases if c.find("skipped") is not None]
    grounding = [c.get("name") for c in cases if any(w in (c.get("name") or "") for w in
                                                      ("grounded", "hallucinated", "regenerat", "user_sources"))]
    return {"label": "tests unitaires (LLM simulé)", "file": ASK_TESTS, "run_at": started.isoformat(timespec="seconds"),
            "total": len(cases), "passed": len(cases) - len(failed) - len(skipped), "failed": failed,
            "skipped": len(skipped), "grounding_tests": grounding,
            "grounding_passed": sum(1 for name in grounding if name not in failed)}


def configured_model(cfg: dict) -> str | None:
    from biflow.llm import key_format_ok, provider_env_var

    llm = cfg.get("llm") or {}
    for name in (llm.get("routing") or {}).get("ask") or []:
        spec = (llm.get("providers") or {}).get(name) or {}
        key = os.getenv(provider_env_var(name, spec), "")
        if key and key_format_ok(name, spec, key):
            return f"{name} ({spec.get('model')})"
    return None


def ask_live(cfg: dict) -> dict:
    """Questions fixes envoyees a POST /api/ask ; nombres verifies contre les faits FinOVA."""
    from biflow.agents.ask import build_ask_llm

    model = configured_model(cfg)
    if not model or build_ask_llm(cfg) is None:
        return {"status": "non mesuré", "reason": "aucune clé LLM valide pour llm.routing.ask"}
    from fastapi.testclient import TestClient
    from dashboard_app.api.app import create_app

    questions = (yaml.safe_load(QUESTIONS.read_text(encoding="utf-8")) or {}).get("questions") or []
    client = TestClient(create_app(prewarm=False))
    peers = [(cfg.get("kpi") or {}).get("focus", "TUN"), *(cfg.get("kpi") or {}).get("peers", [])]
    reference_cache: dict[int, set[str]] = {}

    def reference(year: int) -> set[str]:
        """Nombres des faits FinOVA du pays focus et des pairs pour l'annee (valeur affichee, annee)."""
        if year not in reference_cache:
            # libelles d'unite (« pour 100 000 adultes ») : unites, pas des donnees
            allowed: set[str] = {n for labels in UNIT_LABELS.values() for label in labels.values()
                                 for n in extract_numbers(label)}
            for code in peers:
                spec = client.get("/api/spec", params={"iso3": code, "year": year}).json()
                for fact in spec.get("facts") or []:
                    allowed |= set(extract_numbers(f"{fact.get('display', '')} {fact.get('year', '')}"))
                allowed |= {str(y) for y in spec.get("years") or []}
            reference_cache[year] = allowed
        return reference_cache[year]

    results = []
    for item in questions:
        body = client.post("/api/ask", json={"question": item["question"], "iso3": item["iso3"],
                                             "year": item["year"], "page": item.get("page"),
                                             "session_id": "evaluation"}).json()
        numbers = extract_numbers(body.get("answer") or "")
        unknown = [n for n in numbers if n not in reference(int(item["year"]))]
        results.append({"id": item["id"], "question": item["question"], "mode": body.get("mode"),
                        "numbers": numbers, "unknown": unknown, "grounded": not unknown,
                        "facts": [f.get("id") for f in body.get("facts") or []],
                        "answer": body.get("answer")})
    return {"status": "mesuré", "model": model,
            "method": "chaque nombre de la réponse doit figurer dans les faits FinOVA du pays focus et des pairs "
                      "(même année), être une année de la spec ou un nombre d'un libellé d'unité ; le contrôle ne "
                      "vérifie pas que le nombre est attribué au bon indicateur", "run_at": datetime.now().isoformat(timespec="seconds"),
            "questions": len(results), "grounded": sum(r["grounded"] for r in results),
            "llm_answers": sum(r["mode"] == "llm" for r in results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=EVALUATION_DIR)
    parser.add_argument("--with-fault-injection", action="store_true", help="relance l'injection de fautes")
    parser.add_argument("--ask-live", action="store_true", help="questions fixes envoyees au LLM (cle requise)")
    parser.add_argument("--skip-unit-tests", action="store_true", help="ne relance pas les tests d'Ask Finova")
    args = parser.parse_args(argv)
    out = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    if args.with_fault_injection and run_fault_injection() != 0:
        print("injection de fautes en echec")
        return 1
    ctx = load_context()
    previous = ctx.agents_eval
    faults = ctx.fault_injection
    insight = ctx.audit.get("route2_insight_audit") or {}
    unit = previous.get("ask_unit_tests") if args.skip_unit_tests and previous else ask_unit_tests()
    live_path = out / "ask_live.json"
    if args.ask_live:
        live = ask_live(ctx.cfg)
        live_path.write_text(json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "route1_run_id": ctx.run_id, "route2_run_id": ctx.route2_run_id, "snapshot_id": ctx.snapshot_id,
        "catalog_version": ctx.catalog_version,
        "agents": agent_summaries(ctx),
        "fault_injection": {"created_at": faults.get("created_at"), "audit_run_id": faults.get("audit_run_id"),
                            "detected": faults.get("detected"), "total": faults.get("total"),
                            "faults": [{k: f.get(k) for k in ("id", "label", "expected_check", "detected", "verdict")}
                                       for f in faults.get("faults") or []]} if faults else None,
        "insight_audit": {k: insight.get(k) for k in ("run_id", "created_at", "audited", "accepted", "rejected",
                                                      "not_auditable")} if insight else None,
        "ask_unit_tests": unit,
    }
    (out / "agents.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"ecrit : {out / 'agents.json'}")
    if unit:
        print(f"Ask Finova, {unit['label']} : {unit.get('passed')}/{unit.get('total')} reussis")
    if args.ask_live:
        print(f"Ask Finova en direct : {live.get('grounded', 'non mesuré')}/{live.get('questions', '-')} fondees")
    return 0 if not (unit or {}).get("failed") else 1


if __name__ == "__main__":
    sys.exit(main())
