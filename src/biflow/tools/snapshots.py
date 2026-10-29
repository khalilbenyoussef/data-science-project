"""Versions des donnees brutes : data/snapshots/{index.json, blobs/, vN/manifest.json}.

Chaque fichier brut est stocke une seule fois, nomme par son SHA-256
(blobs/<sha256>.<ext>) ; chaque vN/manifest.json reference ces hash. Une
version n'est creee que si le contenu change (empreinte insensible a l'ordre
des lignes). Elle reste "pending" jusqu'a la fin du run : publiee si le run
reussit, "not_published" sinon ; la version publiee precedente est conservee.
Aucune valeur n'est modifiee : les blobs sont des copies octet par octet.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from biflow.config import resolve
from biflow.utils.io import _detect_header_and_sep, cached_sha256_file

INDEX_VERSION = 1
CONTENT_METHOD = "sha256 of sorted per-line sha256 (BOM and line endings normalized, blank lines ignored)"


def content_sha256(path: str | Path) -> str:
    """Empreinte du contenu insensible a l'ordre des lignes (un tri de lignes
    donne la meme valeur ; toute valeur ou en-tete modifie la change)."""
    line_hashes = []
    with open(path, "rb") as handle:
        for index, line in enumerate(handle):
            if index == 0 and line.startswith(b"\xef\xbb\xbf"):
                line = line[3:]
            line = line.rstrip(b"\r\n")
            if line.strip():
                line_hashes.append(hashlib.sha256(line).digest())
    digest = hashlib.sha256()
    for line_hash in sorted(line_hashes):
        digest.update(line_hash)
    return digest.hexdigest()


def count_rows(path: str | Path, header_marker: str | None = None) -> int:
    """Enregistrements CSV apres l'en-tete (marqueur eventuel), enregistrements vides
    ignores. Un champ entre guillemets sur plusieurs lignes compte pour un seul
    enregistrement (cas du fichier FAS). Lecture latin-1 : transparente pour les
    separateurs et guillemets ASCII, quel que soit l'encodage reel."""
    header_index, separator = _detect_header_and_sep(Path(path), "latin-1", header_marker)
    rows = 0
    with open(path, encoding="latin-1", newline="") as handle:
        for index, record in enumerate(csv.reader(handle, delimiter=separator)):
            if index > header_index and any(field.strip() for field in record):
                rows += 1
    return rows


