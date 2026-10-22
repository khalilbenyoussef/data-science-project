"""Verifie que les providers LLM sont configures et joignables.

Usage :
    python scripts/check_llm.py                 # teste Gemini et Groq
    python scripts/check_llm.py --provider groq
    python scripts/check_llm.py --agent quality

Sortie : un statut par provider, puis le budget et les tokens consommes.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from langchain_core.messages import HumanMessage  # noqa: E402

from biflow.config import load_config  # noqa: E402
from biflow.llm import (  # noqa: E402
    LLMConfigError,
    build_agent_llm,
    build_chat_model,
    key_format_ok,
    provider_env_var,
)

PROMPT = "Reponds uniquement par le mot OK."


def _key_format_hint(name: str, spec: dict, key: str) -> str:
    if key_format_ok(name, spec, key):
        return ""
    ptype = str(spec.get("type", name)).lower()
    expected = {
        "google": "AQ. ou AIza",
        "gemini": "AQ. ou AIza",
        "groq": "gsk_",
    }.get(ptype, "?")
    return f"la cle ne ressemble pas a une cle {name} (prefixe attendu : {expected})"


def _explain_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if "getaddrinfo" in text or "connection" in text or "timed out" in text:
        return "reseau/DNS indisponible (verifier connexion ou VPN)"
    if "429" in text or "rate limit" in text or "quota" in text:
        return "quota / limite de debit atteint (fallback ou attendre)"
    if "1010" in text or "403" in text or "forbidden" in text:
        return "acces refuse 403 (cle restreinte ou blocage Cloudflare/reseau)"
    if (
        "401" in text
        or "unauthorized" in text
        or "invalid api key" in text
        or "invalid x-api-key" in text
        or "authentication" in text
    ):
        return "cle refusee 401 (invalide, revoquee ou mauvais service)"
    if "404" in text or "not_found" in text or "not found" in text:
        return "modele introuvable 404 (ajuster le champ model dans config.yaml)"
    return ""


def _content(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        content = " ".join(parts)
    return " ".join(str(content).split())[:120]


def _model_label(message) -> str:
    meta = getattr(message, "response_metadata", None) or {}
    return str(meta.get("model_name") or meta.get("model") or "")


def test_provider(name: str, spec: dict, temperature: float) -> tuple[bool, str]:
    env_var = provider_env_var(name, spec)
    key = os.getenv(env_var)
    if not key:
        return False, f"cle absente : {env_var}"

    hint = _key_format_hint(name, spec, key)
    if hint:
        return False, hint

    try:
        llm = build_chat_model(name, spec, temperature)
    except ImportError as exc:
        return False, f"paquet manquant ({exc})"
    except Exception as exc:
        detail = _explain_error(exc)
        return False, f"initialisation : {exc}" + (f" -> {detail}" if detail else "")

    started = time.perf_counter()
    try:
        message = llm.invoke([HumanMessage(content=PROMPT)])
    except Exception as exc:
        detail = _explain_error(exc)
        return False, f"appel : {type(exc).__name__}: {str(exc)[:160]}" + (
            f" -> {detail}" if detail else ""
        )
    elapsed = time.perf_counter() - started

    model = _model_label(message) or spec.get("model", "?")
    return True, f"{model} | {elapsed:.1f}s | reponse: {_content(message)!r}"


def test_agent(agent: str, cfg: dict) -> bool:
    print(f"\n[agent] {agent}")
    try:
        client = build_agent_llm(agent, cfg)
        message = client.invoke([HumanMessage(content=PROMPT)])
    except LLMConfigError as exc:
        print(f"  [FAIL] {exc}")
        return False
    except Exception as exc:
        detail = _explain_error(exc)
        print(f"  [FAIL] appel : {type(exc).__name__}: {str(exc)[:200]}")
        if detail:
            print(f"         -> {detail}")
        return False

    print(f"  [OK] modele: {_model_label(message) or '?'} | reponse: {_content(message)!r}")
    print(f"  usage: {client.usage()}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifie les providers LLM de BIFlow")
    parser.add_argument("--provider", help="tester un seul provider (ex. gemini)")
    parser.add_argument("--agent", help="tester la chaine de fallback d'un agent (ex. quality)")
    args = parser.parse_args()

    cfg = load_config()
    llm_cfg = cfg.get("llm") or {}
    providers = llm_cfg.get("providers") or {}
    temperature = float(llm_cfg.get("temperature", 0))

    if args.agent:
        return 0 if test_agent(args.agent, cfg) else 1

    names = [args.provider] if args.provider else list(providers)
    unknown = [n for n in names if n not in providers]
    if unknown:
        print(f"[FAIL] provider(s) inconnu(s) dans config.llm.providers : {unknown}")
        return 1

    print("=" * 74)
    print("BIFlow - verification des providers LLM")
    print("=" * 74)

    results = []
    for name in names:
        ok, detail = test_provider(name, providers[name], temperature)
        results.append(ok)
        status = "[OK]  " if ok else "[FAIL]"
        print(f"{status} {name:<8} {detail}")

    if not any(results):
        print("\nAucun provider operationnel.")
        print("1. Copie .env.example vers .env")
        print("2. Renseigne GOOGLE_API_KEY / GROQ_API_KEY")
        print("3. Relance : python scripts/check_llm.py")
        return 1

    print(f"\n{sum(results)}/{len(results)} provider(s) operationnel(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
