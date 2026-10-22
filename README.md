# BIFlow — Automatisation d'un pipeline BI multi-agents

Pipeline Business Intelligence automatique : **données brutes → profilage →
qualité → ETL**, orchestré par un graphe LangGraph et des agents LLM
(Gemini, Groq).

Cette version couvre le **P1 — Données** : collecte, profilage, quality gate et
construction du modèle en étoile.

Domaine : **Économie & Finance / inclusion financière**.

Sources de données :

| Source | Rôle | Fichier |
|---|---|---|
| World Bank **Global Findex** | demande / usage des services financiers | `data/raw/findex.csv` |
| IMF **Financial Access Survey (FAS)** | offre (agences, ATM, dépôts, crédits) | `data/raw/fas.csv` |
| World Bank **WDI** (PIB) | contexte macroéconomique | `data/raw/gdp.csv` |

## État d'avancement

- [x] **P0 — Socle** : configuration, package `biflow`, couche LLM multi-provider,
      vérification des clés.
- [x] **P1 — Données** : collector, profiler, quality gate, ETL (nœuds LangGraph).

Cette branche est limitée au périmètre P1. Les phases KPI, analyse, dashboard et
XAI ne sont pas incluses.

## Architecture (P1)

```
main.py / scripts/check_llm.py
src/biflow/
  config.py        configuration YAML + chemins
  llm.py           providers, fallback, cache, compteur de tokens
  state.py         etat partage du pipeline
  graph.py         graphe LangGraph + repli sequentiel
  agents/          base, collector, profiler, quality, etl
  tools/           dictionnaire d'indicateurs (libelles, unites)
  utils/           io, logger, pays (ISO3)
config/config.yaml     chemins, LLM, sources, seuils
data/                  raw, staging, processed, profiles, quality
outputs/               reports, profiles, logs, cache LLM
```

## Pipeline (S6 → S9)

| Etape | Agent | Sorties principales |
|---|---|---|
| S6 | `collector` | `data/raw/*.csv` + SHA-256, telechargement WDI pagine |
| S7 | `profiler` | `outputs/profiles/profile_*.{json,md}`, couverture indicateurs |
| S8 | `quality` | `data/quality/quality_report.{json,md}`, gate PASS/FAIL |
| S9 | `etl` | `data/processed/*.parquet`, `warehouse.duckdb`, `lineage.json` |

Chaque execution ecrit un rapport dans `outputs/reports/<run_id>/`.

## Démarrage

```powershell
# 1. Environnement
.\.venv-adsp\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Clés LLM (optionnelles pour l'ETL, utiles au quality gate)
Copy-Item .env.example .env
# renseigner GOOGLE_API_KEY, GROQ_API_KEY

# 3. Vérification des providers
python scripts/check_llm.py

# 4. Pipeline complet P1 (collector -> etl)
python main.py run

# Etapes ciblees
python main.py steps
python main.py run --only quality
python main.py run --from etl
python main.py run --to etl --no-llm

# 5. Tests
python -m pytest tests -q
```

## Sorties P1

- `data/raw/` : sources brutes et empreintes SHA-256 ;
- `outputs/profiles/` : profils JSON/Markdown et diagnostics de couverture ;
- `data/quality/` : rapport qualité JSON/Markdown, anomalies et gate PASS/FAIL ;
- `data/processed/` : tables Parquet, `warehouse.duckdb` et `lineage.json` ;
- `outputs/reports/<run_id>/` : rapport standardisé de chaque agent.

## Données et périmètre

- Findex : vagues 2011, 2014, 2017, 2021, 2022 (partielle), 2024 ; les agrégats
  régionaux sont conservés mais signalés comme non-pays.
- FAS : séries `FA26N.PHTADLT_NUM`, `FA18N.PHTADLT_NUM`,
  `FA29N_COMBANK.PTADLT_NUM`, `FA21N_COMBANK.PTADLT_NUM`,
  `LOANACCN_COMBANK.PTADLT_NUM`, `FA30N_COMBANK.PTADLT_NUM` ; 2025 exclue car
  incomplète.
- WDI : PIB et PIB par habitant, lignes sans code ISO3 ignorées.
- Codes non ISO3 normalisés : `KOS -> XKX`, `WBG -> PSE` ; agrégats `EAP`,
  `WLD`, etc. conservés dans `country_dim` mais identifiés comme agrégats.

