# Semantic & KPI interface

> **Update 2026-10-30.** `publication_status` below is `not_evaluated` for
> on-demand requests only; the pipeline's `auditor` step evaluates every
> `kpi_values` row (`approved`, `approved_with_review_note`, `blocked`).
>
> **Update 2026-10-29.** The agent is now also registered as the pipeline step
> `semantic_kpi` (after `etl`): without a `semantic_kpi_request` it computes the
> whole catalog for `kpi.focus` / `kpi.peers` into table `kpi_values`. With a
> request it behaves exactly as described below.

`SemanticKpiAgent` is a `BaseAgent` available directly or through an opt-in
semantic orchestration route. It remains absent from the normal data-processing
registry and does not invoke the Collector, BI Analyst, or an LLM.
All KPI arithmetic and DuckDB access remain in the existing deterministic tools.

```python
from biflow.agents import SemanticKpiAgent
from biflow.tools.semantic_kpi import (
    ListKpisRequest, DescribeKpiRequest, CalculateKpiRequest,
)

agent = SemanticKpiAgent()
catalog = agent.list_kpis(ListKpisRequest())
definition = agent.describe_kpi(DescribeKpiRequest(kpi_id="saving_rate"))
response = agent.calculate_kpi(CalculateKpiRequest(
    iso3="TUN", year=2024, kpi_id="account_ownership",
))
result = response.result  # unchanged KpiResult, including nested dependencies
payload = response.model_dump(mode="json")
```

Discovery needs only the local catalog. Calculation uses the existing configured
processed warehouse and quality-report paths; constructors also accept explicit
`warehouse_path`, `catalog_path`, `lineage_path`, and `quality_report_path`.
No directories or datasets are created by direct tool requests.

For use without an agent, construct `SemanticKpiTools(warehouse_path=...)` from
`biflow.tools.semantic_kpi`. Its methods accept the same typed contracts.
`agent.get_tools()` or `tools.as_tools()` returns six LangChain `StructuredTool`
objects: `list_kpis`, `describe_kpi`, `calculate_kpi`, `latest_available`,
`compare_countries`, and `compare_years`. Calling their `invoke()`
methods executes the deterministic functions directly; it does not call an LLM.

```python
tools = {tool.name: tool for tool in agent.get_tools()}
payload = tools["calculate_kpi"].invoke({
    "kpi_id": "unbanked_share", "iso3": "TUN", "year": 2024,
})
```

Shared-state callers can use the existing report lifecycle:

```python
report = agent.run({"semantic_kpi_request": {
    "action": "calculate", "kpi_id": "unbanked_share",
    "iso3": "TUN", "year": 2024,
}})
payload = report["outputs"]["semantic_kpi_response"]
```

The `action` discriminator is required in shared-state requests (`list`,
`describe`, `calculate`, `latest_available`, `compare_countries`, or `compare_years`). Typed request objects supply their action defaults.
`REQUEST_ADAPTER` and `RESPONSE_ADAPTER` validate the request/response unions.
`run()` writes the standard `outputs/reports/<run_id>/semantic_kpi.json` report;
`execute()`, direct methods and callable tools do not write reports.

Unknown KPIs and invalid parameters raise `ValueError`/Pydantic `ValidationError`
on direct calls. `run()` records them as standard failed agent reports. Missing
observations produce successful responses with a null value and `unavailable`
availability status. They are never replaced with zero.

Calculation availability is separate from review. Results preserve units,
provisional definitions, source lineage, exact input warnings, source-wide
notices, review reasons, and dependency results. Publication status remains
`not_evaluated`, including when the value is available. Missing provenance or
unresolved warnings are not waived by the interface.

## Latest available mode

Use `agent.latest_available(LatestAvailableKpiRequest(iso3="TUN",
kpi_id="unbanked_share"))`, importing the request from
`biflow.tools.semantic_kpi`. The callable tool accepts `{"iso3": "TUN",
"kpi_id": "unbanked_share"}`. Shared-state requests use `action: latest_available`.
This mode accepts no year; explicit-year `calculate` requests still require one
and never fall back to other years.

