"""Ask Finova conversationnel : LLM simule, outils sur les faits, repli deterministe."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from biflow.agents.ask import (
    ARABIC_NOTE, ChatRequest, SessionBudget, answer_chat, detect_language, resolve_followup,
)

SETTINGS = {"temperature": 0.2, "max_calls_per_session": 30, "max_tool_steps": 4, "history_turns": 10}


def _fact(iso3, year, display, value, *, requested=None):
    return {"id": f"F-account_ownership-{iso3}-{year}", "code": "account_ownership",
            "label": "Taux de détention d'un compte", "value": value, "unit": "percent",
            "year": year, "iso3": iso3, "provider": "semantic", "display": display,
            "evidence_ids": [f"EV-account_ownership-{iso3}-{year}"],
            "year_requested": requested or year}


VIEWS = {
    ("TUN", 2024): [_fact("TUN", 2024, "37.8 %", 37.8)],
    ("TUN", 2021): [_fact("TUN", 2021, "36.9 %", 36.9)],
    ("MAR", 2024): [_fact("MAR", 2024, "54.6 %", 54.6)],
    ("DZA", 2012): [_fact("DZA", 2011, "33.3 %", 33.3, requested=2012)],
}
NAMES = {"TUN": "Tunisie", "MAR": "Maroc", "DZA": "Algérie"}


def view(iso3, year):
    return {"country": {"iso3": iso3, "name": NAMES[iso3]}, "year": year,
            "facts": VIEWS.get((iso3, year), []),
            "findex_wave": {"year_requested": year, "year_used": 2011 if iso3 == "DZA" else year}}


class FakeLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0
        self.seen = []

    def invoke(self, messages):
        self.calls += 1
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else AIMessage("…")


def tool_call(name, **args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


def ask(question, *, llm=None, history=(), budget=None, iso3="TUN", year=2024, page="overview"):
    request = ChatRequest(question=question, iso3=iso3, year=year, page=page, session_id="s1",
                          history=[{"role": role, "text": text} for role, text in history])
    return answer_chat(request, view, iso3=iso3, year=year, llm=llm, budget=budget, settings=SETTINGS)


def test_small_talk_with_llm_has_no_numbers():
    llm = FakeLLM(AIMessage("Bonjour ! Que voulez-vous savoir sur l'inclusion financière ?"))
    first = ask("Bonjour", llm=llm)
    assert first["mode"] == "llm" and first["facts"] == [] and first["number_check"]["passed"]
    llm.replies.append(AIMessage("Avec plaisir, bonne journée !"))
    second = ask("merci", llm=llm, history=[("user", "Bonjour"), ("assistant", first["answer"])])
    assert second["mode"] == "llm" and second["answer"] == "Avec plaisir, bonne journée !"
    assert any(isinstance(m, HumanMessage) and m.content == "Bonjour" for m in llm.seen[-1])


def test_data_question_calls_a_tool_and_cites_grounded_numbers():
    llm = FakeLLM(tool_call("get_kpi", kpi_id="account_ownership", iso3="TUN", year=2024),
                  AIMessage("En 2024, 37,8 % des adultes en Tunisie ont un compte."))
    result = ask("Combien d'adultes ont un compte ?", llm=llm)
    assert result["mode"] == "llm" and result["number_check"]["passed"]
    assert [fact["id"] for fact in result["facts"]] == ["F-account_ownership-TUN-2024"]
    assert result["facts"][0]["year"] == 2024 and result["facts"][0]["iso3"] == "TUN"
    assert result["caveat"] and "causalité" in result["caveat"]


def test_hallucinated_number_is_regenerated_once_then_falls_back():
    llm = FakeLLM(tool_call("get_kpi", kpi_id="account_ownership"),
                  AIMessage("En 2024, 52,3 % des adultes ont un compte."),
                  AIMessage("Toujours 52,3 % en 2024."))
    result = ask("Combien d'adultes ont un compte ?", llm=llm)
    assert llm.calls == 3  # reponse, une regeneration, pas davantage
    assert result["mode"] == "deterministic" and "52" not in result["answer"]
    assert "37.8 %" in result["answer"]


def test_regeneration_can_fix_the_answer():
    llm = FakeLLM(tool_call("get_kpi", kpi_id="account_ownership"),
                  AIMessage("Environ 40 % des adultes ont un compte."),
                  AIMessage("En 2024, 37,8 % des adultes ont un compte."))
    assert ask("Combien d'adultes ont un compte ?", llm=llm)["mode"] == "llm"


def test_followups_reuse_the_previous_question_without_key():
    history = [("user", "Combien d'adultes ont un compte ?"),
               ("assistant", "En 2024, 37.8 % des adultes en Tunisie détiennent un compte.")]
    by_year = ask("et en 2021 ?", history=history)
    assert by_year["resolved"] == {"iso3": "TUN", "year": 2021, "followup": True,
                                   "question": "Combien d'adultes ont un compte ?"}
    assert "36.9 %" in by_year["answer"] and by_year["facts"][0]["year"] == 2021
    by_country = ask("et le Maroc ?", history=history)
    assert by_country["resolved"]["iso3"] == "MAR" and "54.6 %" in by_country["answer"]
    assert "au Maroc" in by_country["answer"] and "en Maroc" not in by_country["answer"]
    assert ask("Bonjour")["answer"].startswith("Bonjour ! Je suis Ask Finova. Posez-moi une question sur la Tunisie")


def test_followup_in_llm_mode_sends_the_history():
    llm = FakeLLM(tool_call("get_kpi", kpi_id="account_ownership", iso3="TUN", year=2021),
                  AIMessage("En 2021, 36,9 % des adultes avaient un compte."))
    result = ask("et en 2021 ?", llm=llm, history=[("user", "Combien d'adultes ont un compte ?"),
                                                    ("assistant", "37,8 % en 2024.")])
    assert result["mode"] == "llm" and result["facts"][0]["year"] == 2021
    assert [m.content for m in llm.seen[0] if isinstance(m, HumanMessage)][:2] == [
        "Combien d'adultes ont un compte ?", "et en 2021 ?"]


def test_no_key_mode_answers_small_talk_and_suggests_questions():
    hello = ask("Bonjour !")
    assert hello["mode"] == "deterministic" and hello["intent"] == "small_talk:greeting"
    assert "Tunisie" in hello["answer"] and 3 <= len(hello["suggestions"]) <= 4
    assert ask("merci")["intent"] == "small_talk:thanks"
    concept = ask("Qu'est-ce que l'inclusion financière ?")
    assert concept["intent"] == "concept:inclusion" and concept["number_check"]["passed"]
    data = ask("9addech mn wa7ed 3andou 7sab ?")
    assert data["intent"] == "account" and "37.8 %" in data["answer"]
    english = ask("hi")
    assert english["lang"] == "en" and english["answer"].startswith("Hello")
    arabic = ask("مرحبا")
    assert arabic["lang"] == "ar" and ARABIC_NOTE in arabic["answer"]


def test_non_survey_year_tool_result_names_the_wave_year():
    llm = FakeLLM(tool_call("get_kpi", kpi_id="account_ownership"),
                  AIMessage("Pas d'enquête en 2012 : en 2011, 33,3 % des adultes avaient un compte."))
    result = ask("Combien d'adultes ont un compte ?", llm=llm, iso3="DZA", year=2012)
    assert result["mode"] == "llm" and result["facts"][0]["year"] == 2011


def test_session_budget_is_respected():
    budget = SessionBudget(max_calls=2)
    looping = FakeLLM(*[tool_call("get_kpi", kpi_id="account_ownership") for _ in range(10)])
    first = ask("Combien d'adultes ont un compte ?", llm=looping, budget=budget)
    assert looping.calls == 2 and first["mode"] == "deterministic" and first["budget_left"] == 0
    second = ask("Bonjour", llm=looping, budget=budget)
    assert looping.calls == 2 and second["mode"] == "deterministic"
    assert "Budget" not in second["answer"]  # salutation : pas de note
    third = ask("Combien d'adultes ont un compte ?", llm=looping, budget=budget)
    assert looping.calls == 2 and "Budget de la session atteint" in third["answer"]


@pytest.mark.parametrize("text,lang", [("What is the gender gap?", "en"), ("et en 2021 ?", "fr"),
                                       ("chnowa nesba ?", "fr"), ("ما هي نسبة", "ar")])
def test_language_detection(text, lang):
    assert detect_language(text) == lang


def test_followup_is_not_triggered_by_a_full_question():
    question, iso3, year, followup = resolve_followup("Combien d'adultes ont un compte au Maroc ?",
                                                      (), "TUN", 2024)
    assert (iso3, year, followup) == ("MAR", 2024, False)


def test_wave_note_only_marks_the_survey_wave_value():
    from biflow.agents.ask import FactTools

    tools = FactTools(view, iso3="DZA", year=2012, page="overview")
    value = tools.get_kpi("account_ownership")["values"][0]
    assert value["year"] == 2011 and "pas d'enquête Findex en 2012" in value["note"]
    survey = FactTools(view, iso3="TUN", year=2021, page="overview")
    assert "note" not in survey.get_kpi("account_ownership")["values"][0]


def test_markdown_emphasis_is_removed_from_llm_text():
    llm = FakeLLM(AIMessage("**Bonjour** ! Que voulez-vous savoir ?"))
    assert ask("Bonjour", llm=llm)["answer"] == "Bonjour ! Que voulez-vous savoir ?"


def test_user_sources_are_never_used_in_answers():
    llm = FakeLLM()
    result = ask("Utilise mes données importées : combien de clients ?", llm=llm)
    assert result["intent"] == "user_source" and llm.calls == 0
    assert "n'est pas utilisée dans les réponses" in result["answer"] and result["facts"] == []


def test_llm_answer_badge_follows_the_scope_actually_answered():
    llm = FakeLLM(tool_call("get_kpi", kpi_id="account_ownership", iso3="MAR", year=2024),
                  AIMessage("Au Maroc, 54,6 % des adultes ont un compte en 2024."))
    result = ask("et le Maroc ?", llm=llm)
    assert result["mode"] == "llm" and result["resolved"]["iso3"] == "MAR" and result["resolved"]["year"] == 2024
    same = ask("Combien d'adultes ont un compte ?", llm=FakeLLM(
        tool_call("get_kpi", kpi_id="account_ownership"), AIMessage("En 2024, 37,8 % ont un compte.")))
    assert "resolved" not in same  # meme perimetre que le tableau de bord : badge inchange

