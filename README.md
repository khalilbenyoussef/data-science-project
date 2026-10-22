# BIFlow — Automatisation d'un pipeline BI multi-agents

Pipeline Business Intelligence automatique : **données brutes → profilage →
qualité → ETL → KPI → analyse → dashboard → explications XAI**, orchestré par
un graphe LangGraph et des agents LLM (Gemini, Groq).

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
- [x] **P2 — Semantic / KPI** : catalogue KPI + calcul DuckDB (14 KPI).
- [x] **P3 — BI Analyst** : tendances, classements, corrélations, insights.
- [x] **P4 — Dashboard** : Streamlit + Plotly.
- [ ] **P5 — Auditor / XAI** : lineage, explications, évaluation.
- [ ] **P6 — Livrables** : docs, tests, démo.

## Architecture cible

```
main.py / scripts/check_llm.py
src/biflow/
  config.py        configuration YAML + chemins
  llm.py           providers, fallback, cache, compteur de tokens
  state.py         etat partage du pipeline
  graph.py         graphe LangGraph + repli sequentiel
  agents/          base, collector, profiler, quality, etl, semantic, analyst
  tools/           dictionnaire d'indicateurs (libelles, unites)
  utils/           io, logger, lineage, pays (ISO3)
config/config.yaml     chemins, LLM, sources, seuils
config/kpis.yaml       catalogue KPI
dashboard/app.py       dashboard Streamlit            (P4)
data/                  raw, staging, processed, profiles, quality
outputs/               reports, kpis, insights, logs, cache LLM
```

## Pipeline (S6 → S11)

| Etape | Agent | Sorties principales |
|---|---|---|
| S6 | `collector` | `data/raw/*.csv` + SHA-256, telechargement WDI pagine |
| S7 | `profiler` | `outputs/profiles/profile_*.{json,md}`, couverture indicateurs |
| S8 | `quality` | `data/quality/quality_report.{json,md}`, gate PASS/FAIL |
| S9 | `etl` | `data/processed/*.parquet`, `warehouse.duckdb`, `lineage.json` |
| S10 | `semantic` | `outputs/kpis/kpi_values.parquet`, catalogue + synthese |
| S11 | `analyst` | `outputs/insights/insights.{json,md}` |

Chaque execution ecrit un rapport dans `outputs/reports/<run_id>/`.

## Démarrage

```powershell
# 1. Environnement
.\.venv-adsp\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Clés LLM
Copy-Item .env.example .env
# renseigner GOOGLE_API_KEY, GROQ_API_KEY

# 3. Vérification des providers
python scripts/check_llm.py

# 4. Pipeline complet (collector -> analyst)
python main.py run

# Etapes ciblees
python main.py steps
python main.py run --only quality
python main.py run --from etl
python main.py run --to semantic --no-llm

# 5. Tests
python -m pytest tests -q
```

## Dashboard

```powershell
streamlit run dashboard/app.py
```

Le dashboard est en lecture seule et lit les artefacts du dernier run :

- `Vue d'ensemble` : cartes KPI, qualité et synthèse ;
- `Tendances` : séries par KPI et par dimension ;
- `Pays` : classements, comparaison et carte ISO3 ;
- `Qualité et insights` : anomalies, plan de remédiation, constats et recommandations.

## Données et périmètre

- Findex : vagues 2011, 2014, 2017, 2021, 2022 (partielle), 2024 ; les agrégats
  regionaux sont exclus des KPI, les lignes 2022 sont signalees comme partielles.
- FAS : séries `FA26N.PHTADLT_NUM`, `FA18N.PHTADLT_NUM`, `FA29N_COMBANK.PTADLT_NUM`,
  `FA21N_COMBANK.PTADLT_NUM`, `LOANACCN_COMBANK.PTADLT_NUM`,
  `FA30N_COMBANK.PTADLT_NUM` ; 2025 exclue car incomplete.
- WDI : PIB par habitant et croissance, lignes sans code ISO3 ignorees.
- Codes non ISO3 normalises : `KOS -> XKX`, `WBG -> PSE` ; agregats `EAP`, `WLD`,
  etc. conserves dans `country_dim` mais exclus des KPI.

## Choix techniques

- **LangGraph** : graphe d'états explicite, reprise par checkpoint, traçabilité ;
  repli sequentiel si l'import LangGraph est indisponible.
- **LLM par agent** : routage primaire/fallback, température 0, sorties JSON
  validées, cache disque, plafond d'appels.
- **Calculs déterministes** : pandas / DuckDB pour toutes les statistiques et
  agrégats ; le LLM interprète et rédige, il ne calcule pas les chiffres.
- **Dashboard** : Streamlit + Plotly.

## Livrables attendus

Code + architecture, pipeline automatisé, documentation des sources,
Data Quality Report, catalogue KPI, dashboard interactif, rapport d'insights,
rapport d'évaluation/XAI, démonstration.
