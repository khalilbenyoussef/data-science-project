import type { DashboardData } from "./types";

const REQUIRED_ARRAYS = [
  "cards",
  "series",
  "rankings",
  "comparisons",
  "table",
  "insights",
  "notices",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fail(message: string): never {
  throw new Error(message);
}

/**
 * Fail closed on a contract violation. The React app must never repair,
 * coerce or zero-fill a value: a missing observation stays null.
 */
export function validateDashboardData(raw: unknown): DashboardData {
  if (!isRecord(raw)) fail("Le fichier de données n'est pas un objet JSON.");
  if (raw.schema_version !== "1.0") {
    fail(`Version de schéma non supportée : ${String(raw.schema_version)}.`);
  }
  for (const key of REQUIRED_ARRAYS) {
    if (!Array.isArray(raw[key])) fail(`Champ manquant ou invalide : ${key}.`);
  }
  if (!isRecord(raw.scope)) fail("Périmètre (scope) absent.");
  if (!Array.isArray(raw.scope.countries) || !Array.isArray(raw.scope.kpis)) {
    fail("Périmètre (scope) incomplet : countries/kpis requis.");
  }
  if (!isRecord(raw.catalog) || typeof raw.catalog.version !== "string") {
    fail("Catalogue absent ou invalide.");
  }
  if (!isRecord(raw.provenance)) fail("Provenance absente.");
  if (typeof raw.provenance.warehouse_sha256 !== "string") {
    fail("Empreinte du warehouse manquante.");
  }
  if (typeof raw.publication_status !== "string") {
    fail("Statut de publication absent.");
  }

  const evidence = new Set<string>();
  for (const card of raw.cards as unknown[]) {
    if (!isRecord(card)) fail("Carte invalide.");
    if (typeof card.evidence_id !== "string" || card.evidence_id.length === 0) {
      fail("Carte sans identifiant de preuve.");
    }
    if (evidence.has(card.evidence_id)) {
      fail(`Identifiant de preuve dupliqué : ${card.evidence_id}.`);
    }
    evidence.add(card.evidence_id);
    if (typeof card.value === "number" && !Number.isFinite(card.value)) {
      fail(`Valeur non finie pour ${card.evidence_id}.`);
    }
    if (card.availability_status === "available" && typeof card.value !== "number") {
      fail(`Valeur disponible non numérique pour ${card.evidence_id}.`);
    }
    if (card.availability_status !== "available" && card.value !== null) {
      fail(`Valeur non nulle pour une observation indisponible : ${card.evidence_id}.`);
    }
  }
  return raw as unknown as DashboardData;
}
