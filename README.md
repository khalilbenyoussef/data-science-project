# BIFlow — Automatisation d'un pipeline BI multi-agents

Pipeline Business Intelligence automatique en deux routes :

- **Route 1 — Données** : données brutes → profilage → qualité → ETL, orchestré
  par LangGraph ; les agents LLM existants (Gemini, Groq) restent inchangés.
- **Route 2 — Analyse** : warehouse → Semantic & KPI → **BI Analyst** →
  **Dashboard React/ECharts**, entièrement déterministe (aucun LLM, aucun
  recalcul, aucune interpolation).

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
- [x] **P2 — Semantic & KPI** : couche KPI déterministe (6 KPI, 6 actions,
      provenance et revue).
- [x] **P3 — Route 2** : BI Analyst déterministe, contrat dashboard et front
      React/ECharts.

La Route 1 n'est pas modifiée par la Route 2 : graphe, agents et CLI existants
conservent leur comportement.

## Architecture

```
main.py / scripts/check_llm.py
src/biflow/
  config.py        configuration YAML + chemins
  llm.py           providers, fallback, cache, compteur de tokens
  state.py         etat partage du pipeline
  graph.py         graphe LangGraph Route 1 + repli sequentiel
  analysis_graph.py graphe Route 2 (BI Analyst -> Dashboard)
  agents/          base, collector, profiler, quality, etl
                   + bi_analyst, dashboard, semantic_kpi
  tools/           dictionnaire d'indicateurs, kpi, semantic_kpi,
                   analysis, dashboard_contract
  utils/           io, logger, pays (ISO3)
config/config.yaml     chemins, LLM, sources, seuils, analyst, dashboard
data/                  raw, staging, processed, profiles, quality
dashboard/             front React + Vite + ECharts (donnees JSON)
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

## Route 2 — BI Analyst et Dashboard

La Route 2 lit le warehouse en **lecture seule** et passe uniquement par les
contrats sémantiques KPI (`list`, `describe`, `calculate`, `latest_available`,
`compare_countries`, `compare_years`). Elle ne contient ni LLM, ni SQL ad hoc,
ni calcul parallèle.

| Etape | Agent | Sorties |
|---|---|---|
| S10 | `bi_analyst` | `analysis_dataset.json`, `bi_analyst.json`, `bi_analyst.md` |
| S11 | `dashboard` | `dashboard_data.json`, `dashboard/public/data/dashboard.json` |

Le **BI Analyst** produit des constats déterministes (`F-001`, …) rattachés à
des identifiants de preuve (`EV-…`, `TR-…`, `CMP-…`). Le **Dashboard** valide
le contrat (schéma `1.0`) puis l'exporte de façon atomique pour le front.

```powershell
# Rapport BI Analyst seul
python main.py analyze --country TUN,MAR,DZA --mode latest --run-id demo

# Analyste + donnees du dashboard
python main.py dashboard --country TUN,MAR,DZA --kpis account_ownership,saving_rate `
  --mode year --year 2024 --reference TUN --top 5 --run-id demo

# Front React (Vite + ECharts)
cd dashboard
npm install
npm run dev        # http://127.0.0.1:5173
npm run build      # tsc --noEmit && vite build
```

Options : `--country` (répétable ou CSV), `--kpis`, `--mode latest|year`,
`--year`, `--reference`, `--top`, `--no-series`, `--run-id`.

- **Aucune valeur n'est inventée** : une observation absente reste `null` avec
  `availability_status="unavailable"` et un motif ; aucun zéro de remplissage,
  aucune interpolation.
- **Comparaisons** : différence absolue `droite − gauche`, en points de
  pourcentage pour les KPI en `percent`.
- **Revue et publication** : `publication_status="not_evaluated"` est conservé
  de bout en bout ; les motifs `requires_review` restent affichés (badges,
  bandeau, notices, pied de page).
- **Provenance** : SHA-256 du warehouse, lineage, rapport qualité, liaison de
  contenu et écarts de sources sont exposés dans les rapports et l'interface.

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

# 5. Route 2 (warehouse deja construit)
python main.py dashboard --country TUN,MAR,DZA --mode latest

