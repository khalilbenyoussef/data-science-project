import { PdfDownload } from "./pdf";
import { useEffect, useState } from "react";
import { ApiError } from "./api";
import { apiFetch } from "./auth";
import { t } from "./i18n";
import { getLang } from "./preferences";
import { unitLabel } from "./format";
import { plainText } from "./copy";

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
    faults: {
      id: string; label: string; expected_check: string; expected_check_name?: string; detected: boolean;
      verdict: string; failing_checks: string[];
    }[];
    insight_faults_note?: string | null;
  };
}

interface AuditCheck {
  check_id: string;
  name?: string;
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
  const response = await apiFetch(url);
  if (!response.ok) {
    let detail = t("Erreur HTTP {status}", { status: response.status });
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
  const locale = getLang() === "fr" ? "fr-FR" : "en-GB";
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

function num(value: number | null | undefined, digits = 4): string {
  return value === null || value === undefined
    ? "—"
    : value.toLocaleString(getLang() === "fr" ? "fr-FR" : "en-US", { maximumFractionDigits: digits });
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
          <span className="eyebrow">{t("Données officielles uniquement")}</span>
          <h2>{t("Audit et confiance")}</h2>
          <p className="page-sub">
            {t("Comment chaque chiffre publié est vérifié : contrôles indépendants, publication, constats et test de l'Auditor par injection de fautes. Les sources utilisateur ne sont pas comptées ici.")}
          </p>
        </div>
        <div className="page-head-badges">
          <PdfDownload href="/api/reports/evaluation.pdf"
                       title={t("Rapport d'évaluation et d'explicabilité, construit à partir des données courantes")} />
        </div>
      </header>
      {error && <div className="error-card"><p>{t(error)}</p></div>}
      {!summary && !error && <p className="muted">{t("Chargement du rapport d'audit…")}</p>}
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
        <span className="eyebrow">{t("Verdict")}</span>
        <h3>{t(VERDICTS[summary.verdict] ?? summary.verdict)}</h3>
        <div className="verdict-counts">
          <span className="status status-available">{t("{count} réussis", { count: summary.counts.pass })}</span>
          <span className="status status-warning">{t("{count} avertissements", { count: summary.counts.warn })}</span>
          <span className={`status ${summary.counts.fail ? "status-removed" : "status-available"}`}>{t("{count} échec", { count: summary.counts.fail })}</span>
        </div>
      </div>
      <dl className="verdict-meta">
        <dt>{t("Run")}</dt><dd><code>{summary.run_id}</code></dd>
        <dt>{t("Version des données")}</dt><dd>{summary.snapshot_id}</dd>
        <dt>{t("Catalogue")}</dt><dd>{summary.catalog_version}</dd>
        <dt>{t("Date")}</dt><dd>{date(summary.created_at)}</dd>
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
          <h3>{t("Publication des valeurs")}</h3>
          <p className="muted small">{t("Statut attribué par l'Auditor à chaque valeur d'indicateur (pays × année).")}</p>
        </div>
      </div>
      <div className="check-stats">
        <div><span className="muted small">{t("Approuvé")}</span><strong>{num(pub.approved)}</strong></div>
        <div><span className="muted small">{t("Approuvé avec réserve")}</span><strong>{num(pub.approved_with_review_note)}</strong></div>
        <div><span className="muted small">{t("Bloqué")}</span><strong>{num(pub.blocked)}</strong></div>
      </div>
      {summary.review_reasons.length > 0 && (
        <p className="muted small reason-line">
          {t("Motifs des réserves :")}{" "}
          {summary.review_reasons.map((item) => `${plainText(item.label)} (${item.reason}) : ${num(item.rows)}`).join(" · ")}
        </p>
      )}
    </section>
  );
}

// Noms et descriptions des contrôles de l'Auditor (référentiel stable, traduit par identifiant).
const CHECK_TEXT: Record<string, { en: [string, string]; ar: [string, string] }> = {
  A1_recomputed_values: {
    en: ["A1 – Recomputed values", "Each published value is recomputed from the warehouse facts using the catalogue formula: no discrepancy tolerated."],
    ar: ["A1 – القيم المعاد حسابها", "تُعاد حساب كل قيمة منشورة من وقائع المستودع وفق صيغة الكتالوج: دون أي تفاوت مسموح."],
  },
  A2_unavailable_rows_are_null: {
    en: ["A2 – Unavailable values left empty", "An unavailable value stays empty, and the observation is genuinely missing from the data: nothing is invented."],
    ar: ["A2 – القيم غير المتاحة تبقى فارغة", "القيمة غير المتاحة تبقى فارغة، والملاحظة غائبة فعلًا من البيانات: لا شيء مُختلق."],
  },
  A3_peers_recomputed: {
    en: ["A3 – Peer averages recomputed", "The peer average is recomputed from the observed peer countries (simple average)."],
    ar: ["A3 – متوسطات الأقران معاد حسابها", "يُعاد حساب متوسط الأقران من البلدان القريبة المرصودة (متوسط بسيط)."],
  },
  A4_row_completeness: {
    en: ["A4 – Expected rows present", "All expected rows (indicator × country × valid year) are present."],
    ar: ["A4 – الصفوف المتوقعة موجودة", "جميع الصفوف المتوقعة (مؤشر × بلد × سنة صالحة) موجودة."],
  },
  A5_raw_to_fact: {
    en: ["A5 – Raw files match the warehouse", "Input values are found identically in the versioned raw file (snapshot)."],
    ar: ["A5 – الملفات الخام مطابقة للمستودع", "قيم المدخلات موجودة كما هي في الملف الخام المؤرشف (اللقطة)."],
  },
  A6_user_source_facts: {
    en: ["A6 – User sources match their file", "Concerns user sources (My data page): their facts match the file and the mapping. Outside official figures."],
    ar: ["A6 – مصادر المستخدم مطابقة لملفها", "يتعلق بمصادر المستخدم (صفحة بياناتي): وقائعها تطابق الملف والربط. وخارج الأرقام الرسمية."],
  },
  B1_one_unit_per_kpi: {
    en: ["B1 – One unit per indicator", "Each indicator keeps the unit defined in the catalogue."],
    ar: ["B1 – وحدة واحدة لكل مؤشر", "يحافظ كل مؤشر على الوحدة المحددة في الكتالوج."],
  },
  B2_value_ranges: {
    en: ["B2 – Values within bounds", "Values stay within possible bounds (a share between 0 and 100%, a positive density…)."],
    ar: ["B2 – القيم ضمن الحدود", "تبقى القيم ضمن حدود ممكنة (حصة بين 0 و100%، كثافة موجبة…)."],
  },
  B3_country_entities_only: {
    en: ["B3 – Countries only, no aggregates", "Only countries carry values: no regional aggregate slips into country data."],
    ar: ["B3 – بلدان فقط، دون تجميعات", "البلدان وحدها تحمل القيم: ولا يتسرّب أي تجميع إقليمي إلى بيانات البلدان."],
  },
  B4_peers_are_configured_peers: {
    en: ["B4 – Peers match the configuration", "The peer average covers exactly the configured peer countries."],
    ar: ["B4 – الأقران مطابقون للإعداد", "يغطي متوسط الأقران بالضبط البلدان القريبة المضبوطة."],
  },
  B5_snapshot_and_run_ids: {
    en: ["B5 – Consistent version and run", "Data version and run identifier are identical everywhere (index, lineage, quality, indicators)."],
    ar: ["B5 – إصدار وتشغيل متسقان", "إصدار البيانات ومعرّف التشغيل متطابقان في كل مكان (الفهرس والتتبّع والجودة والمؤشرات)."],
  },
  B6_source_hashes: {
    en: ["B6 – Source fingerprints", "SHA-256 fingerprints of source files match from one step to the next."],
    ar: ["B6 – بصمات المصادر", "بصمات SHA-256 لملفات المصادر متطابقة من خطوة إلى أخرى."],
  },
  B7_warehouse_content_digest: {
    en: ["B7 – Warehouse fingerprint", "The warehouse content fingerprint is recomputed independently and matches."],
    ar: ["B7 – بصمة المستودع", "تُعاد بصمة محتوى المستودع حسابها باستقلال وهي متطابقة."],
  },
  B8_catalog_definitions: {
    en: ["B8 – Catalogue definitions", "The catalogue used has no provisional definition and matches the one of published indicators."],
    ar: ["B8 – تعريفات الكتالوج", "الكتالوج المستخدم لا يحتوي تعريفًا مؤقتًا ويطابق كتالوج المؤشرات المنشورة."],
  },
  B9_quality_gate: {
    en: ["B9 – Quality control passed", "Quality control of the sources is passed."],
    ar: ["B9 – نجحت مراقبة الجودة", "اجتازت المصادر مراقبة الجودة."],
  },
  C1_partial_survey_wave: {
    en: ["C1 – Partial survey waves", "Flags partial survey waves (incomplete country coverage)."],
    ar: ["C1 – موجات استقصاء جزئية", "يُنبّه إلى موجات الاستقصاء الجزئية (تغطية بلدان غير مكتملة)."],
  },
  C2_partial_peer_coverage: {
    en: ["C2 – Incomplete peer averages", "Flags peer averages computed without all peers (published with review)."],
    ar: ["C2 – متوسطات أقران غير مكتملة", "يُنبّه إلى متوسطات أقران محسوبة دون كل الأقران (تُنشر مع تحفّظ)."],
  },
  C3_input_quality_findings: {
    en: ["C3 – Input quality findings", "Flags quality-control findings that touch an input value of an indicator."],
    ar: ["C3 – ملاحظات جودة على المدخلات", "يُنبّه إلى ملاحظات مراقبة الجودة التي تمسّ قيمة مدخلة لمؤشر."],
  },
  C4_within_survey_noise: {
    en: ["C4 – Changes within survey noise", "Flags wave-to-wave changes smaller than survey noise (to be presented as stable)."],
    ar: ["C4 – تغيّرات ضمن ضجيج الاستقصاء", "يُنبّه إلى تغيّرات بين الموجات أصغر من ضجيج الاستقصاء (تُعرض كاستقرار)."],
  },
};

function checkText(check: AuditCheck, field: "name" | "description"): string {
  const lang = getLang();
  const entry = CHECK_TEXT[check.check_id];
  if (lang !== "fr" && entry) {
    const [name, description] = lang === "ar" ? entry.ar : entry.en;
    return field === "name" ? name : description;
  }
  return plainText(field === "name" ? check.name : check.description);
}

function ChecksPanel({ checks }: { checks: AuditCheck[] }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{t("Contrôles de l'Auditor")}</h3>
          <p className="muted small">{t("Chaque contrôle est recalculé indépendamment du pipeline.")}</p>
        </div>
        <span className="muted small">{t("{count} contrôles", { count: checks.length })}</span>
      </div>
      <table className="data-table audit-checks">
        <thead><tr><th>{t("Contrôle")}</th><th>{t("Ce qui est vérifié")}</th><th>{t("Résultat")}</th><th>{t("Lignes")}</th></tr></thead>
        <tbody>
          {checks.map((check) => (
            <tr key={check.check_id}>
              <td className="check-cell">
                <span className="check-name">{checkText(check, "name") || check.check_id}</span>
                <small className="check-id">{check.check_id}</small>
              </td>
              <td>
                {checkText(check, "description")}
                {check.user_sources && <span className="chip chip-user">{t("Sources utilisateur")}</span>}
                <details className="tech-details">
                  <summary>
                    {check.affected_count
                      ? t("Détail et lignes concernées ({count})", { count: check.affected_count })
                      : t("Détail")}
                  </summary>
                  <p className="muted small">{plainText(check.detail)}</p>
                  {check.affected_rows.length > 0 && (
                    <ul className="affected-rows">
                      {check.affected_rows.map((row, index) => <li key={index}>{rowText(row)}</li>)}
                    </ul>
                  )}
                  {check.truncated && <p className="muted small">{t("Liste limitée aux 200 premières lignes.")}</p>}
                </details>
              </td>
              <td>
                <span className={`status ${RESULTS[check.result]?.className ?? ""}`}>
                  {t(RESULTS[check.result]?.label ?? check.result)}
                </span>
              </td>
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
          <h3>{t("Audit des constats")}</h3>
          <p className="muted small">{t("Chaque nombre d'un constat doit être une valeur publiée, son année ou un écart entre deux valeurs du même indicateur.")}</p>
        </div>
      </div>
      <div className="check-stats">
        <div><span className="muted small">{t("Audités")}</span><strong>{audit.audited}</strong></div>
        <div><span className="muted small">{t("Acceptés")}</span><strong>{audit.accepted}</strong></div>
        <div><span className="muted small">{t("Rejetés")}</span><strong>{audit.rejected}</strong></div>
        <div><span className="muted small">{t("Non auditables")}</span><strong>{audit.not_auditable}</strong></div>
      </div>
      <ul className="audit-insights">
        {audit.insights.map((item) => (
          <li key={item.insight_id}>
            <span className={`status ${item.accepted === true ? "status-available" : item.accepted === false ? "status-removed" : "status-placeholder"}`}>
              {item.accepted === true ? t("Accepté") : item.accepted === false ? t("Rejeté") : t("Non auditable")}
            </span>
            <div>
              <p>
                {item.statement
                  ? plainText(item.statement)
                  : item.insight_id === "non auditable"
                    ? t("Non auditable")
                    : item.insight_id}
              </p>
              {item.cited.length > 0 && (
                <div className="tag-row">
                  {item.cited.map((claim, index) => (
                    <code key={index}>
                      {plainText(claim.kpi)} · {claim.iso3 === "PEERS" ? t("moyenne des pairs") : claim.iso3} · {claim.year}
                    </code>
                  ))}
                </div>
              )}
              {item.reasons.length > 0 && (
                <p className="muted small">{item.reasons.map(plainText).join(" ; ")}</p>
              )}
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
          <h3>{t("Comment un chiffre est vérifié")}</h3>
          <p className="muted small">{t("Choisissez un indicateur, un pays et une année : la valeur est retracée jusqu'au fichier source.")}</p>
        </div>
      </div>
      <div className="data-filters">
        <label className="select">
          <span className="sr-only">{t("Indicateur")}</span>
          <select value={kpi} onChange={(event) => setKpi(event.target.value)} title={t("Indicateur")}>
            {(options?.kpis ?? [{ kpi_id: kpi, label: kpi }]).map((item) => <option key={item.kpi_id} value={item.kpi_id}>{plainText(item.label)}</option>)}
          </select>
        </label>
        <label className="select">
          <span className="sr-only">{t("Pays")}</span>
          <select value={iso3} onChange={(event) => setIso3(event.target.value)} title={t("Pays")}>
            {(options?.countries ?? [iso3]).map((code) => (
              <option key={code} value={code}>{code === "PEERS" ? t("moyenne des pairs") : code}</option>
            ))}
          </select>
        </label>
        <label className="select">
          <span className="sr-only">{t("Année")}</span>
          <select value={year} onChange={(event) => setYear(Number(event.target.value))} title={t("Année")}>
            {(options?.years ?? [year]).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="muted">{t(error)}</p>}
      {record && (
        <ol className="trace">
          <li>
            <strong>{t("Valeur publiée")}</strong>
            <span>
              {plainText(record.kpi_name)} · {plainText(record.country)} ({record.iso3}) · {record.year} :{" "}
              {record.value === null
                ? t("indisponible ({reason})", { reason: plainText(record.reason) || t("non observée") })
                : `${num(record.value)} (${unitLabel(record.unit)})`}
            </span>
          </li>
          <li>
            <strong>{t("Sources lues")}</strong>
            {record.inputs.length === 0 && <span className="muted">{t("Aucune observation : la valeur reste vide.")}</span>}
            {record.inputs.map((input, index) => (
              <span key={index}>
                {input.raw
                  ? t("{source} · fichier {file} · colonne {column} · texte brut « {text} »", {
                      source: plainText(input.raw.source),
                      file: input.raw.file,
                      column: input.raw.column,
                      text: input.raw.raw_value_text,
                    })
                  : `${plainText(input.role)} : ${num(input.fact_value)} ${input.fact_unit}`}
              </span>
            ))}
          </li>
          <li><strong>{t("Formule")}</strong><span><code>{plainText(record.formula)}</code> — {plainText(record.transformation)}</span></li>
          <li>
            <strong>{t("Valeur recalculée")}</strong>
            <span>
              {record.value === null ? "—" : num(record.value)} · {t("version des données {id}", { id: record.snapshot_id })} ·{" "}
              {t("catalogue {version}", { version: record.catalog_version })}
            </span>
          </li>
          <li>
            <strong>{t("Contrôles")}</strong>
            <span>
              {t("{passed} contrôles réussis sur cette valeur", { passed: record.checks_passed.length })}
              {record.checks_touching.length > 0
                && ` ; ${t("à noter : {list}", {
                  list: record.checks_touching
                    .map((c) => `${c.check_id} (${t(RESULTS[c.result]?.label ?? c.result)})`)
                    .join(", "),
                })}`}
            </span>
          </li>
          <li>
            <strong>{t("Publication")}</strong>
            <span>
              {t("Valeur {status}", { status: t(STATUS_FR[record.publication_status] ?? record.publication_status) })}
              {record.review_reasons.length ? ` (${record.review_reasons.map(plainText).join(", ")})` : ""}
            </span>
          </li>
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
          <h3>{t("Test de l'Auditor par injection de fautes")}</h3>
          <p className="muted small">
            {t("Des erreurs sont introduites dans une copie des données ; l'Auditor doit les détecter. Évaluation du {date}.", {
              date: date(evaluation.created_at),
            })}
          </p>
        </div>
        {evaluation.available && (
          <span className="status status-available">
            {t("{detected} / {total} détectées", {
              detected: evaluation.detected,
              total: evaluation.total,
            })}
          </span>
        )}
      </div>
      {evaluation.stale && (
        <div className="generated-banner">
          {t("Résultat antérieur au dernier audit : relancez scripts/evaluate_auditor.py pour le mettre à jour.")}
        </div>
      )}
      {!evaluation.available && <p className="muted">{t("Aucune évaluation enregistrée.")}</p>}
      {evaluation.available && (
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("Faute injectée")}</th>
              <th>{t("Contrôle attendu")}</th>
              <th>{t("Détectée")}</th>
              <th>{t("Verdict obtenu")}</th>
            </tr>
          </thead>
          <tbody>
            {evaluation.faults.map((fault, index) => (
              <tr key={fault.id}>
                <td>{index + 1}. {plainText(fault.label)}</td>
                <td className="check-cell">
                  <span className="check-name">{plainText(fault.expected_check_name ?? fault.expected_check)}</span>
                  <small className="check-id">{fault.expected_check}</small>
                </td>
                <td>
                  <span className={`status ${fault.detected ? "status-available" : "status-removed"}`}>
                    {fault.detected ? t("Oui") : t("Non")}
                  </span>
                </td>
                <td>
                  {t(VERDICTS[fault.verdict] ?? fault.verdict)}
                  {fault.failing_checks.length ? ` (${fault.failing_checks.join(", ")})` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {evaluation.available && evaluation.insight_faults_note && (
        <p className="muted small faults-note">{plainText(evaluation.insight_faults_note)}</p>
      )}
    </section>
  );
}
