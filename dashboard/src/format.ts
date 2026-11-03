const decimal = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const integer = new Intl.NumberFormat("fr-FR");

const REASON_LABELS: Record<string, string> = {
  raw_source_unavailable: "Source brute inaccessible",
  raw_source_hash_mismatch: "Empreinte source incohérente",
  source_metadata_missing: "Source non décrite dans la lineage",
  source_version_incomplete: "Version de source incomplète",
  lineage_run_id_missing: "Run de lineage absent",
  lineage_warehouse_path_missing: "Chemin warehouse absent",
  lineage_warehouse_path_mismatch: "Chemin warehouse incohérent",
  lineage_warehouse_path_invalid: "Chemin warehouse invalide",
  warehouse_content_binding_unverified: "Lien de contenu non vérifié",
  warehouse_hash_mismatch: "Empreinte warehouse incohérente",
  quality_provenance_mismatch: "Rapport qualité incohérent",
  quality_provenance_unverified: "Rapport qualité non rattaché",
  quality_gate_failed: "Gate qualité en échec",
  quality_gate_unknown: "Gate qualité indéterminé",
  quality_diagnostics_invalid: "Diagnostics qualité invalides",
  quality_issues_invalid: "Liste d'anomalies invalide",
  provisional_definition: "Définition provisoire",
  unresolved_input_quality_warning: "Alerte qualité sur l'entrée",
  out_of_catalog_year: "Année hors catalogue",
  missing_observation: "Observation absente",
  country_not_in_warehouse: "Pays absent du warehouse",
  invalid_country_dimension: "Dimension pays invalide",
  duplicate_observations: "Observations dupliquées",
  unexpected_input_unit: "Unité d'entrée inattendue",
  missing_or_nonfinite_input: "Valeur d'entrée absente",
  out_of_range_input: "Valeur d'entrée hors plage",
  no_available_observation: "Aucune observation disponible",
  observation_requires_review: "Revue d'observation",
};

const STATUS_LABELS: Record<string, string> = {
  available: "Disponible",
  unavailable: "Indisponible",
  requires_review: "Revue requise",
  complete: "Complet",
  incomplete: "Incomplet",
  single_country: "Pays unique",
  no_comparable_year: "Aucune année comparable",
  no_common_year: "Aucune année commune",
  out_of_catalog_year: "Année hors catalogue",
  verified: "Vérifié",
  verified_metadata: "Métadonnées vérifiées",
  derived_verified: "Dérivé vérifié",
  provisional: "Provisoire",
};

export function formatValue(
  value: number | null | undefined,
  unit: string,
  signed = false,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Indisponible";
  }
  const text = decimal.format(value);
  if (unit === "percent") return `${text} %`;
  if (unit === "percentage_points") {
    return `${signed && value > 0 ? "+" : ""}${text} pts`;
  }
  if (unit === "per_100k_adults") return `${text} / 100k adultes`;
  return `${text} ${unit}`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return integer.format(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "non disponible";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) {
    return "non disponible";
  }
  return `${decimal.format(bytes / (1024 * 1024))} Mo`;
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "non disponible";
  }
  return new Intl.NumberFormat("fr-FR", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function shortHash(hash: string | null | undefined): string {
  return hash ? `${hash.slice(0, 12)}…` : "non disponible";
}

export function reasonLabel(code: string | null | undefined): string {
  if (!code) return "motif non détaillé";
  return REASON_LABELS[code] ?? code;
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "non déterminé";
  return STATUS_LABELS[status] ?? status;
}

export function severityLabel(severity: string): string {
  if (severity === "review") return "Revue requise";
  if (severity === "warning") return "Alerte";
  return "Information";
}

export function unitLabel(unit: string): string {
  if (unit === "percent") return "pourcentage";
  if (unit === "percentage_points") return "points de pourcentage";
  if (unit === "per_100k_adults") return "pour 100 000 adultes";
  return unit;
}

export function contentBindingLabel(binding: string): string {
  if (binding === "recorded_and_verified") return "Enregistré et vérifié";
  if (binding === "recorded_mismatch") return "Enregistré mais incohérent";
  return "Non enregistré";
}

export function associationLabel(status: string): string {
  if (status === "matches_lineage") return "Concordante";
  if (status === "inconsistent") return "Incohérente";
  return "Non vérifiée";
}

// Statut de publication fixé par l'Auditor (kpi_values) ; jamais déduit ici.
const PUBLICATION_LABELS: Record<string, string> = {
  approved: "Approuvé",
  approved_with_review_note: "Approuvé avec réserve",
  blocked: "Bloqué",
  not_evaluated: "En attente de validation",
};

export function publicationLabel(status: string | null | undefined): string {
  return PUBLICATION_LABELS[status ?? "not_evaluated"] ?? PUBLICATION_LABELS.not_evaluated;
}

// Classes existantes uniquement : rouge pour « Bloqué », succès pour « Approuvé ».
export function publicationBadgeClass(status: string | null | undefined): string {
  if (status === "blocked") return "badge-danger";
  if (status === "approved") return "badge-ok";
  return "badge-neutral";
}
