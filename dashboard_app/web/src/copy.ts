import type { Chip, Notice } from "./types";
import { englishNumbers, localizeProse } from "./i18n";
import { getLang, type Lang } from "./preferences";

const ISO_NAMES_FR: Record<string, string> = {
  TUN: "Tunisie",
  DZA: "Algérie",
  EGY: "Égypte",
  JOR: "Jordanie",
  MAR: "Maroc",
};

const ISO_NAMES_EN: Record<string, string> = {
  TUN: "Tunisia",
  DZA: "Algeria",
  EGY: "Egypt",
  JOR: "Jordan",
  MAR: "Morocco",
};

const ISO_NAMES_AR: Record<string, string> = {
  TUN: "تونس",
  DZA: "الجزائر",
  EGY: "مصر",
  JOR: "الأردن",
  MAR: "المغرب",
};

const TEXT_RULES: [RegExp, string][] = [
  // déjà expliqué sous le graphique : on évite la répétition
  [
    /Ce n'est pas un entonnoir de cohorte : les questions Findex sont posées séparément, la baisse n'est pas un taux de conversion individuel\./g,
    "",
  ],
  [
    /Chaque point est une observation observée; aucune interpolation\./g,
    "Chaque point est un chiffre publié par l'enquête ; aucune valeur n'est estimée.",
  ],
  [
    /; le pays sélectionné est mis en évidence\./g,
    ". Le pays sélectionné est mis en évidence.",
  ],
  [
    /Les colonnes fin11a-fin11f existent dans le fichier Findex brut mais ne sont pas configurées dans l'ETL : elles restent 'To load'\./g,
    "Les six colonnes détaillées existent dans le fichier Findex brut, mais ne sont pas encore intégrées à la préparation des données : elles restent en attente.",
  ],
  [/l'écart entre milieux/gi, "l'écart entre villes et campagnes"],
  [
    /sont des associations observées sur des sous-groupes distincts\./g,
    "sont des écarts observés entre groupes distincts, pas des effets mesurés.",
  ],
  [
    /Les sous-groupes ne sont pas des populations appariées\./g,
    "Les sous-groupes ne représentent pas les mêmes personnes.",
  ],
  [
    /Les barrières déclarées ne sont pas chargées dans le warehouse/g,
    "Les obstacles déclarés ne sont pas encore intégrés à la base de données",
  ],
  [/Les barrières déclarées/gi, "Les obstacles déclarés"],
  [/ces barrières/gi, "ces obstacles"],
  [/dessous; la/gi, "dessous ; la"],
  [/dans ce run/gi, "dans cette analyse"],
  [/\bUNDP\b/g, "PNUD"],
  [/des KPI d'inclusion/g, "des indicateurs d'inclusion"],
  [/un KPI d'inclusion/g, "un indicateur d'inclusion"],
  [/Contexte macro,/g, "Contexte macroéconomique,"],
  [
    /World Bank WDI - PA\.NUS\.FCRF \(taux de change officiel, moyenne annuelle\)/g,
    "Taux de change officiel, moyenne annuelle (Banque mondiale)",
  ],
  [
    /le libellé du dictionnaire ne concorde pas avec la définition Findex attendue/gi,
    "la description officielle de la Banque mondiale ne correspond pas exactement à la définition attendue",
  ],
  [
    /colonnes détaillées : cellules vides tant que la source n'est pas chargée\./gi,
    "Ces obstacles seront affichés dès que la source sera chargée.",
  ],
  [/\(Findex, dimension urbanicity\)/gi, "(enquête Findex, milieu de résidence)"],
  [/Instantane UNDP - Human Development Report \(cadre analytique\)/g, "Instantané — PNUD, Rapport sur le développement humain (cadre analytique)"],
  [/UNDP - Human Development Report \(cadre analytique\)/g, "PNUD — Rapport sur le développement humain (cadre analytique)"],
  [/Ventilation urbaine/gi, "Milieu urbain"],
  [/Ventilation rurale/gi, "Milieu rural"],
  [/colonnes d'années/gi, "données annuelles"],
  [
    /Le frais saisi est une hypothèse illustrative, pas une donnée\./g,
    "Les frais saisis sont une hypothèse illustrative, pas une donnée.",
  ],
  [/Le frais saisi/gi, "Les frais saisis"],
  [/budget\/consommation/gi, "budget et consommation"],
  [/Dérivé = PIB par habitant × FX \/ 12/g, "Calcul : PIB par habitant × taux de change ÷ 12"],
  [/unité : \/ 100 000 adultes/g, "unité : nombre pour 100 000 adultes"],
  [
    /Les repères statiques sont des agrégats Findex 2025 \(vague 2024\), pas des observations du pays\./g,
    "Ces repères régionaux proviennent de l'enquête Findex 2025 ; ce ne sont pas des observations de ce pays.",
  ],
  [/Association, pas causalité/gi, "Lien observé, pas une cause"],
  [/DZA, EGY, JOR, MAR, TUN/g, "Algérie, Égypte, Jordanie, Maroc, Tunisie"],
  [/Warehouse DuckDB/g, "Base de données"],
  [/\bdu warehouse\b/gi, "de la base de données"],
  [/\bau warehouse\b/gi, "à la base de données"],
  [/\bdans le warehouse\b/gi, "dans la base de données"],
  [/\ble warehouse\b/gi, "la base de données"],
  [/\bwarehouse\b/gi, "base de données"],
  [/\blineage\b/gi, "traçabilité"],
  [/\bspec\b/gi, "contrat de données"],
  [/KPI catalog/g, "Catalogue d'indicateurs"],
  [/catalogue KPI/g, "catalogue d'indicateurs"],
  [/\(fin24aP, (\d{4})\)/g, "($1)"],
  [/\bfin24aP\b/g, "indicateur d'urgence"],
  [/\s*\((?:fin17a|fin22a)\)/g, ""],
  [/\bfin11a ?[-→] ?fin11f\b/g, "colonnes détaillées"],
  [/sha256/gi, "empreinte"],
  [/\bATMs\b/g, "distributeurs automatiques"],
  [/\/ 100k adultes/g, "/ 100 000 adultes"],
  [/To load/g, "En attente de données"],
  [/not_evaluated/g, "en attente de validation"],
  [/ne sont pas configurées dans l'ETL/gi, "ne sont pas encore intégrées à la préparation des données"],
  [/dans l'ETL/gi, "dans la préparation des données"],
  [/agrégats Findex 2025 \(vague 2024\)/g, "repères de l'enquête Findex 2025 (vague 2024)"],
  [/aucune interpolation/gi, "aucune valeur estimée"],
  [/taux de conversion individuel/gi, "taux de passage individuel"],
  [/populations appariées/gi, "les mêmes personnes"],
  [/Tunisia/g, "Tunisie"],
  [/MENA hors revenu eleve/g, "MENA hors revenu élevé"],
  [/Revenu intermediaire inferieur/g, "Revenu intermédiaire inférieur"],
  [/Encours de crédits/g, "Crédits bancaires"],
  [/Encours de dépôts/g, "Dépôts bancaires"],
  [/Encours des prets/g, "Crédits bancaires"],
  [/Encours des depots/g, "Dépôts bancaires"],
  [/Deposants/g, "Déposants"],
  [/Bareme/g, "Barème"],
  [/Enquete/g, "Enquête"],
  [/menages/g, "ménages"],
  [/programmee/g, "programmée"],
  [/Verifier/g, "Vérifier"],
  [/annees -> lignes/g, "années mises en ligne"],
  [/echelles verifiees/g, "échelles vérifiées"],
  [/fractions converties en % au pivot/g, "fractions converties en pourcentages"],
  [/selection des series configurees/g, "sélection des séries configurées"],
  [/indicateurs PIB -> lignes/g, "indicateurs de PIB intégrés"],
  [/Pivot par pays x annee/g, "Croisement par pays et par année"],
  [/croissance PIB sur annee-1 uniquement/g, "croissance du PIB calculée sur l'année précédente"],
  [/jointure dimension pays/g, "rattachement à la liste des pays"],
  [/\bpt\b/g, "points"],
  [/ vs (\d{4})/g, " depuis $1"],
  [/ & /g, " et "],
];

export function plainText(text: string | null | undefined): string {
  if (!text) return "";
  if (getLang() !== "fr") {
    const localized = localizeProse(text);
    return getLang() === "en" ? englishNumbers(localized) : localized;
  }
  let out = text;
  for (const [pattern, replacement] of TEXT_RULES) out = out.replace(pattern, replacement);
  // décimales à la française, hors suffixes de version (2.0) et codes
  out = out.replace(/(\d)\.(\d)/g, (_match, before: string, after: string) =>
    `${before},${after}`,
  );
  // séparateur de milliers à la française pour les nombres à quatre chiffres
  out = out.replace(/\b(\d)(\d{3}),(\d)/g, "$1 $2,$3");
  return out;
}

function L(fr: string, en: string, ar: string): string {
  const lang = getLang();
  return lang === "en" ? en : lang === "ar" ? ar : fr;
}

function localizedMap<T>(
  fr: Record<string, T>,
  en: Record<string, T> | undefined,
  ar: Record<string, T> | undefined,
): Record<string, T> {
  return new Proxy(fr, {
    get(target, prop, receiver) {
      if (typeof prop !== "string") return Reflect.get(target, prop, receiver);
      const lang = getLang();
      if (lang === "en") return en && prop in en ? en[prop] : target[prop];
      if (lang === "ar") return ar && prop in ar ? ar[prop] : target[prop];
      return target[prop];
    },
  });
}

const METRIC_LABELS_FR: Record<string, string> = {
  account_ownership: "Taux de détention d'un compte",
  digital_payment_rate: "Paiement numérique utilisé",
  saving_rate: "Épargne (toute forme)",
  emergency_money: "Fonds d'urgence en 30 jours : possible",
  atm_per_100k: "Distributeurs automatiques",
  branch_density: "Agences bancaires",
  depositors_per_1k: "Déposants pour 1 000 adultes",
  borrowers_per_1k: "Emprunteurs pour 1 000 adultes",
  loans_pct_gdp: "Crédits bancaires (% du PIB)",
  deposits_pct_gdp: "Dépôts bancaires (% du PIB)",
  urban_account: "Compte — milieu urbain",
  rural_account: "Compte — milieu rural",
};

const METRIC_LABELS_EN: Record<string, string> = {
  account_ownership: "Account ownership rate",
  digital_payment_rate: "Digital payment used",
  saving_rate: "Savings (any form)",
  emergency_money: "Emergency funds within 30 days: possible",
  atm_per_100k: "ATMs",
  branch_density: "Bank branches",
  depositors_per_1k: "Depositors per 1,000 adults",
  borrowers_per_1k: "Borrowers per 1,000 adults",
  loans_pct_gdp: "Bank credit (% of GDP)",
  deposits_pct_gdp: "Bank deposits (% of GDP)",
  urban_account: "Account — urban areas",
  rural_account: "Account — rural areas",
};

const METRIC_LABELS_AR: Record<string, string> = {
  account_ownership: "معدل امتلاك حساب",
  digital_payment_rate: "استخدام الدفع الرقمي",
  saving_rate: "الادخار (بأي شكل)",
  emergency_money: "أموال طارئة خلال 30 يومًا: ممكن",
  atm_per_100k: "الصرافات الآلية",
  branch_density: "الفروع البنكية",
  depositors_per_1k: "المودعون لكل 1000 بالغ",
  borrowers_per_1k: "المقترضون لكل 1000 بالغ",
  loans_pct_gdp: "الائتمان البنكي (% من الناتج)",
  deposits_pct_gdp: "الودائع البنكية (% من الناتج)",
  urban_account: "حساب — المدن",
  rural_account: "حساب — الريف",
};

export const METRIC_LABELS = localizedMap(METRIC_LABELS_FR, METRIC_LABELS_EN, METRIC_LABELS_AR);

const INFO_LABELS_FR: Record<string, string> = {
  "macro-gdp_pc": "PIB par habitant",
  fx_tnd_usd_2024: "Taux de change officiel moyen 2024",
  derived_monthly_magnitude: "Ordre de grandeur mensuel (calculé)",
};

const INFO_LABELS_EN: Record<string, string> = {
  "macro-gdp_pc": "GDP per capita",
  fx_tnd_usd_2024: "Official average exchange rate 2024",
  derived_monthly_magnitude: "Monthly order of magnitude (calculated)",
};

const INFO_LABELS_AR: Record<string, string> = {
  "macro-gdp_pc": "الناتج المحلي للفرد",
  fx_tnd_usd_2024: "سعر الصرف الرسمي المتوسط 2024",
  derived_monthly_magnitude: "حجم شهري تقريبي (محسوب)",
};

export const INFO_LABELS = localizedMap(INFO_LABELS_FR, INFO_LABELS_EN, INFO_LABELS_AR);

const PAGE_COPY_FR: Record<string, { title: string; subtitle: string }> = {
  overview: {
    title: "Vue d'ensemble",
    subtitle: "L'accès et l'usage des services financiers, chiffres à l'appui.",
  },
  inclusion: {
    title: "Inclusion et inégalités",
    subtitle: "Qui utilise les services financiers, et comment les écarts évoluent.",
  },
  access: {
    title: "Accès et crédit",
    subtitle: "Réseau bancaire, dépôts, crédits et équilibre entre offre et demande.",
  },
  exclusion: {
    title: "Pourquoi l'exclusion ?",
    subtitle: "Obstacles déclarés, différence entre villes et campagnes, analyse prudente des causes.",
  },
  pipeline: {
    title: "Sources et qualité",
    subtitle: "D'où viennent les chiffres, comment ils sont contrôlés et mis à jour.",
  },
};

const PAGE_COPY_EN: Record<string, { title: string; subtitle: string }> = {
  overview: {
    title: "Overview",
    subtitle: "Access to and use of financial services, backed by figures.",
  },
  inclusion: {
    title: "Inclusion and inequalities",
    subtitle: "Who uses financial services, and how the gaps evolve.",
  },
  access: {
    title: "Access and credit",
    subtitle: "Banking network, deposits, credit and the balance between supply and demand.",
  },
  exclusion: {
    title: "Why exclusion?",
    subtitle: "Reported barriers, urban–rural differences and a careful analysis of causes.",
  },
  pipeline: {
    title: "Sources and quality",
    subtitle: "Where the figures come from, how they are checked and updated.",
  },
};

const PAGE_COPY_AR: Record<string, { title: string; subtitle: string }> = {
  overview: {
    title: "نظرة عامة",
    subtitle: "الوصول إلى الخدمات المالية واستخدامها، بالأرقام.",
  },
  inclusion: {
    title: "الإدماج والفوارق",
    subtitle: "من يستخدم الخدمات المالية، وكيف تتطور الفجوات.",
  },
  access: {
    title: "الوصول والائتمان",
    subtitle: "الشبكة البنكية والودائع والائتمان والتوازن بين العرض والطلب.",
  },
  exclusion: {
    title: "لماذا الإقصاء؟",
    subtitle: "العوائق المعلنة والفروق بين المدن والأرياف وتحليل حذر للأسباب.",
  },
  pipeline: {
    title: "المصادر والجودة",
    subtitle: "من أين تأتي الأرقام وكيف تُفحص وتُحدَّث.",
  },
};

export const PAGE_COPY = localizedMap(PAGE_COPY_FR, PAGE_COPY_EN, PAGE_COPY_AR);

const CHART_TITLES_FR: Record<string, string> = {
  account_ownership_history: "Détention d'un compte, par enquête Findex",
  account_ownership_peers: "Comparaison régionale — détention d'un compte",
  inclusion_funnel: "Du compte à l'usage formel",
  formal_vs_any: "Usage formel et usage informel",
  account_ownership_groups: "Détention d'un compte par groupe",
  physical_network: "Réseau physique (2015-2024)",
  supply_demand_index: "Offre et demande, base 100 en 2017",
  atm_peers: "Distributeurs automatiques pour 100 000 adultes — comparaison régionale",
  barriers_heatmap: "Obstacles à l'ouverture d'un compte",
  urban_rural: "Détention d'un compte : villes et zones rurales",
};

const CHART_TITLES_EN: Record<string, string> = {
  account_ownership_history: "Account ownership, by Findex survey",
  account_ownership_peers: "Regional comparison — account ownership",
  inclusion_funnel: "From account to formal use",
  formal_vs_any: "Formal and informal use",
  account_ownership_groups: "Account ownership by group",
  physical_network: "Physical network (2015-2024)",
  supply_demand_index: "Supply and demand, 2017 = 100",
  atm_peers: "ATMs per 100,000 adults — regional comparison",
  barriers_heatmap: "Barriers to opening an account",
  urban_rural: "Account ownership: urban and rural areas",
};

const CHART_TITLES_AR: Record<string, string> = {
  account_ownership_history: "ملكية الحساب حسب موجة Findex",
  account_ownership_peers: "مقارنة إقليمية — ملكية الحساب",
  inclusion_funnel: "من الحساب إلى الاستخدام الرسمي",
  formal_vs_any: "الاستخدام الرسمي وغير الرسمي",
  account_ownership_groups: "ملكية الحساب حسب المجموعة",
  physical_network: "الشبكة الفيزيائية (2015-2024)",
  supply_demand_index: "العرض والطلب، أساس 100 في 2017",
  atm_peers: "الصرافات الآلية لكل 100 ألف بالغ — مقارنة إقليمية",
  barriers_heatmap: "عوائق فتح حساب",
  urban_rural: "ملكية الحساب: المدن والمناطق الريفية",
};

export const CHART_TITLES = localizedMap(CHART_TITLES_FR, CHART_TITLES_EN, CHART_TITLES_AR);

const STEP_LABELS_FR: Record<string, string> = {
  account_ownership: "Détention d'un compte",
  digital_payment_rate: "Paiement numérique",
  formal_saving: "Épargne formelle",
  formal_borrowing: "Emprunt formel",
};

const STEP_LABELS_EN: Record<string, string> = {
  account_ownership: "Account ownership",
  digital_payment_rate: "Digital payment",
  formal_saving: "Formal savings",
  formal_borrowing: "Formal borrowing",
};

const STEP_LABELS_AR: Record<string, string> = {
  account_ownership: "ملكية حساب",
  digital_payment_rate: "دفع رقمي",
  formal_saving: "ادخار رسمي",
  formal_borrowing: "اقتراض رسمي",
};

export const STEP_LABELS = localizedMap(STEP_LABELS_FR, STEP_LABELS_EN, STEP_LABELS_AR);

// Libellés du glossaire Findex 2025 (lignes 6 à 11)
const HEATMAP_ROW_LABELS_FR: Record<string, string> = {
  fin11a: "Trop éloigné",
  fin11b: "Trop cher",
  fin11c: "Documents manquants",
  fin11d: "Fonds insuffisants",
  fin11e: "Un proche en a déjà un",
  fin11f: "Manque de confiance",
};

const HEATMAP_ROW_LABELS_EN: Record<string, string> = {
  fin11a: "Too far",
  fin11b: "Too expensive",
  fin11c: "Missing documents",
  fin11d: "Insufficient funds",
  fin11e: "A relative already has one",
  fin11f: "Lack of trust",
};

const HEATMAP_ROW_LABELS_AR: Record<string, string> = {
  fin11a: "بعيد جدًا",
  fin11b: "مكلف جدًا",
  fin11c: "وثائق ناقصة",
  fin11d: "أموال غير كافية",
  fin11e: "أحد الأقارب لديه حساب",
  fin11f: "غياب الثقة",
};

export const HEATMAP_ROW_LABELS = localizedMap(
  HEATMAP_ROW_LABELS_FR,
  HEATMAP_ROW_LABELS_EN,
  HEATMAP_ROW_LABELS_AR,
);

// Statut de publication fixé par l'Auditor ; « en attente de validation » reprend la règle not_evaluated ci-dessus.
const PUBLICATION_LABELS_FR: Record<string, string> = {
  approved: "Approuvé",
  approved_with_review_note: "Approuvé avec réserve",
  blocked: "Bloqué",
  not_evaluated: "En attente de validation",
};

const PUBLICATION_LABELS_EN: Record<string, string> = {
  approved: "Approved",
  approved_with_review_note: "Approved with reservation",
  blocked: "Blocked",
  not_evaluated: "Awaiting validation",
};

const PUBLICATION_LABELS_AR: Record<string, string> = {
  approved: "معتمد",
  approved_with_review_note: "معتمد بتحفظ",
  blocked: "محجوب",
  not_evaluated: "في انتظار التحقق",
};

export const PUBLICATION_LABELS = localizedMap(
  PUBLICATION_LABELS_FR,
  PUBLICATION_LABELS_EN,
  PUBLICATION_LABELS_AR,
);

const DEFINITION_STATUS_FR: Record<string, string> = {
  verified: "Définition vérifiée",
  verified_metadata: "Métadonnées vérifiées",
  provisional: "Définition provisoire",
  hors_catalogue: "Indicateur complémentaire",
  secondary_source: "Source secondaire",
  official_source: "Source officielle",
};

const DEFINITION_STATUS_EN: Record<string, string> = {
  verified: "Verified definition",
  verified_metadata: "Verified metadata",
  provisional: "Provisional definition",
  hors_catalogue: "Complementary indicator",
  secondary_source: "Secondary source",
  official_source: "Official source",
};

const DEFINITION_STATUS_AR: Record<string, string> = {
  verified: "تعريف متحقق منه",
  verified_metadata: "بيانات وصفية متحقق منها",
  provisional: "تعريف مؤقت",
  hors_catalogue: "مؤشر تكميلي",
  secondary_source: "مصدر ثانوي",
  official_source: "مصدر رسمي",
};

export const DEFINITION_STATUS = localizedMap(
  DEFINITION_STATUS_FR,
  DEFINITION_STATUS_EN,
  DEFINITION_STATUS_AR,
);

const REVIEW_REASONS_FR: Record<string, string> = {
  source_version_incomplete: "Référence de la source incomplète",
  warehouse_content_binding_unverified: "Empreinte de la base non confirmée",
  quality_provenance_unverified: "Contrôle qualité non rattaché à la collecte",
  provisional_definition: "Définition provisoire",
  not_in_kpi_catalog: "Hors du catalogue d'indicateurs",
  warehouse_definition_unverified: "Définition non confirmée",
  dictionary_label_mismatch: "Libellé du dictionnaire à confirmer",
  secondary_source: "Source secondaire",
  qualitative: "Donnée qualitative",
  derived_value: "Valeur calculée",
};

const REVIEW_REASONS_EN: Record<string, string> = {
  source_version_incomplete: "Incomplete source reference",
  warehouse_content_binding_unverified: "Database fingerprint not confirmed",
  quality_provenance_unverified: "Quality check not linked to collection",
  provisional_definition: "Provisional definition",
  not_in_kpi_catalog: "Outside the indicator catalogue",
  warehouse_definition_unverified: "Definition not confirmed",
  dictionary_label_mismatch: "Dictionary label to confirm",
  secondary_source: "Secondary source",
  qualitative: "Qualitative data",
  derived_value: "Calculated value",
};

const REVIEW_REASONS_AR: Record<string, string> = {
  source_version_incomplete: "مرجع المصدر غير مكتمل",
  warehouse_content_binding_unverified: "بصمة قاعدة البيانات غير مؤكدة",
  quality_provenance_unverified: "فحص الجودة غير مرتبط بالجمع",
  provisional_definition: "تعريف مؤقت",
  not_in_kpi_catalog: "خارج فهرس المؤشرات",
  warehouse_definition_unverified: "تعريف غير مؤكد",
  dictionary_label_mismatch: "تسمية القاموس بحاجة إلى تأكيد",
  secondary_source: "مصدر ثانوي",
  qualitative: "بيانات نوعية",
  derived_value: "قيمة محسوبة",
};

export const REVIEW_REASONS = localizedMap(REVIEW_REASONS_FR, REVIEW_REASONS_EN, REVIEW_REASONS_AR);

const DEFINITION_FR: Record<string, string> = {
  account_ownership:
    "Part des adultes qui détiennent un compte dans une banque ou un établissement financier, ou un compte mobile money.",
  digital_payment_rate:
    "Part des adultes ayant effectué ou reçu un paiement numérique au cours de l'année écoulée, tous usages confondus.",
  saving_rate:
    "Part des adultes ayant épargné ou mis de côté de l'argent, pour toute raison et sous toute forme, au cours de l'année écoulée.",
  emergency_money:
    "Part des adultes déclarant pouvoir réunir une somme d'argent d'urgence en 30 jours.",
  atm_per_100k: "Nombre de distributeurs automatiques pour 100 000 adultes.",
  branch_density:
    "Nombre d'agences de banques commerciales pour 100 000 adultes, selon le Fonds monétaire international (FAS).",
  depositors_per_1k: "Nombre de déposants dans les banques commerciales pour 1 000 adultes.",
  borrowers_per_1k: "Nombre d'emprunteurs dans les banques commerciales pour 1 000 adultes.",
  loans_pct_gdp:
    "Encours des crédits accordés par les banques commerciales, en pourcentage du produit intérieur brut (PIB).",
  deposits_pct_gdp:
    "Encours des dépôts dans les banques commerciales, en pourcentage du produit intérieur brut (PIB).",
  urban_account: "Part des adultes vivant en ville qui détiennent un compte.",
  rural_account: "Part des adultes vivant en zone rurale qui détiennent un compte.",
};

const DEFINITION_EN: Record<string, string> = {
  account_ownership:
    "Share of adults who have an account at a bank or financial institution, or a mobile money account.",
  digital_payment_rate:
    "Share of adults who made or received a digital payment in the past year, for any purpose.",
  saving_rate:
    "Share of adults who saved or set aside money, for any reason and in any form, in the past year.",
  emergency_money:
    "Share of adults who say they could raise emergency money within 30 days.",
  atm_per_100k: "Number of automated teller machines (ATMs) per 100,000 adults.",
  branch_density:
    "Number of commercial bank branches per 100,000 adults, according to the International Monetary Fund (FAS).",
  depositors_per_1k: "Number of depositors at commercial banks per 1,000 adults.",
  borrowers_per_1k: "Number of borrowers from commercial banks per 1,000 adults.",
  loans_pct_gdp:
    "Outstanding loans by commercial banks as a percentage of gross domestic product (GDP).",
  deposits_pct_gdp:
    "Outstanding deposits at commercial banks as a percentage of gross domestic product (GDP).",
  urban_account: "Share of adults living in cities who have an account.",
  rural_account: "Share of adults living in rural areas who have an account.",
};

const DEFINITION_AR: Record<string, string> = {
  account_ownership:
    "نسبة البالغين الذين يمتلكون حسابًا في بنك أو مؤسسة مالية، أو حساب أموال عبر الهاتف المحمول.",
  digital_payment_rate:
    "نسبة البالغين الذين أجروا أو استلموا دفعة رقمية خلال السنة الماضية، لأي غرض.",
  saving_rate:
    "نسبة البالغين الذين ادّخروا أو خصّصوا أموالًا، لأي سبب وبأي شكل، خلال السنة الماضية.",
  emergency_money:
    "نسبة البالغين الذين يقولون إنهم يستطيعون جمع أموال طارئة خلال 30 يومًا.",
  atm_per_100k: "عدد الصرافات الآلية لكل 100 ألف بالغ.",
  branch_density:
    "عدد فروع البنوك التجارية لكل 100 ألف بالغ، وفق صندوق النقد الدولي (FAS).",
  depositors_per_1k: "عدد المودعين في البنوك التجارية لكل 1000 بالغ.",
  borrowers_per_1k: "عدد المقترضين من البنوك التجارية لكل 1000 بالغ.",
  loans_pct_gdp:
    "الائتمان القائم الممنوح من البنوك التجارية كنسبة من الناتج المحلي الإجمالي.",
  deposits_pct_gdp:
    "الودائع القائمة في البنوك التجارية كنسبة من الناتج المحلي الإجمالي.",
  urban_account: "نسبة البالغين المقيمين في المدن الذين يمتلكون حسابًا.",
  rural_account: "نسبة البالغين المقيمين في المناطق الريفية الذين يمتلكون حسابًا.",
};

const CAVEAT_FR: Record<string, string> = {};

export function friendlyDefinition(metricId: string, definition: string | null): string {
  const lang = getLang();
  if (lang === "en") return DEFINITION_EN[metricId] ?? (plainText(definition) || "—");
  if (lang === "ar") return DEFINITION_AR[metricId] ?? (plainText(definition) || "—");
  return DEFINITION_FR[metricId] ?? (plainText(definition) || "—");
}

export function friendlyCaveat(metricId: string, caveat: string | null): string {
  if (!caveat) return "";
  return CAVEAT_FR[metricId] ?? plainText(caveat);
}

const FILTER_TOKENS_FR: Record<string, string> = {
  total_population: "population totale",
  commercial_banks_all_adults: "banques commerciales, tous adultes",
  "bank_type=commercial_banks": "banques commerciales",
  "urbanicity=urban": "milieu urbain",
  "urbanicity=rural": "milieu rural",
  "all=all": "ensemble des adultes",
};

const FILTER_TOKENS_EN: Record<string, string> = {
  total_population: "total population",
  commercial_banks_all_adults: "commercial banks, all adults",
  "bank_type=commercial_banks": "commercial banks",
  "urbanicity=urban": "urban areas",
  "urbanicity=rural": "rural areas",
  "all=all": "all adults",
};

const FILTER_TOKENS_AR: Record<string, string> = {
  total_population: "إجمالي السكان",
  commercial_banks_all_adults: "بنوك تجارية، جميع البالغين",
  "bank_type=commercial_banks": "بنوك تجارية",
  "urbanicity=urban": "المناطق الحضرية",
  "urbanicity=rural": "المناطق الريفية",
  "all=all": "جميع البالغين",
};

export function friendlyFilter(filter: string | null): string {
  const lang = getLang();
  if (!filter) return "—";
  if (filter.startsWith("référence statique")) {
    return L(
      "Référence nationale, sans filtre pays",
      "National reference, no country filter",
      "مرجع وطني، دون تصفية حسب البلد",
    );
  }
  const iso = lang === "en" ? ISO_NAMES_EN : lang === "ar" ? ISO_NAMES_AR : ISO_NAMES_FR;
  const tokens = lang === "en" ? FILTER_TOKENS_EN : lang === "ar" ? FILTER_TOKENS_AR : FILTER_TOKENS_FR;
  const parts = filter
    .split(" · ")
    .map((part) => {
      const match = part.match(/^iso3=([A-Z]{3})$/);
      if (match) return iso[match[1]] ?? match[1];
      if (tokens[part]) return tokens[part];
      if (/^[a-z0-9_]+$/.test(part)) return null;
      return plainText(part);
    })
    .filter(Boolean);
  return parts.length
    ? parts.join(" · ")
    : L("Population totale", "Total population", "إجمالي السكان");
}

const SOURCE_NAMES_FR: Record<string, string> = {
  findex: "enquête Findex (Banque mondiale)",
  fas: "FMI — accès aux services financiers (FAS)",
  gdp: "indicateurs mondiaux (Banque mondiale)",
  wdi: "indicateurs mondiaux (Banque mondiale)",
};

const SOURCE_NAMES_EN: Record<string, string> = {
  findex: "Findex survey (World Bank)",
  fas: "IMF — Financial Access Survey (FAS)",
  gdp: "World Development Indicators (World Bank)",
  wdi: "World Development Indicators (World Bank)",
};

const SOURCE_NAMES_AR: Record<string, string> = {
  findex: "مسح Findex (البنك الدولي)",
  fas: "صندوق النقد الدولي — مسح الوصول إلى الخدمات المالية (FAS)",
  gdp: "مؤشرات التنمية العالمية (البنك الدولي)",
  wdi: "مؤشرات التنمية العالمية (البنك الدولي)",
};

export function friendlySource(source: string | null): string {
  const lang = getLang();
  if (!source) return "—";
  const names = lang === "en" ? SOURCE_NAMES_EN : lang === "ar" ? SOURCE_NAMES_AR : SOURCE_NAMES_FR;
  const catalog = source.match(/^KPI catalog · ([a-z0-9_]+)/);
  if (catalog) {
    const prefix = L("Catalogue d'indicateurs", "Indicator catalogue", "فهرس المؤشرات");
    return `${prefix} · ${names[catalog[1]] ?? catalog[1]}`;
  }
  if (source.startsWith("Warehouse DuckDB") || source.startsWith("Base de données")) {
    return L(
      "Base de données interne · FMI (FAS) et enquête Findex",
      "Internal database · IMF (FAS) and Findex survey",
      "قاعدة بيانات داخلية · صندوق النقد الدولي (FAS) ومسح Findex",
    );
  }
  if (source.startsWith("INS - Enquete nationale")) {
    return L(
      "INS — enquête sur le budget et le niveau de vie des ménages (2021)",
      "INS — national household budget and living standards survey (2021)",
      "المعهد الوطني للإحصاء — مسح ميزانية الأسر ومستويات المعيشة (2021)",
    );
  }
  if (source.startsWith("INS - ENBCNV")) {
    return L(
      "INS — enquête ENBCNV 2021",
      "INS — ENBCNV survey 2021",
      "المعهد الوطني للإحصاء — مسح ENBCNV 2021",
    );
  }
  return plainText(source);
}

export function chipLabel(chip: Chip | null): string {
  if (!chip) return "";
  const kind = chip.label.split("·").pop()?.trim() ?? "";
  switch (chip.provider) {
    case "semantic":
      return kind === "provisional"
        ? L("Indicateur provisoire", "Provisional indicator", "مؤشر مؤقت")
        : L("Indicateur suivi", "Tracked indicator", "مؤشر متابَع");
    case "warehouse":
      return L("Source interne", "Internal source", "مصدر داخلي");
    case "reference":
      return kind === "secondary_source"
        ? L("Source secondaire", "Secondary source", "مصدر ثانوي")
        : L("Source officielle", "Official source", "مصدر رسمي");
    case "derived":
      return L("Valeur calculée", "Calculated value", "قيمة محسوبة");
    default:
      return plainText(chip.label);
  }
}

export function chipNeedsReview(chip: Chip | null): boolean {
  if (!chip || !chip.requires_review) return false;
  const kind = chip.label.split("·").pop()?.trim() ?? "";
  if (kind === "provisional") return false;
  return chip.provider === "warehouse" || kind === "secondary_source" || kind === "hors_catalogue";
}

export function chipTitle(chip: Chip | null): string {
  if (!chip) return "";
  return chip.note ? `${chip.label} — ${plainText(chip.note)}` : chip.label;
}

export interface NoticeCopy {
  tag: string;
  message: string;
}

export function noticeCopy(notice: Notice): NoticeCopy {
  const count = notice.message.match(/\d+/)?.[0];
  switch (notice.code) {
    case "observation_requires_review":
      return {
        tag: L("À vérifier", "To review", "بحاجة إلى مراجعة"),
        message: L(
          `${count ?? "Plusieurs"} observations sont signalées : définition provisoire ou traçabilité à compléter.`,
          `${count ?? "Several"} observations are flagged: provisional definition or incomplete traceability.`,
          `${count ?? "عدة"} ملاحظات مُشار إليها: تعريف مؤقت أو تتبّع غير مكتمل.`,
        ),
      };
    case "provisional_definition": {
      const name =
        notice.kpi_id === "saving_rate"
          ? L("L'épargne, toutes formes confondues,", "Savings, in any form,", "الادخار، بجميع أشكاله،")
          : notice.kpi_id === "borrowing_rate"
            ? L("L'emprunt, toutes formes confondues,", "Borrowing, in any form,", "الاقتراض، بجميع أشكاله،")
            : L("Cet indicateur", "This indicator", "هذا المؤشر");
      return {
        tag: L("Définition provisoire", "Provisional definition", "تعريف مؤقت"),
        message: L(
          `${name} repose sur une définition provisoire, en attente de validation.`,
          `${name} relies on a provisional definition pending validation.`,
          `${name} يعتمد على تعريف مؤقت في انتظار التحقق.`,
        ),
      };
    }
    case "quality_provenance_unverified":
      return {
        tag: L("Traçabilité", "Traceability", "التتبّع"),
        message: L(
          "Le contrôle qualité n'est pas encore rattaché à la collecte d'origine.",
          "The quality check is not yet linked to the original collection.",
          "فحص الجودة غير مرتبط بعد بعملية الجمع الأصلية.",
        ),
      };
    case "source_version_incomplete":
      return {
        tag: L("Traçabilité", "Traceability", "التتبّع"),
        message: L(
          "La référence complète du fichier source n'est pas disponible.",
          "The full reference of the source file is not available.",
          "المرجع الكامل لملف المصدر غير متاح.",
        ),
      };
    case "warehouse_content_binding_unverified":
      return {
        tag: L("Traçabilité", "Traceability", "التتبّع"),
        message: L(
          "Le lien entre la base de données et les fichiers sources n'a pas encore été confirmé.",
          "The link between the database and the source files has not yet been confirmed.",
          "الرابط بين قاعدة البيانات وملفات المصادر لم يُؤكَّد بعد.",
        ),
      };
    case "source_notice:empty_columns":
      return {
        tag: L("Qualité de la source", "Source quality", "جودة المصدر"),
        message: L(
          "Une colonne entièrement vide a été ignorée dans le fichier FAS.",
          "An entirely empty column was ignored in the FAS file.",
          "تم تجاهل عمود فارغ بالكامل في ملف FAS.",
        ),
      };
    case "source_notice:negative_values":
      return {
        tag: L("Qualité de la source", "Source quality", "جودة المصدر"),
        message: L(
          "Des valeurs négatives ont été détectées dans les colonnes d'années du fichier FAS.",
          "Negative values were detected in the year columns of the FAS file.",
          "تم رصد قيم سالبة في أعمدة السنوات بملف FAS.",
        ),
      };
    case "fin24aP_definition":
      return {
        tag: L("Définition à confirmer", "Definition to confirm", "تعريف بحاجة إلى تأكيد"),
        message: L(
          "L'indicateur « fonds d'urgence » porte un libellé différent dans le dictionnaire de la Banque mondiale : sa valeur est affichée mais signalée.",
          "The “emergency funds” indicator has a different label in the World Bank dictionary: its value is shown but flagged.",
          "مؤشر «الأموال الطارئة» يحمل تسمية مختلفة في قاموس البنك الدولي: تُعرض قيمته مع الإشارة إليها.",
        ),
      };
    case "warehouse_not_in_catalog":
      return {
        tag: L("Indicateurs complémentaires", "Complementary indicators", "مؤشرات تكميلية"),
        message: L(
          "Certains indicateurs (distributeurs, agences, dépôts et crédits) viennent de la base interne et non du catalogue officiel : ils sont à vérifier.",
          "Some indicators (ATMs, branches, deposits and credit) come from the internal database rather than the official catalogue: they are to be checked.",
          "بعض المؤشرات (الصرافات والفروع والودائع والائتمان) تأتي من قاعدة البيانات الداخلية لا من الفهرس الرسمي: وهي بحاجة إلى تحقق.",
        ),
      };
    case "publication_not_evaluated":
      return {
        tag: L("Publication", "Publication", "النشر"),
        message: L(
          "Les données n'ont pas encore reçu de validation finale pour publication.",
          "The data have not yet received final approval for publication.",
          "لم تحصل البيانات بعد على الموافقة النهائية للنشر.",
        ),
      };
    case "loans_pct_gdp_now_available":
      return {
        tag: L("Donnée disponible", "Data available", "بيانات متاحة"),
        message: L(
          "Les crédits bancaires sont désormais disponibles pour 2024 : la valeur réelle remplace la mention « à charger ».",
          "Bank credit is now available for 2024: the actual value replaces the “to load” note.",
          "الائتمان البنكي متاح الآن لعام 2024: القيمة الفعلية تحل محل عبارة «قيد التحميل».",
        ),
      };
    case "deposits_pct_gdp_now_available":
      return {
        tag: L("Donnée disponible", "Data available", "بيانات متاحة"),
        message: L(
          "Les dépôts bancaires sont désormais disponibles pour 2024 : la valeur réelle remplace la mention « à charger ».",
          "Bank deposits are now available for 2024: the actual value replaces the “to load” note.",
          "الودائع البنكية متاحة الآن لعام 2024: القيمة الفعلية تحل محل عبارة «قيد التحميل».",
        ),
      };
    default:
      return { tag: L("À savoir", "Good to know", "للمعلومة"), message: plainText(notice.message) };
  }
}

const PIPELINE_NODES_FR: Record<string, { label: string; detail: string }> = {
  collector: {
    label: "Collecte des sources",
    detail: "Enquêtes internationales et indicateurs mondiaux.",
  },
  profiler: {
    label: "Analyse des fichiers",
    detail: "Structure, colonnes et métadonnées vérifiées.",
  },
  quality: {
    label: "Contrôle qualité",
    detail: "Chaque source doit dépasser le seuil requis.",
  },
  etl: {
    label: "Intégration",
    detail: "Les données validées rejoignent la base centrale.",
  },
  semantic_kpi: {
    label: "Calcul des indicateurs",
    detail: "Indicateurs du catalogue, calcul figé et reproductible.",
  },
  analyst: {
    label: "Analyse automatique",
    detail: "Constats, explications et pistes, sans calcul par IA.",
  },
  dashboard: {
    label: "Tableau de bord",
    detail: "Vue publiée et vérifiée.",
  },
  xai: {
    label: "Explication du constat",
    detail: "Analyse incluse ; moteur avancé hors périmètre.",
  },
};

const PIPELINE_NODES_EN: Record<string, { label: string; detail: string }> = {
  collector: {
    label: "Source collection",
    detail: "International surveys and global indicators.",
  },
  profiler: {
    label: "File analysis",
    detail: "Structure, columns and metadata checked.",
  },
  quality: {
    label: "Quality control",
    detail: "Each source must pass the required threshold.",
  },
  etl: {
    label: "Integration",
    detail: "Validated data joins the central database.",
  },
  semantic_kpi: {
    label: "Indicator computation",
    detail: "Catalogue indicators, fixed and reproducible computation.",
  },
  analyst: {
    label: "Automated analysis",
    detail: "Findings, explanations and leads, without AI computation.",
  },
  dashboard: {
    label: "Dashboard",
    detail: "Published and verified view.",
  },
  xai: {
    label: "Explaining the finding",
    detail: "Analysis included; advanced engine out of scope.",
  },
};

const PIPELINE_NODES_AR: Record<string, { label: string; detail: string }> = {
  collector: {
    label: "جمع المصادر",
    detail: "مسوحات دولية ومؤشرات عالمية.",
  },
  profiler: {
    label: "تحليل الملفات",
    detail: "تم التحقق من البنية والأعمدة والبيانات الوصفية.",
  },
  quality: {
    label: "مراقبة الجودة",
    detail: "يجب أن يتجاوز كل مصدر الحد المطلوب.",
  },
  etl: {
    label: "الدمج",
    detail: "تنضم البيانات المتحقق منها إلى قاعدة البيانات المركزية.",
  },
  semantic_kpi: {
    label: "حساب المؤشرات",
    detail: "مؤشرات الفهرس بحساب ثابت وقابل للتكرار.",
  },
  analyst: {
    label: "تحليل آلي",
    detail: "نتائج وتفسيرات ومسارات، دون حساب بالذكاء الاصطناعي.",
  },
  dashboard: {
    label: "لوحة المعلومات",
    detail: "عرض منشور ومتحقق منه.",
  },
  xai: {
    label: "تفسير النتيجة",
    detail: "التحليل مشمول؛ المحرك المتقدم خارج النطاق.",
  },
};

export const PIPELINE_NODES = localizedMap(PIPELINE_NODES_FR, PIPELINE_NODES_EN, PIPELINE_NODES_AR);

const REJECTED_LABELS_FR: Record<string, string> = {
  value_missing: "valeur manquante",
  population_missing: "population manquante",
  population_repeated_metadata: "population répétée",
  year_out_of_range: "année hors plage",
  duplicate: "doublon",
  negative_value: "valeur négative",
};

const REJECTED_LABELS_EN: Record<string, string> = {
  value_missing: "missing value",
  population_missing: "missing population",
  population_repeated_metadata: "repeated population",
  year_out_of_range: "year out of range",
  duplicate: "duplicate",
  negative_value: "negative value",
};

const REJECTED_LABELS_AR: Record<string, string> = {
  value_missing: "قيمة ناقصة",
  population_missing: "بيانات سكان ناقصة",
  population_repeated_metadata: "بيانات سكان مكررة",
  year_out_of_range: "سنة خارج النطاق",
  duplicate: "تكرار",
  negative_value: "قيمة سالبة",
};

export const REJECTED_LABELS = localizedMap(REJECTED_LABELS_FR, REJECTED_LABELS_EN, REJECTED_LABELS_AR);

export function rejectedLabel(key: string): string {
  return REJECTED_LABELS[key] ?? plainText(key.replace(/_/g, " "));
}

export function sourceName(name: string): string {
  const lang = getLang();
  const names = lang === "en" ? SOURCE_NAMES_EN : lang === "ar" ? SOURCE_NAMES_AR : SOURCE_NAMES_FR;
  return names[name] ?? name.toUpperCase();
}

export function friendlyRule(rule: string): string {
  if (rule.startsWith("Chaque chiffre de la réponse existe dans les faits")) {
    return L(
      "Chaque chiffre cité provient des données affichées.",
      "Every figure cited comes from the displayed data.",
      "كل رقم مذكور مستمد من البيانات المعروضة.",
    );
  }
  if (rule.startsWith("Aucune recommandation n'est présentée comme une causalité")) {
    return L(
      "Aucune piste n'est présentée comme une cause prouvée.",
      "No lead is presented as a proven cause.",
      "لا يُعرض أي مسار كسبب مثبت.",
    );
  }
  return plainText(rule);
}

export type { Lang };
