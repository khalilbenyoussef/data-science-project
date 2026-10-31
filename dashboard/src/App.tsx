import { useEffect, useMemo, useState } from "react";
import type { DashboardData } from "./types";
import { validateDashboardData } from "./validate";
import {
  formatDateTime,
  formatNumber,
  formatValue,
  severityLabel,
  statusLabel,
  unitLabel,
} from "./format";
import { KpiCard } from "./components/KpiCard";
import { TrendChart } from "./components/TrendChart";
import { BarComparison } from "./components/BarComparison";
import { DataTable } from "./components/DataTable";
import { Notices } from "./components/Notices";
import { ProvenanceFooter } from "./components/ProvenanceFooter";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: DashboardData };

export default function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      try {
        const url = `${import.meta.env.BASE_URL}data/dashboard.json`;
        const response = await fetch(url, { cache: "no-store", signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} — ${response.statusText}`);
        }
        const data = validateDashboardData(await response.json());
        if (!cancelled) setState({ status: "ready", data });
      } catch (error) {
        if (cancelled || controller.signal.aborted) return;
        setState({
          status: "error",
          message: error instanceof Error ? error.message : String(error),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError message={state.message} />;
  return <DashboardView data={state.data} />;
}

function Loading() {
  return (
    <main className="app">
      <div className="state-card" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <h1>Chargement du jeu de données</h1>
        <p>
          Lecture de <code>public/data/dashboard.json</code>.
        </p>
      </div>
    </main>
  );
}

function LoadError({ message }: { message: string }) {
  return (
    <main className="app">
      <div className="state-card state-card--error" role="alert">
        <h1>Données indisponibles ou invalides</h1>
        <p>{message}</p>
        <p>Générez le fichier avec :</p>
        <pre>
          <code>python main.py dashboard --country TUN,MAR,DZA --mode latest</code>
        </pre>
        <p>
          Vérifiez que <code>dashboard/public/data/dashboard.json</code> existe et respecte le
          schéma 1.0.
        </p>
      </div>
    </main>
  );
}

function DashboardView({ data }: { data: DashboardData }) {
  const kpis = data.scope.kpis;
  const [country, setCountry] = useState(
    data.scope.reference_iso3 || data.scope.countries[0]?.iso3 || "ALL",
  );
  const [kpiId, setKpiId] = useState(kpis[0]?.kpi_id ?? "");
  const [showAllInsights, setShowAllInsights] = useState(false);

  const selectedKpi = kpis.find((item) => item.kpi_id === kpiId) ?? kpis[0];
  const comparisonUnit = selectedKpi?.unit ?? "percent";
  const ranking = data.rankings.find((item) => item.kpi_id === kpiId);
  const comparison = data.comparisons.find((item) => item.kpi_id === kpiId);
  const cards = useMemo(
    () => data.cards.filter((card) => country === "ALL" || card.iso3 === country),
    [data.cards, country],
  );
  const reviewCount = data.cards.filter(
    (card) => card.requires_review || card.availability_status === "requires_review",
  ).length;
  const unavailableCount = data.cards.filter((card) => card.value === null).length;
  const visibleInsights = showAllInsights ? data.insights : data.insights.slice(0, 9);
  const countryName =
    data.scope.countries.find((item) => item.iso3 === country)?.name ?? "Tous les pays";

  return (
    <main className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            BF
          </span>
          <div>
            <p className="eyebrow">BIFlow · Route 2</p>
            <h1>Tableau de bord BI</h1>
            <p className="brand-sub">
              Analyse déterministe — aucune génération LLM, aucun recalcul
            </p>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="meta-pill">
            Run <code>{data.run_id}</code>
          </span>
          <span className="meta-pill">Généré le {formatDateTime(data.generated_at)}</span>
          <span className="meta-pill">
            Catalogue <code>{data.catalog.version}</code>
          </span>
          <span className="badge badge-danger">Publication non évaluée</span>
        </div>
      </header>

      <section className="status-strip" aria-label="Synthèse du run">
        <div className="stat">
          <span className="stat__value">{formatNumber(data.cards.length)}</span>
          <span className="stat__label">observations</span>
        </div>
        <div className="stat stat--review">
          <span className="stat__value">{formatNumber(reviewCount)}</span>
          <span className="stat__label">en revue</span>
        </div>
        <div className="stat">
          <span className="stat__value">{formatNumber(unavailableCount)}</span>
          <span className="stat__label">indisponibles</span>
        </div>
        <div className="stat">
          <span className="stat__value">{formatNumber(data.insights.length)}</span>
          <span className="stat__label">constats</span>
        </div>
        <div className="stat stat--gate">
          <span className="stat__value">
            {data.provenance.quality_gate_passed === true
              ? "PASS"
              : data.provenance.quality_gate_passed === false
                ? "FAIL"
                : "?"}
          </span>
          <span className="stat__label">gate qualité</span>
        </div>
        <div className="stat stat--binding">
          <span className="stat__value">
            {data.provenance.content_binding === "recorded_and_verified" ? "OK" : "NON"}
          </span>
          <span className="stat__label">lien de contenu</span>
        </div>
      </section>

      <div className="banner banner--review" role="note">
        <strong>Revue requise :</strong> {formatNumber(reviewCount)} observation(s) sur{" "}
        {formatNumber(data.cards.length)} portent des motifs de provenance ou de définition.
        Aucune publication n'est approuvée par ce tableau de bord.
      </div>

      <section className="controls">
        <div className="control-group">
          <span className="control-label">Pays</span>
          <div className="tabs" role="group" aria-label="Filtrer les cartes par pays">
            <button
              type="button"
              className={`tab${country === "ALL" ? " is-active" : ""}`}
              aria-pressed={country === "ALL"}
              onClick={() => setCountry("ALL")}
            >
              Tous
            </button>
            {data.scope.countries.map((item) => (
              <button
                key={item.iso3}
                type="button"
                className={`tab${country === item.iso3 ? " is-active" : ""}`}
                aria-pressed={country === item.iso3}
                title={item.name}
                onClick={() => setCountry(item.iso3)}
              >
                {item.iso3}
              </button>
            ))}
          </div>
        </div>
        <label className="control-group">
          <span className="control-label">KPI des graphiques</span>
          <select value={kpiId} onChange={(event) => setKpiId(event.target.value)}>
            {kpis.map((item) => (
              <option key={item.kpi_id} value={item.kpi_id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="panel">
        <header className="panel__head">
          <h2>Indicateurs clés</h2>
          <span className="muted">
            {countryName} ·{" "}
            {data.scope.mode === "latest"
              ? "dernière observation disponible"
              : `année ${data.scope.year ?? "—"}`}
          </span>
        </header>
        {country === "ALL" ? (
          data.scope.countries.map((item) => (
            <div className="country-group" key={item.iso3}>
              <h3>
                {item.name}{" "}
                <span className="muted">
                  {item.iso3}
                  {item.income_group ? ` · ${item.income_group}` : ""}
                </span>
              </h3>
              <div className="card-grid">
                {data.cards
                  .filter((card) => card.iso3 === item.iso3)
                  .map((card) => (
                    <KpiCard
                      key={card.evidence_id}
                      card={card}
                      selected={card.kpi_id === kpiId}
                      onSelect={() => setKpiId(card.kpi_id)}
                    />
                  ))}
              </div>
            </div>
          ))
        ) : (
          <div className="card-grid">
            {cards.map((card) => (
              <KpiCard
                key={card.evidence_id}
                card={card}
                selected={card.kpi_id === kpiId}
                onSelect={() => setKpiId(card.kpi_id)}
              />
            ))}
          </div>
        )}
      </section>

      <div className="grid-2">
        <section className="panel">
          <header className="panel__head">
            <h2>Tendance · {selectedKpi?.name ?? "—"}</h2>
            <span className="muted">{selectedKpi ? unitLabel(selectedKpi.unit) : ""}</span>
          </header>
          <TrendChart data={data} kpiId={kpiId} />
          <p className="chart-note">
            Les années manquantes restent nulles (aucune interpolation). Les points ambre
            signalent une revue requise.
          </p>
        </section>
        <section className="panel">
          <header className="panel__head">
            <h2>Classement · {selectedKpi?.name ?? "—"}</h2>
            <span className="muted">
              {ranking?.year ? `année commune ${ranking.year}` : "aucune année commune"}
            </span>
          </header>
          <BarComparison data={data} kpiId={kpiId} />
          <p className="chart-note">
            Règle :{" "}
            {data.scope.ranking_rule === "latest_common_catalog_year"
              ? "dernière année commune du catalogue"
              : data.scope.ranking_rule}
            .
          </p>
        </section>
      </div>

      {comparison && (
        <section className="panel">
          <header className="panel__head">
            <h2>Écarts vs {comparison.reference_iso3}</h2>
            <span className="muted">
              {comparison.year ? `année ${comparison.year}` : statusLabel(comparison.status)} ·
              différence = droite − gauche
            </span>
          </header>
          {comparison.rows.length === 0 ? (
            <div className="empty-chart">{statusLabel(comparison.status)}.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Pays</th>
                    <th scope="col" className="num">
                      Valeur
                    </th>
                    <th scope="col" className="num">
                      Référence
                    </th>
                    <th scope="col" className="num">
                      Écart
                    </th>
                    <th scope="col">Statut</th>
                    <th scope="col">Revue</th>
                    <th scope="col">Preuve</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.rows.map((row) => (
                    <tr key={row.evidence_id}>
                      <td>{row.iso3}</td>
                      <td className="num">{formatValue(row.value, comparisonUnit)}</td>
                      <td className="num">
                        {formatValue(row.reference_value, comparisonUnit)}
                      </td>
                      <td className="num">{formatValue(row.difference, row.unit, true)}</td>
                      <td>
                        <span
                          className={`badge ${
                            row.comparison_status === "complete"
                              ? "badge-ok"
                              : "badge-warning"
                          }`}
                        >
                          {statusLabel(row.comparison_status)}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            row.requires_review ? "badge-review" : "badge-neutral"
                          }`}
                        >
                          {row.requires_review ? "Oui" : "Non"}
                        </span>
                      </td>
                      <td className="mono cell-evidence">{row.evidence_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <section className="panel">
        <header className="panel__head">
          <h2>Constats de l'analyste</h2>
          <span className="panel__count">{data.insights.length}</span>
        </header>
        <div className="insight-grid">
          {visibleInsights.map((insight) => (
            <article
              key={insight.id ?? `${insight.code}-${insight.statement}`}
              className={`insight insight--${insight.severity ?? "info"}`}
            >
              <div className="insight__head">
                <code>{insight.id ?? "—"}</code>
                <span className={`badge badge-${insight.severity ?? "info"}`}>
                  {severityLabel(insight.severity ?? "info")}
                </span>
                <code className="muted">{insight.code}</code>
              </div>
              <p>{insight.statement}</p>
              <div className="evidence-list">
                {insight.evidence_ids.slice(0, 4).map((id) => (
                  <span className="chip" key={id}>
                    {id}
                  </span>
                ))}
                {insight.evidence_ids.length > 4 && (
                  <span className="chip chip-more">+{insight.evidence_ids.length - 4}</span>
                )}
              </div>
            </article>
          ))}
        </div>
        {data.insights.length > 9 && (
          <button
            className="link-button"
            type="button"
            onClick={() => setShowAllInsights((value) => !value)}
          >
            {showAllInsights ? "Réduire" : `Afficher les ${data.insights.length - 9} autres constats`}
          </button>
        )}
      </section>

      <DataTable data={data} country={country} />
      <Notices notices={data.notices} />
      <ProvenanceFooter data={data} />
    </main>
  );
}
