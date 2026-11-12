import { useEffect, useRef, useState } from "react";
import type {
  AskPayload, AskResult, Changes, Chart, InfoBlock, InfoItem, Insight, Metric,
  Notice, PipelinePayload, XaiCard,
} from "./types";
import {
  fmtNumber, fmtPct, fmtSigned, fmtUnit, prettyDate, providerLabel, severityClass,
  shortHash, statusLabel, unitLabel,
} from "./format";
import { SeeWaveButton } from "./waveNav";
import { t, tr } from "./i18n";
import { getLang } from "./preferences";
import {
  ExplainDialog, buildInfoExplanation, buildMetricExplanation,
} from "./explain";
import {
  DEFINITION_STATUS, INFO_LABELS, METRIC_LABELS,
  PIPELINE_NODES, REVIEW_REASONS, chipLabel, chipNeedsReview, chipTitle, friendlyCaveat, friendlyDefinition,
  friendlyFilter, friendlyRule, friendlySource, noticeCopy, plainText, rejectedLabel, sourceName,
} from "./copy";

export const USER_CHIP_TEXT = "Vos données";

// Références hors entrepôt (SMIG, pauvreté INS) : jamais affichées dans l'interface.
const HIDDEN_INFO_IDS = new Set([
  "smig_2025", "smig_2026", "smig_2027", "smig_2028",
  "poverty_rate_2021", "poverty_rate_extreme_2021",
  "poverty_rate_urban_2021", "poverty_rate_rural_2021",
  "context_undp", "context_oif",
]);

export function UserChip() {
  return (
    <span className="chip chip-user" title={t("Valeur importée par l'utilisateur, hors chiffres officiels : BIFlow ne la vérifie pas")}>
      {t(USER_CHIP_TEXT)}
    </span>
  );
}

export function ChipBadge({ chip }: { chip: Metric["chip"] | InfoItem["chip"] | null }) {
  if (!chip) return null;
  return (
    <span className={`chip chip-${chip.provider}`} title={chipTitle(chip)}>
      {chipLabel(chip)}
      {chipNeedsReview(chip) && <span className="chip-review">{t(" · à vérifier")}</span>}
    </span>
  );
}

function WhySheet({ metric, onClose }: { metric: Metric; onClose: () => void }) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
  const why = metric.why;
  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(event) => event.stopPropagation()}>
        <div className="sheet-head">
          <div>
            <span className="eyebrow">{t("D'où vient ce chiffre ?")}</span>
            <h3>{METRIC_LABELS[metric.id] ?? plainText(metric.label)}</h3>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label={t("Fermer")}>
            ×
          </button>
        </div>
        <div className="sheet-value">
          <strong>{plainText(metric.display)}</strong>
          <span className="muted">
            {t("année utilisée : {year} · {provider}", {
              year: why?.year_used ?? metric.year,
              provider: providerLabel(metric.provider),
            })}
          </span>
        </div>
        <dl className="why-grid">
          <dt>{t("Ce que mesure l'indicateur")}</dt>
          <dd>{friendlyDefinition(metric.id, why?.definition ?? null)}</dd>
          <dt>{t("Source")}</dt>
          <dd>
            {friendlySource(why?.source ?? null)}
            {why?.source_url && (
              <a href={why.source_url} target="_blank" rel="noreferrer" className="link">
                {t("consulter la source")}
              </a>
            )}
          </dd>
          <dt>{t("Périmètre")}</dt>
          <dd>{friendlyFilter(why?.filter ?? null)}</dd>
          <dt>{t("Fiabilité de la définition")}</dt>
          <dd>
            {(DEFINITION_STATUS[why?.definition_status ?? ""] ??
              plainText(why?.definition_status)) || "—"}
          </dd>
          <dt>{t("Année réellement utilisée")}</dt>
          <dd>{why?.year_used ?? metric.year}</dd>
          <dt>{t("Repère de provenance")}</dt>
          <dd>
            <ChipBadge chip={metric.chip} />
          </dd>
        </dl>
        {why && why.review_reasons.length > 0 && (
          <div className="why-reasons">
            <span className="eyebrow">{t("Points à vérifier")}</span>
            <div className="tag-row">
              {why.review_reasons.map((reason) => (
                <code key={reason} title={reason}>
                  {REVIEW_REASONS[reason] ?? plainText(reason)}
                </code>
              ))}
            </div>
          </div>
        )}
        {(why?.caveat || metric.caveat) && (
          <p className="caveat">{friendlyCaveat(metric.id, why?.caveat ?? metric.caveat)}</p>
        )}
        <p className="muted small">
          {t("Aucun chiffre n'est recalculé dans l'interface : la valeur et l'année proviennent directement des données source.")}
        </p>
        <details className="tech-details">
          <summary>{t("Détails techniques (pour vérification)")}</summary>
          <dl className="why-grid">
            <dt>{t("Identifiant")}</dt>
            <dd className="mono small">{metric.id}</dd>
            <dt>{t("Définition d'origine")}</dt>
            <dd>{why?.definition || "—"}</dd>
            <dt>{t("Source d'origine")}</dt>
            <dd>{why?.source || "—"}</dd>
            <dt>{t("Filtre d'origine")}</dt>
            <dd>{why?.filter || "—"}</dd>
            <dt>{t("Statut d'origine")}</dt>
            <dd>{why?.definition_status || "—"}</dd>
          </dl>
        </details>
      </div>
    </div>
  );
}

