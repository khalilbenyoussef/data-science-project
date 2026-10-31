export function fmtNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Indisponible";
  }
  const fixed = value.toFixed(digits);
  const [int, dec] = fixed.split(".");
  const spaced = int.replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f");
  return dec ? `${spaced.replace("-", "-")},${dec}` : spaced;
}

export function fmtSigned(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Indisponible";
  }
  const prefix = value > 0 ? "+" : "";
  return prefix + fmtNumber(value, digits);
}

const UNIT_LABELS: Record<string, string> = {
  percent: "%",
  percentage_points: "points",
  per_100k_adults: "/ 100 000 adultes",
  per_1k_adults: "/ 1 000 adultes",
  percent_of_gdp: "% du PIB",
  index_2017_100: "base 100 en 2017",
  TND_per_month: "TND/mois",
  TND_per_USD: "TND/USD",
  usd_current_per_capita: "USD/hab",
  count: "",
};

export function unitLabel(unit: string | null | undefined): string {
  if (!unit) return "";
  return UNIT_LABELS[unit] ?? unit;
}

export function unitDigits(unit: string | null | undefined): number {
  if (unit === "per_100k_adults" || unit === "TND_per_month") return 2;
  if (unit === "TND_per_USD") return 3;
  return 1;
}

export function fmtUnit(value: number | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined) return "Indisponible";
  const digits = unitDigits(unit);
  const label = unitLabel(unit);
  return `${fmtNumber(value, digits)}${label ? ` ${label}` : ""}`;
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "Indisponible";
  return `${fmtNumber(value, digits)} %`;
}

export function severityClass(severity: string | null | undefined): string {
  switch (severity) {
    case "warning":
    case "critical":
      return "sev-warning";
    case "review":
      return "sev-review";
    case "info":
    default:
      return "sev-info";
  }
}

export function providerLabel(provider: string | null | undefined): string {
  switch (provider) {
    case "semantic":
      return "Catalogue d'indicateurs";
    case "warehouse":
      return "Base de données interne";
    case "reference":
      return "Source de référence";
    case "derived":
      return "Valeur calculée";
    default:
      return provider || "—";
  }
}

export function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "available":
      return "Disponible";
    case "placeholder":
      return "En attente de données";
    case "unavailable":
      return "Indisponible";
    case "stable":
      return "Stable";
    case "changed":
      return "Modifié";
    case "new":
      return "Nouveau";
    case "removed":
      return "Retiré";
    case "done":
      return "Terminé";
    case "passed":
      return "Validé";
    case "failed":
      return "Échec";
    case "out_of_scope":
      return "Hors périmètre";
    default:
      return status || "—";
  }
}

export function shortHash(hash: string | null | undefined): string {
  if (!hash) return "non renseignée";
  return hash.length > 16 ? `${hash.slice(0, 12)}…${hash.slice(-4)}` : hash;
}

export function prettyDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
