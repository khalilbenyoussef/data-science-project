import { useMemo } from "react";
import { useECharts } from "../useECharts";
import type { EChartsOption } from "../useECharts";
import type { DashboardData } from "../types";
import { formatValue, reasonLabel, statusLabel } from "../format";
import { escapeHtml } from "../escape";

interface Props {
  data: DashboardData;
  kpiId: string;
}

interface AxisPoint {
  seriesName: string;
  axisValue: string;
}

export function TrendChart({ data, kpiId }: Props) {
  const kpi = data.scope.kpis.find((item) => item.kpi_id === kpiId);
  const series = useMemo(
    () => data.series.filter((item) => item.kpi_id === kpiId),
    [data.series, kpiId],
  );
  const names = useMemo(
    () => new Map(data.scope.countries.map((item) => [item.iso3, item.name])),
    [data.scope.countries],
  );

  const option = useMemo<EChartsOption>(() => {
    const years = Array.from(
      new Set(series.flatMap((item) => item.points.map((point) => point.year))),
    ).sort((a, b) => a - b);
    return {
      aria: { enabled: true },
      color: ["#1d4ed8", "#0f766e", "#b45309", "#7c3aed", "#be123c", "#4d7c0f"],
      grid: { left: 58, right: 24, top: 28, bottom: 56 },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const items = (params as AxisPoint[]) ?? [];
          // S4 : infobulle HTML, chaque libelle issu des donnees est echappe
          const lines = [`<strong>${escapeHtml(items[0]?.axisValue)}</strong>`];
          for (const item of items) {
            const source = series.find(
              (candidate) => (names.get(candidate.iso3) ?? candidate.iso3) === item.seriesName,
            );
            const point = source?.points.find(
              (candidate) => String(candidate.year) === String(item.axisValue),
            );
            if (!point || !kpi) continue;
            lines.push(
              `${escapeHtml(item.seriesName)} : ${escapeHtml(formatValue(point.value, kpi.unit))} — ` +
                `${escapeHtml(statusLabel(point.availability_status))}${
                  point.requires_review ? " — revue requise" : ""
                }`,
            );
            if (point.reason) lines.push(`&nbsp;&nbsp;motif : ${escapeHtml(reasonLabel(point.reason))}`);
          }
          return lines.join("<br/>");
        },
      },
      legend: { bottom: 8, type: "scroll", textStyle: { color: "#334155" } },
      xAxis: {
        type: "category",
        data: years,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        axisLabel: { color: "#475569" },
      },
      yAxis: {
        type: "value",
        scale: true,
        name: kpi?.unit ?? "",
        nameTextStyle: { color: "#64748b" },
        axisLabel: { color: "#475569" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      series: series.map((item) => ({
        type: "line" as const,
        name: names.get(item.iso3) ?? item.iso3,
        connectNulls: false,
        symbolSize: 8,
        lineStyle: { width: 2.4 },
        emphasis: { focus: "series" as const },
        data: years.map((year) => {
          const point = item.points.find((candidate) => candidate.year === year);
          if (!point || point.value === null) return null;
          return {
            value: point.value,
            itemStyle: point.requires_review
              ? { color: "#b45309", borderColor: "#7c2d12", borderWidth: 2 }
              : undefined,
          };
        }),
      })),
    };
  }, [kpi, series, names]);

  const container = useECharts(option);

  if (!kpi || series.length === 0) {
    return <div className="empty-chart">Aucune série exportée pour ce KPI.</div>;
  }
  return (
    <div
      className="chart"
      ref={container}
      role="img"
      aria-label={`Tendance de ${kpi.name} par pays`}
    />
  );
}
