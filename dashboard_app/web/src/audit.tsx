import { useEffect, useState } from "react";
import { ApiError } from "./api";

// ------------------------------------------------------------------ types
interface AuditInsight {
  insight_id: string;
  accepted: boolean | null;
  reasons: string[];
  statement: string | null;
  cited: { kpi_id: string; kpi: string; iso3: string; year: number }[];
}

interface AuditSummary {
  verdict: string;
  counts: { pass: number; warn: number; fail: number };
  run_id: string;
  snapshot_id: string;
  created_at: string;
  catalog_version: string;
  publication: { approved: number; approved_with_review_note: number; blocked: number };
  review_reasons: { reason: string; label: string; rows: number }[];
  insight_audit: {
    run_id: string; created_at: string; audited: number; accepted: number; rejected: number;
    not_auditable: number; insights: AuditInsight[];
  };
  evaluation: {
    available: boolean; created_at: string | null; stale: boolean; detected: number | null; total: number | null;
    faults: { id: string; label: string; expected_check: string; detected: boolean; verdict: string; failing_checks: string[] }[];
  };
}

interface AuditCheck {
  check_id: string;
  category: string;
  result: "pass" | "warn" | "fail";
  description: string;
  detail: string;
  affects_publication: boolean;
  user_sources: boolean;
  affected_count: number;
  affected_rows: Record<string, unknown>[];
  truncated: boolean;
}

interface Explanation {
  kpi_id: string;
  kpi_name: string;
  iso3: string;
  country: string;
  year: number;
  value: number | null;
  unit: string;
  availability_status: string;
  reason: string | null;
  definition: string;
  formula: string;
  transformation: string;
  snapshot_id: string;
  catalog_version: string;
  publication_status: string;
  review_reasons: string[];
  inputs: {
    role: string; fact_value: number | null; fact_unit: string; status: string;
    raw?: { source: string; file: string; column: string; raw_value_text: string; record_key: Record<string, unknown> };
  }[];
  checks_touching: { check_id: string; result: string; affects_publication: boolean }[];
  checks_passed: string[];
  narrative: string | null;
}

