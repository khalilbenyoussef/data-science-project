"""« Vos données : IA externe » : choix par session, consentement toujours obligatoire.

Une session commence toujours en traitement local, même si la configuration suggère
l'option ; le choix vit en mémoire (perdu au redémarrage) ; journal des consentements
sans question ni valeur ; ``user_data_llm_switch: false`` masque et refuse l'option."""
from __future__ import annotations

import copy
import json

import duckdb
import pytest
import yaml
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from biflow.agents.ask import USER_POLICY_REASON
from biflow.config import load_config
from biflow.tools.user_sources.data import USER_MARKER
from dashboard_app.api.app import create_app
from dashboard_app.api.ask_mode import NO_KEY, SWITCH_OFF, session_hash
from test_dashboard_api import _spec, spec_path  # noqa: F401 - fixture reutilisee

SECRET = ("7319.53", "61.37", "7 319,53", "61,37", "7319,53")
QUESTION = "Quel est le taux de clients digitaux de ma banque ?"


class RecordingLLM:
    """LLM simule : consigne tout ce qu'il recoit ; appelle l'outil utilisateur si on le lui demande."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []

    def invoke(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else AIMessage("Je n'ai pas cette information.")

    def sent(self):
        return "\n".join(str(getattr(m, "content", m)) for batch in self.seen for m in batch)


@pytest.fixture
def world(tmp_path, spec_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "banque.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "name": "banque", "fingerprint": "d" * 64, "file": "data/uploads/banque.csv",
        "read": {"encoding": "utf-8", "separator": ";", "decimal": ",", "header_row": 0},
        "layout": "wide_by_indicator",
        "columns": {"country": {"column": "Pays", "kind": "name"}, "year": "Annee",
                    "indicator_columns": {"a": "clients_actifs", "b": "taux_digital"}},
        "indicators": {"clients_actifs": {"label": "Clients actifs", "unit": "count"},
                       "taux_digital": {"label": "Taux de clients digitaux (exemple fictif)", "unit": "percent"}}},
        allow_unicode=True), encoding="utf-8")
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE fact (source VARCHAR, indicator_code VARCHAR, iso3 VARCHAR, year INTEGER, "
                    "dimension VARCHAR, dimension_value VARCHAR, value DOUBLE, unit VARCHAR)")
        con.executemany("INSERT INTO fact VALUES ('user:banque', ?, 'TUN', ?, 'all', 'all', ?, ?)", [
            ("banque.clients_actifs", 2023, 7319.53, "count"), ("banque.taux_digital", 2024, 61.37, "percent")])
    base = load_config()
    base["uploads"] = {**(base.get("uploads") or {}), "mappings_dir": str(sources)}

    def make(*, ask=None, provider="Groq", model=None, user_model=None):
        cfg = copy.deepcopy(base)
        cfg["llm"]["ask"] = {**cfg["llm"]["ask"], **(ask or {})}
        app = create_app(spec_path=spec_path, warehouse_path=warehouse, reports_dir=tmp_path / "reports",
                         history_dir=tmp_path / "history", web_dist=tmp_path / "dist",
                         spec_builder=lambda iso3, year: _spec(iso3, year), prewarm=False, config=cfg,
                         ask_model=model, ask_user_model=user_model, ask_provider=provider,
                         consent_log=tmp_path / "logs" / "user_data_consent.log")
        return TestClient(app)

    make.log = tmp_path / "logs" / "user_data_consent.log"
    return make


def mode(client, session="s1"):
    return client.get("/api/ask/user-data-mode", params={"session_id": session}).json()


def set_mode(client, enabled, consent=False, session="s1"):
    return client.post("/api/ask/user-data-mode", json={"session_id": session, "enabled": enabled, "consent": consent})


def ask(client, session="s1", history=()):
    return client.post("/api/ask", json={"question": QUESTION, "session_id": session, "page": "overview",
                                         "history": list(history)}).json()


# ------------------------------------------------------------------ etat par defaut
def test_new_session_is_off_and_restart_resets(world):
    client = world(model=RecordingLLM())
    assert mode(client) == {"enabled": False, "switch_available": True, "llm_available": True,
                            "provider": "Groq", "suggested": False, "reason": None}
    assert set_mode(client, True, consent=True).json()["enabled"] is True
    restarted = world(model=RecordingLLM())  # nouvelle instance = redemarrage du serveur
    assert mode(restarted)["enabled"] is False


def test_config_true_only_suggests_and_never_turns_a_session_on(world):
    llm = RecordingLLM()
    user_llm = RecordingLLM(AIMessage("", tool_calls=[{"name": "get_user_indicator", "id": "c1",
                                                        "args": {"indicator": "taux_digital"}}]))
    client = world(ask={"allow_user_data_to_llm": True}, model=llm, user_model=user_llm)
    status = mode(client)
    assert status["suggested"] is True and status["enabled"] is False
    body = ask(client)
    assert body["mode"] == "deterministic" and body["user_data_policy"]["llm_allowed"] is False
    assert llm.seen == [] and user_llm.seen == []  # aucun modele appele, outil utilisateur jamais lie


# ------------------------------------------------------------------ activation
def test_enabling_requires_consent_and_a_key(world):
    client = world(model=RecordingLLM())
    refused = set_mode(client, True, consent=False)
    assert refused.status_code == 400 and "Consentement requis" in refused.json()["detail"]
    no_key = world(model=None, provider=None)
    status = mode(no_key)
    assert status["llm_available"] is False and status["reason"] == NO_KEY
    response = set_mode(no_key, True, consent=True)
    assert response.status_code == 400 and response.json()["detail"] == NO_KEY


def test_consent_applies_to_one_session_only_and_off_needs_no_consent(world):
    client = world(model=RecordingLLM())
    assert set_mode(client, True, consent=True, session="s1").json()["enabled"] is True
    assert mode(client, "s1")["enabled"] is True and mode(client, "s2")["enabled"] is False
    off = set_mode(client, False, consent=False, session="s1")
    assert off.status_code == 200 and off.json()["enabled"] is False


@pytest.mark.parametrize("session", ["../x", "a b", "x" * 65, ""])
def test_invalid_session_ids_are_refused(world, session):
    client = world(model=RecordingLLM())
    assert set_mode(client, True, consent=True, session=session).status_code in (400, 422)


def test_admin_switch_off_hides_and_refuses(world):
    client = world(ask={"user_data_llm_switch": False, "allow_user_data_to_llm": True}, model=RecordingLLM())
    status = mode(client)
    assert status["switch_available"] is False and status["suggested"] is False and status["reason"] == SWITCH_OFF
    response = set_mode(client, True, consent=True)
    assert response.status_code == 400 and response.json()["detail"] == SWITCH_OFF


# ------------------------------------------------------------------ ce qui part au LLM
def test_off_no_user_value_reaches_the_llm_even_through_history(world):
    llm = RecordingLLM(AIMessage("", tool_calls=[{"name": "get_user_indicator", "id": "c1",
                                                   "args": {"indicator": "taux_digital"}}]),
                       AIMessage("En 2024, 37,8 % des adultes ont un compte."))
    client = world(model=llm)
    local = ask(client)
    assert local["mode"] == "deterministic" and local["answer"].startswith(USER_MARKER)
    assert local["user_data_policy"]["reason"] == USER_POLICY_REASON["fr"]
    client.post("/api/ask", json={"question": "Et le taux de détention d'un compte ?", "session_id": "s1",
                                  "history": [{"role": "user", "text": QUESTION},
                                              {"role": "assistant", "text": local["answer"]}]})
    sent = llm.sent()
    assert llm.seen and not any(value in sent for value in SECRET), sent
    assert "outil inconnu : get_user_indicator" in sent


def test_on_binds_the_user_tool_and_labels_the_answer(world):
    llm = RecordingLLM()
    user_llm = RecordingLLM(AIMessage("", tool_calls=[{"name": "get_user_indicator", "id": "c1",
                                                        "args": {"indicator": "taux_digital"}}]),
                            AIMessage("Le taux de clients digitaux est de 61,37 % en 2024."))
    client = world(model=llm, user_model=user_llm)
    set_mode(client, True, consent=True)
    body = ask(client)
    assert body["mode"] == "llm" and body["answer"].startswith(USER_MARKER)
    assert body["user_data_policy"] == {"llm_allowed": True, "reason": None}
    assert user_llm.seen and llm.seen == []  # modele avec l'outil utilisateur, pour cette session seulement
    other = ask(client, session="s2")
    assert other["mode"] == "deterministic" and other["user_data_policy"]["llm_allowed"] is False


# ------------------------------------------------------------------ journal
def test_consent_log_has_no_question_and_no_value(world):
    client = world(model=RecordingLLM(AIMessage("ok")), user_model=RecordingLLM(AIMessage("ok")))
    set_mode(client, True, consent=True, session="secret-session")
    ask(client, session="secret-session")
    set_mode(client, False, session="secret-session")
    lines = [json.loads(line) for line in world.log.read_text(encoding="utf-8").splitlines()]
    assert [(line["enabled"], line["provider"]) for line in lines] == [(True, "Groq"), (False, "Groq")]
    assert all(line["session"] == session_hash("secret-session") for line in lines)
    raw = world.log.read_text(encoding="utf-8")
    assert "secret-session" not in raw and "digitaux" not in raw and not any(v in raw for v in SECRET)
    assert set(lines[0]) == {"timestamp", "session", "enabled", "provider"}
