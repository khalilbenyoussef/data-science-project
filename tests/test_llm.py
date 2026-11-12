from __future__ import annotations

import pytest

from biflow.agents.base import BaseAgent
from biflow.llm import LLMConfigError, build_agent_llm, key_format_ok


class _ProfilerStub(BaseAgent):
    name = "profiler"


def test_disabled_agent_uses_deterministic_fallback():
    cfg = {
        "llm": {
            "enabled": True,
            "disabled_agents": ["profiler"],
            "providers": {"groq": {"type": "groq", "model": "openai/gpt-oss-120b"}},
            "routing": {"profiler": ["groq"]},
        }
    }
    agent = _ProfilerStub(cfg=cfg)

    assert agent.get_llm() is None
    assert "desactive" in (agent.llm_error or "")
    assert agent.ask_json("prompt", fallback={"ok": True}) == {"ok": True}
    assert agent.llm_usage() == {}


def test_key_format_ok_detects_wrong_service():
    assert key_format_ok("groq", {"type": "groq"}, "gsk_abc")
    assert not key_format_ok("groq", {"type": "groq"}, "sk-ant-abc")
    assert key_format_ok("gemini", {"type": "google"}, "AQ.Ab8abc")
    assert not key_format_ok("gemini", {"type": "google"}, "gsk_abc")


def test_key_format_ok_can_be_disabled():
    spec = {"type": "groq", "skip_key_check": True}
    assert key_format_ok("groq", spec, "n-importe-quoi")


def test_build_agent_llm_without_any_key(monkeypatch):
    for var in ("GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    cfg = {
        "llm": {
            "providers": {
                "gemini": {"type": "google", "model": "gemini-3.5-flash"},
                "groq": {"type": "groq", "model": "openai/gpt-oss-120b"},
            },
            "routing": {"quality": ["groq", "gemini"]},
        }
    }

    with pytest.raises(LLMConfigError, match="aucun LLM disponible"):
        build_agent_llm("quality", cfg)


def test_build_agent_llm_skips_wrong_key_format(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "AQ.fake-key-for-construction")
    monkeypatch.setenv("GROQ_API_KEY", "not-a-groq-key")

    cfg = {
        "llm": {
            "providers": {
                "gemini": {"type": "google", "model": "gemini-3.5-flash"},
                "groq": {"type": "groq", "model": "openai/gpt-oss-120b"},
            },
            "routing": {"quality": ["groq", "gemini"]},
        }
    }

    client = build_agent_llm("quality", cfg)

    assert client.agent == "quality"
    assert client.max_calls is None


# ------------------------------------------------------------- S1 : cache JSON
class _Payload:
    """Objet pickle malveillant : creerait un fichier temoin s'il etait deserialise."""

    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return (open, (str(self.marker), "w"))


def test_llm_cache_round_trips_generations_as_json(tmp_path):
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration

    from biflow.llm import DiskCache

    cache = DiskCache(tmp_path)
    generation = ChatGeneration(message=AIMessage("Bonjour", tool_calls=[
        {"name": "get_kpi", "args": {"kpi_id": "account_ownership"}, "id": "c1"}]))
    cache.update("prompt", "llm", [generation])
    stored, = tmp_path.glob("*.json")
    assert "Bonjour" in stored.read_text(encoding="utf-8") and not list(tmp_path.glob("*.pkl"))
    again, = cache.lookup("prompt", "llm")
    assert again.message.content == "Bonjour" and again.message.tool_calls[0]["name"] == "get_kpi"


def test_planted_pickle_is_never_deserialized(tmp_path):
    import hashlib
    import pickle

    from biflow.llm import DiskCache

    marker = tmp_path / "pwned.txt"
    digest = hashlib.sha256("prompt\x00llm".encode("utf-8")).hexdigest()
    (tmp_path / f"{digest}.pkl").write_bytes(pickle.dumps(_Payload(marker)))
    cache = DiskCache(tmp_path)
    assert cache.lookup("prompt", "llm") is None
    assert not marker.exists()
    # JSON forge pointant vers une classe hors langchain : refuse, aucun effet
    (tmp_path / f"{digest}.json").write_text(
        '{"generations": [{"lc": 1, "type": "constructor", "id": ["os", "system"], "kwargs": {}}]}',
        encoding="utf-8")
    assert cache.lookup("prompt", "llm") is None
    cache.clear()
    assert (tmp_path / f"{digest}.pkl").exists() and not list(tmp_path.glob("*.json"))
