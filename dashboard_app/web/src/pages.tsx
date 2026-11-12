import type { Chart, InfoBlock, Page, Spec } from "./types";
import { ChartView } from "./charts";
import { PAGE_COPY, plainText } from "./copy";
import { AgentsTimeline } from "./agents";
import { InsightsPdf } from "./pdf";
import { Recommendations } from "./recommendations";
import { UserComparisons } from "./comparisons";
import { prettyDate } from "./format";
import { t, tr } from "./i18n";
import {
  AskInline, ChangesPanel, Insights, MetricStrip, MetricsGrid, NoticeList,
  PipelineView, ReferenceCards, XaiPanel,
} from "./ui";

function knownChart(page: Page, id: string): Chart | undefined {
  return page.charts.find((chart) => chart.id === id);
}

function ChartById({
  page, id, onAsk,
}: {
  page: Page;
  id: string;
  onAsk?: (question: string) => void;
}) {
  const chart = knownChart(page, id);
  if (!chart) return null;
  return (
    <div className="chart-slot">
      <ChartView chart={chart} insights={page.insights} xai={page.xai} onAsk={onAsk} />
    </div>
  );
}

function ExtraCharts({
  page, exclude, onAsk,
}: {
  page: Page;
  exclude: string[];
  onAsk?: (question: string) => void;
}) {
  const extras = page.charts.filter((chart) => !exclude.includes(chart.id));
  if (extras.length === 0) return null;
  return (
    <div className="charts-grid">
      {extras.map((chart) => (
        <div key={chart.id} className="chart-slot">
          <ChartView chart={chart} insights={page.insights} xai={page.xai} onAsk={onAsk} />
        </div>
      ))}
    </div>
  );
}

function Block({ block, onAsk }: { block: InfoBlock; onAsk: (question: string) => void }) {
  switch (block.kind) {
    case "metric_strip":
      return <MetricStrip block={block} onAsk={onAsk} />;
    case "reference_cards":
      return <ReferenceCards block={block} onAsk={onAsk} />;
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
          <h3>{t("Page non disponible pour cette sélection")}</h3>
          <p className="muted">
            {page.unavailable_reason
              ? plainText(page.unavailable_reason)
              : t("Les données de cette page ne sont pas disponibles pour ce pays et cette année.")}
          </p>
        </section>
      </div>
    );
  }

  const blockById = (id: string) => page.blocks.find((block) => block.id === id);

  return (
    <div className="page">
      <PageHead page={page} spec={spec} />
      <MetricsGrid
        metrics={page.metrics}
        insights={page.insights}
        xai={page.xai}
        onAsk={onAsk}
      />

      {page.id === "overview" && (
        <>
          <div className="charts-grid">
            <ChartById page={page} id="account_ownership_history" onAsk={onAsk} />
            <ChartById page={page} id="account_ownership_peers" onAsk={onAsk} />
          </div>
          <ExtraCharts
            page={page}
            exclude={["account_ownership_history", "account_ownership_peers"]}
            onAsk={onAsk}
          />
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
            <ChartById page={page} id="inclusion_funnel" onAsk={onAsk} />
            <ChartById page={page} id="account_ownership_groups" onAsk={onAsk} />
            <ChartById page={page} id="formal_vs_any" onAsk={onAsk} />
            <ChartById page={page} id="gap_change" onAsk={onAsk} />
          </div>
          <ExtraCharts
            page={page}
            exclude={["inclusion_funnel", "formal_vs_any", "account_ownership_groups", "gap_change"]}
            onAsk={onAsk}
          />
          <Insights items={page.insights} />
        </>
      )}

      {page.id === "access" && (
        <>
          <div className="charts-grid">
            <ChartById page={page} id="physical_network" onAsk={onAsk} />
            <ChartById page={page} id="atm_peers" onAsk={onAsk} />
            <ChartById page={page} id="supply_demand_index" onAsk={onAsk} />
          </div>
          <ExtraCharts
            page={page}
            exclude={["physical_network", "supply_demand_index", "atm_peers"]}
            onAsk={onAsk}
          />
          <Insights items={page.insights} />
        </>
      )}

      {page.id === "exclusion" && (
        <>
          <div className="charts-grid align-start exclusion-grid">
            <ChartById page={page} id="barriers_heatmap" onAsk={onAsk} />
            <div className="chart-stack">
              <ChartById page={page} id="urban_rural" onAsk={onAsk} />
              {blockById("ask_finova") && (
                <Block block={blockById("ask_finova")!} onAsk={onAsk} />
              )}
            </div>
          </div>
          <ExtraCharts page={page} exclude={["barriers_heatmap", "urban_rural"]} onAsk={onAsk} />
          {page.xai && <XaiPanel card={page.xai} />}
          {blockById("exclusion_context") && (
            <Block block={blockById("exclusion_context")!} onAsk={onAsk} />
          )}
          <Insights items={page.insights} />
        </>
      )}

      {page.id === "pipeline" && (
        <>
          <AgentsTimeline />
          {page.blocks.map((block) => (
            <Block key={block.id} block={block} onAsk={onAsk} />
          ))}
          <ExtraCharts page={page} exclude={[]} onAsk={onAsk} />
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
          {tr(spec.country.name)} · {spec.year}
        </span>
        <h2>{copy?.title ?? plainText(page.title)}</h2>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      <div className="page-head-badges">
        <span className="muted small">
          {t("Mise à jour du {date}", { date: prettyDate(spec.generated_at) })}
        </span>
        {page.id === "overview" && (
          <InsightsPdf
            iso3={spec.country.iso3}
            year={spec.year}
            title={t("Constats et pistes de recommandation — {country}, {year}", {
              country: tr(spec.country.name),
              year: spec.year,
            })}
          />
        )}
      </div>
    </header>
  );
}