# 6. Front (Node.js >= 18)
cd dashboard; npm install; npm run dev

# 7. Tests
python -m pytest tests -q
```

## Sorties P1

- `data/raw/` : sources brutes et empreintes SHA-256 ;
- `outputs/profiles/` : profils JSON/Markdown et diagnostics de couverture ;
- `data/quality/` : rapport qualité JSON/Markdown, anomalies et gate PASS/FAIL ;
- `data/processed/` : tables Parquet, `warehouse.duckdb` et `lineage.json` ;
- `outputs/reports/<run_id>/` : rapport standardisé de chaque agent.

## Sorties Route 2

- `outputs/reports/<run_id>/analysis_dataset.json` : dataset déterministe
  (observations, séries, tendances, classements, comparaisons, couverture,
  notices, provenance) ;
- `outputs/reports/<run_id>/bi_analyst.{json,md}` : rapport et constats
  rattachés aux preuves ;
- `outputs/reports/<run_id>/dashboard_data.json` : contrat validé ;
- `dashboard/public/data/dashboard.json` : copie consommée par le front ;
- `outputs/reports/<run_id>/run.json` : résumé du run Route 2.

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

## Dashboard Finova — `dashboard_app/`

Tableau de bord standalone : API **FastAPI en lecture seule** + front
**React/Vite/TypeScript** (SVG maison). Il expose le contrat de la Route 2 tel
que produit par le pipeline, sans LLM et sans recalcul côté client.

Pré-requis : warehouse et rapport qualité déjà construits
(`python main.py run --from quality --no-llm`) et Node.js >= 18.

### 1. Produire le contrat publié

```powershell
$env:PYTHONPATH = "src"
python -c "from biflow.route2_graph import run_route2; run_route2(use_llm=False)"
```

Écrit `dashboard_app/public/data/finova.json`, un `finova_spec.json` par run
dans `outputs/reports/<run_id>/` et un snapshot dans
`outputs/dashboard/history/` (Tunisie 2024 par défaut, `config/config.yaml`).

### 2. Lancer le dashboard

```powershell
$env:PYTHONPATH = "src"
$env:FINOVA_PREWARM = "1"   # optionnel : prépare en tâche de fond les vues 2024/2021/2017
python -m uvicorn dashboard_app.api.app:app --host 127.0.0.1 --port 8000
# http://127.0.0.1:8000  (API + UI buildée si dashboard_app/web/dist existe)
```

Les vues générées à la demande sont mises en cache dans
`outputs/dashboard/generated/` (une entrée par pays, année et empreinte du
warehouse) : la première ouverture d'un pays prend 20 à 40 secondes, les
suivantes sont immédiates, y compris après redémarrage du serveur.

Développement front avec proxy `/api` vers le port 8000 :

```powershell
cd dashboard_app/web
npm install
npm run dev        # http://127.0.0.1:5173
npm run build      # tsc --noEmit && vite build
```

Le login est une démonstration d'interface (aucune authentification réelle).

### 3. Endpoints

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/spec?iso3=TUN&year=2024` | contrat du scope demandé |
| GET | `/api/runs?limit=20` | derniers `outputs/reports/*/run.json` |
| POST | `/api/ask` | réponse déterministe vérifiée dans les faits |
| GET | `/api/health` | présence du contrat et du warehouse |

Le scope publié est servi tel quel (`X-Finova-Source: file`). Tout autre
pays/année est **construit à la demande** depuis le warehouse
(`X-Finova-Source: generated`), puis mémorisé ; le cache est invalidé si le
warehouse change. Cette génération réutilise le moteur KPI existant : le
premier appel sur un nouveau couple pays/année peut durer une à deux minutes,
les appels suivants sont instantanés. Aucune année n'est substituée : les
cartes affichent l'année réellement utilisée, ou « To load » / « Indisponible ».

### 4. Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_dashboard_api.py tests/test_dashboard_spec.py `
  tests/test_analyst.py tests/test_warehouse_reader.py tests/test_route2_graph.py -q
cd dashboard_app/web; npm run typecheck
```
