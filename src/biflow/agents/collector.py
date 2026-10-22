
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Mapping

import pandas as pd

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.utils.io import ensure_dir, read_csv_smart, sha256_file

COLUMNS = ["iso3", "country", "indicator_code", "indicator_name", "year", "value"]


class CollectorAPIError(RuntimeError):
    """Erreur de communication avec l'API World Bank."""


# --------------------------------------------------------------------------- payload
def parse_payload(payload: list) -> list[dict]:
    """Reponse JSON paginee de l'API World Bank -> lignes normalisees."""
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return []
    rows = []
    for record in payload[1]:
        date = str(record.get("date") or "")
        rows.append(
            {
                "iso3": record.get("countryiso3code") or None,
                "country": (record.get("country") or {}).get("value"),
                "indicator_code": (record.get("indicator") or {}).get("id"),
                "indicator_name": (record.get("indicator") or {}).get("value"),
                "year": int(date) if date.isdigit() else None,
                "value": record.get("value"),
            }
        )
    return rows


def to_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    if df.empty:
        return df
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def serialize(df: pd.DataFrame) -> bytes:
    """CSV deterministe (tri stable) servant aussi d'empreinte."""
    ordered = df.sort_values(
        ["indicator_code", "iso3", "year"], kind="mergesort", na_position="last"
    )
    return ordered.to_csv(index=False).encode("utf-8-sig")


