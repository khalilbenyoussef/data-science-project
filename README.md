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
