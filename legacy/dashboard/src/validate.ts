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

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

// Nombre fini ou null ; jamais de chaine, de booleen ni d'infini.
function checkNumber(value: unknown, where: string, field = "value"): number | null {
  if (value === null || value === undefined) return null;
  if (!isNumber(value)) fail(`${where} : ${field} doit être un nombre fini ou null.`);
  return value;
}

// Disponibilité et valeur cohérentes : disponible -> nombre, sinon null.
function checkObservation(item: unknown, where: string): void {
  if (!isRecord(item)) fail(`${where} : objet attendu.`);
  const value = checkNumber(item.value, where);
  if (item.availability_status === "available" && value === null) {
    fail(`${where} : valeur disponible non numérique.`);
  }
  if (item.availability_status !== "available" && item.value !== null && item.value !== undefined) {
    fail(`${where} : valeur non nulle pour une observation indisponible.`);
  }
}

// S5 : séries, classements, comparaisons et table vérifiés valeur par valeur.
function checkNested(raw: Record<string, unknown>): void {
  (raw.table as unknown[]).forEach((row, index) => checkObservation(row, `table[${index}]`));
  (raw.series as unknown[]).forEach((series, index) => {
    if (!isRecord(series) || !Array.isArray(series.points)) fail(`series[${index}] : points requis.`);
    series.points.forEach((point, position) => checkObservation(point, `series[${index}].points[${position}]`));
  });
  (raw.rankings as unknown[]).forEach((ranking, index) => {
    if (!isRecord(ranking) || !Array.isArray(ranking.rows)) fail(`rankings[${index}] : rows requis.`);
    ranking.rows.forEach((row, position) => {
      const where = `rankings[${index}].rows[${position}]`;
      checkObservation(row, where);
      const rank = (row as Record<string, unknown>).rank;
      if (rank !== null && rank !== undefined && !Number.isInteger(rank)) fail(`${where} : rang entier attendu.`);
    });
  });
  (raw.comparisons as unknown[]).forEach((comparison, index) => {
    if (!isRecord(comparison) || !Array.isArray(comparison.rows)) fail(`comparisons[${index}] : rows requis.`);
    comparison.rows.forEach((row, position) => {
      const where = `comparisons[${index}].rows[${position}]`;
      if (!isRecord(row)) fail(`${where} : objet attendu.`);
      const values = (["value", "reference_value", "difference"] as const).map((key) => checkNumber(row[key], where, key));
      if (row.comparison_status === "complete" && values.includes(null)) {
        fail(`${where} : comparaison complète sans valeur, référence et écart.`);
      }
      if (row.comparison_status !== "complete" && values[2] !== null) {
        fail(`${where} : comparaison incomplète avec un écart non nul.`);
      }
    });
  });
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
  checkNested(raw);
  return raw as unknown as DashboardData;
}
