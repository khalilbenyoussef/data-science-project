import { useEffect, useState } from "react";
import type { RecommendationsResult } from "./types";
import { fetchRecommendations } from "./api";
import { fmtUnit } from "./format";

// Pistes de recommandation de Vue d'ensemble : regles deterministes appliquees aux
// valeurs auditees du pays et de l'annee affiches (GET /api/recommendations).
export function Recommendations({ iso3, year }: { iso3: string; year: number }) {
  const [data, setData] = useState<RecommendationsResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    fetchRecommendations(iso3, year, controller.signal)
      .then(setData)
      .catch((err: unknown) => {
        if ((err as { name?: string })?.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Pistes indisponibles");
      });
    return () => controller.abort();
  }, [iso3, year]);

  return (
    <section className="panel recommendations" aria-labelledby="reco-title">
      <div className="panel-head">
        <div>
          <h3 id="reco-title">Pistes de recommandation</h3>
          <p className="muted small">
            Règles fixes appliquées aux valeurs auditées · association, pas causalité
          </p>
        </div>
        {data && (
          <span className="muted small">
            {data.recommendations.length} piste{data.recommendations.length > 1 ? "s" : ""} ·{" "}
            {data.rules_checked} comparaisons
          </span>
        )}
      </div>
      {error && <p className="muted small">Pistes indisponibles : {error}</p>}
      {!error && !data && <p className="muted small">Chargement des pistes…</p>}
      {data && data.recommendations.length === 0 && (
        <p className="muted small">
          Aucune règle déclenchée pour {data.country} en {data.year} : aucun écart ne dépasse les seuils.
        </p>
      )}
      {data && data.recommendations.length > 0 && (
        <ul className="insight-list">
          {data.recommendations.map((rec) => (
            <li key={rec.id} className={rec.review_note ? "sev-review" : "sev-info"}>
              <span className="dot" />
              <div>
                <p>{rec.text}</p>
                <div className="reco-meta">
                  <span className="reco-target">Groupe cible : {rec.target_group}</span>
                  <span className="muted small">Règle : {rec.rule}</span>
                </div>
                <div className="tag-row" aria-label="Sources">
                  {rec.evidence.map((ev) => (
                    <code
                      key={ev.id}
                      title={`${ev.id} · ${
                        ev.publication_status === "approved" ? "approuvée" : "approuvée avec réserve"
                      }`}
                    >
                      {ev.kpi} · {ev.iso3 === "PEERS" ? "moyenne des pairs" : ev.iso3} · {ev.year} ·{" "}
                      {fmtUnit(ev.value, ev.unit)}
                      {ev.publication_status !== "approved" ? " · avec réserve" : ""}
                    </code>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
