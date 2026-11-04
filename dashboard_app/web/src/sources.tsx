import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError, confirmSource, deleteSource, detectSource, dryRunSource, fetchSourceData, fetchSourceJob,
  fetchSources,
} from "./api";
import { ChartView } from "./charts";
import type {
  Chart, ColumnRole, DetectResult, DryRunResult, IndicatorChoice, SourceData, SourceJob,
  SourceMappingInput, SourcesList, UserSource,
} from "./types";

// ------------------------------------------------------------------ libelles
const ROLE_LABELS: Record<ColumnRole, string> = {
  country: "Pays",
  year: "Année",
  indicator: "Indicateur",
  value: "Valeur",
  year_column: "Colonne d'année",
  indicator_column: "Colonne d'indicateur",
  ignore: "Ignorer",
};

const LAYOUT_LABELS: Record<string, string> = {
  long: "Format long : une ligne par observation",
  wide_by_year: "Années en colonnes",
  wide_by_indicator: "Indicateurs en colonnes",
};

const UNIT_OPTIONS: { value: string; label: string }[] = [
  { value: "percent", label: "%" },
  { value: "fraction", label: "fraction (0 à 1)" },
  { value: "per_100k_adults", label: "par 100 000 adultes" },
  { value: "per_1k_adults", label: "par 1 000 adultes" },
  { value: "count", label: "nombre" },
  { value: "currency", label: "monnaie" },
];

const STEP_LABELS: Record<string, string> = {
  collector: "Collecte des sources",
  snapshot: "Version des données",
  profiler: "Profil des colonnes",
  quality: "Contrôle qualité",
  etl: "Chargement dans l'entrepôt",
  semantic_kpi: "Calcul des indicateurs",
  auditor: "Audit indépendant",
  route2: "Mise à jour du tableau de bord",
};
const JOB_STEPS = Object.keys(STEP_LABELS);

const WIZARD_STEPS = ["Fichier", "Structure", "Indicateurs", "Vérification", "Confirmation"];

const SEPARATORS: Record<string, string> = { ";": "point-virgule (;)", ",": "virgule (,)", "\t": "tabulation", "|": "barre verticale (|)" };

export function unitText(unit: string | null | undefined): string {
  if (!unit) return "—";
  if (unit.startsWith("currency:")) return `monnaie (${unit.slice("currency:".length)})`;
  return UNIT_OPTIONS.find((option) => option.value === unit)?.label ?? unit;
}

function fmtValue(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("fr-FR", { maximumFractionDigits: 4 });
}

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.detail : String(err);
}

