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
    return cfg


def path_of(cfg: dict[str, Any], key: str) -> Path:
    """Chemin declare dans cfg["paths"][key], resolu et cree."""
    try:
        raw = cfg["paths"][key]
    except KeyError as exc:
        raise ConfigError(f"Chemin manquant dans config.paths : {key}") from exc
    out = resolve(raw)
    out.mkdir(parents=True, exist_ok=True)
    return out
