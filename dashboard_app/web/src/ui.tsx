import { useEffect, useMemo, useRef, useState } from "react";
import type {
  AskPayload, AskResult, Changes, Chart, InfoBlock, InfoItem, Insight, Metric,
  Notice, PipelinePayload, SimulatorPayload, XaiCard,
} from "./types";
import {
  fmtNumber, fmtPct, fmtSigned, fmtUnit, prettyDate, providerLabel, severityClass,
  shortHash, statusLabel, unitLabel,
} from "./format";
import {
  DEFINITION_STATUS, INFO_LABELS, METRIC_LABELS,
  PIPELINE_NODES, REVIEW_REASONS, chipLabel, chipNeedsReview, chipTitle, friendlyCaveat, friendlyDefinition,
  friendlyFilter, friendlyRule, friendlySource, noticeCopy, plainText, rejectedLabel, sourceName,
} from "./copy";

export function ChipBadge({ chip }: { chip: Metric["chip"] | InfoItem["chip"] | null }) {
  if (!chip) return null;
  return (
    <span className={`chip chip-${chip.provider}`} title={chipTitle(chip)}>
      {chipLabel(chip)}
      {chipNeedsReview(chip) && <span className="chip-review"> · à vérifier</span>}
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
            <span className="eyebrow">D'où vient ce chiffre ?</span>
            <h3>{METRIC_LABELS[metric.id] ?? plainText(metric.label)}</h3>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer">
            ×
          </button>
        </div>
        <div className="sheet-value">
          <strong>{plainText(metric.display)}</strong>
          <span className="muted">
            année utilisée : {why?.year_used ?? metric.year} · {providerLabel(metric.provider)}
          </span>
        </div>
        <dl className="why-grid">
          <dt>Ce que mesure l'indicateur</dt>
          <dd>{friendlyDefinition(metric.id, why?.definition ?? null)}</dd>
          <dt>Source</dt>
          <dd>
            {friendlySource(why?.source ?? null)}
            {why?.source_url && (
              <a href={why.source_url} target="_blank" rel="noreferrer" className="link">
                consulter la source
              </a>
            )}
          </dd>
          <dt>Périmètre</dt>
          <dd>{friendlyFilter(why?.filter ?? null)}</dd>
          <dt>Fiabilité de la définition</dt>
          <dd>
            {(DEFINITION_STATUS[why?.definition_status ?? ""] ??
              plainText(why?.definition_status)) || "—"}
          </dd>
          <dt>Année réellement utilisée</dt>
          <dd>{why?.year_used ?? metric.year}</dd>
          <dt>Repère de provenance</dt>
          <dd>
            <ChipBadge chip={metric.chip} />
          </dd>
        </dl>
        {why && why.review_reasons.length > 0 && (
          <div className="why-reasons">
            <span className="eyebrow">Points à vérifier</span>
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
          Aucun chiffre n'est recalculé dans l'interface : la valeur et l'année proviennent
          directement des données source.
        </p>
        <details className="tech-details">
          <summary>Détails techniques (pour vérification)</summary>
          <dl className="why-grid">
            <dt>Identifiant</dt>
            <dd className="mono small">{metric.id}</dd>
            <dt>Définition d'origine</dt>
            <dd>{why?.definition || "—"}</dd>
            <dt>Source d'origine</dt>
            <dd>{why?.source || "—"}</dd>
            <dt>Filtre d'origine</dt>
            <dd>{why?.filter || "—"}</dd>
            <dt>Statut d'origine</dt>
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

function MetricCard({ metric, onWhy }: { metric: Metric; onWhy: () => void }) {
  const unavailable = metric.status !== "available";
  const emptyLabel = metric.status === "placeholder" ? "En attente de données" : "Indisponible";
  const display = plainText(metric.display);
  const [value, unit] = splitDisplay(display);
  return (
    <article className={`metric-card ${unavailable ? "is-unavailable" : ""}`}>
      <header>
        <span className="metric-label">{METRIC_LABELS[metric.id] ?? plainText(metric.label)}</span>
        <ChipBadge chip={metric.chip} />
      </header>
      <div className="metric-value">
        {unavailable ? (
          display || emptyLabel
        ) : (
          <>
            <span className="metric-number">
              {unit === "%" ? `${value} %` : value}
            </span>
            {unit && unit !== "%" && <span className="metric-unit">{unit}</span>}
          </>
        )}
      </div>
      <div className="metric-foot">
        <span className="muted">Année : {metric.year}</span>
        {metric.delta && <span className="delta">{plainText(metric.delta.label)}</span>}
      </div>
      <div className="metric-actions">
        <button className="why-pill" onClick={onWhy}>
          Source et méthode
        </button>
        {metric.caveat && <span className="chip chip-warning">À vérifier</span>}
      </div>
    </article>
  );
}

export function MetricsGrid({ metrics }: { metrics: Metric[] }) {
  const [selected, setSelected] = useState<Metric | null>(null);
  if (metrics.length === 0) return null;
  return (
    <>
      <div className="section-head">
        <span className="eyebrow">Chiffres clés</span>
        <span className="muted small">Chaque chiffre peut être rattaché à sa source</span>
      </div>
      <div className="metrics-grid">
        {metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} onWhy={() => setSelected(metric)} />
        ))}
      </div>
      {selected && <WhySheet metric={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

export function Insights({ items, title = "À retenir" }: { items: Insight[]; title?: string }) {
  if (items.length === 0) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <span className="muted small">Chaque constat renvoie aux chiffres utilisés</span>
      </div>
      <ul className="insight-list">
        {items.map((item) => (
          <li key={item.id} className={severityClass(item.severity)}>
            <span className="dot" />
            <div>
              <p>{plainText(item.statement)}</p>
              {item.evidence_ids.length > 0 && (
                <details className="evidence">
                  <summary>Voir les données sources</summary>
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
          <h3>Évolutions depuis la précédente mise à jour</h3>
        </div>
        <p className="muted">
          Aucune mise à jour antérieure comparable : l'historique démarre avec cette version.
        </p>
      </section>
    );
  }
  const changed = changes.items.filter((item) => item.status !== "stable");
  const stableCount = changes.items.length - changed.length;
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Évolutions depuis la précédente mise à jour</h3>
        <span className="muted small">
          mise à jour du {prettyDate(changes.previous_generated_at)}
        </span>
      </div>
      {changed.length === 0 ? (
        <p className="muted">
          Aucun indicateur n'a changé depuis la mise à jour du{" "}
          {prettyDate(changes.previous_generated_at)}
          {stableCount > 0 ? ` : les ${stableCount} indicateurs suivis restent identiques.` : "."}
        </p>
      ) : (
      <div className="table-scroll">
        <table className="data-table compact">
          <thead>
            <tr>
              <th>Indicateur</th>
              <th>Avant</th>
              <th>Maintenant</th>
              <th>Écart</th>
              <th>État</th>
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
          Les {stableCount} autres indicateurs suivis sont restés identiques.
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
          <h3>{title}</h3>
          <p className="muted small">
            Ce qu'il faut savoir avant de citer ces chiffres.
          </p>
        </div>
        <span className="muted small">
          {notices.length} remarque{notices.length > 1 ? "s" : ""}
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
  if (item.status === "placeholder") return <span className="muted">En attente de données</span>;
  return <span className="muted">Indisponible</span>;
}

function InfoCard({ item }: { item: InfoItem }) {
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
        {item.year !== null && <span className="muted">Année : {item.year}</span>}
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
    </article>
  );
}

export function MetricStrip({ block, variant = "strip" }: { block: InfoBlock; variant?: "strip" | "cards" }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{plainText(block.title)}</h3>
          {block.subtitle && <p className="muted small">{plainText(block.subtitle)}</p>}
        </div>
      </div>
      <div className={variant === "cards" ? "info-grid cards" : "info-grid"}>
        {block.items.map((item) => (
          <InfoCard key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}

export function Simulator({ block }: { block: InfoBlock }) {
  const payload = block.payload as unknown as SimulatorPayload;
  const [fee, setFee] = useState<string>(String(payload.default_fee_tnd));
  const smig = payload.smig_reference;
  const share = useMemo(() => {
    const value = Number(fee.replace(",", "."));
    if (!Number.isFinite(value) || value < 0) return null;
    return (value / smig.value) * 100;
  }, [fee, smig.value]);
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{plainText(block.title)}</h3>
          {block.subtitle && <p className="muted small">{plainText(block.subtitle)}</p>}
        </div>
        <span className="chip chip-derived">Calcul instantané</span>
      </div>
      <div className="simulator">
        <label>
          Frais mensuels du compte (TND)
          <input
            type="number"
            min={0}
            step={0.5}
            value={fee}
            onChange={(event) => setFee(event.target.value)}
          />
        </label>
        <div className="sim-result">
          <span className="muted">Part du SMIG mensuel</span>
          <strong>{share === null ? "—" : `${fmtNumber(share, 2)} %`}</strong>
        </div>
        <div className="sim-reference">
          <span>
            SMIG de référence {smig.year} : <strong>{fmtNumber(smig.value, 2)} TND/mois</strong>
          </span>
          <span className="muted small">{friendlySource(smig.source)}</span>
        </div>
      </div>
      <p className="sim-formula">
        Calcul : part du SMIG = frais mensuels ÷ SMIG mensuel × 100
      </p>
      <ul className="chart-notes">
        {payload.rules.map((rule) => (
          <li key={rule}>{friendlyRule(rule)}</li>
        ))}
      </ul>
    </section>
  );
}

function XaiItem({ item }: { item: Insight }) {
  return (
    <article className={`xai-item ${severityClass(item.severity)}`}>
      <p>{plainText(item.statement)}</p>
      {item.evidence_ids.length > 0 && (
        <details className="evidence">
          <summary>Voir les données sources</summary>
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
  const title = plainText(card.title).replace("Lecture XAI", "Pourquoi ces écarts ?");
  return (
    <section className="panel xai">
      <div className="panel-head">
        <div>
          <span className="eyebrow">Analyse du constat</span>
          <h3>{title}</h3>
        </div>
        <span className="chip chip-warning">Lien observé, pas une cause</span>
      </div>
      <div className="xai-grid">
        <div className="xai-col">
          <h4>1 · Ce que montrent les données</h4>
          {card.evidence.map((item) => (
            <XaiItem key={item.id} item={item} />
          ))}
        </div>
        <div className="xai-col">
          <h4>2 · Comment le lire</h4>
          {card.interpretation.map((item) => (
            <XaiItem key={item.id} item={item} />
          ))}
        </div>
        <div className="xai-col">
          <h4>3 · Piste à explorer</h4>
          <article className="xai-item xai-hypothesis">
            <span className="eyebrow">Hypothèse à tester</span>
            <p>{plainText(card.recommendation.statement)}</p>
            {card.recommendation.evidence_ids.length > 0 && (
              <details className="evidence">
                <summary>Voir les données sources</summary>
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
        Ces écarts décrivent des groupes observés : ils ne prouvent pas un lien de cause à
        effet.
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
            <h3>Du fichier source au tableau de bord</h3>
            <p className="muted small">
              Chaque étape est contrôlée automatiquement avant la publication.
            </p>
          </div>
          <span className={`status ${payload.gate.passed ? "status-available" : "status-warning"}`}>
            Qualité : {payload.gate.passed ? "validée" : "à corriger"}
          </span>
        </div>
        <div className="pipe-route">
          <span className="eyebrow">Étape 1 — Fiabiliser les données</span>
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
              <strong>Validé</strong>
              <span>→ les données rejoignent la base centrale</span>
            </div>
            <div className="branch fail">
              <strong>Anomalie</strong>
              <span>→ arrêt de la mise à jour, aucune donnée publiée</span>
            </div>
          </div>
        </div>
        <div className="pipe-route">
          <span className="eyebrow">Étape 2 — Calculer, expliquer, publier</span>
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
            <h3>Contrôle qualité</h3>
            <span className={`status ${payload.quality.passed ? "status-available" : "status-warning"}`}>
              score {fmtNumber(payload.quality.score, 2)} / {fmtNumber(payload.gate.threshold, 2)} requis
            </span>
          </div>
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Lignes</th>
                <th>Colonnes</th>
                <th>Score</th>
                <th>Résultat</th>
              </tr>
            </thead>
            <tbody>
              {payload.quality.checks.map((check) => (
                <tr key={check.source}>
                  <td>{sourceName(check.source)}</td>
                  <td>{fmtNumber(check.rows, 0)}</td>
                  <td>{fmtNumber(check.cols, 0)}</td>
                  <td>{fmtNumber(check.score, 2)}</td>
                  <td>{check.gate ? "Validé" : "À corriger"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Résultat global : {payload.gate.passed ? "validé" : "à corriger"} ·{" "}
            {payload.gate.critical_issues} problème(s) critique(s).
          </p>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3>Base de données</h3>
            <span className="chip chip-warehouse">consultation seule</span>
          </div>
          <dl className="kv">
            <dt>Données enregistrées</dt>
            <dd>{fmtNumber(payload.warehouse.fact_rows, 0)}</dd>
            <dt>Pays couverts</dt>
            <dd>{fmtNumber(payload.warehouse.countries, 0)}</dd>
            <dt>Par source</dt>
            <dd>
              {Object.entries(payload.warehouse.by_source)
                .map(([source, rows]) => `${sourceName(source)} : ${fmtNumber(rows, 0)}`)
                .join(" · ")}
            </dd>
            <dt>Signature</dt>
            <dd title={payload.warehouse.sha256 || ""}>{shortHash(payload.warehouse.sha256)}</dd>
            <dt>Fichier</dt>
            <dd className="mono small" title={payload.warehouse.path}>
              {payload.warehouse.path.split(/[\\/]/).pop()}
            </dd>
          </dl>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h3>Sources utilisées</h3>
          <span className="muted small">Signatures et dates de collecte réelles</span>
        </div>
        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Fichier</th>
                <th>Lignes</th>
                <th>Signature</th>
                <th>Collecté le</th>
                <th>Lignes écartées</th>
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
                  <td className="mono small" title={source.sha256 || "non fournie"}>
                    {shortHash(source.sha256)}
                    {source.sha256_match === false && <span className="tag-warn"> écart</span>}
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
            <h3>Dernière collecte</h3>
          </div>
          {payload.last_run ? (
            <dl className="kv">
              <dt>Identifiant</dt>
              <dd className="mono">{payload.last_run.run_id}</dd>
              <dt>Date</dt>
              <dd>{prettyDate(payload.last_run.created_at)}</dd>
              <dt>Période couverte</dt>
              <dd>
                {payload.last_run.period.min_year} – {payload.last_run.period.max_year}
              </dd>
            </dl>
          ) : (
            <p className="muted">Historique indisponible.</p>
          )}
          <h4>Traitements appliqués</h4>
          <ul className="chart-notes">
            {payload.transforms.map((item) => (
              <li key={item}>{plainText(item)}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3>Historique des mises à jour</h3>
          </div>
          <div className="report-columns">
            <div>
              <h4>Générations du tableau de bord</h4>
              <p className="muted small">
                {payload.reports.length} génération(s) enregistrée(s).
              </p>
              <details className="tech-details">
                <summary>Voir les identifiants</summary>
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
              <h4>Versions archivées</h4>
              <p className="muted small">
                {payload.history.length === 0
                  ? "aucune version archivée"
                  : `${payload.history.length} version(s) archivée(s).`}
              </p>
              {payload.history.length > 0 && (
                <details className="tech-details">
                  <summary>Voir les versions</summary>
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
          <h4>Contrôles de cohérence</h4>
          <p className="muted small">
            {passedChecks} contrôle(s) automatique(s) réussi(s) sur {Object.keys(payload.checks).length}.
          </p>
          <details className="tech-details">
            <summary>Détails techniques des contrôles</summary>
            <div className="tag-row">
              {Object.entries(payload.checks).map(([key, value]) => (
                <code key={key}>
                  {key}: {Array.isArray(value) ? `${value.length} valeurs` : String(value)}
                </code>
              ))}
            </div>
          </details>
        </section>
      </div>
    </div>
  );
}

export function ReferenceCards({ block }: { block: InfoBlock }) {
  return <MetricStrip block={block} variant="cards" />;
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
    <aside className="ask-dock" aria-label="Ask Finova">
      <header>
        <div>
          <strong>Ask Finova</strong>
          <span className="muted small">Réponses fondées sur les chiffres du tableau de bord</span>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Fermer le chat">
          ×
        </button>
      </header>
      <div className="ask-scroll">
        {messages.length === 0 && (
          <div className="ask-empty">
            <p className="muted">
              Posez une question sur le pays et l'année sélectionnés. Les réponses
              n'utilisent que les chiffres vérifiés du tableau de bord.
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
                    <span className={`status ${message.result.number_check.passed ? "status-available" : "status-warning"}`}>
                      {message.result.number_check.passed
                        ? "Chiffres vérifiés"
                        : "Chiffres à vérifier"}
                    </span>
                    <span className="muted small">
                      {message.result.country_name} · {message.result.year}
                    </span>
                  </div>
                  {message.result.facts.length > 0 && (
                    <div className="tag-row">
                      {message.result.facts.map((fact) => (
                        <code key={fact.id} title={fact.id}>
                          {plainText(fact.label)} : {plainText(fact.display)} ({fact.year})
                        </code>
                      ))}
                    </div>
                  )}
                  {message.result.caveat && <p className="caveat small">{plainText(message.result.caveat)}</p>}
                </>
              )}
            </div>
          ),
        )}
        {busy && <div className="bubble assistant pending">Recherche dans les chiffres…</div>}
        <div ref={bottom} />
      </div>
      <footer>
        <input
          value={draft}
          maxLength={500}
          placeholder="Écrire une question…"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
          }}
        />
        <button className="primary-btn" onClick={submit} disabled={busy || !draft.trim()}>
          Envoyer
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
        <span className="chip chip-semantic">Réponse automatique</span>
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
      Années observées : {years.join(", ")}
    </span>
  );
}
