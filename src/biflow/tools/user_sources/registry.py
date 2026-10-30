"""Enregistrement des sources utilisateur : mappings confirmes et copies des fichiers.

config/sources/<name>.yaml : mapping confirme (avec empreinte des colonnes).
data/uploads/<name>.csv : copie du fichier (jamais une source officielle).
Les deux dossiers sont ignores par git.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from biflow.config import ROOT, resolve
from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.mapping import OFFICIAL_SOURCES, SourceMapping, validate_mapping

DEFAULT_MAPPINGS_DIR = "config/sources"
DEFAULT_UPLOADS_DIR = "data/uploads"


def _settings(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((cfg or {}).get("uploads") or {})


def mappings_dir(cfg: Mapping[str, Any] | None = None) -> Path:
    return resolve(_settings(cfg).get("mappings_dir", DEFAULT_MAPPINGS_DIR))


def uploads_dir(cfg: Mapping[str, Any] | None = None) -> Path:
    return resolve(_settings(cfg).get("dir", DEFAULT_UPLOADS_DIR))


def mapping_path(name: str, cfg: Mapping[str, Any] | None = None) -> Path:
    return mappings_dir(cfg) / f"{name}.yaml"


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def load_mapping(path: str | Path) -> SourceMapping:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UserSourceError(f"Mapping illisible {path} : {exc}") from exc
    if not isinstance(data, dict):
        raise UserSourceError(f"Mapping invalide (objet YAML attendu) : {path}")
    return validate_mapping(data)


def list_mappings(cfg: Mapping[str, Any] | None = None) -> dict[str, SourceMapping]:
    folder = mappings_dir(cfg)
    if not folder.is_dir():
        return {}
    return {path.stem: load_mapping(path) for path in sorted(folder.glob("*.yaml"))}


def find_reusable(name: str, fingerprint: str, cfg: Mapping[str, Any] | None = None,
                  ) -> tuple[SourceMapping | None, str]:
    """Mapping reutilisable : meme nom et meme empreinte, sinon meme empreinte ailleurs.

    Renvoie (mapping, statut) : reused | template | structure_changed | new.
    """
    existing = list_mappings(cfg)
    if name in existing:
        if existing[name].fingerprint == fingerprint:
            return existing[name], "reused"
        return None, "structure_changed"
    for other in existing.values():
        if other.fingerprint == fingerprint:
            return other, "template"
    return None, "new"


def register(mapping: SourceMapping, source_file: str | Path, cfg: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Copie le fichier dans data/uploads/ et enregistre le mapping confirme."""
    if mapping.name in OFFICIAL_SOURCES:
        raise UserSourceError(f"'{mapping.name}' est une source officielle : choisir un autre nom")
    target = uploads_dir(cfg) / f"{mapping.name}.csv"
    official = {resolve(s.get("path")) for n, s in ((cfg or {}).get("sources") or {}).items()
                if n in OFFICIAL_SOURCES and s.get("path")}
    if target.resolve() in {p.resolve() for p in official}:
        raise UserSourceError("Refus : la copie ecraserait une source officielle")
    target.parent.mkdir(parents=True, exist_ok=True)
    if Path(source_file).resolve() != target.resolve():
        tmp = target.with_name(f".{target.name}.tmp")
        shutil.copyfile(source_file, tmp)
        os.replace(tmp, target)
    data = mapping.model_dump(mode="json")
    data.update(file=_relative(target), confirmed_at=datetime.now().isoformat(timespec="seconds"))
    validate_mapping(data)
    path = mapping_path(mapping.name, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text("# Mapping confirme par add-source ; modifiable puis revalide au chargement.\n"
                   + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, path)
    return {"mapping": str(path), "file": str(target)}


def unregister(name: str, cfg: Mapping[str, Any] | None = None) -> bool:
    """Retire le mapping (la copie dans data/uploads/ est conservee)."""
    path = mapping_path(name, cfg)
    if not path.exists():
        return False
    path.unlink()
    return True


__all__ = ["find_reusable", "list_mappings", "load_mapping", "mapping_path", "mappings_dir", "register",
           "unregister", "uploads_dir"]
