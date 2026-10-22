
import re
from typing import Any, Mapping

import numpy as np
import pandas as pd

try:  # sklearn peut etre bloque par une policy Windows (DLL)
    from sklearn.ensemble import IsolationForest
except Exception:  # noqa: BLE001
    IsolationForest = None

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.utils.io import load_source, save_json

YEAR_RE = re.compile(r"^(19|20)\d{2}$")

# colonnes décrivant le type de série (utile pour FAS) : affichées en entier dans le profil
CATALOG_COLUMNS = ["TYPE_OF_TRANSFORMATION", "TRANSFORMATION", "UNIT", "SCALE",
                   "COUNTERPART_SECTOR", "SEX", "ACCOUNTING_ENTRY", "INSTR_ASSET", "FREQUENCY"]
INDICATOR_COLUMN = "FA_INDICATORS"


# --------------------------------------------------------------------------- helpers
def year_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if YEAR_RE.match(str(c))]


def text_columns(df: pd.DataFrame) -> list[str]:
    """Colonnes non numériques (object, str, category...). Robuste à pandas 2 et 3."""
    return [c for c in df.columns
            if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]


def _f(x):
    """float propre (NaN -> None) pour le JSON."""
    return None if pd.isna(x) else float(x)


def _short(v, n: int = 40) -> str:
    s = str(v).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _year_col_name(df: pd.DataFrame):
    return next((c for c in df.columns if str(c).lower() in ("year", "annee")), None)


def numeric_year_view(df: pd.DataFrame, ycols: list[str]) -> pd.DataFrame:
    """Colonnes d'années converties en nombres (le texte non numérique devient NaN)."""
    return df[ycols].apply(pd.to_numeric, errors="coerce")


def find_key_candidates(df: pd.DataFrame) -> list[dict]:
    """Repère les colonnes structurantes (ISO3 direct ou en préfixe, année)."""
    cands = []
    for c in text_columns(df):
        sample = df[c].dropna().astype(str).head(500)
        if sample.empty:
            continue
        if sample.str.fullmatch(r"[A-Z]{3}").mean() >= 0.9 and sample.nunique() >= 3:
            cands.append({"column": c, "type": "iso3", "how": "direct"})
        elif sample.str.match(r"^[A-Z]{3}\.").mean() >= 0.9 and sample.str.split(".").str[0].nunique() >= 3:
            cands.append({"column": c, "type": "iso3", "how": "prefix avant le premier '.'"})
    for c in df.columns:
        if str(c).lower() in ("year", "annee"):
            cands.append({"column": c, "type": "year", "how": "direct"})
    return cands


def country_series(df: pd.DataFrame, keys: list[dict]):
    """Code pays de chaque ligne (ISO3 direct, ou préfixe de SERIES_CODE), sinon colonne COUNTRY."""
    for k in keys:
        if k["type"] == "iso3":
            s = df[k["column"]].astype(str)
            return s if k["how"] == "direct" else s.str.split(".").str[0]
    return df["COUNTRY"].astype(str) if "COUNTRY" in df.columns else None


