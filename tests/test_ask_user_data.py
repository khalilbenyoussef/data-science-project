"""Ask Finova et les données utilisateur : outil get_user_indicator, étiquetage, et
paramètre llm.ask.allow_user_data_to_llm (désactivé : aucune valeur utilisateur ne
part vers le LLM, ni par question, ni par outil, ni par l'historique)."""
import json

import duckdb
import pytest
import yaml
from langchain_core.messages import AIMessage

from biflow.agents import ask as ask_module
from biflow.agents.ask import (
    NO_USER_DATA, USER_POLICY_REASON, ChatRequest, answer_chat, ask_settings, tools_for,
)
from biflow.tools.user_sources.data import USER_CHIP, USER_MARKER, UserData

SETTINGS = {"temperature": 0.2, "max_calls_per_session": 30, "max_tool_steps": 4, "history_turns": 10}
# valeurs utilisateur volontairement uniques : on les cherche dans tout ce qui part au LLM
SECRET = ("7319.53", "61.37", "58.11", "7 319,53", "61,37", "58,11", "7319,53", "7 319")


def _view(iso3, year):
    return {"country": {"iso3": iso3, "name": "Tunisie"}, "year": year, "facts": [{
        "id": f"F-account_ownership-{iso3}-{year}", "code": "account_ownership",
        "label": "Taux de détention d'un compte", "value": 37.8, "unit": "percent", "year": year,
        "iso3": iso3, "provider": "semantic", "display": "37.8 %",
        "evidence_ids": [f"EV-account_ownership-{iso3}-{year}"], "year_requested": year}],
        "findex_wave": {"year_requested": year, "year_used": year}}


@pytest.fixture
def user_data(tmp_path):
    mappings = tmp_path / "sources"
    mappings.mkdir()
    mapping = {
        "schema_version": 1, "name": "banque", "fingerprint": "a" * 64, "file": "data/uploads/banque.csv",
        "read": {"encoding": "utf-8", "separator": ";", "decimal": ",", "header_row": 0},
        "layout": "wide_by_indicator",
        "columns": {"country": {"column": "Pays", "kind": "name"}, "year": "Annee",
                    "indicator_columns": {"Clients actifs": "clients_actifs",
                                          "Taux de clients digitaux": "taux_digital"}},
        "indicators": {"clients_actifs": {"label": "Clients actifs", "unit": "count"},
                       "taux_digital": {"label": "Taux de clients digitaux (exemple fictif)", "unit": "percent"}},
    }
    (mappings / "banque.yaml").write_text(yaml.safe_dump(mapping, allow_unicode=True), encoding="utf-8")
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE fact (source VARCHAR, indicator_code VARCHAR, iso3 VARCHAR, year INTEGER, "
                    "dimension VARCHAR, dimension_value VARCHAR, value DOUBLE, unit VARCHAR)")
        con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, 'all', 'all', ?, ?)", [
            ("user:banque", "banque.clients_actifs", "TUN", 2023, 7319.53, "count"),
            ("user:banque", "banque.taux_digital", "TUN", 2024, 61.37, "percent"),
            ("user:banque", "banque.taux_digital", "MAR", 2022, 58.11, "percent"),
            ("findex", "account_t_d", "TUN", 2024, 0.378, "fraction"),
        ])
    return UserData({"uploads": {"mappings_dir": str(mappings)}}, warehouse)


