"""Chargement d'une source utilisateur enregistree (type: user) pour les agents.

Une seule implementation du mapping pour le profiler, la qualite, l'ETL et
l'Auditor : fichier (copie ou blob de snapshot) + mapping -> forme canonique.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from biflow.config import resolve
from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.canonical import canonical
from biflow.tools.user_sources.countries import CountryResolver
from biflow.tools.user_sources.detect import read_user_csv
from biflow.tools.user_sources.mapping import SourceMapping
from biflow.tools.user_sources.registry import load_mapping

USER_PREFIX = "user:"


def is_user_source(source_cfg: Mapping[str, Any] | None) -> bool:
    return isinstance(source_cfg, Mapping) and source_cfg.get("type") == "user"


def source_name(fact_source: str) -> str:
    """'user:clients' -> 'clients' ; une source officielle est renvoyee telle quelle."""
    return fact_source[len(USER_PREFIX):] if fact_source.startswith(USER_PREFIX) else fact_source


def user_mapping(source_cfg: Mapping[str, Any]) -> SourceMapping:
    if not source_cfg.get("mapping"):
        raise UserSourceError("source utilisateur sans mapping declare")
    return load_mapping(resolve(source_cfg["mapping"]))


def load_user_canonical(source_cfg: Mapping[str, Any], path: str | Path | None = None,
                        aliases: Mapping[str, str] | None = None,
                        ) -> tuple[pd.DataFrame, dict[str, Any], SourceMapping]:
    """(observations canoniques, rapport, mapping) depuis le fichier indique
    (blob de snapshot) ou la copie enregistree."""
    mapping = user_mapping(source_cfg)
    target = resolve(path or source_cfg.get("path") or mapping.file)
    if not target.is_file():
        raise UserSourceError(f"fichier de la source {mapping.name} introuvable : {target}")
    df = read_user_csv(target, mapping.read.model_dump())
    frame, report = canonical(mapping, df, CountryResolver({**(aliases or {}), **mapping.country_names}))
    return frame, report, mapping


__all__ = ["USER_PREFIX", "is_user_source", "load_user_canonical", "source_name", "user_mapping"]