The calculator checks catalog years newest first using the existing source,
subgroup, unit, uniqueness and numeric validation. The selected `result` carries
the actual observation year; derived dependencies use that same year. All
skipped observations are returned separately with their original reasons and
warnings. If no valid observation exists, `result` and `observation_year` are
null, with status `unavailable` and reason `no_available_observation`; no current
year is fabricated. Diagnostic/provenance review flags do not make a numerically
valid observation disappear or grant approval. Publication remains unevaluated.

## Explicit comparisons

```python
from biflow.tools.semantic_kpi import CompareCountriesRequest, CompareYearsRequest

countries = agent.compare_countries(CompareCountriesRequest(
    kpi_id="account_ownership", left_iso3="TUN", right_iso3="MAR", year=2024,
))
years = agent.compare_years(CompareYearsRequest(
    kpi_id="account_ownership", iso3="TUN", left_year=2021, right_year=2024,
))
```

The callable tools accept the same fields, without requiring `action`.
Shared-state requests require the matching action discriminator. Countries are
compared at one explicit year; year comparisons retain both explicitly requested
years for one country. Neither mode calls `latest_available` or imputes data.

`difference` is the signed absolute change **right minus left**. Percentage KPI
values are already percentages, so differences use `percentage_points`, without
another factor of 100. Branch density retains `per_100k_adults`. This is not a
relative percentage change or growth rate. Negative changes and observed zeros
are valid results. Reversing operands reverses the sign.

Both complete `KpiResult` operands are retained as `left` and `right`, including
definitions, actual/requested years, units, lineage and same-year derived inputs.
If either input is unavailable or invalid, `comparison_status` is `incomplete`
and `difference` is null; the available operand is preserved. Incompatible
metadata or a detected warehouse content change also makes it incomplete.
Comparison warnings and review reasons combine both inputs; provisional
definitions and unresolved anomalies remain review requirements. A `complete`
comparison means the difference was calculable, not approved for publication.
`publication_status` remains `not_evaluated` for both operands and the comparison.

## Opt-in orchestration

```python
from biflow.graph import run_pipeline
from biflow.semantic_graph import run_semantic_request

state = run_pipeline(semantic_kpi_request={
    "action": "latest_available", "kpi_id": "account_ownership", "iso3": "TUN",
})
# Equivalent standalone entry point, also accepting explicit provenance paths:
state = run_semantic_request({"action": "list"})
response = state.get("semantic_kpi_response")
```

Semantic requests execute only `START -> semantic_kpi -> END`, or an equivalent
sequential fallback when LangGraph is unavailable. Accepted envelopes invoke
`SemanticKpiAgent.run(state)` exactly once; invalid envelopes fail validation
before invocation. There are no automatic retries or data-processing fallbacks.
`only`, `start`, and `stop` cannot be combined with `semantic_kpi_request`.
Omitting the semantic keyword preserves the normal pipeline; explicitly passing
null is an invalid semantic request and cannot start collection.

`run_semantic_request` supports `cfg`, `run_id`, `objective`, `warehouse_path`,
`lineage_path`, `quality_report_path`, and `catalog_path`. Defaults use configured
`paths.processed/warehouse.duckdb`, adjacent `lineage.json`, and
`paths.quality/quality_report.json`. No warehouse is needed for list/describe.
Missing warehouses for calculations return `status: failed` with an explicit
error. Invalid requests and runtime errors also return failed states; unavailable
observations and incomplete comparisons remain successful executions with their
original result statuses. Stage-selection conflicts raise `ValueError` before
any execution.

The route writes `semantic_kpi.json` and `run.json` under the configured reports
directory and query run ID. Automatic semantic IDs include microseconds; use a
fresh ID when supplying one to avoid replacing an earlier query report. The
warehouse provenance run ID is retained separately in the result. Neither the
Quality Gate nor publication-review requirements are re-evaluated or waived.
There is no new CLI command or natural-language intent routing in this change.