## Choix techniques

- **LangGraph** : graphe d'états explicite et traçabilité ; repli séquentiel si
  l'import LangGraph est indisponible.
- **LLM pour le quality gate** : routage primaire/fallback, température 0,
  sorties JSON validées, cache disque et plafond d'appels. Les décisions
  PASS/FAIL restent déterministes.
- **ETL déterministe** : pandas / DuckDB pour l'harmonisation, les jointures et
  le modèle en étoile ; le LLM ne calcule aucun chiffre.
- **Traçabilité** : SHA-256 des sources, volumes rejetés, contrôles ETL et
  `lineage.json`.

## Livrables P1

Code et architecture, pipeline automatisé, documentation des sources,
Data Quality Report, tables du modèle en étoile, lineage et tests unitaires.

## Findex digital indicator definitions (verified 2026-10-22)

| Raw/fact code | Meaning | `country_year` column |
|---|---|---|
| `dig_acc` | Adults with a digitally enabled account: mobile money, or a bank/similar account allowing payments by card or phone. This measures account ownership/enabling, not transaction frequency. | `digitally_enabled_account` |
| `g20_any` | Adults who made or received a digital payment in the past year. The measure includes several payment purposes, not just remittances. | `digital_payment` |

For total-population estimates, the population is adults aged 15+; facts also
retain the survey subgroups. Both raw/fact measures remain fractions. The wide
table continues to display percentages (`100 * value`), preserving missing values.

Sources: [World Bank indicator `dig-acc`](https://genderdata.worldbank.org/en/indicator/dig-acc),
[Little Data Book 2025, glossary p. 160](https://thedocs.worldbank.org/en/doc/be6615202d1f08a25855c8ac2d615122-0050012025/related/Little-Data-Book-2025-Web.pdf),
and [Global Findex 2025 glossary, sheet `Glossary`, row 118, code `g20.any`](https://thedocs.worldbank.org/en/doc/be6615202d1f08a25855c8ac2d615122-0050012025/related/GlobalFindex2025-glossary.xlsx).
The official portal/glossary use hyphens/dots in codes; the local CSV uses underscores.

Schema correction: `digital_payment` previously contained `dig_acc`; it now
contains `g20_any`. The misleading `remittance_use` column is removed rather
than retained as a false remittance measure. Consumers must update references;
existing warehouse files are not migrated by this code change.

No remittance-specific or digital-account transaction-frequency KPI has been
verified from these two columns. Do not infer either one or substitute one
measure when the other is missing. This verification does not certify other
Findex labels or every historical wave's detailed questionnaire construction.

## Source schema validation

Quality checks use the mandatory column lists from the ETL. Missing columns,
null/blank keys, malformed country/indicator/annual FAS series codes, and
nonnumeric, nonfinite or fractional key years are critical errors. FAS also
requires at least one four-digit year column. Country aliases and aggregate
codes retain their existing treatment; unknown three-letter codes retain warnings.

Minimum structural indicator coverage is one selected Findex column, one
configured FAS series, and one configured GDP indicator code. The Quality Agent
passes its source configuration into these checks. Standalone checks without
source configuration use dictionary indicators (Findex/GDP) or structural FAS
series coverage. Missing optional indicators are listed in schema metrics.
No complete annual panel, survey-wave list, or non-null value per indicator is
required. Existing row-count, missingness, duplicate and range scoring still
applies; missing observations alone are not new critical schema errors.

## FAS percentage plausibility diagnostics

`quality.fas_pct_gdp_threshold` defaults to `1000.0` (% GDP). Finite values
strictly above this diagnostic threshold are flagged only for
`OUTD_COMBANK.POGDP` (`deposits_pct_gdp`) and `OUTL_COMBANK.POGDP`
(`loans_pct_gdp`). The check covers all four-digit year columns in the raw
source, including years outside the ETL analysis period.

Flags appear under `diagnostics` in the quality JSON, in a separate Markdown
section, and in `quality_diagnostics.csv`. Each records country/ISO3, year,
original series code and value, numeric value, unit, threshold and review reason.
They are separate from structural/scored `issues` and do not change scores,
critical issue counts or gate decisions. No value is dropped, clamped or rescaled.
The threshold is a review trigger, not an official IMF validity limit; the
underlying values and their denominators still require source verification.
