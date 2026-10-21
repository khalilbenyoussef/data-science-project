from __future__ import annotations

import pytest

from biflow.llm import LLMConfigError, build_agent_llm, key_format_ok


def test_key_format_ok_detects_wrong_service():
    assert key_format_ok("claude", {"type": "anthropic"}, "sk-ant-api03-abc")
    assert not key_format_ok("claude", {"type": "anthropic"}, "cfut_abc")
    assert key_format_ok("groq", {"type": "groq"}, "gsk_abc")
    assert not key_format_ok("groq", {"type": "groq"}, "sk-ant-abc")
    assert key_format_ok("gemini", {"type": "google"}, "AQ.Ab8abc")


def test_key_format_ok_can_be_disabled():
    spec = {"type": "anthropic", "skip_key_check": True}
    assert key_format_ok("claude", spec, "n-importe-quoi")


def test_build_agent_llm_without_any_key(monkeypatch):
    for var in ("GOOGLE_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    cfg = {
        "llm": {
            "providers": {
                "gemini": {"type": "google", "model": "gemini-3.5-flash"},
                "groq": {"type": "groq", "model": "openai/gpt-oss-120b"},
                "claude": {"type": "anthropic", "model": "claude-sonnet-4-5"},
            },
            "routing": {"semantic": ["claude", "gemini", "groq"]},
        }
    }

    with pytest.raises(LLMConfigError, match="aucun LLM disponible"):
        build_agent_llm("semantic", cfg)


def test_build_agent_llm_skips_wrong_key_format(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "AQ.fake-key-for-construction")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cfut_fake-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    cfg = {
        "llm": {
            "providers": {
                "gemini": {"type": "google", "model": "gemini-3.5-flash"},
                "groq": {"type": "groq", "model": "openai/gpt-oss-120b"},
                "claude": {"type": "anthropic", "model": "claude-sonnet-4-5"},
            },
            "routing": {"semantic": ["claude", "gemini", "groq"]},
        }
    }

    client = build_agent_llm("semantic", cfg)

    assert client.agent == "semantic"
    assert client.max_calls is None
