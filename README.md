# FinOVA (BIFlow) — an audited multi-agent BI platform for financial inclusion

An automated BI pipeline (LangGraph) that turns official Findex, FAS and WDI data into 44 audited KPIs,
then serves them in the FinOVA dashboard with a conversational assistant whose every number is verified.

**Team**: Najeh Ben Rebeh, Mohamed Ali Jabri, Farah Baklouti, Eya Guirat, Khalil Ben Youssef, Mohamed Khalil Kamessi
**ESPRIT** — Advanced Data Science Project 2026

## Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Running](#running)
4. [Expected results](#expected-results)
5. [Project structure](#project-structure)
6. [Architecture](#architecture)
7. [Documentation](#documentation)

## Prerequisites

- **Git**.
- **Python 3.10** (`requirements.lock` is generated for Windows / Python 3.10; verified with 3.10.11).
- **Node.js >= 18** to build the FinOVA front end (verified with Node 24).
- **Network access** on the first run: GDP (WDI) is downloaded from the World Bank API.
- Windows 11 / PowerShell for `start.ps1` and `stop.ps1` (on Linux/macOS, uvicorn is started directly).

## Installation

### Windows (PowerShell)

```powershell
git clone --branch main https://github.com/khalilbenyoussef/data-science-project.git data-science-project
cd data-science-project

py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip      # the pip 23 shipped with Python 3.10 rejects the lock file
.\.venv\Scripts\python -m pip install --require-hashes -r requirements.lock

Copy-Item .env.example .env                              # optional keys, see below
```

### Linux / macOS (bash)

`requirements.lock` is Windows-specific: install `requirements.txt`, or regenerate the lock file
(`python -m uv pip compile requirements.txt --generate-hashes --python-version 3.10 --python-platform <plateforme> -o requirements.lock`, where `<plateforme>` is your platform).

```bash
git clone --branch main https://github.com/khalilbenyoussef/data-science-project.git data-science-project
cd data-science-project
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

### `.env` file (optional)

`GROQ_API_KEY` and/or `GOOGLE_API_KEY` (personal keys, never committed). Without a key, the pipeline and the
dashboard still work; only the LLM assistance in the quality gate and Ask FinOVA's AI mode are disabled.
Check: `python scripts/check_llm.py`. Login and SMTP settings: see
[docs/TECHNICAL.md](docs/TECHNICAL.md#authentification-comptes-finova) (in French).

### Data files (not in Git)

| File | Required | Location | Download | SHA-256 (team files) |
|---|---|---|---|---|
| `findex.csv` | yes | `data/raw/findex.csv` | [World Bank Global Findex 2025 — Download data](https://www.worldbank.org/en/publication/globalfindex/download-data) (country-level database) | `35f3fa934adf940c3ec20603b64e8ed81b4315ff550bdb08d61968e38fc0bf66` |
| `fas.csv` | yes | `data/raw/fas.csv` | [IMF Financial Access Survey](https://data.imf.org/Datasets/FAS) (wide export, `;`) | `f60b4d1b3de68e15b6b29c286b2954942d6d226c86e1f13c42e372965ac5e9b5` |
| `gdp.csv` | no | `data/raw/gdp.csv` | downloaded automatically by the Collector (World Bank WDI API) | `b746f41a1c591493feca1490d64f937ca00c227e7661b6694779735e79886c17` (2026-11-04) |

Check: `Get-FileHash data\raw\findex.csv` (PowerShell) or `sha256sum data/raw/*.csv`. The expected results
below assume these hashes; without `findex.csv` or `fas.csv`, `main.py run` stops at the Collector.

## Running

Windows commands, run from the project root (on Linux/macOS: `.venv/bin/python` and `PYTHONPATH=src`).

1. **Route 1 — data pipeline** (collector → snapshot → profiler → quality → etl → semantic_kpi → auditor, ~1 min):
   ```powershell
   .\.venv\Scripts\python main.py run
   ```
   Available steps: `python main.py steps`.
2. **Route 2 — published dashboard contract** (Tunisia 2024, ~1 min):
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python -c "from biflow.route2_graph import run_route2; run_route2(use_llm=False)"
   ```
3. **Build the FinOVA front end**:
   ```powershell
   cd dashboard_app\web; npm ci; npm run build; cd ..\..
   ```
4. **Create the first administrator** (before `start.ps1`; there is no public sign-up, and the password is asked interactively):
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python -m dashboard_app.auth.cli create-admin --email admin@finova.tn --name "Admin"
   ```
   Other commands: `invite`, `reset`, `disable`, `enable`, `list` (`--help`).
5. **Start the server**:
   ```powershell
   .\start.ps1        # -NoBrowser, -Port 8001; if blocked: powershell -ExecutionPolicy Bypass -File .\start.ps1
   ```
   Linux/macOS: `PYTHONPATH=src .venv/bin/python -m uvicorn dashboard_app.api.app:app --host 127.0.0.1 --port 8000`.
6. **Open <http://127.0.0.1:8000>** and log in with the administrator account.
7. **Stop**: `.\stop.ps1` (stops only the server started by `start.ps1`).
8. **Tests** (~11 min):
   ```powershell
   $env:PYTHONPATH = "src"; .\.venv\Scripts\python -m pytest -q
   ```

Evaluations (optional): `python scripts/evaluate_auditor.py` (fault injection),
`python scripts/baseline_reference.py` (naive reference recomputation), `python scripts/build_deliverables.py`
(regenerates `docs/deliverables/` and `docs/DEMO.md`).

## Expected results

With the data files above, a reproducible run must give:

| Check | Expected value | Where to read it |
|---|---|---|
| Run status | `success` | output of `main.py run`, `outputs/reports/<run_id>/run.json` |
| Quality gate | **PASS**, score **0.936** | `data/quality/quality_report.json` |
| Computed KPIs | **44 KPIs**, **1,620 values** (catalogue 1.8.0) | `kpi_values` table |
| Publication | **1,509** approved / **111** with a review note / **0** blocked | `data/audit/audit_report.json` |
| Audit verdict | `pass_with_warnings`: **17** pass / **2** warn / **0** fail | `data/audit/audit_report.json` |
| Fault injection | **9/9** faults detected | `data/audit/evaluation.json` |
| Naive reference | **132/132** identical values (tolerance 1e-9) | `outputs/evaluation/baseline.json` |
| Tests | **1,395** tests passed | `python -m pytest -q` |

## Project structure

```
main.py                   CLI: run, steps, analyze, dashboard, add-source, remove-source, explain
start.ps1 / stop.ps1      start / stop the FinOVA server (Windows)
src/biflow/agents/        agents: collector, snapshot, profiler, quality, etl, semantic_kpi, auditor, bi_analyst, analyst, dashboard, ask, mapper
src/biflow/tools/         deterministic tools: KPIs, snapshots, audit checks, explanations, insights, recommendations, user sources
src/biflow/graph.py       Route 1 LangGraph graph (+ route2_graph.py, analysis_graph.py, semantic_graph.py, state.py, llm.py, config.py)
config/                   config.yaml, KPI catalogue kpi_catalog.v1.yaml (1.8.0), recommendations.yaml, evaluation questions
dashboard_app/api/        FastAPI API (spec, Ask FinOVA, sources, audit, PDF reports)
dashboard_app/auth/       accounts, sessions, invitations, admin CLI
dashboard_app/web/        React / Vite / TypeScript front end
scripts/                  check_llm, evaluate_auditor, evaluate_agents, baseline_reference, build_deliverables
tests/                    pytest suite (1,395 tests)
docs/                     technical documentation, demo, generated deliverables, examples
legacy/dashboard/         former React/ECharts front end, retired from service
data/, outputs/           data, warehouse, audits, run reports — generated locally, not versioned
```

## Architecture

- **Route 1 — Data**: six agents orchestrated by **LangGraph** (`src/biflow/graph.py`): collection, versioned snapshot, profiling, quality gate, ETL into DuckDB, deterministic KPI computation, followed by the Auditor. No number is computed by an LLM.
- **BI Auditor**: an independent agent that recomputes every value from the facts, checks units, entities, traceability and the catalogue, then decides publication row by row (`approved`, `approved_with_review_note`, `blocked`).
- **Route 2 — Analysis**: the BI Analyst and Dashboard agents read the warehouse read-only through the KPI contracts and produce the FinOVA spec (findings linked to evidence).
- **Ask FinOVA**: a conversational assistant; numbers come only from tools over the audited values, and any number that cannot be traced is rejected.
- **Orchestrator**: bounded retries, stop on a gate FAIL, one `run.json` report per run; sequential fallback if LangGraph is unavailable.

Details (S06→S12 pipeline, A1–F1 checks, user sources, banker mode, endpoints): [docs/TECHNICAL.md](docs/TECHNICAL.md) (in French).

## Documentation

- [docs/TECHNICAL.md](docs/TECHNICAL.md) — full technical documentation (in French).
- [docs/DEMO.md](docs/DEMO.md) — demo script (10 minutes).
- [AUDIT_REPORT.md](AUDIT_REPORT.md) — project audit report.
- [docs/deliverables/](docs/deliverables/) — generated deliverables (architecture, quality, KPI catalogue, evaluation, insights).
