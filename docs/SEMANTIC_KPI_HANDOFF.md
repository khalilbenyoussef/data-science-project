# Semantic & KPI Agent handoff

> **Update 2026-10-29 (catalog 1.2.0).** Several statements below are superseded:
> `SemanticKpiAgent` is now also the pipeline step `semantic_kpi` after `etl`
> (writes table `kpi_values`; the separate `run_semantic_request()` route is
> unchanged); failed agents are retried once by the orchestrator (never a
> quality-gate FAIL); `quality_report.json` records `run_id` and source hashes,
> so matching runs no longer get `quality_provenance_unverified`; the catalog
> adds `formal_saving_rate`, `formal_borrowing_rate`, `gender_gap`, `income_gap`
> and `age_gap`; `saving_rate` / `borrowing_rate` are now **verified** (glossary
> rows 121 and 3); lineage records a digest of the `fact`, `country_year` and
> `country_dim` contents that KPI provenance checks; `.gitignore` now tracks `docs/` except
> `docs/sources/`. See `README.md`.

Review date: 2026-10-22. Catalog: `config/kpi_catalog.v1.yaml`, version 1.0.0.
Readiness: ready for downstream development and review-only display; publication
approval is not implemented. No production-code defect confirmed during review.

## Verified integration

`src/biflow/graph.py` preserves the original `AGENT_CLASSES`, `STEP_ORDER`,
`_gate()`, `_node()`, `build_graph()` and `run_steps()` implementations against
Git HEAD. Normal execution remains Collector -> Profiler -> Quality -> ETL;
the existing mandatory-source gate still blocks ETL. Production ETL was not run.

`src/biflow/semantic_graph.py:run_semantic_request()` uses a separate one-node
LangGraph route or sequential fallback. Accepted requests call
`SemanticKpiAgent.run(state)` once. Invalid envelopes fail before invocation.
Runtime failures never trigger collection, data refresh, or automatic retries.
The route disables LLM use and all KPI DuckDB connections are read-only.

## Callable interface and schemas

Preferred integration entry point:

```python
from biflow.graph import run_pipeline
from biflow.tools.semantic_kpi import REQUEST_ADAPTER, RESPONSE_ADAPTER

request = {"action": "calculate", "kpi_id": "account_ownership",
           "iso3": "TUN", "year": 2024}
REQUEST_ADAPTER.validate_python(request)
state = run_pipeline(semantic_kpi_request=request)
if state["status"] == "success":
    response = RESPONSE_ADAPTER.validate_python(state["semantic_kpi_response"])
else:
    errors = state["errors"]
```

The standalone `run_semantic_request(request, cfg=..., run_id=...,
warehouse_path=..., lineage_path=..., quality_report_path=..., catalog_path=...)`
allows explicit artifact paths. `SemanticKpiAgent` also exposes typed methods;
`agent.get_tools()` returns six `StructuredTool` objects callable with `.invoke()`.
Direct tools do not write reports. Agent `run()` and orchestration do.

Canonical contracts live in `src/biflow/tools/semantic_kpi.py`. Obtain complete
JSON Schemas through `REQUEST_ADAPTER.json_schema()` and
`RESPONSE_ADAPTER.json_schema()`; do not maintain a separate incompatible schema.

| Request action / callable tool | Additional request fields | Main response fields |
|---|---|---|
| `list` / `list_kpis` | none | `kpis`, `catalog_version`, `catalog_sha256` |
| `describe` / `describe_kpi` | `kpi_id` | complete `definition`, `policies`, `references`, catalog identity |
| `calculate` / `calculate_kpi` | `kpi_id`, `iso3`, integer `year` | `result: KpiResult` |
| `latest_available` | `kpi_id`, `iso3`; no year | nullable `result`, actual `observation_year`, `availability_status`, `reason`, `skipped_observations` |
| `compare_countries` | `kpi_id`, `left_iso3`, `right_iso3`, integer `year` | `left`, `right`, `comparison_status`, nullable `difference`, `difference_unit`, review fields |
| `compare_years` | `kpi_id`, `iso3`, integer `left_year`, integer `right_year` | same comparison shape |

All responses include `action`. Shared-state requests require it; typed requests
and individual callable tools provide defaults. Extra fields, string/bool years,
and aggregate country codes are rejected. ISO3 aliases KOS -> XKX and WBG -> PSE
are retained. Do not combine semantic requests with `only`, `start`, or `stop`.
Explicit null requests fail; omitting the semantic keyword starts the normal
pipeline, so downstream query clients must always supply it.

`KpiResult` retains value/unit, ISO3/year, source and indicator IDs, definition and
verification status, subgroup, input fact key/value/unit, formula, catalog
version/hash, dependencies and nested dependency results, provenance, exact
`quality_warnings`, separate `source_warnings`, `requires_review`, `review_reasons`,
and `publication_status="not_evaluated"`. Provenance contains recorded source
path/hash/row count, observed source hash, source run ID, artifact hashes,
recorded quality-gate result, association status, and evidence issues.

## KPI semantics and downstream responsibilities

