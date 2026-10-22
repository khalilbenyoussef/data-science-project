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
