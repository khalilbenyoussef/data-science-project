"""Chargement de la configuration et resolution des chemins du projet."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# src/biflow/config.py -> src -> racine du projet
ROOT = Path(__file__).resolve().parents[2]

# Charge .env a la racine (sans ecraser les variables deja definies)
load_dotenv(ROOT / ".env", override=False)


class ConfigError(RuntimeError):
    """Configuration absente ou invalide."""


def resolve(path: str | Path) -> Path:
    """Chemin relatif au projet -> chemin absolu."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Charge config/config.yaml (ou le chemin fourni)."""
    cfg_path = resolve(path or os.getenv("BIFLOW_CONFIG", "config/config.yaml"))
    if not cfg_path.exists():
        raise ConfigError(f"Configuration introuvable : {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise ConfigError(f"Configuration invalide (objet attendu) : {cfg_path}")
    register_user_sources(cfg)
    return cfg


def register_user_sources(cfg: dict[str, Any]) -> list[str]:
    """Ajoute a cfg["sources"] chaque mapping confirme de config/sources/*.yaml
    (type: user). Une source deja declaree (officielle) n'est jamais remplacee ;
    la validite du mapping est verifiee par le collector. config.yaml n'est
    jamais reecrit."""
    folder = resolve(os.getenv("BIFLOW_SOURCES_DIR")
                     or (cfg.get("uploads") or {}).get("mappings_dir", "config/sources"))
    if not folder.is_dir():
        return []
    sources = cfg.setdefault("sources", {})
    added = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        name = data.get("name") if isinstance(data, dict) else None
        name = name or path.stem
        if name in sources:
            continue
        sources[name] = {"type": "user", "path": data.get("file") if isinstance(data, dict) else None,
                         "mapping": str(path)}
        added.append(name)
    return added


def path_of(cfg: dict[str, Any], key: str) -> Path:
    """Chemin declare dans cfg["paths"][key], resolu et cree."""
    try:
        raw = cfg["paths"][key]
    except KeyError as exc:
        raise ConfigError(f"Chemin manquant dans config.paths : {key}") from exc
    out = resolve(raw)
    out.mkdir(parents=True, exist_ok=True)
    return out
