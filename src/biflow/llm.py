"""Fabrication des LLM multi-provider (Gemini / Groq).

Chaque agent recoit une chaine de fallback definie dans config.llm.routing.
Les cles sont lues dans l'environnement (.env), jamais dans la configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.load import dumpd, load
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, Generation
from langchain_core.outputs import LLMResult

from biflow.config import load_config, resolve

# provider declare dans config -> variable d'environnement contenant la cle
PROVIDER_ENV = {
    "gemini": "GOOGLE_API_KEY",
    "google": "GOOGLE_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
}

# cles de configuration passees telles quelles au constructeur LangChain
_PASSTHROUGH = {"max_tokens", "timeout", "max_retries", "top_p", "top_k"}

# prefixes attendus par provider (detecte une cle du mauvais service)
KEY_PREFIXES = {
    "google": ("AQ.", "AIza"),
    "gemini": ("AQ.", "AIza"),
    "google_genai": ("AQ.", "AIza"),
    "groq": ("gsk_",),
}


class LLMConfigError(RuntimeError):
    """Provider absent, cle manquante ou configuration LLM invalide."""


class LLMCallBudgetExceeded(RuntimeError):
    """Trop d'appels LLM pour un agent sur un meme run."""


def provider_env_var(name: str, spec: dict[str, Any] | None = None) -> str:
    """Nom de la variable d'environnement portant la cle du provider."""
    spec = spec or {}
    declared = spec.get("api_key_env")
    if declared:
        return str(declared)
    ptype = str(spec.get("type", name)).lower()
    if ptype not in PROVIDER_ENV:
        raise LLMConfigError(f"Provider LLM inconnu : {name} (type={ptype})")
    return PROVIDER_ENV[ptype]


def key_format_ok(name: str, spec: dict[str, Any], key: str) -> bool:
    """Heuristique : la cle ressemble-t-elle au bon service ?

    Desactive avec `skip_key_check: true` pour un provider passant par un
    proxy compatible (base_url) qui n'utilise pas le prefixe officiel.
    """
    if spec.get("skip_key_check"):
        return True
    ptype = str(spec.get("type", name)).lower()
    expected = KEY_PREFIXES.get(ptype)
    return not expected or key.startswith(expected)