# --------------------------------------------------------------------------- anomalies
def iqr_outliers(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    """INFORMATIF : distribution asymétrique ou petits pays, ce ne sont pas forcément des erreurs."""
    out = []
    for c in cols:
        s = df[c].dropna()
        if len(s) < 10:
            continue
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n = int(((s < lo) | (s > hi)).sum())
        if n:
            out.append({"column": c, "rule": "IQR 1.5", "bounds": [float(lo), float(hi)],
                        "n_outliers": n, "pct_outliers": round(n / len(s) * 100, 2),
                        "note": "informatif, pas une erreur"})
    return out


def isolation_forest(df: pd.DataFrame, cols: list[str], contamination: float) -> list[dict]:
    if IsolationForest is None:
        return []
    cols = [c for c in cols if df[c].isna().mean() < 0.5]
    if len(cols) < 2 or len(df) < 20:
        return []
    X = df[cols].fillna(df[cols].median())
    model = IsolationForest(contamination=contamination, random_state=42).fit(X)
    scores = model.score_samples(X)
    worst = np.argsort(scores)[:5]
    return [{"row_index": int(df.index[i]), "score": float(scores[i]), "features": cols} for i in worst]


def rate_range_check(df: pd.DataFrame, numeric: list[str]) -> dict:
    """Colonnes qui ressemblent à des FRACTIONS (0.09 = 9 %) : combien de valeurs hors [0, 1] ?"""
    out = {}
    for c in numeric:
        s = df[c].dropna()
        if len(s) < 10:
            continue
        if 0 <= s.median() <= 1 and s.quantile(0.99) <= 1.0:
            out[c] = {"min": _f(s.min()), "max": _f(s.max()),
                      "n_out_of_range": int(((s < 0) | (s > 1)).sum())}
    return out


# --------------------------------------------------------------------------- détail colonne par colonne
def column_details(df: pd.DataFrame, ycols: list[str]) -> list[dict]:
    n = len(df)
    rows = []
    for c in df.columns:
        s = df[c]
        miss = int(s.isna().sum())
        non_null = n - miss
        nun = int(s.nunique(dropna=True))
        row = {
            "column": c,
            "dtype": str(s.dtype),
            "is_year_column": c in ycols,
            "non_null": non_null,
            "missing": miss,
            "missing_pct": round(miss / n * 100, 2) if n else 0.0,
            "unique": nun,
            "unique_pct": round(nun / non_null * 100, 2) if non_null else 0.0,
            "example": _short(s.dropna().iloc[0]) if non_null else None,
        }
        if pd.api.types.is_numeric_dtype(s) and non_null:
            row.update(min=_f(s.min()), max=_f(s.max()), mean=_f(s.mean()),
                       median=_f(s.median()), std=_f(s.std()))
        elif non_null:
            top = s.value_counts().head(1)
            row.update(avg_length=round(float(s.dropna().astype(str).str.len().mean()), 1),
                       top_value=_short(top.index[0]), top_freq=int(top.iloc[0]))
        rows.append(row)
    return rows


def missing_buckets(miss_pct: pd.Series) -> dict:
    """Nombre de colonnes par tranche de valeurs manquantes."""
    return {
        "0% (complètes)": int((miss_pct == 0).sum()),
        "0-20%": int(((miss_pct > 0) & (miss_pct <= 20)).sum()),
        "20-50%": int(((miss_pct > 20) & (miss_pct <= 50)).sum()),
        "50-80%": int(((miss_pct > 50) & (miss_pct <= 80)).sum()),
        "80-100%": int((miss_pct > 80).sum()),
    }


# --------------------------------------------------------------------------- couverture par année
def coverage_by_year(df: pd.DataFrame, ycols: list[str]) -> dict:
    """Combien de valeurs/lignes par année (format wide temporel ou colonne 'year')."""
    n = len(df)
    if ycols:
        vals = numeric_year_view(df, ycols)
        return {str(y): {"non_null": int(df[y].notna().sum()),
                         "numeric": int(vals[y].notna().sum()),
                         "coverage_pct": round(float(vals[y].notna().mean()) * 100, 2)} for y in ycols}
    ycol = _year_col_name(df)
    if ycol is not None:
        counts = df[ycol].value_counts().sort_index()
        return {str(int(y)): {"rows": int(k), "share_pct": round(float(k) / n * 100, 2)}
                for y, k in counts.items() if pd.notna(y)}
    return {}


def partial_years(cov: dict) -> dict:
    """Années anormalement peu remplies.
    - tabulaire : une vague avec moins de 25 % des lignes de la vague médiane (ex. Findex 2022)
    - wide temporel : la DERNIÈRE année si elle est à moins de 60 % de la moyenne des 5 précédentes."""
    if not cov:
        return {}
    first = next(iter(cov.values()))
    out = {}
    if "rows" in first:
        med = float(np.median([d["rows"] for d in cov.values()]))
        for y, d in cov.items():
            if med and d["rows"] < 0.25 * med:
                out[y] = {"rows": d["rows"], "median_rows": med,
                          "reason": "vague partielle : vérifier quels pays sont couverts"}
    else:
        years = list(cov)
        if len(years) >= 3:
            last = years[-1]
            ref = np.mean([cov[y]["coverage_pct"] for y in years[-6:-1]])
            if ref and cov[last]["coverage_pct"] < 0.6 * ref:
                out[last] = {"coverage_pct": cov[last]["coverage_pct"], "reference_pct": round(float(ref), 2),
                             "reason": "dernière année incomplète : marquer comme partielle ou exclure des tendances"}
    return out


def year_column_issues(df: pd.DataFrame, ycols: list[str]) -> dict:
    """Colonnes d'années qui ne sont pas numériques (ex. FAS 2025 lue comme texte)."""
    issues = {}
    for y in ycols:
        s = df[y]
        if pd.api.types.is_numeric_dtype(s):
            continue
        nn = s.dropna()
        coerced = pd.to_numeric(nn, errors="coerce")
        bad = nn[coerced.isna()]
        issues[str(y)] = {"dtype": str(s.dtype), "non_null": int(len(nn)),
                          "non_numeric": int(len(bad)),
                          "examples": [_short(v, 20) for v in pd.unique(bad)[:5]]}
    return issues


# --------------------------------------------------------------------------- couverture par indicateur
def scope_mask(df: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    """Périmètre 'population totale' pour compter la couverture (group/group2 == 'all')."""
    mask = pd.Series(True, index=df.index)
    scope = []
    for g in ("group", "group2"):
        if g in df.columns:
            is_all = df[g].astype(str).str.lower() == "all"
            if is_all.any():
                mask &= is_all
                scope.append(f"{g} == 'all'")
    return mask, scope


def indicator_coverage(df: pd.DataFrame) -> dict:
    """[tabulaire] Pour chaque indicateur numérique décimal : nb de valeurs non vides par année.
    Répond à : "cette colonne vide à 90 % existe-t-elle au moins certaines années ?" """
    ycol = _year_col_name(df)
    if ycol is None:
        return {}
    mask, scope = scope_mask(df)
    sub = df[mask]
    cols = [c for c in sub.select_dtypes("floating").columns]
    if not cols or sub.empty:
        return {}
    size = sub.groupby(ycol).size()
    counts = sub.groupby(ycol)[cols].count()
    matrix = {c: {str(int(y)): int(counts.loc[y, c]) for y in counts.index} for c in cols}
    first_last = {}
    for c in cols:
        ys = [int(y) for y in counts.index if counts.loc[y, c] > 0]
        first_last[c] = [min(ys), max(ys)] if ys else None
    return {"scope": " et ".join(scope) or "toutes les lignes",
            "rows_per_year": {str(int(y)): int(v) for y, v in size.items()},
            "matrix": matrix, "first_last_year": first_last}


def classify_sparse(df: pd.DataFrame, high_missing: list[str], cov: dict) -> tuple[dict, list[str]]:
    """Sépare les colonnes très vides en :
       - structurelles : bien remplies (>= 50 % du périmètre) au moins UNE année -> à GARDER
       - éparses       : jamais bien remplies -> à examiner"""
    structural, sparse = {}, []
    if not cov:
        return structural, [c for c in high_missing]
    rows = cov["rows_per_year"]
    for c in high_missing:
        if c not in cov["matrix"]:
            sparse.append(c)
            continue
        good = [y for y, n in cov["matrix"][c].items() if rows.get(y) and n >= 0.5 * rows[y]]
        (structural.__setitem__(c, good) if good else sparse.append(c))
    return structural, sparse


def indicator_catalog(df: pd.DataFrame, ycols: list[str], keys: list[dict],
                      indicator_col: str = INDICATOR_COLUMN) -> list[dict]:
    """[wide temporel] Liste des types d'indicateurs : nb de séries, pays couverts, 1re et dernière année."""
    if indicator_col not in df.columns or not ycols:
        return []
    has = numeric_year_view(df, ycols).notna().to_numpy()
    years = np.array([int(str(y)) for y in ycols])
    any_data = has.any(axis=1)
    last = np.where(any_data, (has * years).max(axis=1), 0)
    first = np.where(any_data, np.where(has, years, 9999).min(axis=1), 0)
    iso = country_series(df, keys)
    tmp = pd.DataFrame({"indicator": df[indicator_col].fillna("(vide)").astype(str).to_numpy(),
                        "iso": iso.to_numpy() if iso is not None else np.nan,
                        "first": first, "last": last, "has": any_data})
    rows = []
    for ind, g in tmp.groupby("indicator"):
        d = g[g["has"]]
        rows.append({"indicator": ind, "n_series": int(len(g)), "n_series_with_data": int(len(d)),
                     "n_countries": int(d["iso"].nunique()) if len(d) else 0,
                     "first_year": int(d["first"].min()) if len(d) else None,
                     "last_year": int(d["last"].max()) if len(d) else None})
    return sorted(rows, key=lambda r: -r["n_countries"])


# --------------------------------------------------------------------------- profil complet
def profile(df: pd.DataFrame, name: str, cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    th = cfg.get("high_missing_threshold", 0.8)
    text_len = cfg.get("metadata_text_length", 150)
    contamination = cfg.get("isolation_forest_contamination", 0.02)
    enable_iforest = bool(cfg.get("enable_isolation_forest", True))

    n, p = df.shape
    ycols = year_columns(df)
    fmt = "wide_temporal" if len(ycols) >= 3 else "tabular"
    miss_pct = (df.isna().mean() * 100).round(2)
    row_miss = df.isna().sum(axis=1)
    txt_cols = text_columns(df)

    keys = find_key_candidates(df)
    iso = country_series(df, keys)
    n_countries = int(iso.nunique()) if iso is not None else None

    n_dup = int(df.duplicated().sum())
    overview = {
        "rows": int(n), "cols": int(p),
        "cells": int(n * p),
        "missing_cells": int(df.isna().sum().sum()),
        "missing_cells_pct": round(float(df.isna().sum().sum()) / (n * p) * 100, 2) if n * p else 0.0,
        "columns_without_missing": int((miss_pct == 0).sum()),
        "columns_with_missing": int((miss_pct > 0).sum()),
        "columns_fully_empty": miss_pct[miss_pct == 100].index.tolist(),
        "complete_rows": int((row_miss == 0).sum()),
        "rows_with_missing": int((row_miss > 0).sum()),
        "avg_missing_per_row": round(float(row_miss.mean()), 2) if n else 0.0,
        "duplicates": n_dup,
        "n_countries": n_countries,
        "dtype_counts": df.dtypes.astype(str).value_counts().to_dict(),
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1e6, 2),
    }

    columns = column_details(df, ycols)
    metadata_cols = [c for c in txt_cols if c not in ycols
                     and df[c].dropna().astype(str).str.len().mean() > text_len]
    high_missing = miss_pct[miss_pct > th * 100].index.tolist()
    constant = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    low_card = {c: df[c].value_counts().head(10).to_dict()
                for c in txt_cols if c not in metadata_cols and c not in ycols and df[c].nunique() <= 15}

    numeric = [c for c in df.select_dtypes("number").columns if c not in ycols and str(c).lower() != "year"]
    anomalies = {"iqr": iqr_outliers(df, numeric), "isolation_forest": []}
    if fmt == "tabular" and enable_iforest:
        anomalies["isolation_forest"] = isolation_forest(df, numeric, contamination)

    # --- couverture dans le temps
    cov_year = coverage_by_year(df, ycols)
    partial = partial_years(cov_year)
    year_issues = year_column_issues(df, ycols)
    ind_cov = indicator_coverage(df) if fmt == "tabular" else {}
    structural, sparse = classify_sparse(
        df, [c for c in high_missing if c not in ycols and c not in overview["columns_fully_empty"]], ind_cov) \
        if fmt == "tabular" else ({}, [])

    # --- contrôle des fractions (Findex)
    rates = rate_range_check(df, numeric) if fmt == "tabular" else {}

    # --- spécifique FAS : types d'unités et catalogue d'indicateurs
    units = {}
    for k in keys:
        if k["how"].startswith("prefix"):
            units = df[k["column"]].astype(str).str.split(".").str[2].value_counts().to_dict()
    value_catalog = {c: df[c].value_counts(dropna=False).head(100).to_dict()
                     for c in CATALOG_COLUMNS if c in df.columns and df[c].nunique(dropna=True) <= 100}
    ind_catalog = indicator_catalog(df, ycols, keys) if fmt == "wide_temporal" else []
    descriptive_partial = [c for c in high_missing if c not in ycols and c not in structural
                           and c not in overview["columns_fully_empty"]] if fmt == "wide_temporal" else []

    # --- recommandations
    reco = []
    if n_dup:
        reco.append(f"supprimer {n_dup} doublons")
    for c, vals in low_card.items():
        if "all" in [str(v).lower() for v in vals] and len(vals) > 1:
            reco.append(f"{c} : GARDER tous les groupes dans le warehouse (comparaisons genre/revenu) ; "
                        f"filtrer {c} == 'all' seulement pour les agregats globaux")
    if metadata_cols:
        reco.append(f"sortir vers le catalogue de métadonnées (inutiles pour l'analyse) : {metadata_cols}")
    if overview["columns_fully_empty"]:
        reco.append(f"supprimer les colonnes 100% vides : {overview['columns_fully_empty']}")
    if structural:
        reco.append("NE PAS supprimer (colonnes remplies seulement certaines années) : "
                    + "; ".join(f"{c} -> {', '.join(ys)}" for c, ys in structural.items())
                    + " ; l'ETL doit conserver l'annee de disponibilite")
    if sparse:
        reco.append(f"à examiner (jamais bien remplies sur une année) : {sparse}")
    if descriptive_partial:
        reco.append(f"colonnes descriptives partiellement remplies (normal, ne concernent que certaines séries) : "
                    f"{descriptive_partial}")
    if year_issues:
        reco.append("colonnes d'années stockées en texte : " + "; ".join(
            f"{y} ({d['non_numeric']} valeurs non numériques)" for y, d in year_issues.items())
            + " -> convertir en numérique avant tout calcul")
    for y, d in partial.items():
        reco.append(f"année/vague {y} partielle ({d['reason']})")
    if rates:
        n_bad = sum(d["n_out_of_range"] for d in rates.values())
        reco.append(f"{len(rates)} colonnes en fractions 0-1 : convertir en % à l'ETL"
                    + (f" ; {n_bad} valeurs hors [0, 1] à contrôler" if n_bad else " ; aucune valeur hors [0, 1]"))
    if len(units) > 1:
        reco.append(f"séries d'unités différentes {list(units)} : ne comparer que des séries de même "
                    f"type (TYPE_OF_TRANSFORMATION / UNIT) ; pour dépôts et prêts, éviter la monnaie locale")
    if ind_catalog:
        reco.append(f"{len(ind_catalog)} types d'indicateurs ({INDICATOR_COLUMN}) : voir indicator_catalog_{name}.csv "
                    f"pour vérifier ATMs, agences, mobile money, banque mobile")
    if fmt == "wide_temporal":
        reco.append("format wide temporel : passer les colonnes années en lignes (unpivot) à l'ETL")
    if not any(k["type"] == "iso3" for k in keys):
        reco.append("aucune clé ISO3 détectée : mapping de pays nécessaire")

    return {
        "source": name,
        "format": fmt,
        "rows": int(n),
        "cols": int(p),
        "overview": overview,
        "missing_summary": missing_buckets(miss_pct),
        "top_missing_columns": [{"column": c, "missing_pct": float(v)}
                                for c, v in miss_pct.sort_values(ascending=False).head(15).items() if v > 0],
        "columns": columns,
        "coverage_by_year": cov_year,
        "partial_years": partial,
        "year_columns": ycols,
        "year_column_issues": year_issues,
        "indicator_coverage": ind_cov,
        "structural_columns": structural,
        "sparse_columns": sparse,
        "rate_range_check": rates,
        "key_candidates": keys,
        "constant_columns": constant,
        "metadata_columns": metadata_cols,
        "high_missing_columns": high_missing,
        "categorical_values": low_card,
        "value_catalog": value_catalog,
        "indicator_catalog": ind_catalog,
        "series_code_units": units,
        "anomalies": anomalies,
        "recommendations": reco,
    }


# --------------------------------------------------------------------------- rapport markdown
def to_markdown(prof: dict) -> str:
    o = prof["overview"]
    L = [f"# Profil de la source : {prof['source']}", "", f"Format détecté : **{prof['format']}**", "",
         "## Vue d'ensemble", "", "| Indicateur | Valeur |", "|---|---|",
         f"| Lignes | {o['rows']:,} |", f"| Colonnes | {o['cols']} |",
         f"| Cellules totales | {o['cells']:,} |",
         f"| Valeurs manquantes | {o['missing_cells']:,} ({o['missing_cells_pct']} %) |",
         f"| Colonnes sans NaN | {o['columns_without_missing']} |",
         f"| Colonnes avec NaN | {o['columns_with_missing']} |",
         f"| Colonnes 100 % vides | {len(o['columns_fully_empty'])} |",
         f"| Lignes complètes (0 NaN) | {o['complete_rows']:,} |",
         f"| Lignes avec au moins 1 NaN | {o['rows_with_missing']:,} |",
         f"| NaN moyen par ligne | {o['avg_missing_per_row']} |",
         f"| Doublons | {o['duplicates']:,} |",
         f"| Pays distincts | {o['n_countries']} |",
         f"| Mémoire | {o['memory_mb']} Mo |", "",
         f"Types : {o['dtype_counts']}", "",
         "## Colonnes par tranche de valeurs manquantes", "", "| Tranche | Nb colonnes |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in prof["missing_summary"].items()]
    L += ["", "## Top 15 colonnes les plus vides", "", "| Colonne | % manquant |", "|---|---|"]
    L += [f"| {d['column']} | {d['missing_pct']} |" for d in prof["top_missing_columns"]]

    # couverture par année
    if prof["coverage_by_year"]:
        L += ["", "## Couverture par année", ""]
        for y, d in prof["coverage_by_year"].items():
            if "rows" in d:
                L.append(f"- {y} : {d['rows']:,} lignes ({d['share_pct']} %)")
            else:
                L.append(f"- {y} : {d['numeric']:,} valeurs numériques ({d['coverage_pct']} %)")
    if prof["partial_years"]:
        L += ["", "### Années / vagues partielles", ""]
        L += [f"- **{y}** : {d['reason']}" for y, d in prof["partial_years"].items()]
    if prof["year_column_issues"]:
        L += ["", "### Colonnes d'années en texte", ""]
        L += [f"- `{y}` ({d['dtype']}) : {d['non_numeric']} valeurs non numériques, exemples {d['examples']}"
              for y, d in prof["year_column_issues"].items()]

    # couverture par indicateur et par année
    ic = prof["indicator_coverage"]
    if ic:
        years = list(ic["rows_per_year"])
        L += ["", "## Couverture par indicateur et par année",
              "", f"Périmètre : {ic['scope']}. Chaque case = nombre de lignes avec une valeur. "
              "Une colonne vide à 90 % mais remplie une année est **structurelle** : à garder.", "",
              "| Indicateur | " + " | ".join(years) + " |", "|---|" + "---|" * len(years),
              "| *(lignes du périmètre)* | " + " | ".join(str(ic["rows_per_year"][y]) for y in years) + " |"]
        for c, row in sorted(ic["matrix"].items(), key=lambda kv: sum(kv[1].values())):
            L.append(f"| {c} | " + " | ".join(str(row.get(y, 0)) for y in years) + " |")
        if prof["structural_columns"]:
            L += ["", "**Structurelles (à garder)** : "
                  + "; ".join(f"`{c}` ({', '.join(ys)})" for c, ys in prof["structural_columns"].items())]
        if prof["sparse_columns"]:
            L += ["", f"**Éparses (à examiner)** : {prof['sparse_columns']}"]

    if prof["rate_range_check"]:
        bad = {c: d for c, d in prof["rate_range_check"].items() if d["n_out_of_range"]}
        L += ["", "## Contrôle des fractions [0, 1]", "",
              f"{len(prof['rate_range_check'])} colonnes ressemblent à des fractions ; "
              f"{len(bad)} contiennent des valeurs hors [0, 1]."]
        L += [f"- `{c}` : {d['n_out_of_range']} valeurs hors [0, 1] (min {d['min']}, max {d['max']})"
              for c, d in bad.items()]

    if prof["value_catalog"]:
        L += ["", "## Valeurs des colonnes de type / unité", ""]
        for c, vals in prof["value_catalog"].items():
            L.append(f"- `{c}` : " + ", ".join(f"{k} ({v:,})" for k, v in list(vals.items())[:15])
                     + (" …" if len(vals) > 15 else ""))
    if prof["indicator_catalog"]:
        L += ["", f"## Catalogue des indicateurs ({INDICATOR_COLUMN})", "",
              "| Indicateur | Séries | Séries avec données | Pays | 1re année | Dernière année |",
              "|---|---|---|---|---|---|"]
        L += [f"| {r['indicator']} | {r['n_series']} | {r['n_series_with_data']} | {r['n_countries']} | "
              f"{r['first_year']} | {r['last_year']} |" for r in prof["indicator_catalog"]]

    L += ["", "## Détail colonne par colonne (triées par % manquant)", "",
          "| Colonne | Type | Manquants | % manquant | Uniques | Exemple |", "|---|---|---|---|---|---|"]
    for c in sorted(prof["columns"], key=lambda d: -d["missing_pct"]):
        L.append(f"| {c['column']} | {c['dtype']} | {c['missing']:,} | {c['missing_pct']} | "
                 f"{c['unique']:,} | {str(c['example']).replace('|', '/')} |")
    L += ["", "## Clés candidates", ""]
    L += [f"- `{k['column']}` ({k['type']}, {k['how']})" for k in prof["key_candidates"]] or ["- aucune"]
    L += ["", "## Valeurs atypiques (IQR, informatif : pas forcément des erreurs)", ""]
    L += [f"- `{a['column']}` : {a['n_outliers']} valeurs ({a['pct_outliers']} %)" for a in prof["anomalies"]["iqr"][:15]] or ["- aucune"]
    L += ["", "## Recommandations de nettoyage (pistes)", ""]
    L += [f"- {r}" for r in prof["recommendations"]] or ["- aucune"]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- agent
class ProfilerAgent(BaseAgent):
    name = "profiler"

    def _profile_source(self, name: str, source_cfg: dict) -> tuple[dict, str]:
        self.log.info("[%s] chargement", name)
        df = load_source(source_cfg)
        prof = profile(df, name, self.cfg.get("profiler"))

        out_dir = self.cfg["paths"]["profiles"]
        json_path = resolve(f"{out_dir}/profile_{name}.json")
        save_json(prof, json_path)
        pd.DataFrame(prof["columns"]).to_csv(
            resolve(f"{out_dir}/columns_{name}.csv"), index=False, encoding="utf-8-sig"
        )
        if prof["indicator_coverage"]:
            ic = prof["indicator_coverage"]
            pd.DataFrame(ic["matrix"]).T.fillna(0).astype(int).to_csv(
                resolve(f"{out_dir}/indicator_coverage_{name}.csv"), encoding="utf-8-sig"
            )
        if prof["indicator_catalog"]:
            pd.DataFrame(prof["indicator_catalog"]).to_csv(
                resolve(f"{out_dir}/indicator_catalog_{name}.csv"),
                index=False,
                encoding="utf-8-sig",
            )
        resolve(f"{out_dir}/profile_{name}.md").write_text(to_markdown(prof), encoding="utf-8")
        return prof, str(json_path)

    def _summary(self, prof: dict, path: str) -> dict:
        overview = prof["overview"]
        return {
            "path": path,
            "format": prof["format"],
            "rows": prof["rows"],
            "cols": prof["cols"],
            "missing_cells_pct": overview["missing_cells_pct"],
            "duplicates": overview["duplicates"],
            "n_countries": overview["n_countries"],
            "columns_fully_empty": len(overview["columns_fully_empty"]),
            "structural_columns": prof["structural_columns"],
            "sparse_columns": prof["sparse_columns"],
            "partial_years": prof["partial_years"],
            "year_column_issues": prof["year_column_issues"],
            "key_candidates": prof["key_candidates"],
            "anomaly_count": sum(len(v) for v in prof["anomalies"].values()),
            "recommendations": prof["recommendations"],
        }

    def _notes(self, summaries: dict) -> str:
        """Synthese deterministe : aucun appel LLM."""
        return " | ".join(
            f"{name}: {s['rows']} lignes x {s['cols']} colonnes, "
            f"{s['missing_cells_pct']}% de cellules vides, {s['n_countries']} pays"
            for name, s in summaries.items()
        )

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        sources = ctx.get("sources") or self.cfg.get("sources") or {}
        raw_paths = ctx.get("raw_paths") or {}
        if not sources:
            raise AgentError("aucune source a profiler")

        summaries: dict[str, Any] = {}
        for name, source_cfg in sources.items():
            source_cfg = dict(source_cfg)
            if name in raw_paths:
                source_cfg["path"] = raw_paths[name]
            prof, path = self._profile_source(name, source_cfg)
            summaries[name] = self._summary(prof, path)
            o = prof["overview"]
            self.log.info(
                "[%s] %s lignes x %s colonnes | format=%s | NaN=%s%% | %s pays",
                name,
                f"{o['rows']:,}",
                o["cols"],
                prof["format"],
                o["missing_cells_pct"],
                o["n_countries"],
            )

        notes = dict(ctx.get("llm_notes") or {})
        notes["profiler"] = self._notes(summaries)
        return {"profiles": summaries, "llm_notes": notes}
