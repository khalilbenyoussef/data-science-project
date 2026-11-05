import type { Chart, InfoBlock, Page, Spec } from "./types";
import { ChartView } from "./charts";
import { PAGE_COPY, plainText } from "./copy";
import { AgentsTimeline } from "./agents";
import { PdfDownload } from "./pdf";
import { Recommendations } from "./recommendations";
import { UserComparisons } from "./comparisons";
import { prettyDate } from "./format";
import {
  AskInline, ChangesPanel, Insights, MetricStrip, MetricsGrid, NoticeList,
  PipelineView, ReferenceCards, Simulator, XaiPanel,
} from "./ui";

function knownChart(page: Page, id: string): Chart | undefined {
  return page.charts.find((chart) => chart.id === id);
}

function ChartById({ page, id, wide = false }: { page: Page; id: string; wide?: boolean }) {
  const chart = knownChart(page, id);
  if (!chart) return null;
  return (
    <div className={wide ? "chart-slot wide" : "chart-slot"}>
      <ChartView chart={chart} />
    </div>
  );
}

function ExtraCharts({ page, exclude }: { page: Page; exclude: string[] }) {
  const extras = page.charts.filter((chart) => !exclude.includes(chart.id));
  if (extras.length === 0) return null;
  return (
    <div className="charts-grid">
      {extras.map((chart) => (
        <div key={chart.id} className="chart-slot">
          <ChartView chart={chart} />
        </div>
      ))}
    </div>
  );
}

function Block({ block, onAsk }: { block: InfoBlock; onAsk: (question: string) => void }) {
  switch (block.kind) {
    case "metric_strip":
      return <MetricStrip block={block} />;
    case "reference_cards":
      return <ReferenceCards block={block} />;
    case "simulator":
      return <Simulator block={block} />;
    case "ask":
      return <AskInline block={block} onAsk={onAsk} />;
    case "pipeline":
      return <PipelineView block={block} />;
    default:
      return null;
  }
}

export function PageView({
  page, spec, onAsk,
}: {
  page: Page;
  spec: Spec;
  onAsk: (question: string) => void;
}) {
  if (!page.available) {
    return (
      <div className="page">
        <PageHead page={page} spec={spec} />
        <section className="panel empty-panel">
          <h3>Page non disponible pour cette sélection</h3>
          <p className="muted">
            {page.unavailable_reason
              ? plainText(page.unavailable_reason)
              : "Les données de cette page ne sont pas disponibles pour ce pays et cette année."}
          </p>
        </section>
      </div>
    );
  }

  const blockById = (id: string) => page.blocks.find((block) => block.id === id);

  return (
    <div className="page">
      <PageHead page={page} spec={spec} />
      <MetricsGrid metrics={page.metrics} />

      {page.id === "overview" && (
        <>
          <div className="charts-grid">
            <ChartById page={page} id="account_ownership_history" wide />
            <ChartById page={page} id="account_ownership_peers" wide />
          </div>
          <ExtraCharts page={page} exclude={["account_ownership_history", "account_ownership_peers"]} />
          <Insights items={page.insights} />
          <ChangesPanel changes={page.changes} />
          {blockById("macro_context") && <Block block={blockById("macro_context")!} onAsk={onAsk} />}
          <UserComparisons iso3={spec.country.iso3} year={spec.year} />
          <Recommendations iso3={spec.country.iso3} year={spec.year} />
        </>
      )}

      {page.id === "inclusion" && (
        <>
          <div className="charts-grid">
            <ChartById page={page} id="inclusion_funnel" wide />
            <ChartById page={page} id="account_ownership_groups" wide />
            <ChartById page={page} id="formal_vs_any" />
            <ChartById page={page} id="gap_change" />
          </div>
          <ExtraCharts
            page={page}
            exclude={["inclusion_funnel", "formal_vs_any", "account_ownership_groups", "gap_change"]}
          />
          <Insights items={page.insights} />
        </>
      )}

      {page.id === "access" && (
        <>
          <div className="charts-grid">
            <ChartById page={page} id="physical_network" wide />
            <ChartById page={page} id="supply_demand_index" wide />
            <ChartById page={page} id="atm_peers" wide />
          </div>
          <ExtraCharts page={page} exclude={["physical_network", "supply_demand_index", "atm_peers"]} />
          <Insights items={page.insights} />
        </>
      )}

      {page.id === "exclusion" && (
        <>
          <div className="charts-grid">
            <ChartById page={page} id="barriers_heatmap" wide />
            <ChartById page={page} id="urban_rural" wide />
          </div>
          <ExtraCharts page={page} exclude={["barriers_heatmap", "urban_rural"]} />
          {page.xai && <XaiPanel card={page.xai} />}
          {blockById("exclusion_context") && (
            <Block block={blockById("exclusion_context")!} onAsk={onAsk} />
          )}
          <Insights items={page.insights} />
          {blockById("ask_finova") && <Block block={blockById("ask_finova")!} onAsk={onAsk} />}
        </>
      )}

      {page.id === "poverty" && (
        <>
          <ChartById page={page} id="smig_trajectory" wide />
          <ExtraCharts page={page} exclude={["smig_trajectory"]} />
          {blockById("poverty_context") && <Block block={blockById("poverty_context")!} onAsk={onAsk} />}
          {blockById("fee_simulator") && <Block block={blockById("fee_simulator")!} onAsk={onAsk} />}
          {blockById("income_context") && <Block block={blockById("income_context")!} onAsk={onAsk} />}
          <Insights items={page.insights} />
        </>
      )}

      {page.id === "pipeline" && (
        <>
          <AgentsTimeline />
          {page.blocks.map((block) => (
            <Block key={block.id} block={block} onAsk={onAsk} />
          ))}
          <ExtraCharts page={page} exclude={[]} />
          <Insights items={page.insights} />
        </>
      )}

      <NoticeList notices={page.notices} />
    </div>
  );
}

function PageHead({ page, spec }: { page: Page; spec: Spec }) {
  const copy = PAGE_COPY[page.id];
  const subtitle = copy?.subtitle ?? plainText(page.subtitle);
  return (
    <header className="page-head">
      <div>
        <span className="eyebrow">
          {spec.country.name} · {spec.year}
        </span>
        <h2>{copy?.title ?? plainText(page.title)}</h2>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      <div className="page-head-badges">
        <span className={`status ${page.available ? "status-available" : "status-warning"}`}>
          {page.available ? "Données réelles" : "Indisponible"}
        </span>
        <span className="muted small">Mise à jour du {prettyDate(spec.generated_at)}</span>
        {page.id === "overview" && (
          <PdfDownload
            href={`/api/reports/insights.pdf?iso3=${encodeURIComponent(spec.country.iso3)}&year=${spec.year}`}
            title={`Constats et pistes de recommandation — ${spec.country.name}, ${spec.year}`}
          />
        )}
      </div>
    </header>
  );
}