| KPI ID | Warehouse indicator | Returned unit | Definition status |
|---|---|---|---|
| `account_ownership` | Findex `account_t_d` | percent | verified |
| `branch_density` | FAS `branch_density` / `FA26N.PHTADLT_NUM` | per_100k_adults | verified_metadata |
| `digital_payment_rate` | Findex `g20_any` | percent | verified |
| `saving_rate` | Findex `save_any_t_d` | percent | provisional |
| `borrowing_rate` | Findex `borrow_any_t_d` | percent | provisional |
| `unbanked_share` | validated account ownership dependency | percent | derived_verified |

BI Analyst: use returned calculations and definitions; preserve input evidence
in analysis. Do not recalculate from wide tables, rescale returned percentages,
equate digital payments with account ownership/remittances, or present saving
and borrowing as verified. Cross-wave comparability and FAS adult-population
conventions still require methodological review.

Dashboard: populate selectors from list/describe and catalog years. Display the
actual selected year, units, definition status, review badge and reasons. Render
missing values as unavailable, never zero. Explicit years never fall back;
latest mode selects a valid catalog-year total-subgroup observation and discloses
skips. For derived KPIs, dependencies stay in the selected year. Latest-per-country
results can have different years: use explicit comparison actions for comparisons.

Comparisons return signed **right minus left**, in percentage points for percent
KPIs or native density units. They are not relative growth rates. An unavailable
or invalid operand yields `incomplete` with null difference; retain both operands.

Execution `status="success"` does not imply data availability or publication
approval. Inspect nested availability/comparison/review fields. Exact input
warnings inherit into derived KPIs and comparisons; source-wide notices are not
evidence that every observation is anomalous. The semantic state's empty
`quality` field is not a new Quality Gate decision: inspect result provenance.

Direct calls raise validation/domain/database errors. Orchestration returns
failed states for validation and agent errors; stage conflicts raise `ValueError`.
Callers must also handle configuration/report-filesystem exceptions. Do not
rebuild the warehouse, substitute years, or approve publication on errors.

## Artifacts, limitations and ownership

Inputs default to `data/processed/warehouse.duckdb`, adjacent `lineage.json`, and
`data/quality/quality_report.json`. Catalog discovery needs no warehouse. Query
reports use configured `paths.reports/<query_run_id>/{semantic_kpi,run}.json`
(pre-agent failures produce only `run.json`). Use unique IDs; query IDs must not
replace the source run ID recorded in provenance. Reports include local paths.

| Owner / teammate | Remaining responsibility |
|---|---|
| Orchestrator owner | Coordinate shared `graph.py`/`state.py` changes; retain separate routing, reducers, error semantics and mandatory-source gate. No natural-language router or semantic CLI exists yet. |
| Quality / ETL owners | Resolve warehouse-content and quality-report run/source-hash binding gaps; retain snapshots. Investigate FAS deposits/loans anomalies without silently changing values. |
| Domain / governance owner | Verify saving/borrowing definitions and historical comparability; provide an auditable anomaly-review and publication-approval workflow. None is implemented here. |
| BI Analyst / Dashboard owners | Consume typed payloads, preserve warnings and actual years, apply review-only display and access policies. There is no HTTP service, batching, rollup or dashboard implementation in this module. |
| Repository / handoff owner | `.gitignore` currently excludes `docs`; explicitly arrange version control/sharing of this handoff and `semantic_kpi.md`. No ignore rules were changed. |

Current real results require review because lineage lacks a recorded warehouse
content digest and the standalone quality report lacks run/source-hash binding.
Observed hashes are returned, but missing historical evidence is not invented.
All publication statuses remain `not_evaluated`; no automated publication is ready.
Latest queries scan catalog years and evidence is re-read/hashed per lookup;
measure latency before production dashboard usage. See [detailed usage](semantic_kpi.md).

## Review evidence

Full suite: **506 passed, zero failures**, in 132.40 seconds; two non-failing
pytest plugin rewrite warnings (`anyio`, `langsmith`). All 12 action/backend
smokes and 10 failure/availability checks passed. Hashes of 77 existing
source/test/config/data files were unchanged; network attempts: zero.
Real read-only checks cover all six actions on both backends, matching responses
and one agent invocation each, plus unknown actions/KPIs, missing warehouse,
unavailable survey years and incomplete comparisons. Independent read-only SQL
matched all six Tunisia 2024 KPI values. A Namibia check confirmed unrelated FAS
anomalies do not become branch-density input warnings. No production-code fix
was required.

| Real query | Observed result |
|---|---|
| Tunisia account ownership, 2024 | 37.844486% |
| Yemen latest unbanked share | 88.096634%, year 2022, same-year dependency |
| Morocco minus Tunisia account ownership, 2024 | +6.541843 percentage points |
| Tunisia account ownership, 2024 minus 2021 | +0.991250 percentage points |

Re-run: `.venv\Scripts\python.exe -B -m pytest -q`. Regression coverage is in
`tests/test_semantic_graph.py`, `test_semantic_kpi.py`, `test_kpi.py`,
`test_kpi_catalog.py`, `test_kpi_latest.py`, `test_kpi_comparisons.py`,
`test_quality.py`, and `test_state.py`. Tests use temporary fixtures; the normal
production processing pipeline is not part of the handoff smoke checks.
