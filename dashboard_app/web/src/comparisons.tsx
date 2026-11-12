import { useEffect, useState } from "react";
import type { ComparisonRow, ComparisonsResult } from "./types";
import { fetchComparisons } from "./api";
import { UserChip } from "./ui";
import { fmtUnit } from "./format";
import { t } from "./i18n";
import { plainText } from "./copy";

// « Vos indicateurs face aux données officielles » (Vue d'ensemble) : bloc séparé des
// cartes officielles ; chaque valeur utilisateur porte la puce « Données utilisateur ·
// non vérifiée par BIFlow ». Masqué si aucun indicateur n'est déclaré comparable.
export function UserComparisons({ iso3, year }: { iso3: string; year: number }) {
  const [data, setData] = useState<ComparisonsResult | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    fetchComparisons(iso3, year, controller.signal)
      .then(setData)
      .catch(() => setData(null)); // bloc facultatif : absent en cas d'erreur
    return () => controller.abort();
  }, [iso3, year]);

  if (!data || data.rows.length === 0) return null;
  return (
    <section className="panel user-comparisons" aria-labelledby="user-comparisons-title">
      <div className="panel-head">
        <div>
          <h3 id="user-comparisons-title">{t("Vos indicateurs face aux données officielles")}</h3>
          <p className="muted small">{plainText(data.note)}</p>
        </div>
        <UserChip />
      </div>
      <ul className="comparison-list">
        {data.rows.map((row) => <ComparisonItem key={row.indicator_code} row={row} />)}
      </ul>
    </section>
  );
}

function ComparisonItem({ row }: { row: ComparisonRow }) {
  const comparable = row.status !== "unit_mismatch" && row.status !== "unknown_kpi";
  return (
    <li className={`comparison-item status-${row.status}`}>
      <div className="comparison-values">
        <div className="comparison-side user-side">
          <span className="comparison-caption">{t("Votre indicateur")}</span>
          <strong>{plainText(row.label)}</strong>
          {comparable && (row.user ? (
            <span className="comparison-value">
              {fmtUnit(row.user.value, row.user.unit)} <span className="muted">({row.user.year})</span>
            </span>
          ) : <span className="muted small">{t("aucune valeur")}</span>)}
          <UserChip />
        </div>
        <div className="comparison-side official-side">
          <span className="comparison-caption">{t("Indicateur officiel")}</span>
          <strong>{plainText(row.kpi)}</strong>
          {comparable && (row.official ? (
            <span className="comparison-value">
              {fmtUnit(row.official.value, row.official.unit)} <span className="muted">({row.official.year})</span>
            </span>
          ) : <span className="muted small">{t("aucune valeur approuvée")}</span>)}
        </div>
      </div>
      {row.definition && (
        <p className="small muted comparison-definition">
          {t("Définition officielle : {definition}", { definition: plainText(row.definition) })}
          {row.denominator
            ? ` · ${t("Dénominateur : {value}", { value: plainText(row.denominator) })}`
            : ""}
        </p>
      )}
      {row.notes.length > 0 && (
        <p className="small comparison-notes">{row.notes.map(plainText).join(" · ")}</p>
      )}
    </li>
  );
}
