import { useLayoutEffect, useRef, useState } from "react";
import type { Bar, Chart, GapPoint, ReferenceLine, Series } from "./types";
import { fmtNumber, fmtPct, fmtSigned, fmtUnit, unitLabel } from "./format";
import {
  CHART_TITLES, HEATMAP_ROW_LABELS, STEP_LABELS, chipLabel, chipNeedsReview, chipTitle, plainText,
} from "./copy";
import { SeeWaveButton } from "./waveNav";

const BASE_W = 760;
const MIN_W = 260;
const PAD = { left: 62, right: 28, top: 26, bottom: 52 };

/* Largeur reelle du graphique (ResizeObserver) : le viewBox suit les pixels affiches,
   donc une unite SVG = un pixel et les tailles de police CSS restent fixes. Sous
   MIN_W, le graphique garde MIN_W pixels et son conteneur defile horizontalement. */
function useChartWidth(): [React.RefObject<HTMLDivElement>, number] {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(BASE_W);
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    const update = () => setWidth(Math.max(MIN_W, Math.round(element.clientWidth)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [box, width];
}

function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function niceMax(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
  const scaled = value / magnitude;
  const step =
    scaled <= 1 ? 1 : scaled <= 1.5 ? 1.5 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5
      : scaled <= 3 ? 3 : scaled <= 4 ? 4 : scaled <= 5 ? 5 : scaled <= 6 ? 6
        : scaled <= 8 ? 8 : 10;
  return step * magnitude;
}

function unitNote(unit: string): string {
  if (unit.startsWith("/ 100 000")) return "nombre pour 100 000 adultes";
  if (unit.startsWith("/ 1 000")) return "nombre pour 1 000 adultes";
  if (unit === "%") return "valeur en %";
  if (unit === "% du PIB") return "en pourcentage du PIB";
  if (unit === "TND/mois") return "en dinars par mois";
  if (unit === "TND/USD") return "en dinars par dollar";
  return unit;
}

function valueLabel(value: number, unit: string | null): string {
  if (unit === "percent") return fmtPct(value);
  if (unit === "index_2017_100") return fmtNumber(value, 0);
  return fmtUnit(value, unit);
}

function ChartShell({ chart, children }: { chart: Chart; children: React.ReactNode }) {
  // les annees de l'evolution des ecarts suivent les vagues lues (jamais une vague posterieure)
  const span = chart.id === "gap_change" ? chart.gap_points[0] : undefined;
  const title = span
    ? `Évolution des écarts entre ${span.from_year} et ${span.to_year}`
    : CHART_TITLES[chart.id] ?? plainText(chart.title);
  return (
    <section className="chart-card">
      <header className="card-head">
        <div>
          <h3>{title}</h3>
          {chart.subtitle && <p className="card-sub">{plainText(chart.subtitle)}</p>}
        </div>
        {chart.chip && (
          <span
            className={`chip chip-${chart.chip.provider}`}
            title={chipTitle(chart.chip)}
          >
            {chipLabel(chart.chip)}
            {chipNeedsReview(chart.chip) ? " · à vérifier" : ""}
          </span>
        )}
      </header>
      {children}
      {chart.notes.length > 0 && (
        <ul className="chart-notes">
          {chart.notes.map(plainText).filter(Boolean).map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {chart.formula && (
        <details className="tech-details formula-details">
          <summary>Formule de calcul</summary>
          <p className="formula mono small">{plainText(chart.formula)}</p>
        </details>
      )}
    </section>
  );
}

function Legend({ series }: { series: Series[] }) {
  if (series.length < 2) return null;
  const colors = ["var(--series)", "var(--accent)", "var(--green)"];
  return (
    <div className="legend">
      {series.map((item, index) => (
        <span key={item.id}>
          <i style={{ background: colors[index % colors.length] }} />
          {plainText(item.label)}
        </span>
      ))}
    </div>
  );
}

function LineChart({ chart }: { chart: Chart }) {
  const [box, W] = useChartWidth();
  // hauteur proportionnelle a la largeur (meme rendu qu'avant), texte de taille fixe
  const H = Math.max(220, Math.round((320 * W) / BASE_W));
  const series = chart.series;
  const refs = chart.reference_lines;
  const years = Array.from(
    new Set(series.flatMap((item) => item.points.map((point) => point.year))),
  ).sort((a, b) => a - b);
  if (years.length === 0) return <p className="empty">Aucune observation.</p>;
  const values = series.flatMap((item) =>
    item.points.filter((point) => point.value !== null).map((point) => point.value as number),
  );
  const refValues = refs.map((ref) => ref.value);
  const all = [...values, ...refValues];
  const rawMax = all.length ? Math.max(...all) : 1;
  const rawMin = all.length ? Math.min(...all) : 0;
  let yMax = chart.unit === "percent" ? Math.max(100, Math.ceil(rawMax / 10) * 10) : niceMax(rawMax * 1.1);
  let yMin = 0;
  if (chart.unit === "index_2017_100") {
    yMin = Math.max(0, Math.floor(rawMin - 5));
    yMax = Math.ceil(rawMax + 5);
  }
  if (yMax <= yMin) yMax = yMin + 1;

  const x0 = PAD.left;
  const x1 = W - PAD.right;
  const y0 = H - PAD.bottom;
  const y1 = PAD.top;
  const xSpan = Math.max(1, years[years.length - 1] - years[0]);
  const sx = (year: number) =>
    years.length === 1 ? (x0 + x1) / 2 : x0 + ((year - years[0]) / xSpan) * (x1 - x0);
  const sy = (value: number) => y0 - ((value - yMin) / (yMax - yMin)) * (y0 - y1);
  const ticks = 5;
  const yTicks = Array.from({ length: ticks + 1 }, (_, index) => yMin + ((yMax - yMin) * index) / ticks);
  const xTickYears =
    years.length <= 10
      ? years
      : years.filter((year, index) => index === 0 || index === years.length - 1 || year % 2 === 0);
  const colors = ["var(--series)", "var(--accent)", "var(--green)"];

  return (
    <div ref={box} className="chart-measure">
      <Legend series={series} />
      <svg className="chart-svg" style={{ width: W }} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={plainText(chart.title)}>
        {yTicks.map((tick) => (
          <g key={tick}>
            <line x1={x0} x2={x1} y1={sy(tick)} y2={sy(tick)} className="grid" />
            <text x={x0 - 10} y={sy(tick) + 4} textAnchor="end" className="tick">
              {fmtNumber(tick, yMax - yMin < 5 ? 1 : 0)}
            </text>
          </g>
        ))}
        <line x1={x0} x2={x1} y1={y0} y2={y0} className="axis" />
        <line x1={x0} x2={x0} y1={y1} y2={y0} className="axis" />
        {xTickYears.map((year) => (
          <g key={year}>
            <line x1={sx(year)} x2={sx(year)} y1={y0} y2={y0 + 5} className="axis" />
            <text x={sx(year)} y={y0 + 20} textAnchor="middle" className="tick">
              {year}
            </text>
          </g>
        ))}
        {refs.map((ref, index) => {
          const y = sy(ref.value);
          return (
            <g key={`${ref.label}-${index}`}>
              <line x1={x0} x2={x1} y1={y} y2={y} className="ref-line" />
              <text x={x1} y={y - 6} textAnchor="end" className="ref-label">
                {clip(plainText(ref.label), 34)} · {valueLabel(ref.value, ref.unit)} ({ref.year})
              </text>
            </g>
          );
        })}
        {series.map((item, index) => {
          const color = item.color || colors[index % colors.length];
          const points = item.points
            .filter((point) => point.value !== null)
            .map((point) => ({ year: point.year, value: point.value as number }));
          const path = points
            .map((point, position) => `${position === 0 ? "M" : "L"} ${sx(point.year)} ${sy(point.value)}`)
            .join(" ");
          const labelAll = points.length <= 6;
          return (
            <g key={item.id}>
              {points.length > 1 && <path d={path} fill="none" stroke={color} strokeWidth={2.5} />}
              {points.map((point, position) => {
                const showLabel = labelAll || position === points.length - 1;
                return (
                  <g key={point.year}>
                    <circle cx={sx(point.year)} cy={sy(point.value)} r={4.5} fill={color} stroke="var(--card)" strokeWidth={1.5}>
                      <title>{`${plainText(item.label)} · ${point.year} · ${valueLabel(point.value, item.unit)}`}</title>
                    </circle>
                    {showLabel && (
                      <text
                        x={sx(point.year) + (position === points.length - 1 && sx(point.year) > W - 170 ? -6 : 0)}
                        y={sy(point.value) - 10 - (index % 2) * 11}
                        textAnchor={
                          position === points.length - 1 && sx(point.year) > W - 170 ? "end" : "middle"
                        }
                        className="point-label"
                      >
                        {valueLabel(point.value, item.unit)}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
        {chart.x_label && (
          <text x={(x0 + x1) / 2} y={H - 10} textAnchor="middle" className="axis-label">
            {chart.x_label}
          </text>
        )}
        {chart.y_label && (
          <text
            transform={`translate(14 ${(y0 + y1) / 2}) rotate(-90)`}
            textAnchor="middle"
            className="axis-label"
          >
            {chart.y_label}
          </text>
        )}
      </svg>
      <p className="chart-hint">
        Chaque point est un chiffre publié
        {unitLabel(chart.unit) ? ` (${unitNote(unitLabel(chart.unit))})` : ""} ; aucune valeur
        estimée.
      </p>
    </div>
  );
}

function BarChart({ chart }: { chart: Chart }) {
  const [box, W] = useChartWidth();
  const bars = chart.bars;
  if (bars.length === 0) return <p className="empty">Aucune valeur.</p>;
  const max = niceMax(Math.max(...bars.map((bar) => bar.value ?? 0)) * 1.15);
  // colonne des libelles a la taille du plus long (13 px, ~7 px par caractere), plafonnee
  const longest = Math.max(...bars.map((bar) => plainText(bar.label).length));
  const labelW = Math.min(Math.round(W * 0.45), Math.max(100, longest * 7 + 18));
  const labelChars = Math.max(8, Math.floor((labelW - 18) / 7));
  const chartW = W - labelW - 96;
  const height = Math.max(190, bars.length * 42 + 26);
  const x0 = labelW;
  const refToX = (value: number) => x0 + (value / max) * chartW;
  return (
    <div ref={box} className="chart-measure">
    <svg className="chart-svg" style={{ width: W }} viewBox={`0 0 ${W} ${height}`} role="img" aria-label={plainText(chart.title)}>
      {chart.reference_lines.map((ref, index) => (
        <g key={`${ref.label}-${index}`}>
          <line x1={refToX(ref.value)} x2={refToX(ref.value)} y1={6} y2={height - 8} className="ref-line" />
          <text x={refToX(ref.value)} y={14} textAnchor="middle" className="ref-label">
            {clip(plainText(ref.label), 22)}
          </text>
        </g>
      ))}
      {bars.map((bar, index) => {
        const y = 24 + index * 42;
        const width = Math.max(2, ((bar.value ?? 0) / max) * chartW);
        const fill = bar.highlight ? "var(--accent)" : "var(--series)";
        return (
          <g key={bar.id}>
            <text x={labelW - 12} y={y + 18} textAnchor="end" className="bar-label">
              {clip(plainText(bar.label), labelChars)}
            </text>
            <rect x={x0} y={y + 3} width={chartW} height={22} rx={6} className="bar-track" />
            <rect x={x0} y={y + 3} width={width} height={22} rx={6} fill={fill}>
              <title>{`${plainText(bar.label)} · ${plainText(bar.display)} · ${bar.year}`}</title>
            </rect>
            <text x={Math.min(x0 + width + 10, W - 4)} y={y + 19} className="bar-value">
              {plainText(bar.display)}
            </text>
          </g>
        );
      })}
      <line x1={x0} x2={x0} y1={2} y2={height - 8} className="axis" />
      {chart.x_label && (
        <text x={x0 + chartW / 2} y={height - 1} textAnchor="middle" className="axis-label">
          {chart.x_label}
        </text>
      )}
    </svg>
    </div>
  );
}

function FunnelChart({ chart }: { chart: Chart }) {
  const steps = chart.steps;
  if (steps.length === 0) return <p className="empty">Aucune étape.</p>;
  const max = Math.max(...steps.map((step) => step.value ?? 0), 1);
  return (
    <div className="funnel">
      {steps.map((step, index) => (
        <div key={step.id} className="funnel-step">
          {index > 0 && step.drop_from_previous_pp !== null && (
            <div className="funnel-drop">
              {fmtSigned(step.drop_from_previous_pp)} points par rapport à l'étape précédente
            </div>
          )}
          <div className="funnel-row">
            <div className="funnel-meta">
              <strong>{STEP_LABELS[step.id] ?? plainText(step.label)}</strong>
              <span className="muted">
                {step.year} · {plainText(step.display)}
              </span>
              <span className={`chip chip-${step.provider}`} title={chipTitle(step.chip)}>{chipLabel(step.chip)}</span>
            </div>
            <div className="funnel-bar-track">
              <div
                className={`funnel-bar ${step.status !== "available" ? "is-empty" : ""}`}
                style={{ width: `${Math.max(3, ((step.value ?? 0) / max) * 100)}%` }}
              >
                {plainText(step.display)}
              </div>
            </div>
          </div>
        </div>
      ))}
      <p className="chart-hint">
        Chaque question est posée séparément : la baisse d'une étape à l'autre ne signifie
        pas que les mêmes personnes quittent le système.
      </p>
    </div>
  );
}

// HTML/CSS (positions en %) : la taille du texte ne suit jamais la largeur du graphique
const DUMBBELL_TICKS = [0, 25, 50, 75, 100];
const DUMBBELL_CLOSE = 9; // points d'ecart sous lesquels une etiquette passe sous son point

function DumbbellChart({ chart }: { chart: Chart }) {
  const rows = chart.groups
    .flatMap((group) => group.rows.map((row) => ({ group, row })))
    .sort((a, b) => (b.row.gap_pp ?? -Infinity) - (a.row.gap_pp ?? -Infinity));
  if (rows.length === 0) return <p className="empty">Aucun groupe.</p>;
  const max = chart.unit === "percent"
    ? 100
    : niceMax(Math.max(...rows.flatMap(({ row }) => [row.left.value ?? 0, row.right.value ?? 0])) * 1.2);
  const pos = (value: number) => `${Math.min(100, Math.max(0, (value / max) * 100))}%`;
  return (
    <div className="db">
      <div className="db-legend">
        <span><i className="dot dot-series" />Groupe le moins équipé</span>
        <span><i className="dot dot-accent" />Groupe le plus équipé</span>
      </div>
      {rows.map(({ group, row }) => {
        const left = row.left.value;
        const right = row.right.value;
        const close = left !== null && right !== null && Math.abs(right - left) < DUMBBELL_CLOSE;
        const gap = row.gap_pp !== null ? `${row.gap_pp >= 0 ? "+" : ""}${fmtNumber(row.gap_pp)} pts` : "—";
        const summary = `${plainText(group.title)}, ${row.year} : ${plainText(row.left.label)} ${plainText(row.left.display)}, `
          + `${plainText(row.right.label)} ${plainText(row.right.display)}, écart ${gap}`;
        return (
          <div key={row.id} className="db-row" role="img" aria-label={summary} title={summary}>
            <div className="db-name">
              <span>{plainText(group.title)}</span>
              <small>
                <b><i className="dot dot-series" />{plainText(row.left.label)}</b>
                <b><i className="dot dot-accent" />{plainText(row.right.label)}</b>
              </small>
            </div>
            <div className="db-track">
              {DUMBBELL_TICKS.map((tick) => (
                <i key={tick} className="db-grid" style={{ left: pos((tick / 100) * max) }} />
              ))}
              <i className="db-line" />
              {left !== null && right !== null && (
                <i className="db-link" style={{ left: pos(Math.min(left, right)), width: `${(Math.abs(right - left) / max) * 100}%` }} />
              )}
              {left !== null && (
                <>
                  <i className="db-dot dot-series" style={{ left: pos(left) }} />
                  <span className="db-value" style={{ left: pos(left) }}>{plainText(row.left.display)}</span>
                </>
              )}
              {right !== null && (
                <>
                  <i className="db-dot dot-accent" style={{ left: pos(right) }} />
                  <span className={`db-value accent ${close ? "below" : ""}`} style={{ left: pos(right) }}>
                    {plainText(row.right.display)}
                  </span>
                </>
              )}
            </div>
            <span className={`db-gap ${row.gap_pp === null ? "muted" : ""}`}>{gap}</span>
          </div>
        );
      })}
      <div className="db-row db-axis" aria-hidden="true">
        <span />
        <div className="db-track">
          {DUMBBELL_TICKS.map((tick) => (
            <span key={tick} className="db-tick" style={{ left: pos((tick / 100) * max) }}>
              {chart.unit === "percent" ? `${tick} %` : fmtNumber((tick / 100) * max, 0)}
            </span>
          ))}
        </div>
        <span />
      </div>
    </div>
  );
}

function GapChart({ chart }: { chart: Chart }) {
  const [box, W] = useChartWidth();
  const points = chart.gap_points;
  if (points.length === 0) return <p className="empty">Aucun écart.</p>;
  const changes = points.map((point) => point.change_pp);
  const min = Math.min(0, ...changes);
  const max = Math.max(0, ...changes);
  const span = Math.max(1, max - min);
  const left = Math.min(160, Math.max(130, Math.round(W * 0.42))); // libelles a 13 px
  const width = W - left - 100; // marge droite : valeur « +28,3 points » a 12 px
  const zero = left + ((0 - min) / span) * width;
  const height = Math.max(200, points.length * 54 + 30);
  const scale = (value: number) => left + ((value - min) / span) * width;
  return (
    <div ref={box} className="chart-measure">
    <svg className="chart-svg" style={{ width: W }} viewBox={`0 0 ${W} ${height}`} role="img" aria-label={plainText(chart.title)}>
      <line x1={zero} x2={zero} y1={14} y2={height - 20} className="axis" />
      {points.map((point: GapPoint, index) => {
        const y = 22 + index * 54;
        const barStart = scale(Math.min(0, point.change_pp));
        const barWidth = Math.max(2, Math.abs(scale(point.change_pp) - zero));
        return (
          <g key={point.id}>
            <text x={left - 14} y={y + 20} textAnchor="end" className="bar-label">
              {plainText(point.label)}
            </text>
            <rect x={barStart} y={y + 5} width={barWidth} height={22} rx={6} fill="var(--accent)">
              <title>{`${plainText(point.label)} : ${fmtSigned(point.change_pp)} points`}</title>
            </rect>
            <text x={point.change_pp >= 0 ? zero + barWidth + 8 : zero - barWidth - 8} y={y + 21} textAnchor={point.change_pp >= 0 ? "start" : "end"} className="bar-value">
              {fmtSigned(point.change_pp)} points
            </text>
            <text x={left - 14} y={y + 38} textAnchor="end" className="tick">
              {fmtNumber(point.gap_from_pp)} → {fmtNumber(point.gap_to_pp)} points
            </text>
          </g>
        );
      })}
      <text x={zero} y={height - 4} textAnchor="middle" className="axis-label">
        0
      </text>
      {chart.x_label && (
        <text x={left + width / 2} y={14} textAnchor="middle" className="axis-label">
          {chart.x_label}
        </text>
      )}
    </svg>
    </div>
  );
}

function HeatmapChart({ chart }: { chart: Chart }) {
  const lookup = new Map(chart.cells.map((cell) => [`${cell.row}|${cell.column}`, cell]));
  const hasValue = chart.cells.some((cell) => cell.status === "available" && cell.value !== null);
  if (!hasValue) {
    if (chart.no_data_scope === "later_wave" && chart.first_available_year) {
      return (
        <div className="empty">
          <p>
            Les raisons de ne pas avoir de compte ne sont mesurées que depuis l'enquête{" "}
            {chart.first_available_year}.
          </p>
          <SeeWaveButton year={chart.first_available_year} />
        </div>
      );
    }
    return <p className="empty">Aucune observation de ces raisons pour ce pays dans les enquêtes disponibles.</p>;
  }
  return (
    <div className="heatmap-wrap">
      <table className="heatmap">
        <thead>
          <tr>
            <th />
            {chart.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chart.rows.map((row) => (
            <tr key={row}>
              <th>{HEATMAP_ROW_LABELS[row] ?? row}</th>
              {chart.columns.map((column) => {
                const cell = lookup.get(`${row}|${column}`);
                return (
                  <td key={column}>
                    <span className={`heat-cell ${cell?.status === "available" ? "is-value" : ""}`} title={plainText(cell?.note) || ""}>
                      {cell?.status === "available" && cell.value !== null
                        ? fmtPct(cell.value)
                        : plainText(cell?.display) || "En attente de données"}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChartView({ chart }: { chart: Chart }) {
  return (
    <ChartShell chart={chart}>
      {chart.kind === "line" && <LineChart chart={chart} />}
      {chart.kind === "bar" && <BarChart chart={chart} />}
      {chart.kind === "funnel" && <FunnelChart chart={chart} />}
      {chart.kind === "dumbbell" && <DumbbellChart chart={chart} />}
      {chart.kind === "gap" && <GapChart chart={chart} />}
      {chart.kind === "heatmap" && <HeatmapChart chart={chart} />}
      {!["line", "bar", "funnel", "dumbbell", "gap", "heatmap"].includes(chart.kind) && (
        <p className="empty">Type de graphique inconnu : {chart.kind}</p>
      )}
    </ChartShell>
  );
}

export function ReferenceLinesLegend({ lines }: { lines: ReferenceLine[] }) {
  if (lines.length === 0) return null;
  return (
    <div className="ref-legend">
      {lines.map((line) => (
        <span key={`${line.label}-${line.year}`} title={line.source}>
          <i />
          {line.label} · {fmtUnit(line.value, line.unit)} ({line.year})
        </span>
      ))}
    </div>
  );
}

export function BarsTable({ bars }: { bars: Bar[] }) {
  return (
    <table className="mini-table">
      <thead>
        <tr>
          <th>Groupe</th>
          <th>Valeur</th>
          <th>Année</th>
        </tr>
      </thead>
      <tbody>
        {bars.map((bar) => (
          <tr key={bar.id}>
            <td>{plainText(bar.label)}</td>
            <td>{plainText(bar.display)}</td>
            <td>{bar.year}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
