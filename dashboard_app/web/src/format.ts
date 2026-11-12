import { t } from "./i18n";
import { getLang } from "./preferences";

function L(fr: string, en: string, ar: string): string {
  const lang = getLang();
  return lang === "en" ? en : lang === "ar" ? ar : fr;
}

function numberLocale(): string {
  // chiffres latins partout : les libellés et séries restent cohérents avec les graphiques
  return getLang() === "fr" ? "fr-FR" : "en-US";
}

export function fmtNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return t("Indisponible");
  }
  try {
    return new Intl.NumberFormat(numberLocale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(value);
  } catch {
    const fixed = value.toFixed(digits);
    const [int, dec] = fixed.split(".");
    const spaced = int.replace(/\B(?=(\d{3})+(?!\d))/g, getLang() === "fr" ? "\u202f" : ",");
    return dec ? `${spaced},${dec}` : spaced;
  }
}

export function fmtSigned(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return t("Indisponible");
  }
  const prefix = value > 0 ? "+" : "";
  return prefix + fmtNumber(value, digits);
}

const UNIT_LABELS: Record<string, { fr: string; en: string; ar: string }> = {
  percent: { fr: "%", en: "%", ar: "%" },
  percentage_points: { fr: "points", en: "points", ar: "نقطة" },
  per_100k_adults: {
    fr: "/ 100 000 adultes",
    en: "per 100,000 adults",
    ar: "لكل 100 ألف بالغ",
  },
  per_1k_adults: {
    fr: "/ 1 000 adultes",
    en: "per 1,000 adults",
    ar: "لكل 1000 بالغ",
  },
  percent_of_gdp: { fr: "% du PIB", en: "% of GDP", ar: "% من الناتج" },
  index_2017_100: { fr: "base 100 en 2017", en: "2017 = 100", ar: "أساس 100 في 2017" },
  TND_per_month: { fr: "TND/mois", en: "TND/month", ar: "دينار/شهر" },
  TND_per_USD: { fr: "TND/USD", en: "TND/USD", ar: "دينار/دولار" },
  usd_current_per_capita: { fr: "USD/hab", en: "USD per capita", ar: "دولار/فرد" },
  count: { fr: "", en: "", ar: "" },
};

export function unitLabel(unit: string | null | undefined): string {
  if (!unit) return "";
  const entry = UNIT_LABELS[unit];
  if (!entry) return unit;
  const lang = getLang();
  return lang === "en" ? entry.en : lang === "ar" ? entry.ar : entry.fr;
}

export function unitDigits(unit: string | null | undefined): number {
  if (unit === "per_100k_adults" || unit === "TND_per_month") return 2;
  if (unit === "TND_per_USD") return 3;
  return 1;
}

export function fmtUnit(value: number | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined) return t("Indisponible");
  // un nombre entier (unite « count », sources utilisateur) s'affiche sans decimale
  const digits = unit === "count" && Number.isInteger(value) ? 0 : unitDigits(unit);
  const label = unitLabel(unit);
  return `${fmtNumber(value, digits)}${label ? ` ${label}` : ""}`;
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return t("Indisponible");
  const separator = getLang() === "fr" ? " " : "";
  return `${fmtNumber(value, digits)}${separator}%`;
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
      return L("Catalogue d'indicateurs", "Indicator catalogue", "فهرس المؤشرات");
    case "warehouse":
      return L("Base de données interne", "Internal database", "قاعدة بيانات داخلية");
    case "reference":
      return L("Source de référence", "Reference source", "مصدر مرجعي");
    case "derived":
      return L("Valeur calculée", "Calculated value", "قيمة محسوبة");
    default:
      return provider || "—";
  }
}

export function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "available":
      return L("Disponible", "Available", "متاح");
    case "placeholder":
      return L("En attente de données", "Awaiting data", "في انتظار البيانات");
    case "unavailable":
      return L("Indisponible", "Unavailable", "غير متاح");
    case "stable":
      return L("Stable", "Stable", "مستقر");
    case "changed":
      return L("Modifié", "Changed", "معدَّل");
    case "new":
      return L("Nouveau", "New", "جديد");
    case "removed":
      return L("Retiré", "Removed", "محذوف");
    case "done":
      return L("Terminé", "Done", "مكتمل");
    case "passed":
      return L("Validé", "Passed", "مقبول");
    case "failed":
      return L("Échec", "Failed", "فشل");
    case "out_of_scope":
      return L("Hors périmètre", "Out of scope", "خارج النطاق");
    default:
      return status || "—";
  }
}

export function shortHash(hash: string | null | undefined): string {
  if (!hash) return L("non renseignée", "not provided", "غير محددة");
  return hash.length > 16 ? `${hash.slice(0, 12)}…${hash.slice(-4)}` : hash;
}

export function prettyDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const lang = getLang();
  const locale = lang === "en" ? "en-GB" : lang === "ar" ? "ar-TN" : "fr-FR";
  try {
    return date.toLocaleString(locale, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return date.toLocaleString("fr-FR", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
}
