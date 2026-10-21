"""Lecture/ecriture robuste des donnees (CSV multi-en-tete, JSON, Parquet)."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from biflow.config import ROOT, resolve

SEPARATORS = (",", ";", "\t", "|")
ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


# --------------------------------------------------------------------------- fichiers
def ensure_dir(path: str | Path) -> Path:
    out = resolve(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """Empreinte SHA-256 d'un fichier (lecture par blocs)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


# --------------------------------------------------------------------------- CSV
def _detect_encoding(path: Path, sample_size: int = 1 << 16) -> str:
    with open(path, "rb") as f:
        raw = f.read(sample_size)
    for encoding in ENCODINGS[:-1]:
        try:
            (raw[:-4] if len(raw) > 4 else raw).decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _detect_header_and_sep(
    path: Path,
    encoding: str,
    header_marker: str | None = None,
    max_lines: int = 20,
) -> tuple[int, str]:
    """Trouve l'index de la ligne d'en-tete et le separateur.

    Le fichier FAS contient deux lignes d'en-tete : la premiere est un
    remplissage Excel ('Column1;Column2;...'), la vraie commence par
    DATASET;SERIES_CODE. On la localise via `header_marker`.
    """
    with open(path, encoding=encoding, errors="replace") as f:
        lines = [line.rstrip("\r\n") for line in (next(f, "") for _ in range(max_lines))]

    header_index = 0
    if header_marker:
        for index, line in enumerate(lines):
            if header_marker in line:
                header_index = index
                break
        else:
            raise ValueError(
                f"En-tete introuvable : marqueur '{header_marker}' absent des "
                f"{max_lines} premieres lignes de {path.name}"
            )

    header_line = lines[header_index] if header_index < len(lines) else ""
    separator = max(SEPARATORS, key=header_line.count)
    if header_line.count(separator) == 0:
        separator = ","
    return header_index, separator


def read_csv_smart(
    path: str | Path,
    header_marker: str | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Lit un CSV en detectant encodage, separateur et ligne d'en-tete."""
    csv_path = resolve(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {csv_path}")

    encoding = _detect_encoding(csv_path)
    header, separator = _detect_header_and_sep(csv_path, encoding, header_marker)

    df = pd.read_csv(csv_path, sep=separator, encoding=encoding, header=header, **kwargs)
    df.columns = [str(col).strip().lstrip("\ufeff") for col in df.columns]
    return df


def load_source(source_cfg: dict[str, Any], **kwargs: Any) -> pd.DataFrame:
    """Charge une source declaree dans config.yaml (csv, excel, json, parquet)."""
    if "path" not in source_cfg:
        raise ValueError("Configuration de source sans cle 'path'")

    path = resolve(source_cfg["path"])
    if not path.exists():
        raise FileNotFoundError(
            f"Source introuvable : {path}. "
            "Verifie la collecte ou le chemin dans config/config.yaml"
        )

    fmt = str(source_cfg.get("type") or path.suffix.lstrip(".")).lower()
    if fmt in ("csv", "txt", "tsv"):
        return read_csv_smart(path, header_marker=source_cfg.get("header_marker"), **kwargs)
    if fmt in ("xlsx", "xls"):
        return pd.read_excel(path, **kwargs)
    if fmt == "json":
        return pd.read_json(path, **kwargs)
    if fmt in ("parquet", "pq"):
        return pd.read_parquet(path, **kwargs)
    raise ValueError(f"Format de source non supporte : {fmt} ({path.name})")


def write_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """Ecrit un CSV UTF-8 avec BOM (Excel) et cree le dossier parent."""
    out = resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out


# --------------------------------------------------------------------------- JSON
def _sanitize(obj: Any) -> Any:
    """Convertit recursivement numpy/pandas en types JSON (NaN -> null)."""
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    raise TypeError(f"Objet non serialisable en JSON : {type(obj).__name__}")


def save_json(obj: Any, path: str | Path) -> Path:
    """Ecrit un JSON lisible, tolerant aux types numpy/pandas."""
    out = resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            _sanitize(obj),
            f,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            default=_json_default,
        )
    return out


def load_json(path: str | Path) -> Any:
    with open(resolve(path), encoding="utf-8") as f:
        return json.load(f)


def existing_files(paths: Iterable[str | Path]) -> list[Path]:
    return [resolve(p) for p in paths if resolve(p).exists()]


__all__ = [
    "ROOT",
    "resolve",
    "ensure_dir",
    "sha256_file",
    "read_csv_smart",
    "load_source",
    "write_csv",
    "save_json",
    "load_json",
    "existing_files",
]