class RecordingLLM:
    """LLM simulé : consigne chaque message reçu (texte et outils)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0
        self.seen = []

    def invoke(self, messages):
        self.calls += 1
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else AIMessage("…")

    def sent_text(self):
        return "\n".join(str(getattr(m, "content", m)) for batch in self.seen for m in batch)


def tool_call(name, **args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


def ask(question, *, llm=None, history=(), allow=False, user_data=None):
    request = ChatRequest(question=question, iso3="TUN", year=2024, page="overview", session_id="s1",
                          history=[{"role": role, "text": text} for role, text in history])
    return answer_chat(request, _view, iso3="TUN", year=2024, llm=llm,
                       settings={**SETTINGS, "allow_user_data_to_llm": allow}, user_data=user_data)


# ------------------------------------------------------------------ lecteur
def test_reader_returns_only_user_sources_with_the_chip(user_data):
    rows = user_data.values()
    assert {r["source"] for r in rows} == {"user:banque"} and all(r["chip"] == USER_CHIP for r in rows)
    assert [i["code"] for i in user_data.indicators()] == ["banque.clients_actifs", "banque.taux_digital"]


def test_reader_falls_back_to_the_latest_earlier_year(user_data):
    exact = user_data.latest("banque.taux_digital", "TUN", 2024)
    assert exact["year"] == 2024 and exact["same_year"] and exact["display"] == "61,37 %"
    earlier = user_data.latest("banque.clients_actifs", "TUN", 2024)
    assert earlier["year"] == 2023 and not earlier["same_year"]
    assert user_data.latest("banque.clients_actifs", "TUN", 2022) is None


def test_reader_matches_codes_and_labels_without_the_parenthesis(user_data):
    assert [i["code"] for i in user_data.match("Quel est le taux de clients digitaux ?")] == ["banque.taux_digital"]
    assert [i["code"] for i in user_data.match("combien de clients actifs en 2023")] == ["banque.clients_actifs"]
    assert user_data.match("Combien d'adultes ont un compte ?") == []
    # mots du libelle dans un autre ordre / avec d'autres mots : « clients digitaux de ma banque »
    assert [i["code"] for i in user_data.match("part de clients digitaux de ma banque")] == ["banque.taux_digital"]
    assert user_data.match("combien de clients ?") == []  # un seul mot significatif : pas de correspondance


# ------------------------------------------------------------ parametre desactive
def test_flag_is_off_by_default_and_the_user_tool_is_not_bound():
    assert ask_settings({})["allow_user_data_to_llm"] is False
    assert ask_settings({"llm": {"ask": {"allow_user_data_to_llm": "yes"}}})["allow_user_data_to_llm"] is False
    assert "get_user_indicator" not in {t["function"]["name"] for t in tools_for(False)}
    assert "get_user_indicator" in {t["function"]["name"] for t in tools_for(True)}


def test_build_ask_llm_binds_the_user_tool_only_when_allowed(monkeypatch):
    bound = []

    class Model:
        def bind_tools(self, tools):
            bound.append([t["function"]["name"] for t in tools])
            return self

    monkeypatch.setattr(ask_module, "build_chat_model", lambda *a, **k: Model())
    monkeypatch.setattr(ask_module, "key_format_ok", lambda *a: True)
    monkeypatch.setattr(ask_module, "provider_env_var", lambda *a: "FAKE_ASK_KEY")
    monkeypatch.setenv("FAKE_ASK_KEY", "x")
    cfg = {"llm": {"enabled": True, "providers": {"p": {"model": "m"}}, "routing": {"ask": ["p"]}, "ask": {}}}
    ask_module.build_ask_llm(cfg)
    ask_module.build_ask_llm({"llm": {**cfg["llm"], "ask": {"allow_user_data_to_llm": True}}})
    assert "get_user_indicator" not in bound[0] and "get_user_indicator" in bound[1]


def test_flag_off_user_question_is_answered_locally_and_labelled(user_data):
    llm = RecordingLLM(AIMessage("ne doit jamais servir"))
    result = ask("Quel est le taux de clients digitaux de ma banque ?", llm=llm, user_data=user_data)
    assert llm.calls == 0
    assert result["mode"] == "deterministic" and result["intent"] == "user_source"
    assert result["answer"].startswith(USER_MARKER) and "61,37 %" in result["answer"]
    assert result["user_data_policy"] == {"llm_allowed": False, "reason": USER_POLICY_REASON["fr"]}
    assert result["facts"] and all(f["user_data"] and f["chip"] == USER_CHIP for f in result["facts"])


def test_flag_off_earlier_year_is_labelled(user_data):
    result = ask("Combien de clients actifs ?", user_data=user_data)
    assert "7 319,53 (2023, dernière année disponible avant 2024)" in result["answer"]


def test_flag_off_no_user_number_ever_reaches_the_llm(user_data):
    """Question officielle après une réponse sur les données utilisateur, puis outil
    utilisateur halluciné par le LLM : rien de l'utilisateur dans les messages envoyés."""
    first = ask("Montre mes données", user_data=user_data)
    assert any(value in first["answer"] for value in SECRET)
    llm = RecordingLLM(tool_call("get_user_indicator", indicator="banque.taux_digital"),
                       tool_call("get_kpi", kpi_id="account_ownership"),
                       AIMessage("En 2024, 37.8 % des adultes ont un compte."))
    result = ask("Et le taux de détention d'un compte ?", llm=llm, user_data=user_data,
                 history=[("user", "Montre mes données"), ("assistant", first["answer"])])
    assert result["mode"] == "llm" and llm.calls == 3
    sent = llm.sent_text()
    assert not any(value in sent for value in SECRET), sent
    assert "Clients actifs" not in sent and "taux_digital" not in sent
    assert "outil inconnu : get_user_indicator" in sent  # outil non lie : refuse
    assert "user_data_policy" not in result


