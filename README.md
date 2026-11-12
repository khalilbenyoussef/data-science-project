# FinOVA (BIFlow) — plateforme BI multi-agents auditée pour l'inclusion financière

Pipeline BI automatisé (LangGraph) qui transforme les données officielles Findex, FAS et WDI en 44 KPI audités,
puis les sert dans le tableau de bord FinOVA avec un assistant conversationnel dont chaque chiffre est vérifié.

**Équipe** : Najeh Ben Rebeh, Mohamed Ali Jabri, Farah Baklouti, Eya Guirat, Khalil Ben Youssef, Mohamed Khalil Kamessi
**ESPRIT** — Advanced Data Science Project 2026

## Sommaire

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Exécution](#exécution)
4. [Résultats attendus](#résultats-attendus)
5. [Structure du projet](#structure-du-projet)
6. [Architecture](#architecture)
7. [Documentation](#documentation)

## Prérequis

- **Git**.
- **Python 3.10** (`requirements.lock` est généré pour Windows / Python 3.10 ; vérifié avec 3.10.11).
- **Node.js >= 18** pour construire le front FinOVA (vérifié avec Node 24).
- **Accès réseau** au premier lancement : le PIB (WDI) est téléchargé depuis l'API World Bank.
- Windows 11 / PowerShell pour `start.ps1` et `stop.ps1` (sous Linux/macOS, uvicorn est lancé directement).

## Installation

### Windows (PowerShell)

```powershell
git clone --branch main https://github.com/khalilbenyoussef/data-science-project.git data-science-project
cd data-science-project

py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip      # le pip 23 livré avec Python 3.10 refuse le verrou
.\.venv\Scripts\python -m pip install --require-hashes -r requirements.lock

Copy-Item .env.example .env                              # clés optionnelles, voir ci-dessous
```

### Linux / macOS (bash)

`requirements.lock` est propre à Windows : installer `requirements.txt`, ou régénérer le verrou
(`python -m uv pip compile requirements.txt --generate-hashes --python-version 3.10 --python-platform <plateforme> -o requirements.lock`).

```bash
git clone --branch main https://github.com/khalilbenyoussef/data-science-project.git data-science-project
cd data-science-project
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

### Fichier `.env` (optionnel)

`GROQ_API_KEY` et/ou `GOOGLE_API_KEY` (clés personnelles, jamais commitées). Sans clé, le pipeline et le
dashboard fonctionnent ; seuls l'assistance LLM du quality gate et Ask FinOVA en mode IA sont désactivés.
Vérification : `python scripts/check_llm.py`. Réglages de connexion et SMTP : voir
[docs/TECHNICAL.md](docs/TECHNICAL.md#authentification-comptes-finova).

### Fichiers de données (absents de Git)

| Fichier | Obligatoire | Emplacement | Téléchargement | SHA-256 (fichiers de l'équipe) |
|---|---|---|---|---|
| `findex.csv` | oui | `data/raw/findex.csv` | [World Bank Global Findex 2025 — Download data](https://www.worldbank.org/en/publication/globalfindex/download-data) (base niveau pays) | `35f3fa934adf940c3ec20603b64e8ed81b4315ff550bdb08d61968e38fc0bf66` |
| `fas.csv` | oui | `data/raw/fas.csv` | [IMF Financial Access Survey](https://data.imf.org/Datasets/FAS) (export large, `;`) | `f60b4d1b3de68e15b6b29c286b2954942d6d226c86e1f13c42e372965ac5e9b5` |
| `gdp.csv` | non | `data/raw/gdp.csv` | téléchargé automatiquement par le Collector (API World Bank WDI) | `b746f41a1c591493feca1490d64f937ca00c227e7661b6694779735e79886c17` (2026-11-04) |

Contrôle : `Get-FileHash data\raw\findex.csv` (PowerShell) ou `sha256sum data/raw/*.csv`. Les résultats
attendus ci-dessous supposent ces empreintes ; sans `findex.csv` ou `fas.csv`, `main.py run` s'arrête au Collector.

## Exécution

Commandes Windows depuis la racine du projet (sous Linux/macOS : `.venv/bin/python` et `PYTHONPATH=src`).

1. **Route 1 — pipeline de données** (collector → snapshot → profiler → quality → etl → semantic_kpi → auditor, ~1 min) :
   ```powershell
   .\.venv\Scripts\python main.py run
   ```
   Étapes disponibles : `python main.py steps`.
2. **Route 2 — contrat publié du dashboard** (Tunisie 2024, ~1 min) :
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python -c "from biflow.route2_graph import run_route2; run_route2(use_llm=False)"
   ```
3. **Build du front FinOVA** :
   ```powershell
   cd dashboard_app\web; npm ci; npm run build; cd ..\..
   ```
4. **Créer le premier administrateur** (avant `start.ps1` ; aucune inscription publique, mot de passe demandé en interactif) :
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python -m dashboard_app.auth.cli create-admin --email admin@finova.tn --name "Admin"
   ```
   Autres commandes : `invite`, `reset`, `disable`, `enable`, `list` (`--help`).
5. **Démarrer le serveur** :
   ```powershell
   .\start.ps1        # -NoBrowser, -Port 8001 ; si bloqué : powershell -ExecutionPolicy Bypass -File .\start.ps1
   ```
   Linux/macOS : `PYTHONPATH=src .venv/bin/python -m uvicorn dashboard_app.api.app:app --host 127.0.0.1 --port 8000`.
6. **Ouvrir <http://127.0.0.1:8000>** et se connecter avec le compte administrateur.
7. **Arrêter** : `.\stop.ps1` (n'arrête que le serveur lancé par `start.ps1`).
8. **Tests** (~11 min) :
   ```powershell
   $env:PYTHONPATH = "src"; .\.venv\Scripts\python -m pytest -q
   ```

Évaluations (facultatif) : `python scripts/evaluate_auditor.py` (injection de fautes),
`python scripts/baseline_reference.py` (recalcul naïf de référence), `python scripts/build_deliverables.py`
(régénère `docs/deliverables/` et `docs/DEMO.md`).

## Résultats attendus

Avec les fichiers de données ci-dessus, un run reproductible doit donner :

| Contrôle | Valeur attendue | Où le lire |
|---|---|---|
| Statut du run | `success` | sortie de `main.py run`, `outputs/reports/<run_id>/run.json` |
| Quality gate | **PASS**, score **0.936** | `data/quality/quality_report.json` |
| KPI calculés | **44 KPI**, **1 620 valeurs** (catalogue 1.8.0) | table `kpi_values` |
| Publication | **1 509** approuvées / **111** avec note de revue / **0** bloquée | `data/audit/audit_report.json` |
| Verdict d'audit | `pass_with_warnings` : **17** pass / **2** warn / **0** fail | `data/audit/audit_report.json` |
| Injection de fautes | **9/9** fautes détectées | `data/audit/evaluation.json` |
| Référence naïve | **132/132** valeurs identiques (tolérance 1e-9) | `outputs/evaluation/baseline.json` |
| Tests | **1 395** tests passés | `python -m pytest -q` |

## Structure du projet

```
main.py                   CLI : run, steps, analyze, dashboard, add-source, remove-source, explain
start.ps1 / stop.ps1      démarrage / arrêt du serveur FinOVA (Windows)
src/biflow/agents/        agents : collector, snapshot, profiler, quality, etl, semantic_kpi, auditor, bi_analyst, analyst, dashboard, ask, mapper
src/biflow/tools/         outils déterministes : KPI, snapshots, contrôles d'audit, explications, insights, recommandations, sources utilisateur
src/biflow/graph.py       graphe LangGraph Route 1 (+ route2_graph.py, analysis_graph.py, semantic_graph.py, state.py, llm.py, config.py)
config/                   config.yaml, catalogue KPI kpi_catalog.v1.yaml (1.8.0), recommendations.yaml, questions d'évaluation
dashboard_app/api/        API FastAPI (spec, Ask FinOVA, sources, audit, rapports PDF)
dashboard_app/auth/       comptes, sessions, invitations, CLI d'administration
dashboard_app/web/        front React / Vite / TypeScript
scripts/                  check_llm, evaluate_auditor, evaluate_agents, baseline_reference, build_deliverables
tests/                    suite pytest (1 395 tests)
docs/                     documentation technique, démo, livrables générés, exemples
legacy/dashboard/         ancien front React/ECharts, retiré du service
data/, outputs/           données, warehouse, audits, rapports de run — générés localement, non versionnés
```

## Architecture

- **Route 1 — Données** : six agents orchestrés par **LangGraph** (`src/biflow/graph.py`) : collecte, snapshot versionné, profilage, quality gate, ETL vers DuckDB, calcul déterministe des KPI, suivis de l'Auditor. Aucun chiffre n'est calculé par un LLM.
- **BI Auditor** : agent indépendant qui recalcule chaque valeur depuis les faits, contrôle unités, entités, traçabilité et catalogue, puis décide la publication ligne par ligne (`approved`, `approved_with_review_note`, `blocked`).
- **Route 2 — Analyse** : BI Analyst et Dashboard lisent le warehouse en lecture seule via les contrats KPI et produisent la spec FinOVA (constats rattachés à des preuves).
- **Ask FinOVA** : assistant conversationnel ; les chiffres ne viennent que d'outils sur les valeurs auditées et tout nombre non retrouvé est rejeté.
- **Orchestrateur** : retry borné, arrêt sur gate FAIL, rapport `run.json` par exécution ; repli séquentiel si LangGraph est indisponible.

Détails (pipeline S06→S12, contrôles A1–F1, sources utilisateur, mode banquier, endpoints) : [docs/TECHNICAL.md](docs/TECHNICAL.md).

## Documentation

- [docs/TECHNICAL.md](docs/TECHNICAL.md) — documentation technique complète.
- [docs/DEMO.md](docs/DEMO.md) — script de démonstration (10 minutes).
- [AUDIT_REPORT.md](AUDIT_REPORT.md) — rapport d'audit du projet.
- [docs/deliverables/](docs/deliverables/) — livrables générés (architecture, qualité, catalogue KPI, évaluation, insights).
