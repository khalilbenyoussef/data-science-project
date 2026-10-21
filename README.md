# BIFlow — Automatisation d'un pipeline BI multi-agents

Pipeline Business Intelligence automatique : **données brutes → profilage →
qualité → ETL → KPI → analyse → dashboard → explications XAI**, orchestré par
un graphe LangGraph et des agents LLM (Gemini, Groq, Claude).

Domaine : **Économie & Finance / inclusion financière**.

Sources de données :

| Source | Rôle | Fichier |
|---|---|---|
| World Bank **Global Findex** | demande / usage des services financiers | `data/raw/findex.csv` |
| IMF **Financial Access Survey (FAS)** | offre (agences, ATM, dépôts, crédits) | `data/raw/fas.csv` |
| World Bank **WDI** (PIB) | contexte macroéconomique | `data/raw/gdp.csv` |

## État d'avancement

- [x] **P0 — Socle** : configuration, package `biflow`, couche LLM multi-provider,
      vérification des clés, documentation.
- [ ] **P1 — Données** : collector, profiler, quality gate, ETL (nœuds LangGraph).
- [ ] **P2 — Semantic / KPI** : catalogue KPI + calcul DuckDB.
- [ ] **P3 — BI Analyst** : tendances, anomalies, insights, recommandations.
- [ ] **P4 — Dashboard** : Streamlit + Plotly.
- [ ] **P5 — Auditor / XAI** : lineage, explications, évaluation.
- [ ] **P6 — Livrables** : docs, tests, démo.

## Architecture cible

```
main.py / scripts/check_llm.py
src/biflow/
  config.py        configuration YAML + chemins
  llm.py           providers, fallback, cache, compteur de tokens
  state.py         etat partage du pipeline          (P1)
  graph.py         graphe LangGraph                  (P1)
  agents/          orchestrator, collector, profiler, quality,
                   etl, semantic, analyst, dashboard, xai
  tools/           outils deterministes (pandas, DuckDB, Plotly)
  utils/           io, logger, lineage
config/config.yaml     chemins, LLM, sources, seuils
config/kpis.yaml       catalogue KPI                  (P2)
dashboard/app.py       dashboard Streamlit            (P4)
data/                  raw, staging, processed, profiles, quality, reports
outputs/               logs, cache LLM, artefacts
docs/                  LLM_SETUP, ARCHITECTURE, DATA_QUALITY, KPI_CATALOG, XAI
```

## Démarrage

```powershell
# 1. Environnement
.\.venv-adsp\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Clés LLM (voir docs/LLM_SETUP.md)
Copy-Item .env.example .env
# renseigner GOOGLE_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY

# 3. Vérification des providers
python scripts/check_llm.py

# 4. (P1) Pipeline complet
python main.py run
```

## Choix techniques

- **LangGraph** : graphe d'états explicite, reprise par checkpoint, traçabilité.
- **LLM par agent** : routage primaire/fallback, température 0, sorties JSON
  validées, cache disque, plafond d'appels.
- **Calculs déterministes** : pandas / DuckDB pour toutes les statistiques et
  agrégats ; le LLM interprète et rédige, il ne calcule pas les chiffres.
- **Dashboard** : Streamlit + Plotly.

## Livrables attendus

Code + architecture, pipeline automatisé, documentation des sources,
Data Quality Report, catalogue KPI, dashboard interactif, rapport d'insights,
rapport d'évaluation/XAI, démonstration.