// sépare le nombre de son unité pour éviter les retours à la ligne au milieu d'un montant
function splitDisplay(text: string): [string, string] {
  const match = text.match(/^([\d\u00a0\s.,]+(?:points|%|TND)?)\s+(.+)$/);
  if (!match) return [text, ""];
  return [match[1].trim(), match[2].trim()];
}

// compte progressif des valeurs numériques (désactivé si l'utilisateur préfère moins de mouvement)
function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function parseDisplayNumber(raw: string): { target: number; decimals: number } | null {
  // un nombre contenant un séparateur de milliers a déjà été scindé par splitDisplay :
  // on ne l'anime pas pour ne pas compter seulement le premier groupe de chiffres
  if (/\s/.test(raw.trim())) return null;
  // séparateur de milliers anglais (« 12,345 ») : pas d'animation
  if (getLang() !== "fr" && /^-?\d{1,3}(,\d{3})+$/.test(raw.trim())) return null;
  const cleaned = raw.replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(cleaned)) return null;
  const target = Number(cleaned);
  if (!Number.isFinite(target)) return null;
  const decimals = cleaned.includes(".") ? cleaned.split(".")[1].length : 0;
  return { target, decimals };
}

function isSimpleNumericDisplay(text: string): boolean {
  return /^-?\d+(?:[.,]\d+)?\s*(?:%|points?)?$/i.test(text.trim());
}