function slugName(filename: string): string {
  const base = filename.replace(/\.[^.]+$/, "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const slug = base.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);
  return /^[a-z]/.test(slug) && slug.length >= 2 ? slug : `source_${slug || "csv"}`.slice(0, 40);
}

export function UserChip() {
  return <span className="chip chip-user" title="Valeur importée par l'utilisateur, hors chiffres officiels">Données utilisateur</span>;
}

function StatusChip({ source }: { source: UserSource }) {
  if (source.status === "included") return <span className="status status-available">Incluse</span>;
  if (source.status === "excluded") {
    return (
      <span className="status status-warning" title={source.reason ?? undefined}>
        Exclue{source.reason ? ` : ${source.reason}` : ""}
      </span>
    );
  }
  return <span className="status status-placeholder">En attente</span>;
}

// ------------------------------------------------------------------ page
type View = { kind: "list" } | { kind: "wizard"; replace?: string } | { kind: "job"; jobId: string } | { kind: "data"; name: string };

export function MyDataPage() {
  const [view, setView] = useState<View>({ kind: "list" });
  const [list, setList] = useState<SourcesList | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    fetchSources()
      .then((result) => {
        setList(result);
        setError(null);
        // un recalcul en cours (rechargement de page, redemarrage) reprend son suivi
        if (result.active_job) setView((current) => (current.kind === "list" ? { kind: "job", jobId: result.active_job!.job_id } : current));
      })
      .catch((err) => setError(errorText(err)));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <div className="page mydata">
      <header className="page-head">
        <div>
          <span className="eyebrow">Sources utilisateur</span>
          <h2>Mes données</h2>
          <p className="page-sub">
            Ajoutez vos propres fichiers CSV. Ils restent séparés des chiffres officiels : jamais
            mélangés aux cartes, à l'audit officiel ni aux réponses d'Ask Finova.
          </p>
        </div>
        <div className="page-head-badges">
          <UserChip />
          {view.kind === "list" && (
            <button className="primary-btn" onClick={() => setView({ kind: "wizard" })} disabled={Boolean(list?.active_job)}>
              Ajouter un fichier
            </button>
          )}
        </div>
      </header>
      {error && <div className="error-card"><p>{error}</p></div>}
      {view.kind === "wizard" && (
        <Wizard
          maxMb={list?.max_file_mb ?? 200}
          replace={view.replace}
          onCancel={() => setView({ kind: "list" })}
          onJob={(jobId) => setView({ kind: "job", jobId })}
        />
      )}
      {view.kind === "job" && (
        <JobProgress
          jobId={view.jobId}
          onDone={reload}
          onList={() => {
            reload();
            setView({ kind: "list" });
          }}
          onData={(name) => setView({ kind: "data", name })}
        />
      )}
      {view.kind === "data" && <SourceDataView name={view.name} onBack={() => setView({ kind: "list" })} />}
      {view.kind === "list" && (
        <SourceList
          list={list}
          onData={(name) => setView({ kind: "data", name })}
          onReplace={(name) => setView({ kind: "wizard", replace: name })}
          onDeleted={(jobId) => setView({ kind: "job", jobId })}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ liste
function SourceList({
  list, onData, onReplace, onDeleted,
}: {
  list: SourcesList | null;
  onData: (name: string) => void;
  onReplace: (name: string) => void;
  onDeleted: (jobId: string) => void;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!list) return <p className="muted">Chargement des sources…</p>;
  if (list.sources.length === 0) {
    return (
      <section className="panel empty-panel">
        <h3>Aucune source ajoutée</h3>
        <p className="muted">Ajoutez un fichier CSV pour comparer vos propres chiffres, à côté du tableau de bord officiel.</p>
      </section>
    );
  }
  const remove = (name: string) => {
    setBusy(true);
    deleteSource(name)
      .then((result) => onDeleted(result.job_id))
      .catch((err) => setError(errorText(err)))
      .finally(() => setBusy(false));
  };
  return (
    <section className="source-grid">
      {error && <div className="error-card"><p>{error}</p></div>}
      {list.sources.map((source) => (
        <article key={source.name} className="panel source-card">
          <header className="source-card-head">
            <div>
              <h3>{source.name}</h3>
              <span className="muted small">{source.file}</span>
            </div>
            <StatusChip source={source} />
          </header>
          <dl className="source-facts">
            <dt>Indicateurs</dt>
            <dd>{source.indicators.map((item) => `${item.label} (${unitText(item.unit)})`).join(" · ")}</dd>
            <dt>Lignes</dt>
            <dd>{source.rows.toLocaleString("fr-FR")}</dd>
            <dt>Années</dt>
            <dd>{source.years ? `${source.years[0]}–${source.years[1]}` : "—"}</dd>
            <dt>Pays</dt>
            <dd>{source.countries.length ? source.countries.join(", ") : "—"}</dd>
            <dt>Mise à jour</dt>
            <dd>{source.last_job?.finished_at?.replace("T", " ") ?? source.confirmed_at?.replace("T", " ") ?? "—"}</dd>
            {source.quality_score !== null && (
              <>
                <dt>Score qualité</dt>
                <dd>{fmtValue(source.quality_score)}</dd>
              </>
            )}
          </dl>
          {confirming === source.name ? (
            <div className="confirm-box" role="alertdialog" aria-label={`Supprimer ${source.name}`}>
              <p>
                Supprimer « {source.name} » ? Ses données seront retirées de l'entrepôt et le tableau de
                bord sera recalculé. La copie du fichier est conservée.
              </p>
              <div className="actions">
                <button className="why-pill" onClick={() => setConfirming(null)} disabled={busy}>Annuler</button>
                <button className="primary-btn danger" onClick={() => remove(source.name)} disabled={busy}>
                  Supprimer et recalculer
                </button>
              </div>
            </div>
          ) : (
            <div className="actions">
              <button className="why-pill" onClick={() => onData(source.name)}>Voir les données</button>
              <button className="why-pill" onClick={() => onReplace(source.name)} disabled={Boolean(list.active_job)}>
                Remplacer le fichier
              </button>
              <button className="why-pill" onClick={() => setConfirming(source.name)} disabled={Boolean(list.active_job)}>
                Supprimer
              </button>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

// ------------------------------------------------------------------ assistant
function Stepper({ step }: { step: number }) {
  return (
    <ol className="stepper" aria-label="Étapes">
      {WIZARD_STEPS.map((label, index) => (
        <li key={label} className={index < step ? "done" : index === step ? "current" : ""}>
          <span className="stepper-dot">{index < step ? "✓" : index + 1}</span>
          <span>{label}</span>
        </li>
      ))}
    </ol>
  );
}

function Wizard({
  maxMb, replace, onCancel, onJob,
}: {
  maxMb: number;
  replace?: string;
  onCancel: () => void;
  onJob: (jobId: string) => void;
}) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detected, setDetected] = useState<DetectResult | null>(null);
  const [name, setName] = useState(replace ?? "");
  const [roles, setRoles] = useState<Record<string, ColumnRole>>({});
  const [indicators, setIndicators] = useState<Record<string, IndicatorChoice & { currency?: string }>>({});
  const [countryNames, setCountryNames] = useState<Record<string, string>>({});
  const [reuse, setReuse] = useState<string | null>(null);
  const [dry, setDry] = useState<DryRunResult | null>(null);

  const mapping = (): SourceMappingInput => {
    if (reuse) return { reuse, replace: Boolean(replace) };
    const chosen: Record<string, IndicatorChoice> = {};
    Object.entries(indicators).forEach(([code, item]) => {
      const unit = item.unit === "currency" ? (item.currency ? `currency:${item.currency.trim()}` : null) : item.unit;
      chosen[code] = { label: item.label, unit, transform: item.transform ?? "none" };
    });
    return { roles, indicators: chosen, country_names: countryNames, replace: Boolean(replace) };
  };

  const run = async <T,>(call: () => Promise<T>): Promise<T | null> => {
    setBusy(true);
    setError(null);
    try {
      return await call();
    } catch (err) {
      setError(errorText(err));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const onFile = async (file: File) => {
    const result = await run(() => detectSource(file));
    if (!result) return;
    setDetected(result);
    setRoles(Object.fromEntries(result.columns.map((column) => [column.name, column.role])));
    setName((current) => current || slugName(result.filename));
    const sameSource = replace ? result.reusable.find((item) => item.name === replace) : undefined;
    if (sameSource) {
      // Remplacer le fichier : meme structure -> configuration enregistree, verification directe
      await useSaved(result, sameSource.name, replace!);
    } else {
      setStep(1);
    }
  };

  const useSaved = async (result: DetectResult, saved: string, sourceName: string) => {
    setReuse(saved);
    const checked = await run(() => dryRunSource(result.upload_id, sourceName, { reuse: saved, replace: Boolean(replace) }));
    if (checked) {
      setDry(checked);
      setStep(3);
    }
  };

  const toIndicators = async () => {
    if (!detected) return;
    const checked = await run(() => dryRunSource(detected.upload_id, name, { roles, country_names: countryNames }));
    if (!checked) return;
    setIndicators((current) => Object.fromEntries(checked.indicators.map((item) => [
      item.code, current[item.code] ?? { label: item.label, unit: null, transform: "none" },
    ])));
    setDry(checked);
    setStep(2);
  };

  const toCheck = async () => {
    if (!detected) return;
    const checked = await run(() => dryRunSource(detected.upload_id, name, mapping()));
    if (checked) {
      setDry(checked);
      setStep(3);
    }
  };

  const confirm = async () => {
    if (!detected) return;
    const result = await run(() => confirmSource(detected.upload_id, name, mapping()));
    if (result) onJob(result.job_id);
  };

  const unitsMissing = Object.values(indicators).some(
    (item) => !item.unit || (item.unit === "currency" && !(item.currency ?? "").trim()),
  );
  const nameValid = /^[a-z][a-z0-9_]{1,40}$/.test(name);

  return (
    <section className="panel wizard">
      <Stepper step={step} />
      {replace && <p className="muted small">Remplacement du fichier de la source « {replace} ».</p>}
      {error && (
        <ul className="notice-list"><li className="sev-warning"><span className="dot" /><span>{error}</span></li></ul>
      )}
      {step === 0 && <UploadStep maxMb={maxMb} busy={busy} onFile={onFile} />}
      {step === 1 && detected && (
        <StructureStep
          detected={detected}
          roles={roles}
          setRoles={setRoles}
          name={name}
          setName={setName}
          nameLocked={Boolean(replace)}
          onReuse={(saved) => useSaved(detected, saved, name || saved)}
        />
      )}
      {step === 2 && (
        <IndicatorStep indicators={indicators} setIndicators={setIndicators} />
      )}
      {step === 3 && dry && (
        <CheckStep
          dry={dry}
          countryNames={countryNames}
          setCountryNames={setCountryNames}
          onApply={toCheck}
          busy={busy}
          reused={reuse}
        />
      )}
      {step === 4 && dry && <ConfirmStep dry={dry} name={name} replace={replace} />}

      <footer className="wizard-actions">
        <button className="why-pill" onClick={step === 0 ? onCancel : () => setStep(reuse && step === 3 ? 0 : step - 1)} disabled={busy}>
          {step === 0 ? "Annuler" : "Retour"}
        </button>
        {busy && <span className="muted small">Traitement…</span>}
        {step === 1 && (
          <button className="primary-btn" onClick={toIndicators} disabled={busy || !nameValid}>Continuer</button>
        )}
        {step === 2 && (
          <button className="primary-btn" onClick={toCheck} disabled={busy || unitsMissing}
            title={unitsMissing ? "Choisissez une unité pour chaque indicateur" : undefined}>
            Continuer
          </button>
        )}
        {step === 3 && dry && (
          <button className="primary-btn" onClick={() => setStep(4)} disabled={busy || dry.blocking.length > 0}>
            Continuer
          </button>
        )}
        {step === 4 && (
          <button className="primary-btn" onClick={confirm} disabled={busy}>Ajouter et recalculer</button>
        )}
      </footer>
    </section>
  );
}

function UploadStep({ maxMb, busy, onFile }: { maxMb: number; busy: boolean; onFile: (file: File) => void }) {
  const input = useRef<HTMLInputElement | null>(null);
  const [over, setOver] = useState(false);
  return (
    <div className="upload-step">
      <div
        className={`drop-zone ${over ? "over" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          const file = event.dataTransfer.files?.[0];
          if (file) onFile(file);
        }}
      >
        <strong>Glissez votre fichier CSV ici</strong>
        <span className="muted">ou</span>
        <button className="primary-btn" onClick={() => input.current?.click()} disabled={busy}>
          Choisir un fichier
        </button>
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = "";
          }}
        />
        <span className="muted small">
          Format accepté : CSV (séparateur ; , tabulation ou |) · {maxMb.toLocaleString("fr-FR")} Mo maximum ·
          le fichier n'est jamais exécuté ni ouvert par un tableur.
        </span>
      </div>
      <div className="layout-examples">
        <h4>Trois dispositions reconnues</h4>
        <div className="layout-grid">
          <LayoutExample title="Format long" rows={[["Pays", "Année", "Indicateur", "Valeur"], ["Tunisie", "2023", "Clients", "1 200"]]} />
          <LayoutExample title="Années en colonnes" rows={[["Pays", "Indicateur", "2022", "2023"], ["Tunisie", "Clients", "1 150", "1 200"]]} />
          <LayoutExample title="Indicateurs en colonnes" rows={[["Pays", "Année", "Clients", "Agences"], ["Tunisie", "2023", "1 200", "45"]]} />
        </div>
      </div>
    </div>
  );
}

function LayoutExample({ title, rows }: { title: string; rows: string[][] }) {
  return (
    <figure className="layout-example">
      <figcaption>{title}</figcaption>
      <table className="data-table compact">
        <thead><tr>{rows[0].map((cell) => <th key={cell}>{cell}</th>)}</tr></thead>
        <tbody><tr>{rows[1].map((cell, index) => <td key={index}>{cell}</td>)}</tr></tbody>
      </table>
    </figure>
  );
}

function StructureStep({
  detected, roles, setRoles, name, setName, nameLocked, onReuse,
}: {
  detected: DetectResult;
  roles: Record<string, ColumnRole>;
  setRoles: (roles: Record<string, ColumnRole>) => void;
  name: string;
  setName: (name: string) => void;
  nameLocked: boolean;
  onReuse: (saved: string) => void;
}) {
  const country = detected.country;
  return (
    <div className="structure-step">
      {detected.reusable.length > 0 && (
        <div className="generated-banner reuse-banner">
          Une configuration enregistrée correspond à ces colonnes (« {detected.reusable[0].name} »).{" "}
          <button className="why-pill" onClick={() => onReuse(detected.reusable[0].name)}>
            Réutiliser la configuration enregistrée
          </button>
        </div>
      )}
      <div className="detected-row">
        <span className="chip">Fichier : {detected.filename} · {detected.rows} ligne(s)</span>
        <span className="chip">Séparateur : {SEPARATORS[detected.read.separator] ?? detected.read.separator}</span>
        <span className="chip">Décimale : {detected.read.decimal === "," ? "virgule" : "point"}</span>
        <span className="chip">{detected.layout ? LAYOUT_LABELS[detected.layout] : "Disposition à préciser"}</span>
        {country && (
          <span className="chip chip-semantic">
            Pays : {country.kind === "iso3" ? "codes ISO3" : "noms de pays"} ({Math.round(country.share * 100)} % reconnus)
          </span>
        )}
      </div>
      {detected.problem && (
        <ul className="notice-list"><li className="sev-review"><span className="dot" /><span>{detected.problem}</span></li></ul>
      )}
      <label className="field">
        <span>Nom de la source</span>
        <input value={name} disabled={nameLocked} onChange={(event) => setName(event.target.value.trim().toLowerCase())} maxLength={41} />
        <small className="muted">Minuscules, chiffres et _ (ex. clients_microfinance).</small>
      </label>
      <table className="data-table">
        <thead>
          <tr><th>Colonne</th><th>Exemples</th><th>Rôle</th><th>Preuve</th></tr>
        </thead>
        <tbody>
          {detected.columns.map((column) => (
            <tr key={column.name}>
              <td><strong>{column.name}</strong></td>
              <td className="muted">{column.samples.join(" · ") || "—"}</td>
              <td>
                <select
                  aria-label={`Rôle de la colonne ${column.name}`}
                  value={roles[column.name] ?? "ignore"}
                  onChange={(event) => setRoles({ ...roles, [column.name]: event.target.value as ColumnRole })}
                >
                  {(Object.keys(ROLE_LABELS) as ColumnRole[]).map((role) => (
                    <option key={role} value={role}>{ROLE_LABELS[role]}</option>
                  ))}
                </select>
              </td>
              <td className="muted small">{column.evidence || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IndicatorStep({
  indicators, setIndicators,
}: {
  indicators: Record<string, IndicatorChoice & { currency?: string }>;
  setIndicators: (value: Record<string, IndicatorChoice & { currency?: string }>) => void;
}) {
  const update = (code: string, patch: Partial<IndicatorChoice & { currency?: string }>) =>
    setIndicators({ ...indicators, [code]: { ...indicators[code], ...patch } });
  return (
    <div className="indicator-step">
      <p className="muted">
        L'unité n'est jamais devinée : choisissez celle des valeurs telles qu'elles sont écrites dans le
        fichier. Aucune conversion n'est faite sauf si vous la demandez.
      </p>
      <table className="data-table">
        <thead>
          <tr><th>Code</th><th>Libellé</th><th>Unité (obligatoire)</th><th>Conversion</th></tr>
        </thead>
        <tbody>
          {Object.entries(indicators).map(([code, item]) => (
            <tr key={code}>
              <td><code>{code}</code></td>
              <td>
                <input aria-label={`Libellé de ${code}`} value={item.label ?? ""} onChange={(event) => update(code, { label: event.target.value })} />
              </td>
              <td>
                <div className="unit-cell">
                  <select
                    aria-label={`Unité de ${code}`}
                    className={!item.unit ? "missing" : ""}
                    value={item.unit ?? ""}
                    onChange={(event) => update(code, {
                      unit: event.target.value || null,
                      transform: event.target.value === "percent" ? item.transform : "none",
                    })}
                  >
                    <option value="">— à choisir —</option>
                    {UNIT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                  {item.unit === "currency" && (
                    <input aria-label={`Monnaie de ${code}`} placeholder="ex. TND" value={item.currency ?? ""}
                      maxLength={10} onChange={(event) => update(code, { currency: event.target.value.replace(/[^A-Za-z]/g, "") })} />
                  )}
                </div>
              </td>
              <td>
                {item.unit === "percent" ? (
                  <label className="inline-check">
                    <input type="checkbox" checked={item.transform === "percent_to_fraction"}
                      onChange={(event) => update(code, { transform: event.target.checked ? "percent_to_fraction" : "none" })} />
                    pourcentage → fraction
                  </label>
                ) : (
                  <span className="muted small">aucune</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CheckStep({
  dry, countryNames, setCountryNames, onApply, busy, reused,
}: {
  dry: DryRunResult;
  countryNames: Record<string, string>;
  setCountryNames: (value: Record<string, string>) => void;
  onApply: () => void;
  busy: boolean;
  reused: string | null;
}) {
  const unknown = Object.entries(dry.unmapped_countries);
  const warnings: { severity: string; text: string }[] = [
    ...dry.blocking.map((text) => ({ severity: "warning", text })),
    ...(dry.non_numeric.count
      ? [{ severity: "review", text: `${dry.non_numeric.count} valeur(s) non numérique(s) ignorée(s) : ${dry.non_numeric.examples.slice(0, 3).map((e) => `ligne ${e.line} « ${e.text} »`).join(", ")}` }]
      : []),
    ...(dry.duplicates.exact_removed ? [{ severity: "info", text: `${dry.duplicates.exact_removed} doublon(s) identique(s) retiré(s).` }] : []),
    ...(dry.invalid_years.count ? [{ severity: "review", text: `${dry.invalid_years.count} année(s) invalide(s) ignorée(s).` }] : []),
    // constats du controle qualite : prefixe technique retire, doublons des avertissements ci-dessus ignores
    ...dry.quality.issues
      .filter((issue) => !["non_numeric_values", "invalid_years", "unmapped_countries"].includes(issue.code))
      .map((issue) => ({
        severity: issue.severity === "critical" ? "warning" : "review",
        text: `Contrôle qualité : ${(issue.message ?? issue.code).replace(/^\[[^\]]+\]\s*/, "")}`,
      })),
  ];
  return (
    <div className="check-step">
      {reused && <p className="muted small">Configuration enregistrée réutilisée : « {reused} ».</p>}
      <div className="check-stats">
        <div><span className="muted small">Lignes retenues</span><strong>{fmtValue(dry.rows_mapped_pct)} %</strong><span className="muted small">{dry.mapped} valeur(s)</span></div>
        <div><span className="muted small">Années</span><strong>{dry.year_range ? `${dry.year_range[0]}–${dry.year_range[1]}` : "—"}</strong></div>
        <div><span className="muted small">Pays reconnus</span><strong>{dry.countries.length}</strong><span className="muted small">{dry.countries.join(", ")}</span></div>
        <div><span className="muted small">Contrôle qualité</span><strong>{dry.quality.gate ? "Réussi" : "Échec"}</strong><span className="muted small">score {fmtValue(dry.quality.score)}</span></div>
      </div>
      {unknown.length > 0 && !reused && (
        <div className="unknown-countries">
          <h4>Pays non reconnus</h4>
          <p className="muted small">Indiquez un code ISO3 (ex. MRT) ou laissez vide pour ignorer ces lignes.</p>
          {unknown.map(([raw, info]) => (
            <label key={raw} className="field inline">
              <span>« {raw} » · {info.rows} valeur(s)</span>
              <input placeholder="ISO3 ou vide = ignorer" maxLength={3} value={countryNames[raw] ?? ""}
                onChange={(event) => setCountryNames({ ...countryNames, [raw]: event.target.value.toUpperCase() })} />
            </label>
          ))}
          <button className="why-pill" onClick={onApply} disabled={busy}>Appliquer et revérifier</button>
        </div>
      )}
      {warnings.length > 0 && (
        <ul className="notice-list">
          {warnings.map((warning, index) => (
            <li key={index} className={`sev-${warning.severity}`}><span className="dot" /><span>{warning.text}</span></li>
          ))}
        </ul>
      )}
      <h4>Aperçu (10 premières valeurs)</h4>
      <table className="data-table compact">
        <thead><tr><th>Pays</th><th>Année</th><th>Indicateur</th><th>Valeur</th><th>Unité</th><th>Texte du fichier</th><th>Ligne</th></tr></thead>
        <tbody>
          {dry.preview.map((row, index) => (
            <tr key={index}>
              <td>{row.iso3}</td><td>{row.year}</td><td>{row.indicator_label}</td><td>{fmtValue(row.value)}</td>
              <td>{unitText(row.unit)}</td><td className="muted">{row.raw_value}</td><td className="muted">{row.line}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfirmStep({ dry, name, replace }: { dry: DryRunResult; name: string; replace?: string }) {
  return (
    <div className="confirm-step">
      <h4>{replace ? "Remplacer le fichier de la source" : "Ajouter la source"} « {name} »</h4>
      <ul className="confirm-list">
        <li>{dry.mapped} valeur(s), {dry.countries.length} pays, années {dry.year_range ? `${dry.year_range[0]}–${dry.year_range[1]}` : "—"}.</li>
        <li>Indicateurs : {dry.indicators.map((item) => `${item.label} (${unitText(item.unit)})`).join(" · ")}.</li>
        <li>Le fichier est copié dans data/uploads/, puis le pipeline est recalculé (contrôle qualité, entrepôt, audit, tableau de bord). Les sources officielles ne sont pas retéléchargées.</li>
        <li>Les chiffres officiels du tableau de bord ne changent pas : vos données restent sur cette page.</li>
      </ul>
    </div>
  );
}

// ------------------------------------------------------------------ recalcul
function JobProgress({
  jobId, onDone, onList, onData,
}: {
  jobId: string;
  onDone: () => void;
  onList: () => void;
  onData: (name: string) => void;
}) {
  const [job, setJob] = useState<SourceJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let stop = false;
    let timer = 0;
    const poll = () => {
      fetchSourceJob(jobId)
        .then((result) => {
          if (stop) return;
          setJob(result);
          if (result.status === "queued" || result.status === "running") timer = window.setTimeout(poll, 1500);
          else onDone();
        })
        .catch((err) => {
          if (!stop) setError(errorText(err));
        });
    };
    poll();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const active = !job || job.status === "queued" || job.status === "running";
  const doneSteps = new Set(job?.steps_done ?? []);
  return (
    <section className="panel job-panel" aria-live="polite">
      <div className="panel-head">
        <div>
          <h3>{job?.kind === "delete" ? "Suppression et recalcul" : "Ajout et recalcul"} · {job?.source ?? "…"}</h3>
          <p className="muted small">L'opération continue même si vous rechargez la page.</p>
        </div>
        {job?.seconds != null && <span className="muted small">{fmtValue(job.seconds)} s</span>}
      </div>
      {error && <p className="error-card">{error}</p>}
      <ol className="job-steps">
        {JOB_STEPS.map((step) => {
          const state = doneSteps.has(step) ? "done" : job?.step === step && active ? "current" : "";
          return (
            <li key={step} className={state}>
              <span className="stepper-dot">{state === "done" ? "✓" : state === "current" ? "…" : ""}</span>
              {STEP_LABELS[step]}
            </li>
          );
        })}
      </ol>
      {job && !active && (
        <div className={`job-result job-${job.status}`}>
          <strong>
            {job.status === "success"
              ? job.kind === "add" ? "Source intégrée à l'entrepôt" : "Source retirée"
              : job.status === "quality_failed" ? "Source exclue par le contrôle qualité"
                : job.status === "audit_failed" ? "Audit en échec : version précédente conservée" : "Le recalcul a échoué"}
          </strong>
          {job.message && <p>{job.message}</p>}
          {job.reasons.length > 0 && <ul>{job.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
          <div className="actions">
            <button className="why-pill" onClick={onList}>Voir mes sources</button>
            {job.status === "success" && job.kind === "add" && (
              <button className="primary-btn" onClick={() => onData(job.source)}>Voir les données</button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ donnees
function SourceDataView({ name, onBack }: { name: string; onBack: () => void }) {
  const [data, setData] = useState<SourceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [indicator, setIndicator] = useState("");
  const [iso3, setIso3] = useState("");
  useEffect(() => {
    fetchSourceData(name)
      .then((result) => {
        setData(result);
        const first = result.values.find((value) => value.iso3 === "TUN") ?? result.values[0];
        setIndicator(first?.indicator_code ?? result.indicators[0]?.code ?? "");
        setIso3(first?.iso3 ?? "");
      })
      .catch((err) => setError(errorText(err)));
  }, [name]);
  const countries = useMemo(
    () => Array.from(new Set((data?.values ?? []).filter((v) => v.indicator_code === indicator).map((v) => v.iso3))).sort(),
    [data, indicator],
  );
  useEffect(() => {
    if (countries.length && !countries.includes(iso3)) setIso3(countries.includes("TUN") ? "TUN" : countries[0]);
  }, [countries, iso3]);
  const rows = (data?.values ?? []).filter((v) => v.indicator_code === indicator && v.iso3 === iso3);
  const meta = data?.indicators.find((item) => item.code === indicator);
  const chart: Chart = {
    id: `user-${name}`, kind: "line", title: meta?.label ?? indicator,
    subtitle: `${iso3} · ${unitText(meta?.unit)} · Données utilisateur`, x_label: "Année", y_label: unitText(meta?.unit),
    unit: null, bars: [], steps: [], groups: [], gap_points: [], columns: [], rows: [], cells: [], reference_lines: [],
    notes: ["Valeurs importées par l'utilisateur, publiées telles quelles : elles ne sont pas des chiffres officiels."],
    formula: null, chip: null,
    series: [{
      id: indicator, label: `${meta?.label ?? indicator} — ${iso3}`, unit: meta?.unit ?? "",
      points: rows.map((row) => ({ year: row.year, value: row.value, status: row.value === null ? "unavailable" : "available", reason: null })),
    }],
  };
  return (
    <section className="data-view">
      <div className="data-view-head">
        <button className="why-pill" onClick={onBack}>← Mes sources</button>
        <h3>{name}</h3>
        <UserChip />
      </div>
      {error && <div className="error-card"><p>{error}</p></div>}
      {data && data.values.length === 0 && (
        <section className="panel empty-panel">
          <h3>Aucune valeur publiée</h3>
          <p className="muted">La source n'est pas (ou plus) intégrée à l'entrepôt : voir son statut dans la liste.</p>
        </section>
      )}
      {data && data.values.length > 0 && (
        <>
          <div className="data-filters">
            <label className="select">
              <span className="sr-only">Indicateur</span>
              <select value={indicator} onChange={(event) => setIndicator(event.target.value)} title="Indicateur">
                {data.indicators.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
              </select>
            </label>
            <label className="select">
              <span className="sr-only">Pays</span>
              <select value={iso3} onChange={(event) => setIso3(event.target.value)} title="Pays">
                {countries.map((code) => <option key={code} value={code}>{code}</option>)}
              </select>
            </label>
          </div>
          <ChartView chart={chart} />
          <table className="data-table">
            <thead><tr><th>Année</th><th>Valeur</th><th>Unité</th><th>Provenance</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.year}>
                  <td>{row.year}</td><td>{fmtValue(row.value)}</td><td>{unitText(row.unit)}</td><td><UserChip /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