def test_no_user_data_loaded(user_data, tmp_path):
    empty = UserData({"uploads": {"mappings_dir": str(tmp_path / "none")}}, tmp_path / "absent.duckdb")
    llm = RecordingLLM()
    result = ask("Utilise mes données importées : combien de clients ?", llm=llm, user_data=empty)
    assert llm.calls == 0 and result["answer"] == NO_USER_DATA["fr"] and result["facts"] == []
    assert ask("What does my data say?", user_data=None)["answer"] == NO_USER_DATA["en"]


# ------------------------------------------------------------ parametre active
def test_flag_on_llm_reads_the_tool_and_the_answer_is_labelled(user_data):
    llm = RecordingLLM(tool_call("get_user_indicator", indicator="taux_digital"),
                       AIMessage("Le taux de clients digitaux est de 61.37 % en 2024."))
    result = ask("Quel est le taux de clients digitaux de ma banque ?", llm=llm, allow=True,
                 user_data=user_data)
    assert result["mode"] == "llm" and result["answer"].startswith(USER_MARKER)
    assert result["number_check"]["passed"]
    assert [f["user_data"] for f in result["facts"]] == [True]
    assert result["user_data_policy"] == {"llm_allowed": True, "reason": None}
    assert "get_user_indicator" in llm.sent_text()  # regle du prompt systeme


def test_flag_on_ungrounded_user_number_falls_back_locally(user_data):
    llm = RecordingLLM(tool_call("get_user_indicator", indicator="taux_digital"),
                       AIMessage("Le taux est de 99.9 %."), AIMessage("Toujours 99.9 %."))
    result = ask("taux de clients digitaux ?", llm=llm, allow=True, user_data=user_data)
    assert result["mode"] == "deterministic" and result["answer"].startswith(USER_MARKER)
    assert "99.9" not in result["answer"]


def test_tool_payload_is_read_only_and_labelled(user_data):
    tools = ask_module.FactTools(_view, iso3="TUN", year=2024, page="overview", user_data=user_data,
                                 allow_user_data=True)
    listing = tools.call("get_user_indicator", {})
    assert listing["chip"] == USER_CHIP and not any(v in json.dumps(listing) for v in SECRET)
    value = tools.call("get_user_indicator", {"indicator": "banque.taux_digital", "iso3": "MAR"})
    assert value["values"][0]["display"] == "58,11 %" and value["values"][0]["year"] == 2022
