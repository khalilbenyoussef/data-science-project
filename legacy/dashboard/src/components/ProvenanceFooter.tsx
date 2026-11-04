import type { ReactNode } from "react";
import type { DashboardData } from "../types";
import {
  associationLabel,
  contentBindingLabel,
  formatBytes,
  formatDateTime,
  formatScore,
  publicationBadgeClass,
  publicationLabel,
  reasonLabel,
  shortHash,
} from "../format";

// Limites par défaut (sans rapport de l'analyste) : chaque phrase suit les données du contrat.
function fallbackLimitations(data: DashboardData): string[] {
  const provisional = data.scope.kpis
    .filter((kpi) => kpi.verification_status === "provisional")
    .map((kpi) => kpi.name);
  return [
    "Les valeurs proviennent uniquement des contrats KPI déterministes ; aucun chiffre n'est recalculé, lissé ou extrapolé.",
    ...(data.publication_status === "not_evaluated" || !data.publication_status
      ? ["Le statut de publication reste « non évalué » : ce tableau de bord ne vaut pas approbation."]
      : []),
    "Les observations marquées « revue requise » conservent leurs motifs et ne sont pas certifiées.",
    ...(provisional.length > 0
      ? [`Les définitions provisoires (${provisional.join(", ")}) ne sont pas vérifiées.`]
      : []),
    "Les comparaisons sont des différences absolues (droite − gauche), jamais des taux de croissance.",
    "Le paiement numérique et la détention de compte sont deux mesures distinctes : aucun écart n'est interprété comme une causalité.",
  ];
}

function MetaItem({
  label,
  children,
  title,
}: {
  label: string;
  children: ReactNode;
  title?: string;
}) {
  return (
    <div className="meta-item" title={title}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function gateBadge(passed: boolean | null) {
  if (passed === true) return <span className="badge badge-ok">PASS</span>;
  if (passed === false) return <span className="badge badge-review">FAIL</span>;
  return <span className="badge badge-warning">Indéterminé</span>;
}

export function ProvenanceFooter({ data }: { data: DashboardData }) {
  const provenance = data.provenance;
  const limitations =
    data.limitations && data.limitations.length > 0 ? data.limitations : fallbackLimitations(data);

  return (
    <footer className="panel provenance">
      <header className="panel__head">
        <h2>Provenance et limites</h2>
        <span className={`badge ${publicationBadgeClass(data.publication_status)}`}>
          Publication : {publicationLabel(data.publication_status)}
        </span>
      </header>

      <dl className="meta-grid">
        <MetaItem label="Run de lineage">{provenance.lineage_run_id ?? "non disponible"}</MetaItem>
        <MetaItem label="Lineage créée le">{formatDateTime(provenance.lineage_created_at)}</MetaItem>
        <MetaItem label="Warehouse" title={provenance.warehouse_path}>
          <span className="mono">{provenance.warehouse_path}</span>
        </MetaItem>
        <MetaItem label="Empreinte warehouse" title={provenance.warehouse_sha256}>
          <span className="mono">{shortHash(provenance.warehouse_sha256)}</span>
          <span className="muted"> · {formatBytes(provenance.warehouse_size_bytes)}</span>
        </MetaItem>
        <MetaItem label="Lignage" title={provenance.lineage_path}>
          <span className="mono">{shortHash(provenance.lineage_sha256)}</span>
        </MetaItem>
        <MetaItem label="Rapport qualité" title={provenance.quality_report_path}>
          <span className="mono">{shortHash(provenance.quality_report_sha256)}</span>
        </MetaItem>
        <MetaItem label="Score qualité">{formatScore(provenance.quality_score)}</MetaItem>
        <MetaItem label="Gate qualité">{gateBadge(provenance.quality_gate_passed)}</MetaItem>
        <MetaItem label="Liaison de contenu">
          <span
            className={`badge ${
              provenance.content_binding === "recorded_and_verified"
                ? "badge-ok"
                : "badge-warning"
            }`}
          >
            {contentBindingLabel(provenance.content_binding)}
          </span>
        </MetaItem>
        <MetaItem label="Association qualité">
          <span className="badge badge-neutral">
            {associationLabel(provenance.quality_association_status)}
          </span>
        </MetaItem>
        <MetaItem
          label="Warehouse enregistré"
          title={provenance.recorded_warehouse_path ?? undefined}
        >
          <span className="mono">
            {provenance.recorded_warehouse_path ?? "non renseigné"}
          </span>
        </MetaItem>
        <MetaItem label="Empreinte enregistrée" title={provenance.recorded_warehouse_sha256 ?? undefined}>
          <span className="mono">{shortHash(provenance.recorded_warehouse_sha256)}</span>
        </MetaItem>
      </dl>

      <h3>Sources enregistrées</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">Chemin</th>
              <th scope="col" className="num">
                Lignes
              </th>
              <th scope="col">Empreinte enregistrée</th>
              <th scope="col">Empreinte observée</th>
              <th scope="col">Concordance</th>
            </tr>
          </thead>
          <tbody>
            {provenance.sources.map((source) => (
              <tr key={source.source}>
                <td>{source.source}</td>
                <td className="mono cell-source" title={source.path ?? undefined}>
                  {source.path ?? "non renseigné"}
                </td>
                <td className="num">{source.rows ?? "—"}</td>
                <td className="mono" title={source.sha256 ?? undefined}>
                  {shortHash(source.sha256)}
                </td>
                <td className="mono" title={source.observed_sha256 ?? undefined}>
                  {shortHash(source.observed_sha256)}
                </td>
                <td>
                  {source.hash_match === true ? (
                    <span className="badge badge-ok">Concordante</span>
                  ) : source.hash_match === false ? (
                    <span className="badge badge-review">Incohérente</span>
                  ) : (
                    <span className="badge badge-warning">Non vérifiable</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Points de contrôle</h3>
      <ul className="issue-list">
        {provenance.issues.map((issue) => (
          <li key={issue}>
            <code>{issue}</code>
            <span>{reasonLabel(issue)}</span>
          </li>
        ))}
      </ul>

      <h3>Limites</h3>
      <ul className="limitation-list">
        {limitations.map((limitation) => (
          <li key={limitation}>{limitation}</li>
        ))}
      </ul>

      <p className="disclaimer">
        Ce tableau de bord ne certifie ni la qualité des sources ni l'approbation de publication.
        Toute valeur marquée « revue requise » doit être vérifiée avant diffusion.
      </p>
    </footer>
  );
}
