# BIFlow — Automatisation d'un pipeline BI multi-agents

Pipeline Business Intelligence automatique : **données brutes → profilage →
qualité → ETL → KPI**, orchestré par un graphe LangGraph et des agents LLM
(Gemini, Groq).

Cette version couvre le **P1 — Données** (collecte, profilage, quality gate,
modèle en étoile) et le calcul déterministe des **KPI du catalogue** pour un pays
focus et ses pairs.

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
- [x] **KPI** : étape `semantic_kpi` après l'ETL (table `kpi_values`) et route
      sémantique à la demande (`run_semantic_request`).

Les phases analyse, dashboard et XAI ne sont pas incluses.

## Architecture

```
main.py / scripts/check_llm.py
src/biflow/
  config.py        configuration YAML + chemins
  llm.py           providers, fallback, cache, compteur de tokens
  state.py         etat partage du pipeline
  graph.py         graphe LangGraph + repli sequentiel
  semantic_graph.py  route semantique a la demande (une requete KPI)
  agents/          base, collector, snapshot, profiler, quality, etl, semantic_kpi
  tools/           dictionnaire d'indicateurs, calcul/provenance des KPI, kpi_values, snapshots
  utils/           io, logger, pays (ISO3)
config/config.yaml     chemins, LLM, orchestrateur, KPI, sources, seuils
config/kpi_catalog.v1.yaml  definitions declaratives des KPI (version 1.2.0)
data/                  raw, snapshots, staging, processed, profiles, quality
outputs/               reports, profiles, logs, cache LLM
```

## Pipeline (S06 → S11)

| Etape | Agent | Sorties principales |
|---|---|---|
| S06 | `collector` | `data/raw/*.csv` + SHA-256, telechargement WDI pagine (FAS via API en option) |
| S07 | `snapshot` | `data/snapshots/` : nouvelle version `vN` si le contenu change, sinon `no_change` |
| S08 | `profiler` | `outputs/profiles/profile_*.{json,md}`, couverture indicateurs |
| S09 | `quality` | `data/quality/quality_report.{json,md}` (run_id, snapshot_id, SHA-256 des sources), gate PASS/FAIL |
| S10 | `etl` | `data/processed/*.parquet`, `warehouse.duckdb`, `lineage.json` |
| S11 | `semantic_kpi` | table DuckDB `kpi_values` + `data/processed/kpi_values.parquet` |

Chaque execution ecrit un rapport dans `outputs/reports/<run_id>/` ; `run.json`
liste aussi chaque tentative d'agent (`attempts`).

- **Quality gate** : un FAIL arrête le pipeline avant l'ETL (et donc les KPI).
  C'est une décision, jamais retentée.
- **Retry** : un agent en erreur est relancé `orchestrator.max_retries` fois
  (1 par défaut) après `retry_backoff_s × n` secondes. Au dernier échec, le
  pipeline s'arrête, les sorties publiées précédemment restent en place et
  chaque tentative est tracée dans `run.json` et `errors`.

### Snapshots des sources brutes (`snapshot`)

Le collector réécrit `data/raw/*.csv` et l'ETL remplace ses tables : l'historique
est conservé dans `data/snapshots/` :

```
data/snapshots/
  index.json              versions, statut, version publiée
  blobs/<sha256>.csv      chaque fichier brut stocké une seule fois (copie exacte)
  vN/manifest.json        created_at, run_id, content_key ; par source : blob,
                          sha256, content_sha256, rows, size_bytes, original_path
```

- L'empreinte de contenu ignore l'ordre des lignes (BOM et fins de ligne
  normalisés). Si elle est identique à la version publiée, le run se termine en
  `no_change` après le snapshot : profil, qualité, ETL et KPI ne sont pas relancés
  et aucun artefact publié n'est réécrit.
- Sinon une version `vN` est créée (`pending`) puis publiée seulement si le run
  aboutit (ETL inclus). En cas d'échec, de quality gate FAIL ou de run partiel
  (`--to quality`), elle passe `not_published` et la version publiée reste en place.
- Les blobs référencés par une version de `index.json` sont conservés, les autres
  supprimés. `snapshot_id` est enregistré dans l'état, `run.json`, `lineage.json`,
  `quality_report.json` et `kpi_values`.

### FAS via IMF Data API (optionnel)

`sources.fas.api.enabled: false` par défaut : `fas.csv` statique reste la source.
Activé, le collector interroge l'API SDMX 3.0
(`https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/FAS/~/{pays}.{clé}`,
`Accept: text/csv`) pour chaque série de `sources.fas.api.series`, convertit la
réponse (une ligne par observation) au format large de `fas.csv` sans toucher aux
valeurs, et écrit `data/raw/fas_api.csv`, qui remplace alors `fas.csv` pour ce run.
Une échelle autre que `0` (unités) ou une fréquence non annuelle est refusée.
Si l'API est injoignable, le fichier déjà collecté est conservé (le snapshot
publié reste donc valide).

