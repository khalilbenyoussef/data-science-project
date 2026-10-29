
from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Mapping

import pandas as pd

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.utils.io import ensure_dir, file_stat, read_csv_smart, sha256_file

COLUMNS = ["iso3", "country", "indicator_code", "indicator_name", "year", "value"]
SDMX_REQUIRED = ("COUNTRY", "FREQUENCY", "TIME_PERIOD", "OBS_VALUE", "SCALE")


class CollectorAPIError(RuntimeError):
    """Erreur de communication avec une API (World Bank, IMF)."""


class SdmxFormatError(ValueError):
    """Reponse SDMX hors contrat (colonnes, echelle, frequence) : jamais de repli cache."""


# --------------------------------------------------------------------------- IMF SDMX
def sdmx_to_fas_wide(responses: Mapping[str, str]) -> pd.DataFrame:
    """CSV SDMX 3.0 (une ligne par observation) -> format large de fas.csv.

    responses : serie locale (ex. FA26N.PHTADLT_NUM) -> texte CSV de l'API.
    Les valeurs sont conservees telles que recues (texte) : aucune conversion
    ni mise a l'echelle ; une echelle autre que 0 (unites) est refusee.
    """
    frames = []
    for local_series, text in responses.items():
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        missing = [column for column in SDMX_REQUIRED if column not in df.columns]
        if missing:
            raise SdmxFormatError(f"[fas api] colonnes SDMX absentes ({local_series}) : {missing}")
        df = df[(df["TIME_PERIOD"].str.strip() != "") & (df["OBS_VALUE"].str.strip() != "")]
        scales = sorted(set(df["SCALE"]) - {"0"})
        if scales:
            raise SdmxFormatError(f"[fas api] echelle non verifiee pour {local_series} : {scales}")
        frequencies = sorted(set(df["FREQUENCY"]) - {"A"})
        if frequencies:
            raise SdmxFormatError(f"[fas api] frequence non annuelle pour {local_series} : {frequencies}")
        if not df["TIME_PERIOD"].str.fullmatch(r"\d{4}").all():
            raise SdmxFormatError(f"[fas api] periode non annuelle pour {local_series}")
        frames.append(pd.DataFrame({
            "SERIES_CODE": df["COUNTRY"].str.strip() + "." + local_series + ".A",
            "COUNTRY": df["COUNTRY"].str.strip(),
            "year": df["TIME_PERIOD"],
            "value": df["OBS_VALUE"],
        }))
    long = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if long.empty:
        raise SdmxFormatError("[fas api] aucune observation recue")
    if long.duplicated(["SERIES_CODE", "year"]).any():
        raise SdmxFormatError("[fas api] observations en double (serie, annee)")
    wide = long.pivot(index=["SERIES_CODE", "COUNTRY"], columns="year", values="value").reset_index()
    wide.columns.name = None
    years = sorted(column for column in wide.columns if column not in ("SERIES_CODE", "COUNTRY"))
    return wide[["SERIES_CODE", "COUNTRY", *years]].sort_values("SERIES_CODE", kind="mergesort")


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

    def _get_text(self, url: str, accept: str) -> str:
        """GET avec en-tete Accept (ex. text/csv) et memes nouveaux essais que _get."""
        cfg = self.cfg.get("collector", {})
        timeout = cfg.get("timeout", 60)
        retries = max(1, int(cfg.get("retries", 3)))
        last: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                request = urllib.request.Request(url, headers={"Accept": accept})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return response.read().decode("utf-8")
            except (urllib.error.URLError, TimeoutError, OSError, UnicodeError) as exc:
                last = exc
                self.log.warning("requete %d/%d echouee : %s", attempt, retries, exc)
                if attempt < retries:
                    time.sleep(2 ** attempt)
        raise CollectorAPIError(f"API IMF injoignable : {last}")

    def _fas_api(self, name: str, source_cfg: dict) -> dict[str, Any]:
        """FAS via IMF Data API (SDMX 3.0) -> fichier large ; cache conserve si l'API echoue."""
        api = source_cfg.get("api") or {}
        out = resolve(api.get("path", "data/raw/fas_api.csv"))
        series = api.get("series") or {}
        if not series:
            raise AgentError(f"[{name}] api.series vide : aucune cle SDMX verifiee configuree")
        base = api.get("base_url", "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/FAS/~/")
        countries = api.get("countries", "*")
        unmapped = sorted(set((source_cfg.get("series") or {}).values()) - set(series))
        try:
            responses = {
                local: self._get_text(f"{base}{countries}.{key}", api.get("accept", "text/csv"))
                for local, key in series.items()
            }
        except CollectorAPIError as exc:
            if out.exists():
                self.log.warning("[%s] %s - donnees API existantes conservees", name, exc)
                return {
                    "path": str(out), "source": "imf_sdmx_api_cache", "rows": None,
                    "updated": False, "sha256": sha256_file(out), **file_stat(out),
                    "diagnosis": self._diagnose(exc),
                    "warning": f"{name}: API IMF injoignable, cache conserve ({exc})",
                }
            raise
        wide = sdmx_to_fas_wide(responses)
        payload = wide.to_csv(index=False).encode("utf-8")
        new_hash = hashlib.sha256(payload).hexdigest()
        updated = not out.exists() or sha256_file(out) != new_hash
        if updated:
            ensure_dir(out.parent)
            tmp = out.with_suffix(out.suffix + ".tmp")
            tmp.write_bytes(payload)
            tmp.replace(out)
        self.log.info("[%s] API IMF : %d series x pays, %d serie(s) -> %s",
                      name, len(wide), len(series), out.name)
        meta = {
            "path": str(out), "source": "imf_sdmx_api", "rows": int(len(wide)),
            "updated": updated, "sha256": new_hash, **file_stat(out),
            "series": sorted(series), "unmapped_series": unmapped,
        }
        if unmapped:
            meta["warning"] = (f"{name}: series non couvertes par l'API (non verifiees) : "
                               f"{', '.join(unmapped)}")
        return meta

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
                    **file_stat(out),
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
                **file_stat(out),
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
            **file_stat(out),
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
            **file_stat(out),
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
                if (source_cfg.get("api") or {}).get("enabled"):
                    meta = self._fas_api(name, source_cfg)
                    out = resolve(meta["path"])
                    if meta.get("warning"):
                        warnings.append(meta["warning"])
                elif source_cfg.get("static"):
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
