import { useMemo, useState } from "react";
import type { DashboardData, TableRow } from "../types";
import { formatNumber, formatValue, reasonLabel, statusLabel } from "../format";

type Filter = "all" | "flagged" | "available" | "unavailable";

interface Props {
  data: DashboardData;
  country: string;
}

function matches(row: TableRow, filter: Filter): boolean {
  if (filter === "flagged") {
    return row.requires_review || row.availability_status === "requires_review";
  }
  if (filter === "available") return row.value !== null;
  if (filter === "unavailable") return row.value === null;
  return true;
}

export function DataTable({ data, country }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const scoped = useMemo(
    () => data.table.filter((row) => country === "ALL" || row.iso3 === country),
    [data.table, country],
  );
  const rows = useMemo(() => scoped.filter((row) => matches(row, filter)), [scoped, filter]);

  return (
    <section className="panel">
      <header className="panel__head">
        <h2>Observations détaillées</h2>
        <div className="panel__tools">
          <span className="muted">
            {formatNumber(rows.length)} / {formatNumber(scoped.length)} lignes
          </span>
          <label className="select-label">
            Filtre
            <select
              value={filter}
              onChange={(event) => setFilter(event.target.value as Filter)}
            >
              <option value="all">Toutes</option>
              <option value="flagged">Revue requise</option>
              <option value="available">Disponibles</option>
              <option value="unavailable">Indisponibles</option>
            </select>
          </label>
        </div>
      </header>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">KPI</th>
              <th scope="col">Pays</th>
              <th scope="col">Année</th>
              <th scope="col" className="num">
                Valeur
              </th>
              <th scope="col">Unité</th>
              <th scope="col">Disponibilité</th>
              <th scope="col">Définition</th>
              <th scope="col">Revue</th>
              <th scope="col">Motif</th>
              <th scope="col">Preuve</th>
              <th scope="col">Source / indicateur</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const review =
                row.requires_review || row.availability_status === "requires_review";
              return (
                <tr key={row.evidence_id}>
                  <td>{row.kpi_name}</td>
                  <td>
                    {row.country_name}
                    <span className="muted"> · {row.iso3}</span>
                  </td>
                  <td>{row.year ?? "—"}</td>
                  <td className="num">{formatValue(row.value, row.unit)}</td>
                  <td className="mono">{row.unit}</td>
                  <td>
                    <span
                      className={`badge ${
                        row.availability_status === "available"
                          ? "badge-ok"
                          : row.availability_status === "requires_review"
                            ? "badge-review"
                            : "badge-neutral"
                      }`}
                    >
                      {statusLabel(row.availability_status)}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        row.definition_status === "provisional"
                          ? "badge-warning"
                          : "badge-neutral"
                      }`}
                    >
                      {statusLabel(row.definition_status)}
                    </span>
                  </td>
                  <td>
                    {review ? (
                      <span className="badge badge-review" title={row.review_reasons.join(", ")}>
                        Oui
                      </span>
                    ) : (
                      <span className="badge badge-neutral">Non</span>
                    )}
                  </td>
                  <td className="cell-reason">
                    {row.reason ? (
                      <span className="chip" title={row.reason}>
                        {reasonLabel(row.reason)}
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="mono cell-evidence">{row.evidence_id}</td>
                  <td className="cell-source">
                    {row.source}
                    <span className="muted"> · {row.indicator_code}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && <p className="empty-table">Aucune ligne pour ce filtre.</p>}
      </div>
    </section>
  );
}