# --------------------------------------------------------------------------- agent
class CollectorAgent(BaseAgent):
    name = "collector"

    # ------------------------------------------------------------------ reseau
    def _get(self, url: str) -> Any:
        cfg = self.cfg.get("collector", {})
        timeout = cfg.get("timeout", 60)
        retries = max(1, int(cfg.get("retries", 3)))
        last: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(url, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last = exc
                self.log.warning("requete %d/%d echouee : %s", attempt, retries, exc)
                if attempt < retries:
                    time.sleep(2 ** attempt)
        raise CollectorAPIError(f"API World Bank injoignable : {last}")

    def _fetch_indicator(self, code: str, cfg: dict, date_range: str) -> list[dict]:
        base = cfg.get("api_base", "https://api.worldbank.org/v2")
        country = cfg.get("country", "all")
        per_page = cfg.get("per_page", 20000)
        url = (
            f"{base}/country/{country}/indicator/{code}"
            f"?format=json&per_page={per_page}&date={date_range}&page=1"
        )
        payload = self._get(url)
        rows = parse_payload(payload)
        pages = 1
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            pages = int(payload[0].get("pages") or 1)
        for page in range(2, pages + 1):
            rows += parse_payload(self._get(url.replace("page=1", f"page={page}")))
        return rows

    # ------------------------------------------------------------------ collecte
    def _collect(self, name: str, source_cfg: dict, cfg: dict) -> pd.DataFrame:
        codes = list(source_cfg.get("indicators") or [])
        if not codes:
            raise AgentError(f"[{name}] cle 'indicators' absente de la configuration")
        date_range = source_cfg.get("date_range", cfg.get("date_range", "2011:2024"))
        rows: list[dict] = []
        for code in codes:
            self.log.info("[%s] telechargement %s (%s)", name, code, date_range)
            rows += self._fetch_indicator(code, cfg, date_range)
        if not rows:
            raise CollectorAPIError("l'API n'a renvoye aucune observation")
        frame = to_frame(rows)
        missing_code = int(frame["iso3"].isna().sum())
        if missing_code:
            self.log.info(
                "[%s] %d lignes d'agregats sans code ISO3 ignorees", name, missing_code
            )
            frame = frame[frame["iso3"].notna()]
        return frame

    def _diagnose(self, exc: Exception) -> dict[str, Any]:
        """Diagnostic deterministe : aucun appel LLM."""
        message = str(exc)
        lower = message.lower()
        if isinstance(exc, TimeoutError) or "timed out" in lower:
            action = "augmenter collector.timeout puis relancer la collecte"
        elif "403" in message or "forbidden" in lower:
            action = "verifier le proxy/pare-feu et les droits d'acces a l'API"
        elif "429" in message or "too many" in lower:
            action = "attendre puis relancer avec collector.retries plus eleve"
        else:
            action = "verifier la connexion reseau puis relancer la collecte"
        return {"cause": f"{type(exc).__name__}: {message}", "action": action}

    def _refresh(self, name: str, source_cfg: dict, cfg: dict, out) -> dict[str, Any]:
        hash_file = out.parent / f"{out.name}.sha256"
        try:
            df = self._collect(name, source_cfg, cfg)
            payload = serialize(df)
        except CollectorAPIError as exc:
            if out.exists():
                self.log.warning("[%s] %s - donnees existantes conservees", name, exc)
                diagnosis = self._diagnose(exc)
                return {
                    "path": str(out),
                    "rows": None,
                    "updated": False,
                    "sha256": sha256_file(out),
                    "diagnosis": diagnosis,
                    "warning": f"{name}: collecte echouee, cache conserve ({exc})",
                }
            raise

        new_hash = hashlib.sha256(payload).hexdigest()
        old_hash = hash_file.read_text(encoding="utf-8").strip() if hash_file.exists() else None
        if old_hash == new_hash and out.exists():
            self.log.info("[%s] inchange (sha256 %s)", name, new_hash[:12])
            return {
                "path": str(out),
                "rows": int(len(df)),
                "updated": False,
                "sha256": new_hash,
            }

        ensure_dir(out.parent)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(out)
        hash_file.write_text(new_hash + "\n", encoding="utf-8")
        self.log.info(
            "[%s] %d lignes, %d indicateur(s) -> %s",
            name,
            len(df),
            int(df["indicator_code"].nunique()),
            out.name,
        )
        return {
            "path": str(out),
            "rows": int(len(df)),
            "updated": True,
            "sha256": new_hash,
            "previous_sha256": old_hash,
            "indicators": int(df["indicator_code"].nunique()),
            "year_min": int(df["year"].min()),
            "year_max": int(df["year"].max()),
        }

    def _static(self, name: str, source_cfg: dict, out) -> dict[str, Any]:
        if not out.exists():
            raise FileNotFoundError(f"[{name}] source statique introuvable : {out}")
        header = read_csv_smart(
            out,
            header_marker=source_cfg.get("header_marker"),
            nrows=0,
        )
        meta = {
            "path": str(out),
            "static": True,
            "rows": None,
            "columns": int(len(header.columns)),
            "sha256": sha256_file(out),
            "size_mb": round(out.stat().st_size / 1e6, 2),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.log.info(
            "[%s] source statique OK : %s (%.1f Mo, %d colonnes)",
            name,
            out.name,
            meta["size_mb"],
            meta["columns"],
        )
        return meta

    # ------------------------------------------------------------------ entree
    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        sources = ctx.get("sources") or self.cfg.get("sources") or {}
        if not sources:
            raise AgentError("aucune source dans la configuration")

        raw_paths: dict[str, str] = dict(ctx.get("raw_paths") or {})
        raw_meta: dict[str, Any] = dict(ctx.get("raw_meta") or {})
        warnings: list[str] = []
        failed: list[str] = []

        for name, source_cfg in sources.items():
            out = resolve(source_cfg["path"])
            try:
                if source_cfg.get("static"):
                    meta = self._static(name, source_cfg, out)
                else:
                    meta = self._refresh(name, source_cfg, self.cfg.get("collector", {}), out)
                    if meta.get("warning"):
                        warnings.append(meta["warning"])
                raw_paths[name] = str(out)
                raw_meta[name] = meta
            except Exception as exc:  # noqa: BLE001 - une source ne bloque pas les autres
                failed.append(f"{name}: {exc}")
                self.log.error("[%s] echec : %s", name, exc)

        if failed:
            raise AgentError("collecte incomplete -> " + " | ".join(failed))

        return {
            "raw_paths": raw_paths,
            "raw_meta": raw_meta,
            "warnings": warnings,
            "llm_notes": {
                "collector": f"{len(raw_paths)} source(s) verifiee(s), hash SHA-256 calcule"
            },
        }