def build_chat_model(name: str, spec: dict[str, Any], temperature: float = 0) -> BaseChatModel:
    """Instancie un chat model LangChain pour un provider declare."""
    ptype = str(spec.get("type", name)).lower()
    if "model" not in spec:
        raise LLMConfigError(f"Provider {name} : cle 'model' absente")

    env_var = provider_env_var(name, spec)
    if not os.getenv(env_var):
        raise LLMConfigError(f"Provider {name} : variable {env_var} absente (.env)")

    kwargs: dict[str, Any] = {
        "model": spec["model"],
        "temperature": float(spec.get("temperature", temperature)),
    }
    kwargs.update({k: spec[k] for k in _PASSTHROUGH if k in spec})

    if ptype in ("gemini", "google", "google_genai"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(**kwargs)
    if ptype == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(**kwargs)
    raise LLMConfigError(f"Provider LLM non supporte : {name} (type={ptype})")


# seules classes reconstruites depuis le cache (liste explicite : contenu non fiable)
CACHE_ALLOWED = [Generation, ChatGeneration, AIMessage]


class DiskCache(BaseCache):
    """Cache LLM persistant en JSON (S1) : evite de repayer les memes prompts.

    Les generations sont serialisees par langchain (``dumpd``) et relues par
    ``load`` limite a une liste explicite (generations et message IA) : aucun
    code arbitraire n'est execute ni aucun modele reconstruit. Les anciens fichiers ``.pkl`` ne sont jamais ouverts.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, prompt: str, llm_string: str) -> Path:
        digest = hashlib.sha256(f"{prompt}\x00{llm_string}".encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def lookup(self, prompt: str, llm_string: str) -> list[Any] | None:
        path = self._path(prompt, llm_string)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [load(item, allowed_objects=CACHE_ALLOWED) for item in data["generations"]]
        except Exception:  # entree illisible ou d'un autre format : simple cache manquant
            return None

    def update(self, prompt: str, llm_string: str, return_val: Any) -> None:
        try:
            payload = {"generations": [dumpd(generation) for generation in return_val]}
            path = self._path(prompt, llm_string)
            tmp = path.with_name(f".{path.name}.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            pass

    def clear(self) -> None:
        for path in self.directory.glob("*.json"):
            path.unlink(missing_ok=True)


class TokenCounter(BaseCallbackHandler):
    """Compte appels et tokens par agent (usage_metadata ou llm_output)."""

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.calls += 1
        usage: dict[str, Any] = {}
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        if not usage:
            for generation in getattr(response, "generations", []) or []:
                for item in generation:
                    meta = getattr(getattr(item, "message", None), "usage_metadata", None)
                    if meta:
                        usage = {
                            "prompt_tokens": meta.get("input_tokens"),
                            "completion_tokens": meta.get("output_tokens"),
                        }
                        break
                if usage:
                    break
        self.input_tokens += int(usage.get("prompt_tokens") or 0)
        self.output_tokens += int(usage.get("completion_tokens") or 0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class AgentLLM:
    """LLM d'un agent : fallbacks + budget d'appels + compteur de tokens."""

    agent: str
    runnable: Any
    counter: TokenCounter = field(default_factory=TokenCounter)
    max_calls: int | None = None
    calls: int = 0

    def invoke(self, input: Any, **kwargs: Any) -> Any:
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise LLMCallBudgetExceeded(
                f"[{self.agent}] budget de {self.max_calls} appels LLM atteint"
            )
        self.calls += 1
        return self.runnable.invoke(input, **kwargs)

    def usage(self) -> dict[str, int]:
        data = self.counter.as_dict()
        data["agent_calls"] = self.calls
        return data


def _enable_cache(llm_cfg: dict[str, Any]) -> None:
    cache_dir = llm_cfg.get("cache_dir")
    if not cache_dir:
        return
    target = resolve(cache_dir)
    if not getattr(_enable_cache, "_done", False):
        set_llm_cache(DiskCache(target))
        _enable_cache._done = True  # type: ignore[attr-defined]


def build_agent_llm(agent: str, cfg: dict[str, Any] | None = None) -> AgentLLM:
    """Construit le LLM d'un agent selon llm.routing (primaire + fallbacks)."""
    cfg = cfg or load_config()
    llm_cfg = cfg.get("llm") or {}
    providers = llm_cfg.get("providers") or {}
    routing = llm_cfg.get("routing") or {}
    temperature = float(llm_cfg.get("temperature", 0))

    order = list(routing.get(agent) or providers.keys())
    if not order:
        raise LLMConfigError("Aucun provider LLM declare dans config.llm.providers")

    _enable_cache(llm_cfg)

    built: list[BaseChatModel] = []
    skipped: list[str] = []
    for name in order:
        spec = providers.get(name)
        if not spec:
            skipped.append(f"{name} (provider inconnu)")
            continue
        try:
            key = os.getenv(provider_env_var(name, spec), "")
        except LLMConfigError as exc:
            skipped.append(f"{name} ({exc})")
            continue
        if key and not key_format_ok(name, spec, key):
            skipped.append(f"{name} (format de cle inattendu)")
            continue
        try:
            built.append(build_chat_model(name, spec, temperature))
        except Exception as exc:  # cle absente, paquet manquant...
            skipped.append(f"{name} ({exc})")

    if not built:
        detail = " ; ".join(skipped) if skipped else "aucun provider disponible"
        raise LLMConfigError(
            f"[{agent}] aucun LLM disponible : {detail}. "
            "Renseigne les cles dans .env puis lance scripts/check_llm.py"
        )

    primary, *fallbacks = built
    runnable = (
        primary.with_fallbacks(fallbacks, exceptions_to_handle=(Exception,))
        if fallbacks
        else primary
    )

    counter = TokenCounter()
    runnable = runnable.with_config(callbacks=[counter])

    max_calls = llm_cfg.get("max_calls_per_agent")
    return AgentLLM(
        agent=agent,
        runnable=runnable,
        counter=counter,
        max_calls=int(max_calls) if max_calls else None,
    )