L'API sert FAS 8.0.0 : les codes diffèrent de l'export local FAS 5.0.0. Seules
deux séries sont mappées, vérifiées le 2026-10-29 (valeurs TUN 2019-2023
identiques à `fas.csv`) : `FA26N.PHTADLT_NUM` → `FA26._Z._Z._T.PHTADLT_NUM.A` et
`FA18N.PHTADLT_NUM` → `FA18._Z._Z._T.PHTADLT_NUM.A`. Les autres séries (déposants,
emprunteurs, comptes, % du PIB) ont plusieurs ventilations possibles en 8.0.0 et
restent non mappées : avec l'API activée, elles manquent et le collector le signale.

### Étape KPI (`semantic_kpi`)

En mode pipeline, l'agent calcule chaque KPI du catalogue pour `kpi.focus` et
`kpi.peers`, sur chaque année valide du catalogue, via `SemanticKpiTools`
(lecture seule des faits, aucun LLM). Table `kpi_values` :

| Colonne | Contenu |
|---|---|
| `kpi_id`, `iso3`, `year` | clé (`iso3 = 'PEERS'` pour la moyenne des pairs) |
| `value`, `unit` | valeur calculée ; `NULL` si indisponible (jamais 0) |
| `availability_status`, `reason` | `available` / `unavailable` / `requires_review` |
| `definition_status` | `verified`, `verified_metadata`, `derived_verified`, `provisional` |
| `requires_review`, `review_reasons` | provenance, définition provisoire, alertes qualité |
| `peer_status`, `peers_included`, `missing_peers`, `aggregation_method` | lignes PEERS : `complete` / `partial` / `none` |
| `catalog_version`, `catalog_sha256`, `run_id` | traçabilité |