def _write_json_atomic(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class SnapshotStore:
    """Stockage versionne des sources brutes (lecture seule sur data/raw)."""

    def __init__(self, root: str | Path = "data/snapshots") -> None:
        self.root = resolve(root)
        self.index_path = self.root / "index.json"
        self.blobs = self.root / "blobs"

    # ------------------------------------------------------------------ index
    def load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"index_version": INDEX_VERSION, "published": None, "snapshots": []}
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(index, dict) or not isinstance(index.get("snapshots"), list):
            raise ValueError(f"index de snapshots invalide : {self.index_path}")
        return index

    def published(self, index: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        index = index if index is not None else self.load_index()
        for entry in index["snapshots"]:
            if entry["snapshot_id"] == index.get("published"):
                return entry
        return None

    def manifest(self, snapshot_id: str) -> dict[str, Any]:
        return json.loads((self.root / snapshot_id / "manifest.json").read_text(encoding="utf-8"))

    def blob_path(self, snapshot_id: str, source: str) -> Path:
        return self.root / self.manifest(snapshot_id)["sources"][source]["blob"]

    # ------------------------------------------------------------------ cycle
    def prepare(self, raw_paths: Mapping[str, str], sources: Mapping[str, Any] | None = None,
                run_id: str | None = None) -> dict[str, Any]:
        """Compare le contenu au snapshot publie ; cree vN (pending) s'il differe."""
        sources = sources or {}
        entries: dict[str, dict[str, Any]] = {}
        for name in sorted(raw_paths):
            path = resolve(raw_paths[name])
            entries[name] = {
                "original_path": str(path),
                "sha256": cached_sha256_file(path),
                "content_sha256": content_sha256(path),
                "rows": count_rows(path, (sources.get(name) or {}).get("header_marker")),
                "size_bytes": path.stat().st_size,
                "suffix": path.suffix or ".bin",
            }
        content_key = hashlib.sha256(json.dumps(
            {name: entry["content_sha256"] for name, entry in entries.items()},
            sort_keys=True).encode("utf-8")).hexdigest()

        index = self.load_index()
        current = self.published(index)
        if current is not None and current.get("content_key") == content_key:
            return {"status": "no_change", "snapshot_id": current["snapshot_id"],
                    "content_key": content_key}

        version = 1 + max((entry["version"] for entry in index["snapshots"]), default=0)
        snapshot_id = f"v{version}"
        self.blobs.mkdir(parents=True, exist_ok=True)
        manifest_sources = {}
        for name, entry in entries.items():
            blob = self.blobs / f"{entry['sha256']}{entry['suffix']}"
            if not blob.exists():
                tmp = blob.with_name(f".{blob.name}.tmp")
                shutil.copyfile(entry["original_path"], tmp)
                if cached_sha256_file(tmp) != entry["sha256"]:
                    tmp.unlink()
                    raise OSError(f"[{name}] source modifiee pendant la copie du snapshot")
                os.replace(tmp, blob)
            manifest_sources[name] = {
                "blob": blob.relative_to(self.root).as_posix(),
                **{key: value for key, value in entry.items() if key != "suffix"},
            }
        created_at = datetime.now().isoformat(timespec="seconds")
        _write_json_atomic({
            "snapshot_id": snapshot_id, "version": version, "created_at": created_at,
            "run_id": run_id, "content_key": content_key, "content_method": CONTENT_METHOD,
            "sources": manifest_sources,
        }, self.root / snapshot_id / "manifest.json")
        index["snapshots"].append({
            "snapshot_id": snapshot_id, "version": version, "created_at": created_at,
            "run_id": run_id, "manifest": f"{snapshot_id}/manifest.json",
            "content_key": content_key, "status": "pending",
        })
        _write_json_atomic(index, self.index_path)
        return {"status": "new", "snapshot_id": snapshot_id, "content_key": content_key,
                "previous": current["snapshot_id"] if current else None}

    def finalize(self, snapshot_id: str, published: bool, reason: str | None = None) -> dict[str, Any]:
        """Publie vN, ou le marque not_published en gardant la version publiee."""
        index = self.load_index()
        entry = next((e for e in index["snapshots"] if e["snapshot_id"] == snapshot_id), None)
        if entry is None:
            raise KeyError(f"snapshot inconnu : {snapshot_id}")
        now = datetime.now().isoformat(timespec="seconds")
        if published:
            previous = self.published(index)
            if previous is not None and previous is not entry:
                previous["status"] = "superseded"
            entry.update(status="published", published_at=now)
            index["published"] = snapshot_id
        else:
            entry.update(status="not_published", reason=reason, closed_at=now)
        _write_json_atomic(index, self.index_path)
        self.gc_blobs(index)
        return entry

    def gc_blobs(self, index: Mapping[str, Any] | None = None) -> list[str]:
        """Supprime les blobs references par aucun snapshot de index.json."""
        index = index if index is not None else self.load_index()
        referenced = set()
        for entry in index["snapshots"]:
            manifest = self.manifest(entry["snapshot_id"])
            referenced.update(source["blob"] for source in manifest["sources"].values())
        removed = []
        if self.blobs.exists():
            for blob in self.blobs.iterdir():
                if blob.is_file() and blob.relative_to(self.root).as_posix() not in referenced:
                    blob.unlink()
                    removed.append(blob.name)
        return removed


__all__ = ["CONTENT_METHOD", "SnapshotStore", "content_sha256", "count_rows"]