interface Options {
  kpis: { kpi_id: string; label: string }[];
  countries: string[];
  years: number[];
}

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = `Erreur HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* message HTTP conserve */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

// ------------------------------------------------------------------ libelles
const VERDICTS: Record<string, string> = {
  pass: "Audit réussi",
  pass_with_warnings: "Audit réussi avec avertissements",
  fail: "Audit en échec",
};
const RESULTS: Record<string, { label: string; className: string }> = {
  pass: { label: "Réussi", className: "status-available" },
  warn: { label: "Avertissement", className: "status-warning" },
  fail: { label: "Échec", className: "status-removed" },
};
const STATUS_FR: Record<string, string> = {
  approved: "approuvée",
  approved_with_review_note: "approuvée avec réserve",
  blocked: "bloquée",
  not_evaluated: "non évaluée",
};

function date(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
}

function num(value: number | null | undefined, digits = 4): string {
  return value === null || value === undefined ? "—" : value.toLocaleString("fr-FR", { maximumFractionDigits: digits });
}

function rowText(row: Record<string, unknown>): string {
  return Object.entries(row)
    .map(([key, value]) => `${key} : ${Array.isArray(value) ? value.join(", ") : String(value)}`)
    .join(" · ");
}

// ------------------------------------------------------------------ page
export function AuditPage() {
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [checks, setChecks] = useState<AuditCheck[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    Promise.all([get<AuditSummary>("/api/audit/summary"), get<{ checks: AuditCheck[] }>("/api/audit/checks")])
      .then(([data, list]) => {
        setSummary(data);
        setChecks(list.checks);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : String(err)));
  }, []);

  return (
    <div className="page audit-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Données officielles uniquement</span>
          <h2>Audit et confiance</h2>
          <p className="page-sub">
            Comment chaque chiffre publié est vérifié : contrôles indépendants, publication, constats
            et test de l'Auditor par injection de fautes. Les sources utilisateur ne sont pas comptées ici.
          </p>
        </div>
      </header>
      {error && <div className="error-card"><p>{error}</p></div>}
      {!summary && !error && <p className="muted">Chargement du rapport d'audit…</p>}
      {summary && (
        <>
          <VerdictBanner summary={summary} />
          <PublicationPanel summary={summary} />
          <ChecksPanel checks={checks} />
          <InsightsPanel summary={summary} />
          <ExplainPanel />
          <EvaluationPanel summary={summary} />
        </>
      )}
    </div>
  );
}

function VerdictBanner({ summary }: { summary: AuditSummary }) {
  const tone = summary.verdict === "fail" ? "fail" : summary.verdict === "pass" ? "pass" : "warn";
  return (
    <section className={`panel verdict-banner verdict-${tone}`}>
      <div>
        <span className="eyebrow">Verdict</span>
        <h3>{VERDICTS[summary.verdict] ?? summary.verdict}</h3>
        <div className="verdict-counts">
          <span className="status status-available">{summary.counts.pass} réussis</span>
          <span className="status status-warning">{summary.counts.warn} avertissements</span>
          <span className={`status ${summary.counts.fail ? "status-removed" : "status-available"}`}>{summary.counts.fail} échec</span>
        </div>
      </div>
      <dl className="verdict-meta">
        <dt>Run</dt><dd><code>{summary.run_id}</code></dd>
        <dt>Version des données</dt><dd>{summary.snapshot_id}</dd>
        <dt>Catalogue</dt><dd>{summary.catalog_version}</dd>
        <dt>Date</dt><dd>{date(summary.created_at)}</dd>
      </dl>
    </section>
  );
}

function PublicationPanel({ summary }: { summary: AuditSummary }) {
  const pub = summary.publication;
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>Publication des valeurs</h3>
          <p className="muted small">Statut attribué par l'Auditor à chaque valeur d'indicateur (pays × année).</p>
        </div>
      </div>
      <div className="check-stats">
        <div><span className="muted small">Approuvé</span><strong>{num(pub.approved)}</strong></div>
        <div><span className="muted small">Approuvé avec réserve</span><strong>{num(pub.approved_with_review_note)}</strong></div>
        <div><span className="muted small">Bloqué</span><strong>{num(pub.blocked)}</strong></div>
      </div>
      {summary.review_reasons.length > 0 && (
        <p className="muted small reason-line">
          Motifs des réserves :{" "}
          {summary.review_reasons.map((item) => `${item.label} (${item.reason}) : ${num(item.rows)}`).join(" · ")}
        </p>
      )}
    </section>
  );
}

function ChecksPanel({ checks }: { checks: AuditCheck[] }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>Contrôles de l'Auditor</h3>
          <p className="muted small">Chaque contrôle est recalculé indépendamment du pipeline.</p>
        </div>
        <span className="muted small">{checks.length} contrôles</span>
      </div>
      <table className="data-table audit-checks">
        <thead><tr><th>Contrôle</th><th>Ce qui est vérifié</th><th>Résultat</th><th>Lignes</th></tr></thead>
        <tbody>
          {checks.map((check) => (
            <tr key={check.check_id}>
              <td><code>{check.check_id.split("_")[0]}</code></td>
              <td>
                {check.description}
                {check.user_sources && <span className="chip chip-user">Sources utilisateur</span>}
                <details className="tech-details">
                  <summary>Détail{check.affected_count ? ` et lignes concernées (${check.affected_count})` : ""}</summary>
                  <p className="muted small">{check.detail}</p>
                  {check.affected_rows.length > 0 && (
                    <ul className="affected-rows">
                      {check.affected_rows.map((row, index) => <li key={index}>{rowText(row)}</li>)}
                    </ul>
                  )}
                  {check.truncated && <p className="muted small">Liste limitée aux 200 premières lignes.</p>}
                </details>
              </td>
              <td><span className={`status ${RESULTS[check.result]?.className ?? ""}`}>{RESULTS[check.result]?.label ?? check.result}</span></td>
              <td>{check.affected_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function InsightsPanel({ summary }: { summary: AuditSummary }) {
  const audit = summary.insight_audit;
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>Audit des constats</h3>
          <p className="muted small">Chaque nombre d'un constat doit être une valeur publiée, son année ou un écart entre deux valeurs du même indicateur.</p>
        </div>
      </div>
      <div className="check-stats">
        <div><span className="muted small">Audités</span><strong>{audit.audited}</strong></div>
        <div><span className="muted small">Acceptés</span><strong>{audit.accepted}</strong></div>
        <div><span className="muted small">Rejetés</span><strong>{audit.rejected}</strong></div>
        <div><span className="muted small">Non auditables</span><strong>{audit.not_auditable}</strong></div>
      </div>
      <ul className="audit-insights">
        {audit.insights.map((item) => (
          <li key={item.insight_id}>
            <span className={`status ${item.accepted === true ? "status-available" : item.accepted === false ? "status-removed" : "status-placeholder"}`}>
              {item.accepted === true ? "Accepté" : item.accepted === false ? "Rejeté" : "Non auditable"}
            </span>
            <div>
              <p>{item.statement ?? item.insight_id}</p>
              {item.cited.length > 0 && (
                <div className="tag-row">
                  {item.cited.map((claim, index) => (
                    <code key={index}>{claim.kpi} · {claim.iso3} · {claim.year}</code>
                  ))}
                </div>
              )}
              {item.reasons.length > 0 && <p className="muted small">{item.reasons.join(" ; ")}</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ExplainPanel() {
  const [options, setOptions] = useState<Options | null>(null);
  const [kpi, setKpi] = useState("account_ownership");
  const [iso3, setIso3] = useState("TUN");
  const [year, setYear] = useState(2024);
  const [record, setRecord] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    get<Options>("/api/audit/options").then(setOptions).catch(() => setOptions(null));
  }, []);
  useEffect(() => {
    setError(null);
    get<Explanation>(`/api/audit/explain?kpi_id=${encodeURIComponent(kpi)}&iso3=${encodeURIComponent(iso3)}&year=${year}`)
      .then(setRecord)
      .catch((err) => {
        setRecord(null);
        setError(err instanceof ApiError ? err.detail : String(err));
      });
  }, [kpi, iso3, year]);
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>Comment un chiffre est vérifié</h3>
          <p className="muted small">Choisissez un indicateur, un pays et une année : la valeur est retracée jusqu'au fichier source.</p>
        </div>
      </div>
      <div className="data-filters">
        <label className="select">
          <span className="sr-only">Indicateur</span>
          <select value={kpi} onChange={(event) => setKpi(event.target.value)} title="Indicateur">
            {(options?.kpis ?? [{ kpi_id: kpi, label: kpi }]).map((item) => <option key={item.kpi_id} value={item.kpi_id}>{item.label}</option>)}
          </select>
        </label>
        <label className="select">
          <span className="sr-only">Pays</span>
          <select value={iso3} onChange={(event) => setIso3(event.target.value)} title="Pays">
            {(options?.countries ?? [iso3]).map((code) => <option key={code} value={code}>{code}</option>)}
          </select>
        </label>
        <label className="select">
          <span className="sr-only">Année</span>
          <select value={year} onChange={(event) => setYear(Number(event.target.value))} title="Année">
            {(options?.years ?? [year]).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="muted">{error}</p>}
      {record && (
        <ol className="trace">
          <li>
            <strong>Valeur publiée</strong>
            <span>{record.kpi_name} · {record.country} ({record.iso3}) · {record.year} : {record.value === null ? `indisponible (${record.reason ?? "non observée"})` : `${num(record.value)} (${record.unit})`}</span>
          </li>
          <li>
            <strong>Sources lues</strong>
            {record.inputs.length === 0 && <span className="muted">Aucune observation : la valeur reste vide.</span>}
            {record.inputs.map((input, index) => (
              <span key={index}>
                {input.raw
                  ? `${input.raw.source} · fichier ${input.raw.file} · colonne ${input.raw.column} · texte brut « ${input.raw.raw_value_text} »`
                  : `${input.role} : ${num(input.fact_value)} ${input.fact_unit}`}
              </span>
            ))}
          </li>
          <li><strong>Formule</strong><span><code>{record.formula}</code> — {record.transformation}</span></li>
          <li><strong>Valeur recalculée</strong><span>{record.value === null ? "—" : num(record.value)} · version des données {record.snapshot_id} · catalogue {record.catalog_version}</span></li>
          <li>
            <strong>Contrôles</strong>
            <span>{record.checks_passed.length} contrôles réussis sur cette valeur
              {record.checks_touching.length > 0 && ` ; à noter : ${record.checks_touching.map((c) => `${c.check_id} (${RESULTS[c.result]?.label ?? c.result})`).join(", ")}`}
            </span>
          </li>
          <li><strong>Publication</strong><span>Valeur {STATUS_FR[record.publication_status] ?? record.publication_status}{record.review_reasons.length ? ` (${record.review_reasons.join(", ")})` : ""}</span></li>
        </ol>
      )}
    </section>
  );
}

function EvaluationPanel({ summary }: { summary: AuditSummary }) {
  const evaluation = summary.evaluation;
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>Test de l'Auditor par injection de fautes</h3>
          <p className="muted small">
            Des erreurs sont introduites dans une copie des données ; l'Auditor doit les détecter.
            Évaluation du {date(evaluation.created_at)}.
          </p>
        </div>
        {evaluation.available && <span className="status status-available">{evaluation.detected} / {evaluation.total} détectées</span>}
      </div>
      {evaluation.stale && (
        <div className="generated-banner">Résultat antérieur au dernier audit : relancez scripts/evaluate_auditor.py pour le mettre à jour.</div>
      )}
      {!evaluation.available && <p className="muted">Aucune évaluation enregistrée.</p>}
      {evaluation.available && (
        <table className="data-table">
          <thead><tr><th>Faute injectée</th><th>Contrôle attendu</th><th>Détectée</th><th>Verdict obtenu</th></tr></thead>
          <tbody>
            {evaluation.faults.map((fault) => (
              <tr key={fault.id}>
                <td>{fault.label}</td>
                <td><code>{fault.expected_check}</code></td>
                <td><span className={`status ${fault.detected ? "status-available" : "status-removed"}`}>{fault.detected ? "Oui" : "Non"}</span></td>
                <td>{VERDICTS[fault.verdict] ?? fault.verdict}{fault.failing_checks.length ? ` (${fault.failing_checks.join(", ")})` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
