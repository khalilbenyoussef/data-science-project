import { useEffect, useState } from "react";
import type { RecommendationsResult } from "./types";
import { fetchRecommendations } from "./api";
import { fmtUnit } from "./format";
import { UserChip } from "./ui";
import { t } from "./i18n";
import { plainText } from "./copy";

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
        setError(err instanceof Error ? err.message : String(err));
      });
    return () => controller.abort();
  }, [iso3, year]);

  return (
    <section className="panel recommendations" aria-labelledby="reco-title">
      <div className="panel-head">
        <div>
          <h3 id="reco-title">{t("Pistes de recommandation")}</h3>
          <p className="muted small">
            {t("Règles fixes appliquées aux valeurs auditées · association, pas causalité")}
          </p>
        </div>
        {data && (
          <span className="muted small">
            {data.recommendations.length > 1
              ? t("{count} pistes", { count: data.recommendations.length })
              : t("{count} piste", { count: data.recommendations.length })} ·{" "}
            {t("{count} comparaisons", { count: data.rules_checked })}
          </span>
        )}
      </div>
      {error && <p className="muted small">{t("Pistes indisponibles : {detail}", { detail: error })}</p>}
      {!error && !data && <p className="muted small">{t("Chargement des pistes…")}</p>}
      {data && data.recommendations.length === 0 && (
        <p className="muted small">
          {t("Aucune règle déclenchée pour {country} en {year} : aucun écart ne dépasse les seuils.", {
            country: plainText(data.country),
            year: data.year,
          })}
        </p>
      )}
      {data && data.recommendations.length > 0 && (
        <ul className="insight-list">
          {data.recommendations.map((rec) => (
            <li key={rec.id} className={rec.review_note ? "sev-review" : "sev-info"}>
              <span className="dot" />
              <div>
                <p>{plainText(rec.text)}</p>
                <div className="reco-meta">
                  <span className="reco-target">{t("Groupe cible : {group}", { group: plainText(rec.target_group) })}</span>
                  <span className="muted small">{t("Règle : {rule}", { rule: plainText(rec.rule) })}</span>
                </div>
                <div className="tag-row" aria-label={t("Sources")}>
                  {rec.evidence.map((ev) => (
                    <code
                      key={ev.id}
                      title={`${ev.id} · ${
                        ev.publication_status === "approved"
                          ? t("approuvée")
                          : t("approuvée avec réserve")
                      }`}
                    >
                      {plainText(ev.kpi)} · {ev.iso3 === "PEERS" ? t("moyenne des pairs") : ev.iso3} · {ev.year} ·{" "}
                      {fmtUnit(ev.value, ev.unit)}
                      {ev.publication_status !== "approved" ? ` · ${t("avec réserve")}` : ""}
                    </code>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      {data && (data.user_recommendations?.length ?? 0) > 0 && (
        <div className="user-recommendations">
          <div className="panel-head">
            <h4>{t("À partir de vos données")}</h4>
            <UserChip />
          </div>
          <p className="muted small">
            {t("Même logique de règles fixes, appliquée à vos indicateurs déclarés comparables, seulement quand votre année est celle de la valeur officielle. Comparaison indicative.")}
          </p>
          <ul className="insight-list">
            {data.user_recommendations!.map((rec) => (
              <li key={rec.id} className="sev-info user-reco">
                <span className="dot" />
                <div>
                  <p>{plainText(rec.text)}</p>
                  <div className="reco-meta">
                    <span className="reco-target">{t("Groupe cible : {group}", { group: plainText(rec.target_group) })}</span>
                    <span className="muted small">{t("Règle : {rule}", { rule: plainText(rec.rule) })}</span>
                  </div>
                  <div className="tag-row" aria-label={t("Sources")}>
                    {rec.evidence.map((ev) => (
                      <code key={ev.source} className={ev.source === "vos données" ? "user-fact" : undefined}>
                        {plainText(ev.source)} · {ev.year} · {fmtUnit(ev.value, ev.unit)}
                      </code>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