function useCountUp(raw: string, animate: boolean): string {
  const locale = getLang() === "fr" ? "fr-FR" : "en-US";
  const parsed = parseDisplayNumber(raw);
  const target = parsed?.target ?? null;
  const decimals = parsed?.decimals ?? 0;
  const frame = useRef(0);
  const [display, setDisplay] = useState(() => {
    if (!animate || target === null || prefersReducedMotion()) return raw;
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(0);
  });

  useEffect(() => {
    if (!animate || target === null || prefersReducedMotion()) {
      setDisplay(raw);
      return;
    }
    const formatter = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    const start = performance.now();
    const duration = 900;
    setDisplay(formatter.format(0));
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(formatter.format(target * eased));
      if (progress < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        setDisplay(raw);
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [animate, decimals, raw, target]);

  return display;
}

function MetricCard({
  metric, onWhy, onExplain,
}: {
  metric: Metric;
  onWhy: () => void;
  onExplain: () => void;
}) {
  const unavailable = metric.status !== "available";
  const emptyLabel = metric.status === "placeholder" ? t("En attente de données") : t("Indisponible");
  const display = plainText(metric.display);
  const [value, unit] = splitDisplay(display);
  const animatedValue = useCountUp(
    value,
    !unavailable && isSimpleNumericDisplay(display),
  );
  return (
    <article className={`metric-card ${unavailable ? "is-unavailable" : ""}`}>
      <header>
        <span className="metric-label">{METRIC_LABELS[metric.id] ?? plainText(metric.label)}</span>
        <ChipBadge chip={metric.chip} />
      </header>
      <div className="metric-value">
        {unavailable ? (
          metric.unavailable_reason ? (
            <span className="metric-reason">{plainText(metric.unavailable_reason)}</span>
          ) : (
            display || emptyLabel
          )
        ) : (
          <>
            <span className="metric-number">
              {unit === "%" ? `${animatedValue} %` : animatedValue}
            </span>
            {unit && unit !== "%" && <span className="metric-unit">{unit}</span>}
          </>
        )}
      </div>
      <div className="metric-foot">
        <span className="muted">
          {metric.year_basis === "survey_wave"
            ? t("Année : {year} · dernière enquête", { year: metric.year ?? metric.year_requested })
            : t("Année : {year}", { year: metric.year ?? metric.year_requested })}
        </span>
        {metric.delta && <span className="delta">{plainText(metric.delta.label)}</span>}
      </div>
      <div className="metric-actions">
        <button className="why-pill why-ask" onClick={onExplain}>
          <span className="why-q" aria-hidden="true">?</span>
          {t("Pourquoi ?")}
        </button>
        <button className="why-pill" onClick={onWhy}>
          {t("Source et méthode")}
        </button>
        {metric.first_available_year && <SeeWaveButton year={metric.first_available_year} />}
        {/* rien à vérifier sur une valeur absente */}
        {metric.caveat && !unavailable && <span className="chip chip-warning">{t("À vérifier")}</span>}
      </div>
    </article>
  );
}

export function MetricsGrid({
  metrics, insights = [], xai = null, onAsk,
}: {
  metrics: Metric[];
  insights?: Insight[];
  xai?: XaiCard | null;
  onAsk?: (question: string) => void;
}) {
  const [selected, setSelected] = useState<Metric | null>(null);
  const [explained, setExplained] = useState<Metric | null>(null);
  if (metrics.length === 0) return null;
  return (
    <>
      <div className="section-head">
        <span className="eyebrow">{t("Chiffres clés")}</span>
        <span className="muted small">{t("Chaque chiffre peut être rattaché à sa source")}</span>
      </div>
      <div className={`metrics-grid${metrics.length === 2 ? " is-pair" : ""}`}>
        {metrics.map((metric) => (
          <MetricCard
            key={metric.id}
            metric={metric}
            onWhy={() => setSelected(metric)}
            onExplain={() => setExplained(metric)}
          />
        ))}
      </div>
      {selected && <WhySheet metric={selected} onClose={() => setSelected(null)} />}
      {explained && (
        <ExplainDialog
          content={buildMetricExplanation(explained, insights, xai)}
          onClose={() => setExplained(null)}
          onAsk={onAsk}
        />
      )}
    </>
  );
}

export function Insights({ items, title = "À retenir" }: { items: Insight[]; title?: string }) {
  if (items.length === 0) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>{t(title)}</h3>
        <span className="muted small">{t("Chaque constat renvoie aux chiffres utilisés")}</span>
      </div>
      <ul className="insight-list">
        {items.map((item) => (
          <li key={item.id} className={severityClass(item.severity)}>
            <span className="dot" />
            <div>
              <p>{plainText(item.statement)}</p>
              {item.evidence_ids.length > 0 && (
                <details className="evidence">
                  <summary>{t("Voir les données sources")}</summary>
                  <div className="tag-row">
                    {item.evidence_ids.map((id) => (
                      <code key={id}>{id}</code>
                    ))}
                  </div>
                </details>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ChangesPanel({ changes }: { changes: Changes | null }) {
  if (!changes || !changes.available) {
    return (
      <section className="panel">
        <div className="panel-head">
          <h3>{t("Évolutions depuis la précédente mise à jour")}</h3>
        </div>
        <p className="muted">
          {t("Aucune mise à jour antérieure comparable : l'historique démarre avec cette version.")}
        </p>
      </section>
    );
  }
  const changed = changes.items.filter((item) => item.status !== "stable");
  const stableCount = changes.items.length - changed.length;
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>{t("Évolutions depuis la précédente mise à jour")}</h3>
        <span className="muted small">
          {t("mise à jour du {date}", { date: prettyDate(changes.previous_generated_at) })}
        </span>
      </div>
      {changed.length === 0 ? (
        <p className="muted">
          {t("Aucun indicateur n'a changé depuis la mise à jour du {date}{rest}", {
            date: prettyDate(changes.previous_generated_at),
            rest:
              stableCount > 0
                ? t(" : les {count} indicateurs suivis restent identiques.", { count: stableCount })
                : ".",
          })}
        </p>
      ) : (
      <div className="table-scroll">
        <table className="data-table compact">
          <thead>
            <tr>
              <th>{t("Indicateur")}</th>
              <th>{t("Avant")}</th>
              <th>{t("Maintenant")}</th>
              <th>{t("Écart")}</th>
              <th>{t("État")}</th>
            </tr>
          </thead>
          <tbody>
            {changed.map((item) => (
              <tr key={item.metric_id}>
                <td>{METRIC_LABELS[item.metric_id] ?? plainText(item.label)}</td>
                <td>{fmtUnit(item.previous_value, item.unit)}</td>
                <td>{fmtUnit(item.current_value, item.unit)}</td>
                <td>{item.delta === null ? "—" : fmtSigned(item.delta, 2)}</td>
                <td>
                  <span className={`status status-${item.status}`}>{statusLabel(item.status)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
      {changed.length > 0 && stableCount > 0 && (
        <p className="muted small">
          {t("Les {count} autres indicateurs suivis sont restés identiques.", { count: stableCount })}
        </p>
      )}
    </section>
  );
}

export function NoticeList({ notices, title = "Précautions de lecture" }: { notices: Notice[]; title?: string }) {
  if (notices.length === 0) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{t(title)}</h3>
          <p className="muted small">
            {t("Ce qu'il faut savoir avant de citer ces chiffres.")}
          </p>
        </div>
        <span className="muted small">
          {notices.length > 1
            ? t("{count} remarques", { count: notices.length })
            : t("{count} remarque", { count: notices.length })}
        </span>
      </div>
      <ul className="notice-list">
        {notices.map((notice, index) => {
          const copy = noticeCopy(notice);
          return (
            <li key={`${notice.code}-${index}`} className={severityClass(notice.severity)}>
              <span className="dot" />
              <span>{copy.message}</span>
              <span className="notice-tag" title={notice.code}>
                {copy.tag}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function InfoValue({ item }: { item: InfoItem }) {
  if (item.status === "available" && item.value) return <>{plainText(item.value)}</>;
  if (item.status === "placeholder") return <span className="muted">{t("En attente de données")}</span>;
  return <span className="muted">{t("Indisponible")}</span>;
}

function InfoCard({ item, onExplain }: { item: InfoItem; onExplain: () => void }) {
  return (
    <article className="info-card">
      <header>
        <span className="metric-label">{INFO_LABELS[item.id] ?? plainText(item.label)}</span>
        <ChipBadge chip={item.chip} />
      </header>
      <div className="info-value">
        <InfoValue item={item} />
      </div>
      <div className="metric-foot">
        {item.year !== null && <span className="muted">{t("Année : {year}", { year: item.year })}</span>}
        {item.source && (
          <span className="muted small">
            {item.source_url ? (
              <a href={item.source_url} target="_blank" rel="noreferrer" className="link">
                {friendlySource(item.source)}
              </a>
            ) : (
              friendlySource(item.source)
            )}
          </span>
        )}
      </div>
      {item.note && <p className="note">{plainText(item.note)}</p>}
      <div className="metric-actions">
        <button className="why-pill why-ask" onClick={onExplain}>
          <span className="why-q" aria-hidden="true">?</span>
          {t("Pourquoi ?")}
        </button>
      </div>
    </article>
  );
}

export function MetricStrip({
  block, variant = "strip", onAsk,
}: {
  block: InfoBlock;
  variant?: "strip" | "cards";
  onAsk?: (question: string) => void;
}) {
  const [explained, setExplained] = useState<InfoItem | null>(null);
  const items = block.items.filter((item) => !HIDDEN_INFO_IDS.has(item.id));
  if (items.length === 0) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{plainText(block.title)}</h3>
          {block.subtitle && <p className="muted small">{plainText(block.subtitle)}</p>}
        </div>
      </div>
      <div className={variant === "cards" ? "info-grid cards" : "info-grid"}>
        {items.map((item) => (
          <InfoCard key={item.id} item={item} onExplain={() => setExplained(item)} />
        ))}
      </div>
      {explained && (
        <ExplainDialog
          content={buildInfoExplanation(explained)}
          onClose={() => setExplained(null)}
          onAsk={onAsk}
        />
      )}
    </section>
  );
}

function XaiItem({ item }: { item: Insight }) {
  return (
    <article className={`xai-item ${severityClass(item.severity)}`}>
      <p>{plainText(item.statement)}</p>
      {item.evidence_ids.length > 0 && (
        <details className="evidence">
          <summary>{t("Voir les données sources")}</summary>
          <div className="tag-row">
            {item.evidence_ids.map((id) => (
              <code key={id}>{id}</code>
            ))}
          </div>
        </details>
      )}
    </article>
  );
}

export function XaiPanel({ card }: { card: XaiCard }) {
  const title = plainText(card.title).replace(
    /^(Lecture XAI|XAI reading|قراءة تفسيرية)/,
    t("Pourquoi ces écarts ?"),
  );
  return (
    <section className="panel xai">
      <div className="panel-head">
        <div>
          <span className="eyebrow">{t("Analyse du constat")}</span>
          <h3>{title}</h3>
        </div>
        <span className="chip chip-warning">{t("Lien observé, pas une cause")}</span>
      </div>
      <div className="xai-grid">
        <div className="xai-col">
          <h4>{t("1 · Ce que montrent les données")}</h4>
          {card.evidence.map((item) => (
            <XaiItem key={item.id} item={item} />
          ))}
        </div>
        <div className="xai-col">
          <h4>{t("2 · Comment le lire")}</h4>
          {card.interpretation.map((item) => (
            <XaiItem key={item.id} item={item} />
          ))}
        </div>
        <div className="xai-col">
          <h4>{t("3 · Piste à explorer")}</h4>
          <article className="xai-item xai-hypothesis">
            <span className="eyebrow">{t("Hypothèse à tester")}</span>
            <p>{plainText(card.recommendation.statement)}</p>
            {card.recommendation.evidence_ids.length > 0 && (
              <details className="evidence">
                <summary>{t("Voir les données sources")}</summary>
                <div className="tag-row">
                  {card.recommendation.evidence_ids.map((id) => (
                    <code key={id}>{id}</code>
                  ))}
                </div>
              </details>
            )}
          </article>
        </div>
      </div>
      <p className="caveat">
        {t("Ces écarts décrivent des groupes observés : ils ne prouvent pas un lien de cause à effet.")}
      </p>
    </section>
  );
}

function PipelineNode({
  node,
}: {
  node: { id: string; label: string; status: string; detail: string };
}) {
  const copy = PIPELINE_NODES[node.id];
  return (
    <div className={`pipe-node status-${node.status}`}>
      <span className="pipe-status">{statusLabel(node.status)}</span>
      <strong>{copy?.label ?? plainText(node.label)}</strong>
      <span className="muted small">{copy?.detail ?? plainText(node.detail)}</span>
    </div>
  );
}

export function PipelineView({ block }: { block: InfoBlock }) {
  const payload = block.payload as unknown as PipelinePayload;
  const passedChecks = Object.values(payload.checks).filter((value) => value === true).length;
  return (
    <div className="pipeline-stack">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>{t("Du fichier source au tableau de bord")}</h3>
            <p className="muted small">
              {t("Chaque étape est contrôlée automatiquement avant la publication.")}
            </p>
          </div>
          <span className={`status ${payload.gate.passed ? "status-available" : "status-warning"}`}>
            {t("Qualité : {state}", { state: payload.gate.passed ? t("validée") : t("à corriger") })}
          </span>
        </div>
        <div className="pipe-route">
          <span className="eyebrow">{t("Étape 1 — Fiabiliser les données")}</span>
          <div className="pipe-row">
            {payload.route1.map((node, index) => (
              <div key={node.id} className="pipe-slot">
                {index > 0 && <span className="pipe-arrow">→</span>}
                <PipelineNode node={node} />
              </div>
            ))}
          </div>
          <div className="pipe-branch">
            <div className="branch pass">
              <strong>{t("Validé")}</strong>
              <span>{t("→ les données rejoignent la base centrale")}</span>
            </div>
            <div className="branch fail">
              <strong>{t("Anomalie")}</strong>
              <span>{t("→ arrêt de la mise à jour, aucune donnée publiée")}</span>
            </div>
          </div>
        </div>
        <div className="pipe-route">
          <span className="eyebrow">{t("Étape 2 — Calculer, expliquer, publier")}</span>
          <div className="pipe-row">
            {payload.route2.map((node, index) => (
              <div key={node.id} className="pipe-slot">
                {index > 0 && <span className="pipe-arrow">→</span>}
                <PipelineNode node={node} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="split-2">
        <section className="panel">
          <div className="panel-head">
            <h3>{t("Contrôle qualité")}</h3>
            <span className={`status ${payload.quality.passed ? "status-available" : "status-warning"}`}>
              {t("score {score} / {threshold} requis", {
                score: fmtNumber(payload.quality.score, 2),
                threshold: fmtNumber(payload.gate.threshold, 2),
              })}
            </span>
          </div>
          <table className="data-table compact">
            <thead>
              <tr>
                <th>{t("Source")}</th>
                <th>{t("Lignes")}</th>
                <th>{t("Colonnes")}</th>
                <th>{t("Score")}</th>
                <th>{t("Résultat")}</th>
              </tr>
            </thead>
            <tbody>
              {payload.quality.checks.map((check) => (
                <tr key={check.source}>
                  <td>{sourceName(check.source)}</td>
                  <td>{fmtNumber(check.rows, 0)}</td>
                  <td>{fmtNumber(check.cols, 0)}</td>
                  <td>{fmtNumber(check.score, 2)}</td>
                  <td>{check.gate ? t("Validé") : t("À corriger")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            {t("Résultat global : {state} · {count} problème(s) critique(s).", {
              state: payload.gate.passed ? t("validé") : t("à corriger"),
              count: payload.gate.critical_issues,
            })}
          </p>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3>{t("Base de données")}</h3>
            <span className="chip chip-warehouse">{t("consultation seule")}</span>
          </div>
          <dl className="kv">
            <dt>{t("Données enregistrées")}</dt>
            <dd>{fmtNumber(payload.warehouse.fact_rows, 0)}</dd>
            <dt>{t("Pays couverts")}</dt>
            <dd>{fmtNumber(payload.warehouse.countries, 0)}</dd>
            <dt>{t("Par source")}</dt>
            <dd>
              {Object.entries(payload.warehouse.by_source)
                .map(([source, rows]) => `${sourceName(source)} : ${fmtNumber(rows, 0)}`)
                .join(" · ")}
            </dd>
            <dt>{t("Signature")}</dt>
            <dd title={payload.warehouse.sha256 || ""}>{shortHash(payload.warehouse.sha256)}</dd>
            <dt>{t("Fichier")}</dt>
            <dd className="mono small" title={payload.warehouse.path}>
              {payload.warehouse.path.split(/[\\/]/).pop()}
            </dd>
          </dl>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h3>{t("Sources utilisées")}</h3>
          <span className="muted small">{t("Signatures et dates de collecte réelles")}</span>
        </div>
        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>{t("Source")}</th>
                <th>{t("Fichier")}</th>
                <th>{t("Lignes")}</th>
                <th>{t("Signature")}</th>
                <th>{t("Collecté le")}</th>
                <th>{t("Lignes écartées")}</th>
              </tr>
            </thead>
            <tbody>
              {payload.sources.map((source) => (
                <tr key={source.name}>
                  <td>{sourceName(source.name)}</td>
                  <td className="mono small" title={source.path}>
                    {source.path.split(/[\\/]/).pop()}
                  </td>
                  <td>{fmtNumber(source.rows, 0)}</td>
                  <td className="mono small" title={source.sha256 || t("non fournie")}>
                    {shortHash(source.sha256)}
                    {source.sha256_match === false && <span className="tag-warn"> {t("écart")}</span>}
                  </td>
                  <td>{prettyDate(source.collected_at)}</td>
                  <td className="small">
                    {Object.entries(source.rejected)
                      .map(([key, value]) => `${rejectedLabel(key)} : ${fmtNumber(value, 0)}`)
                      .join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="split-2">
        <section className="panel">
          <div className="panel-head">
            <h3>{t("Dernière collecte")}</h3>
          </div>
          {payload.last_run ? (
            <dl className="kv">
              <dt>{t("Identifiant")}</dt>
              <dd className="mono">{payload.last_run.run_id}</dd>
              <dt>{t("Date")}</dt>
              <dd>{prettyDate(payload.last_run.created_at)}</dd>
              <dt>{t("Période couverte")}</dt>
              <dd>
                {payload.last_run.period.min_year} – {payload.last_run.period.max_year}
              </dd>
            </dl>
          ) : (
            <p className="muted">{t("Historique indisponible.")}</p>
          )}
          <h4>{t("Traitements appliqués")}</h4>
          <ul className="chart-notes">
            {payload.transforms.map((item) => (
              <li key={item}>{plainText(item)}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3>{t("Historique des mises à jour")}</h3>
          </div>
          <div className="report-columns">
            <div>
              <h4>{t("Générations du tableau de bord")}</h4>
              <p className="muted small">
                {t("{count} génération(s) enregistrée(s).", { count: payload.reports.length })}
              </p>
              <details className="tech-details">
                <summary>{t("Voir les identifiants")}</summary>
                <ul className="plain-list">
                  {payload.reports.map((report) => (
                    <li key={report} className="mono">
                      {report}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
            <div>
              <h4>{t("Versions archivées")}</h4>
              <p className="muted small">
                {payload.history.length === 0
                  ? t("aucune version archivée")
                  : t("{count} version(s) archivée(s).", { count: payload.history.length })}
              </p>
              {payload.history.length > 0 && (
                <details className="tech-details">
                  <summary>{t("Voir les versions")}</summary>
                  <ul className="plain-list">
                    {payload.history.map((snapshot) => (
                      <li key={snapshot.file}>
                        <span className="mono">{snapshot.run_id}</span>
                        <span className="muted small">
                          {" "}
                          · {snapshot.iso3} {snapshot.year} · {prettyDate(snapshot.generated_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
          <h4>{t("Contrôles de cohérence")}</h4>
          <p className="muted small">
            {t("{passed} contrôle(s) automatique(s) réussi(s) sur {total}.", {
              passed: passedChecks,
              total: Object.keys(payload.checks).length,
            })}
          </p>
          <details className="tech-details">
            <summary>{t("Détails techniques des contrôles")}</summary>
            <div className="tag-row">
              {Object.entries(payload.checks).map(([key, value]) => (
                <code key={key}>
                  {key}:{" "}
                  {Array.isArray(value)
                    ? t("{count} valeurs", { count: value.length })
                    : String(value)}
                </code>
              ))}
            </div>
          </details>
        </section>
      </div>
    </div>
  );
}

export function ReferenceCards({ block, onAsk }: { block: InfoBlock; onAsk?: (question: string) => void }) {
  return <MetricStrip block={block} variant="cards" onAsk={onAsk} />;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  result?: AskResult;
  isError?: boolean;
}

export function AskDock({
  open, onClose, messages, busy, onAsk, suggestions, rules,
}: {
  open: boolean;
  onClose: () => void;
  messages: ChatMessage[];
  busy: boolean;
  onAsk: (question: string) => void;
  suggestions: string[];
  rules: string[];
}) {
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, open]);
  if (!open) return null;
  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    onAsk(text);
  };
  return (
    <aside className="ask-dock" aria-label={t("Ask Finova")}>
      <header>
        <div>
          <strong>{t("Ask Finova")}</strong>
          <span className="muted small">{t("Réponses fondées sur les chiffres du tableau de bord")}</span>
        </div>
        <div className="ask-head-tools">
          <kbd className="kbd" aria-hidden="true">Ctrl K</kbd>
          <button className="icon-btn" onClick={onClose} aria-label={t("Fermer le chat")}>
            ×
          </button>
        </div>
      </header>
      <div className="ask-scroll">
        {messages.length === 0 && (
          <div className="ask-empty">
            <p className="muted">
              {t("Posez une question sur le pays et l'année sélectionnés. Les réponses n'utilisent que les chiffres vérifiés du tableau de bord.")}
            </p>
            <div className="suggestions">
              {suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => onAsk(suggestion)}>
                  {plainText(suggestion)}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) =>
          message.role === "user" ? (
            <div key={index} className="bubble user">
              {message.text}
            </div>
          ) : (
            <div key={index} className={`bubble assistant ${message.isError ? "error" : ""}`}>
              <p>{plainText(message.text)}</p>
              {message.result && !message.isError && (
                <>
                  <div className="ask-badges">
                    {message.result.intent === "user_source" || message.result.facts.some((fact) => fact.user_data) ? (
                      <UserChip />
                    ) : (
                      <span className={`status ${message.result.number_check.passed ? "status-available" : "status-warning"}`}>
                        {message.result.number_check.passed
                          ? t("Chiffres vérifiés")
                          : t("Chiffres à vérifier")}
                      </span>
                    )}
                    <span className="muted small">
                      {tr(message.result.country_name)} · {message.result.year}
                    </span>
                  </div>
                  {message.result.facts.length > 0 && (
                    <div className="tag-row">
                      {message.result.facts.map((fact) => (
                        <code key={fact.id} title={fact.user_data ? `${fact.id} · ${fact.chip ?? ""}` : fact.id}
                          className={fact.user_data ? "user-fact" : undefined}>
                          {fact.user_data ? t("Vos données · ") : ""}{plainText(fact.label)} : {plainText(fact.display)} ·{" "}
                          {fact.iso3 ?? message.result!.iso3} · {fact.year}
                        </code>
                      ))}
                    </div>
                  )}
                  {message.result.user_data_policy?.reason && (
                    <p className="caveat small user-policy">{plainText(message.result.user_data_policy.reason)}</p>
                  )}
                  {message.result.caveat && <p className="caveat small">{plainText(message.result.caveat)}</p>}
                  {index === messages.length - 1 && !busy && (message.result.suggestions?.length ?? 0) > 0 && (
                    <div className="suggestions chat-suggestions">
                      {message.result.suggestions!.map((suggestion) => (
                        <button key={suggestion} onClick={() => onAsk(suggestion)}>
                          {plainText(suggestion)}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ),
        )}
        {busy && (
          <div className="bubble assistant pending typing" role="status" aria-label={t("Ask Finova écrit…")}>
            <i />
            <i />
            <i />
          </div>
        )}
        <div ref={bottom} />
      </div>
      <footer>
        <input
          value={draft}
          maxLength={500}
          placeholder={t("Écrire une question…")}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
          }}
        />
        <button className="primary-btn" onClick={submit} disabled={busy || !draft.trim()}>
          {t("Envoyer")}
        </button>
      </footer>
      {rules.length > 0 && (
        <ul className="ask-rules">
          {rules.map((rule) => (
            <li key={rule}>{friendlyRule(rule)}</li>
          ))}
        </ul>
      )}
    </aside>
  );
}

export function AskInline({ block, onAsk }: { block: InfoBlock; onAsk: (question: string) => void }) {
  const payload = block.payload as unknown as AskPayload;
  return (
    <section className="panel ask-inline">
      <div className="panel-head">
        <div>
          <h3>{plainText(block.title)}</h3>
          {block.subtitle && <p className="muted small">{plainText(block.subtitle)}</p>}
        </div>
        <span className="chip chip-semantic">{t("Réponse automatique")}</span>
      </div>
      <div className="suggestions">
        {payload.suggestions.map((suggestion) => (
          <button key={suggestion} onClick={() => onAsk(suggestion)}>
            {plainText(suggestion)}
          </button>
        ))}
      </div>
      <ul className="chart-notes">
        {payload.rules.map((rule) => (
          <li key={rule}>{friendlyRule(rule)}</li>
        ))}
      </ul>
    </section>
  );
}

export function YearDisclosure({ chart }: { chart: Chart }) {
  const years = Array.from(
    new Set(chart.series.flatMap((item) => item.points.filter((point) => point.value !== null).map((point) => point.year))),
  ).sort();
  if (years.length === 0) return null;
  return (
    <span className="muted small">
      {t("Années observées : {years}", { years: years.join(", ") })}
    </span>
  );
}