La ligne `PEERS` est une moyenne **simple, non pondérée** des pairs disponibles
(`aggregation_method = simple_mean_4_peers` avec 4 pairs). Elle n'est marquée
pour revue que si un pair manque (`partial_peer_coverage`, ou
`no_peer_observation` si aucun pair n'a de valeur) ; les raisons de revue des
pairs inclus sont héritées.

KPI du catalogue 1.2.0 : `account_ownership`, `branch_density`,
`digital_payment_rate`, `saving_rate` et `borrowing_rate` (mesures « any »,
glossaire lignes 121 et 3), `unbanked_share`, `formal_saving_rate` (`fin17a`),
`formal_borrowing_rate` (`fin22a`, carte de crédit incluse), `gender_gap`,
`income_gap`, `age_gap` (points de pourcentage, mêmes pays et année).

### Clés de configuration

| Clé | Défaut | Rôle |
|---|---|---|
| `kpi.focus` | `TUN` | pays focus de l'étape KPI |
| `kpi.peers` | `[DZA, EGY, JOR, MAR]` | groupe de pairs (ligne `PEERS`) |
| `orchestrator.max_retries` | `1` | nouveaux essais d'un agent en erreur |
| `orchestrator.retry_backoff_s` | `1.0` | attente avant l'essai n (`n × backoff`) |
| `snapshots.enabled` | `true` | versionnement des sources brutes |
| `snapshots.root` | `data/snapshots` | `index.json`, `blobs/`, `vN/manifest.json` |
| `sources.fas.api.enabled` | `false` | collecte FAS via l'API IMF au lieu de `fas.csv` |
| `sources.fas.api.series` | 2 séries vérifiées | série locale → clé SDMX (sans le pays) |
| `sources.fas.api.path` | `data/raw/fas_api.csv` | sortie de la collecte API |
| `sources.gdp.indicators` | `NY.GDP.MKTP.CD`, `NY.GDP.PCAP.CD`, `NY.GDP.MKTP.KD.ZG` | indicateurs WDI collectés |

## Démarrage

Windows (PowerShell) :

```powershell
# 1. Environnement
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Clés LLM (optionnelles pour l'ETL, utiles au quality gate)
Copy-Item .env.example .env
# renseigner GOOGLE_API_KEY, GROQ_API_KEY

# 3. Vérification des providers
python scripts/check_llm.py

# 4. Pipeline complet (collector -> etl -> semantic_kpi)
python main.py run

# Etapes ciblees
python main.py steps
python main.py run --only quality
python main.py run --from etl
python main.py run --to etl --no-llm      # s'arrete apres l'ETL, sans KPI
python main.py run --only semantic_kpi    # recalcule kpi_values sur le warehouse existant

# 5. Tests
.\.venv\Scripts\python -m pytest -q
```

Linux / macOS (bash) :

```bash
# 1. Environnement
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Clés LLM (optionnelles pour l'ETL, utiles au quality gate)
cp .env.example .env
# renseigner GOOGLE_API_KEY, GROQ_API_KEY

# 3. Vérification des providers
python scripts/check_llm.py

# 4. Pipeline complet (collector -> etl -> semantic_kpi)
python main.py run

# Etapes ciblees
python main.py steps
python main.py run --only quality
python main.py run --from etl
python main.py run --to etl --no-llm
python main.py run --only semantic_kpi

# 5. Tests
.venv/bin/python -m pytest -q
```

## Sorties

- `data/raw/` : sources brutes et empreintes SHA-256 ;
- `data/snapshots/` : versions des sources brutes (index, blobs, manifestes) ;
- `outputs/profiles/` : profils JSON/Markdown et diagnostics de couverture ;
- `data/quality/` : rapport qualité JSON/Markdown (`run_id`, `created_at`,
  `inputs.<source>.sha256`), anomalies et gate PASS/FAIL ;
- `data/processed/` : tables Parquet, `warehouse.duckdb` (dont `kpi_values`),
  `kpi_values.parquet` et `lineage.json` ;
- `outputs/reports/<run_id>/` : rapport standardisé de chaque agent et `run.json`.

`main.py run` renvoie le code 0 pour `success` et `no_change`.

Le rapport qualité est lié au run : quand son `run_id` et les SHA-256 des
sources correspondent à `lineage.json`, les KPI ne portent plus la raison de
revue `quality_provenance_unverified` ; un désaccord donne
`quality_provenance_mismatch` (par exemple `--from etl` avec un rapport qualité
d'un run précédent).

## Données et périmètre

- Findex : vagues 2011, 2014, 2017, 2021, 2022 (partielle), 2024 ; les agrégats
  régionaux sont conservés mais signalés comme non-pays.
- FAS : séries `FA26N.PHTADLT_NUM`, `FA18N.PHTADLT_NUM`,
  `FA29N_COMBANK.PTADLT_NUM`, `FA21N_COMBANK.PTADLT_NUM`,
  `LOANACCN_COMBANK.PTADLT_NUM`, `FA30N_COMBANK.PTADLT_NUM` ; 2025 exclue car
  incomplète.
- WDI : PIB, PIB par habitant (USD courants) et croissance du PIB
  `NY.GDP.MKTP.KD.ZG` (% annuel, prix constants 2015), lignes sans code ISO3
  ignorées. `gdp_growth_pct` reprend directement cet indicateur : il n'est plus
  calculé depuis le PIB en USD courants (les effets de change comptaient comme
  de la croissance). Les taux négatifs sont conservés.
- Findex, sous-groupes : `gender` (men / women), `income` (richest 60% /
  poorest 40%), `age_cat` (age 25+ / ages 15-24). `country_year` contient
  `account_male/female`, `account_richest_60/poorest_40`,
  `account_age_25_plus/15_24` et les écarts `gender_gap_pp`, `income_gap_pp`,
  `age_gap_pp` (NULL si un sous-groupe manque). Le pivot filtre sur la dimension
  et sa valeur pour éviter toute collision entre groupes.
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

## Findex labels verified in the 2025 glossary (2026-10-29)

Checked against the official Global Findex 2025 glossary (sheet `Glossary`,
sha256 `8eb99754…f923`); row numbers are kept in
`tools/dictionary.py:FINDEX_GLOSSARY_ROWS`.

| Codes | Meaning | Rows |
|---|---|---|
| `fin17a` | Saved at a bank or similar financial institution (past year) | 24 |
| `fin22a` | Borrowed from a bank or similar financial institution, credit card included (past year) | 31 |
| `fin24aP`, `fin24aN`, `fin24aSD_ND` | Emergency funds within 30 days: possible / not possible / possible and not or somewhat difficult | 44, 45, 43 |
| `fin24sav`, `fin24fam`, `fin24work`, `fin24bor`, `fin24sell`, `fin24other` | Main source of emergency funds: savings, family/friends, work, loan, sale of assets, other | 34-39 |
| `fin11a`-`fin11f` | Reasons for not having an account (distance, cost, documents, insufficient funds, family member has one, trust) | 6-11 |

`fin24aP`, `fin24sav` and `fin24bor` were previously labelled as digital payment,
saving and borrowing; they measure financial resilience and feed no KPI. All
values are fractions of all adults aged 15+. A code that cannot be verified is
listed in `FINDEX_UNVERIFIED`, labelled `(unverified)` and rejected by the KPI
catalog (none today).

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
