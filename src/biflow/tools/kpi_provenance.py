"""Read-only evidence attached to KPI results; never grants publication approval."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from biflow.config import load_config, resolve
from biflow.utils.countries import normalize_iso3
from biflow.utils.io import cached_sha256_file


@dataclass(frozen=True)
class QualityWarning:
    reference: str
    code: str
    message: str
    source: str
    iso3: str | None = None
    year: int | None = None
    indicator_code: str | None = None
    series_code: str | None = None
    association_status: str = "unverified"


@dataclass(frozen=True)
class KpiProvenance:
    lineage_path: str
    lineage_sha256: str | None
    run_id: str | None
    created_at: str | None
    raw_source_path: str | None
    raw_source_sha256: str | None
    raw_source_rows: int | None
    observed_raw_sha256: str | None
    warehouse_sha256: str | None
    quality_report_path: str
    quality_report_sha256: str | None
    quality_gate_passed: bool | None
    quality_association_status: str
    issues: tuple[str, ...]


def _read_json(path, label, issues):
    try:
        content = path.read_bytes()
    except OSError:
        issues.append(f"{label}_unavailable")
        return {}, None
    digest = hashlib.sha256(content).hexdigest()
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Expected object")
    except (ValueError, UnicodeError):
        issues.append(f"{label}_invalid")
        return {}, digest
    return data, digest


def _text(value):
    return value if isinstance(value, str) and value.strip() else None


def _digest(value):
    return value.lower() if isinstance(value, str) and re.fullmatch(r"[a-fA-F0-9]{64}", value) else None


def _year(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}", value):
        return int(value)
    return None


def evidence(warehouse: Path, lineage_path: Path, quality_path: Path, *,
             source: str, iso3: str, year: int, indicator: str,
             dimension: str, dimension_value: str):
    """Return recorded provenance, exact input warnings and source-wide notices.

    Quality reports record run_id and inputs.<source>.sha256. When both agree
    with lineage, association is matches_lineage and no binding review reason is
    added; a disagreement adds quality_provenance_mismatch, and an older report
    without that metadata adds quality_provenance_unverified. Binding is never
    manufactured. Matching a warning does not by itself certify the data.
    """
    issues = []
    lineage, lineage_hash = _read_json(lineage_path, "lineage", issues)
    quality, quality_hash = _read_json(quality_path, "quality_report", issues)
    inputs = lineage.get("inputs")
    meta = inputs.get(source) if isinstance(inputs, dict) else None
    if not isinstance(meta, dict):
        meta = {}
        issues.append("source_metadata_missing")
    raw_path, raw_hash = _text(meta.get("path")), _digest(meta.get("sha256"))
    if raw_path is None or raw_hash is None:
        issues.append("source_version_incomplete")
    rows = meta.get("rows")
    rows = rows if type(rows) is int and rows >= 0 else None
    run_id = _text(lineage.get("run_id"))
    if run_id is None:
        issues.append("lineage_run_id_missing")
    observed_raw_hash = None
    if raw_path:
        try:
            observed_raw_hash = cached_sha256_file(resolve(raw_path))
        except (OSError, ValueError):
            issues.append("raw_source_unavailable")
        if raw_hash and observed_raw_hash and raw_hash != observed_raw_hash:
            issues.append("raw_source_hash_mismatch")
    outputs = lineage.get("outputs")
    recorded_warehouse = outputs.get("warehouse") if isinstance(outputs, dict) else None
    if not _text(recorded_warehouse):
        issues.append("lineage_warehouse_path_missing")
    else:
        try:
            if resolve(recorded_warehouse).resolve() != warehouse:
                issues.append("lineage_warehouse_path_mismatch")
        except (OSError, ValueError):
            issues.append("lineage_warehouse_path_invalid")
    warehouse_hash = cached_sha256_file(warehouse)
    # Current ETL records a path, not a warehouse content digest.
    recorded_hash = _digest(outputs.get("warehouse_sha256")) if isinstance(outputs, dict) else None
    if recorded_hash is None:
        issues.append("warehouse_content_binding_unverified")
    elif recorded_hash != warehouse_hash:
        issues.append("warehouse_hash_mismatch")
    qinputs = quality.get("inputs")
    qmeta = qinputs.get(source) if isinstance(qinputs, dict) else None
    qhash = _digest(qmeta.get("sha256")) if isinstance(qmeta, dict) else None
    qrun = _text(quality.get("run_id"))
    association = "unverified"
    if (qrun and run_id and qrun != run_id) or (qhash and raw_hash and qhash != raw_hash):
        association = "inconsistent"
        issues.append("quality_provenance_mismatch")
    elif qrun and run_id and qhash and raw_hash:
        association = "matches_lineage"
    else:
        issues.append("quality_provenance_unverified")
    passed = quality.get("passed")
    passed = passed if type(passed) is bool else None
    if passed is not True:
        issues.append("quality_gate_failed" if passed is False else "quality_gate_unknown")

    warnings, notices = [], []
    # Resolve both canonical FAS IDs and the raw annual series identity.
    fas_series = load_config().get("sources", {}).get("fas", {}).get("series", {})
    reverse = {v: k for k, v in fas_series.items()}
    for collection in ("diagnostics", "issues"):
        records = quality.get(collection)
        if not isinstance(records, list):
            issues.append(f"quality_{collection}_invalid")
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                issues.append(f"quality_{collection}_record_invalid")
                continue
            if record.get("source") != source:
                continue
            country = normalize_iso3(record.get("iso3"))
            obs_year = _year(record.get("year"))
            code = _text(record.get("indicator_code"))
            series = _text(record.get("series_code"))
            if source == "fas":
                code = reverse.get(code, code)
                if series:
                    match = re.fullmatch(r"([A-Z]{3})\.(.+)\.A", series.strip().upper())
                    series_country = normalize_iso3(match[1]) if match else None
                    series_code = reverse.get(match[2]) if match else None
                    if (not series_code or (country and country != series_country)
                            or (code and code != series_code)):
                        issues.append("quality_series_identity_inconsistent")
                        continue
                    country, code = series_country, series_code
                if code is not None and code not in fas_series:
                    issues.append("quality_indicator_mapping_unresolved")
                    continue
            warning = QualityWarning(
                reference=f"{quality_path}#/{collection}/{index}",
                code=_text(record.get("code")) or "unspecified",
                message=_text(record.get("reason")) or _text(record.get("message")) or "Review source record",
                source=source, iso3=country, year=obs_year, indicator_code=code,
                series_code=series, association_status=association,
            )
            # Source-wide scored issues have no country/year/indicator identity.
            if country is None or obs_year is None or code is None:
                notices.append(warning)
                if collection == "diagnostics":
                    issues.append("quality_diagnostic_identity_incomplete")
                continue
            if ((country, obs_year, code) == (iso3, year, indicator)
                    and record.get("dimension", dimension) == dimension
                    and record.get("dimension_value", dimension_value) == dimension_value):
                warnings.append(warning)
    provenance = KpiProvenance(
        lineage_path=str(lineage_path), lineage_sha256=lineage_hash,
        run_id=run_id, created_at=_text(lineage.get("created_at")),
        raw_source_path=raw_path, raw_source_sha256=raw_hash, raw_source_rows=rows,
        observed_raw_sha256=observed_raw_hash, warehouse_sha256=warehouse_hash,
        quality_report_path=str(quality_path), quality_report_sha256=quality_hash,
        quality_gate_passed=passed, quality_association_status=association,
        issues=tuple(dict.fromkeys(issues)),
    )
    return provenance, tuple(warnings), tuple(notices)
