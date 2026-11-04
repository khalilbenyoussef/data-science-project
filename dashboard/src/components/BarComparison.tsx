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

export function BarComparison({ data, kpiId }: Props) {
  const ranking = data.rankings.find((item) => item.kpi_id === kpiId);
  const names = useMemo(
    () => new Map(data.scope.countries.map((item) => [item.iso3, item.name])),
    [data.scope.countries],
  );
  const rows = useMemo(
    () =>
      (ranking?.rows ?? [])
        .filter((row) => row.value !== null)
        .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999)),
    [ranking],
  );

  const option = useMemo<EChartsOption>(() => {
    const labels = rows.map((row) => names.get(row.iso3) ?? row.iso3);
    return {
      aria: { enabled: true },
      grid: { left: 118, right: 92, top: 16, bottom: 24 },
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const { dataIndex } = params as { dataIndex: number };
          const row = rows[dataIndex];
          if (!row) return "";
          // S4 : infobulle HTML, chaque libelle issu des donnees est echappe
          return [
            `<strong>${escapeHtml(names.get(row.iso3) ?? row.iso3)}</strong>`,
            escapeHtml(formatValue(row.value, row.unit)),
            `Rang ${escapeHtml(row.rank ?? "—")} — ${escapeHtml(statusLabel(row.availability_status))}`,
            row.requires_review ? "Revue requise" : "",
            row.reason ? `Motif : ${escapeHtml(reasonLabel(row.reason))}` : "",
          ]
            .filter(Boolean)
            .join("<br/>");
        },
      },
      xAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: "#475569" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: labels,
        axisLabel: { color: "#334155" },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
      },
      series: [
        {
          type: "bar" as const,
          barMaxWidth: 34,
          data: rows.map((row) => ({
            value: row.value,
            itemStyle: {
              color: row.requires_review ? "#b45309" : "#1d4ed8",
              borderRadius: [0, 4, 4, 0] as [number, number, number, number],
            },
          })),
          label: {
            show: true,
            position: "right" as const,
            color: "#334155",
            formatter: (params: unknown) => {
              const { dataIndex } = params as { dataIndex: number };
              const row = rows[dataIndex];
              return row ? formatValue(row.value, row.unit) : "";
            },
          },
        },
      ],
    };
  }, [names, rows]);

  const container = useECharts(option);

  if (!ranking || ranking.status !== "complete" || ranking.year === null || rows.length === 0) {
    return (
      <div className="empty-chart">
        Classement indisponible : {ranking ? statusLabel(ranking.status) : "KPI absent"}.
      </div>
    );
  }
  return (
    <div
      className="chart"
      ref={container}
      role="img"
      aria-label={`Classement ${ranking.year} du KPI sélectionné`}
    />
  );
}
