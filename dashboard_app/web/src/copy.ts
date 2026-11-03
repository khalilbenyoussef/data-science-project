import type { Chip, Notice } from "./types";

const ISO_NAMES: Record<string, string> = {
  TUN: "Tunisie",
  DZA: "Algérie",
  EGY: "Égypte",
  JOR: "Jordanie",
  MAR: "Maroc",
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
  [/Taux de pauvrete/g, "Taux de pauvreté"],
  [/Pauvrete/g, "Pauvreté"],
  [/Deposants/g, "Déposants"],
  [/Bareme/g, "Barème"],
  [/Enquete/g, "Enquête"],
  [/menages/g, "ménages"],
  [/programmee/g, "programmée"],
  [/Verifier/g, "Vérifier"],
  [/augmentation du SMIG de janvier 2025/g, "revalorisation du SMIG de janvier 2025"],
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
  let out = text;
  for (const [pattern, replacement] of TEXT_RULES) out = out.replace(pattern, replacement);
  // décimales à la française, hors suffixes de version (2.0) et codes
  out = out.replace(/(\d)\.(\d)/g, (match, before: string, after: string) =>
    `${before},${after}`,
  );
  // séparateur de milliers à la française pour les nombres à quatre chiffres
  out = out.replace(/\b(\d)(\d{3}),(\d)/g, "$1 $2,$3");
  return out;
}

export const METRIC_LABELS: Record<string, string> = {
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
  smig_2025: "SMIG 2025",
  smig_2028: "SMIG 2028 (prévu)",
  poverty_rate_2021: "Taux de pauvreté national",
  poverty_rate_extreme_2021: "Taux de pauvreté extrême",
};

export const INFO_LABELS: Record<string, string> = {
  "macro-gdp_pc": "PIB par habitant",
  fx_tnd_usd_2024: "Taux de change officiel moyen 2024",
  smig_2025: "SMIG 2025 (40 h/semaine)",
  poverty_rate_urban_2021: "Pauvreté — milieu urbain",
  poverty_rate_rural_2021: "Pauvreté — milieu rural",
  context_undp: "Inclusion financière et développement humain (PNUD)",
  context_oif: "Francophonie et inclusion financière (OIF)",
  poverty_rate_2021: "Taux de pauvreté national",
  derived_monthly_magnitude: "Ordre de grandeur mensuel (calculé)",
};

export const PAGE_COPY: Record<string, { title: string; subtitle: string }> = {
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
  poverty: {
    title: "Pauvreté et SMIG",
    subtitle: "SMIG, pauvreté INS 2021 et simulateur de frais — références disponibles pour la Tunisie uniquement.",
  },
  pipeline: {
    title: "Sources et qualité",
    subtitle: "D'où viennent les chiffres, comment ils sont contrôlés et mis à jour.",
  },
};

export const CHART_TITLES: Record<string, string> = {
  account_ownership_history: "Détention d'un compte, par enquête Findex",
  account_ownership_peers: "Comparaison régionale — détention d'un compte",
  inclusion_funnel: "Du compte à l'usage formel",
  formal_vs_any: "Usage formel et usage informel",
  account_ownership_groups: "Détention d'un compte par groupe",
  gap_change: "Évolution des écarts entre 2021 et 2024",
  physical_network: "Réseau physique (2015-2024)",
  supply_demand_index: "Offre et demande, base 100 en 2017",
  atm_peers: "Distributeurs automatiques pour 100 000 adultes — comparaison régionale",
  barriers_heatmap: "Obstacles à l'ouverture d'un compte",
  urban_rural: "Détention d'un compte : villes et zones rurales",
  smig_trajectory: "SMIG 2025-2028 (40 h/semaine)",
};

export const STEP_LABELS: Record<string, string> = {
  account_ownership: "Détention d'un compte",
  digital_payment_rate: "Paiement numérique",
  formal_saving: "Épargne formelle",
  formal_borrowing: "Emprunt formel",
};

// Libellés du glossaire Findex 2025 (lignes 6 à 11)
export const HEATMAP_ROW_LABELS: Record<string, string> = {
  fin11a: "Trop éloigné",
  fin11b: "Trop cher",
  fin11c: "Documents manquants",
  fin11d: "Fonds insuffisants",
  fin11e: "Un proche en a déjà un",
  fin11f: "Manque de confiance",
};

// Statut de publication fixé par l'Auditor ; « en attente de validation » reprend la règle not_evaluated ci-dessus.
export const PUBLICATION_LABELS: Record<string, string> = {
  approved: "Approuvé",
  approved_with_review_note: "Approuvé avec réserve",
  blocked: "Bloqué",
  not_evaluated: "En attente de validation",
};

export const DEFINITION_STATUS: Record<string, string> = {
  verified: "Définition vérifiée",
  verified_metadata: "Métadonnées vérifiées",
  provisional: "Définition provisoire",
  hors_catalogue: "Indicateur complémentaire",
  secondary_source: "Source secondaire",
  official_source: "Source officielle",
};

export const REVIEW_REASONS: Record<string, string> = {
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
  smig_2025:
    "Salaire minimum interprofessionnel garanti (SMIG) brut mensuel, régime de 40 heures par semaine, en 2025.",
  smig_2028:
    "Montant du SMIG prévu par le barème publié pour 2028 ; revalorisation à confirmer au Journal officiel.",
  poverty_rate_2021:
    "Part de la population sous le seuil national de pauvreté, selon l'enquête de l'INS de 2021.",
  poverty_rate_extreme_2021:
    "Part de la population sous le seuil national de pauvreté extrême, selon l'enquête de l'INS de 2021.",
};

const CAVEAT_FR: Record<string, string> = {
  smig_2025:
    "Montant brut mensuel, régime de 40 heures par semaine. Vérifier le Journal officiel (JORT).",
  smig_2028:
    "Revalorisation programmée ; à vérifier dans le texte officiel avant tout usage contractuel.",
  poverty_rate_2021: "Seuil national de pauvreté ; enquête 2021 publiée par l'INS.",
  poverty_rate_extreme_2021: "Pauvreté extrême, seuil national, enquête 2021.",
};

export function friendlyDefinition(metricId: string, definition: string | null): string {
  return DEFINITION_FR[metricId] ?? (plainText(definition) || "—");
}

export function friendlyCaveat(metricId: string, caveat: string | null): string {
  if (!caveat) return "";
  return CAVEAT_FR[metricId] ?? plainText(caveat);
}

const FILTER_TOKENS: Record<string, string> = {
  total_population: "population totale",
  commercial_banks_all_adults: "banques commerciales, tous adultes",
  "bank_type=commercial_banks": "banques commerciales",
  "urbanicity=urban": "milieu urbain",
  "urbanicity=rural": "milieu rural",
  "all=all": "ensemble des adultes",
};

export function friendlyFilter(filter: string | null): string {
  if (!filter) return "—";
  if (filter.startsWith("référence statique")) return "Référence nationale, sans filtre pays";
  const parts = filter
    .split(" · ")
    .map((part) => {
      const iso = part.match(/^iso3=([A-Z]{3})$/);
      if (iso) return ISO_NAMES[iso[1]] ?? iso[1];
      if (FILTER_TOKENS[part]) return FILTER_TOKENS[part];
      if (/^[a-z0-9_]+$/.test(part)) return null;
      return plainText(part);
    })
    .filter(Boolean);
  return parts.length ? parts.join(" · ") : "Population totale";
}

const SOURCE_NAMES: Record<string, string> = {
  findex: "enquête Findex (Banque mondiale)",
  fas: "FMI — accès aux services financiers (FAS)",
  gdp: "indicateurs mondiaux (Banque mondiale)",
  wdi: "indicateurs mondiaux (Banque mondiale)",
};

export function friendlySource(source: string | null): string {
  if (!source) return "—";
  const catalog = source.match(/^KPI catalog · ([a-z0-9_]+)/);
  if (catalog) return `Catalogue d'indicateurs · ${SOURCE_NAMES[catalog[1]] ?? catalog[1]}`;
  if (source.startsWith("Warehouse DuckDB")) {
    return "Base de données interne · FMI (FAS) et enquête Findex";
  }
  if (source.startsWith("Bareme de paie tunisien")) {
    return "Barème de paie tunisien — revalorisation du SMIG de janvier 2025";
  }
  if (source.startsWith("Bareme SMIG/SMAG")) {
    return "Barème SMIG/SMAG 2026-2028 — paie-tunisie.com";
  }
  if (source.startsWith("INS - Enquete nationale")) {
    return "INS — enquête sur le budget et le niveau de vie des ménages (2021)";
  }
  if (source.startsWith("INS - ENBCNV")) return "INS — enquête ENBCNV 2021";
  return plainText(source);
}

export function chipLabel(chip: Chip | null): string {
  if (!chip) return "";
  const kind = chip.label.split("·").pop()?.trim() ?? "";
  switch (chip.provider) {
    case "semantic":
      return kind === "provisional" ? "Indicateur provisoire" : "Indicateur suivi";
    case "warehouse":
      return "Source interne";
    case "reference":
      return kind === "secondary_source" ? "Source secondaire" : "Source officielle";
    case "derived":
      return "Valeur calculée";
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
        tag: "À vérifier",
        message: `${count ?? "Plusieurs"} observations sont signalées : définition provisoire ou traçabilité à compléter.`,
      };
    case "provisional_definition": {
      const name =
        notice.kpi_id === "saving_rate"
          ? "L'épargne, toutes formes confondues,"
          : notice.kpi_id === "borrowing_rate"
            ? "L'emprunt, toutes formes confondues,"
            : "Cet indicateur";
      return {
        tag: "Définition provisoire",
        message: `${name} repose sur une définition provisoire, en attente de validation.`,
      };
    }
    case "quality_provenance_unverified":
      return {
        tag: "Traçabilité",
        message: "Le contrôle qualité n'est pas encore rattaché à la collecte d'origine.",
      };
    case "source_version_incomplete":
      return {
        tag: "Traçabilité",
        message: "La référence complète du fichier source n'est pas disponible.",
      };
    case "warehouse_content_binding_unverified":
      return {
        tag: "Traçabilité",
        message:
          "Le lien entre la base de données et les fichiers sources n'a pas encore été confirmé.",
      };
    case "source_notice:empty_columns":
      return {
        tag: "Qualité de la source",
        message: "Une colonne entièrement vide a été ignorée dans le fichier FAS.",
      };
    case "source_notice:negative_values":
      return {
        tag: "Qualité de la source",
        message: "Des valeurs négatives ont été détectées dans les colonnes d'années du fichier FAS.",
      };
    case "fin24aP_definition":
      return {
        tag: "Définition à confirmer",
        message:
          "L'indicateur « fonds d'urgence » porte un libellé différent dans le dictionnaire de la Banque mondiale : sa valeur est affichée mais signalée.",
      };
    case "warehouse_not_in_catalog":
      return {
        tag: "Indicateurs complémentaires",
        message:
          "Certains indicateurs (distributeurs, agences, dépôts et crédits) viennent de la base interne et non du catalogue officiel : ils sont à vérifier.",
      };
    case "publication_not_evaluated":
      return {
        tag: "Publication",
        message: "Les données n'ont pas encore reçu de validation finale pour publication.",
      };
    case "loans_pct_gdp_now_available":
      return {
        tag: "Donnée disponible",
        message:
          "Les crédits bancaires sont désormais disponibles pour 2024 : la valeur réelle remplace la mention « à charger ».",
      };
    case "deposits_pct_gdp_now_available":
      return {
        tag: "Donnée disponible",
        message:
          "Les dépôts bancaires sont désormais disponibles pour 2024 : la valeur réelle remplace la mention « à charger ».",
      };
    default:
      return { tag: "À savoir", message: plainText(notice.message) };
  }
}

export const PIPELINE_NODES: Record<string, { label: string; detail: string }> = {
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
    detail: "Vue publiée, version 2.0.",
  },
  xai: {
    label: "Explication du constat",
    detail: "Analyse incluse ; moteur avancé hors périmètre.",
  },
};

export const REJECTED_LABELS: Record<string, string> = {
  value_missing: "valeur manquante",
  population_missing: "population manquante",
  population_repeated_metadata: "population répétée",
  year_out_of_range: "année hors plage",
  duplicate: "doublon",
  negative_value: "valeur négative",
};

export function rejectedLabel(key: string): string {
  return REJECTED_LABELS[key] ?? plainText(key.replace(/_/g, " "));
}

export function sourceName(name: string): string {
  return SOURCE_NAMES[name] ?? name.toUpperCase();
}

export function friendlyRule(rule: string): string {
  if (rule.startsWith("Chaque chiffre de la réponse existe dans les faits")) {
    return "Chaque chiffre cité provient des données affichées.";
  }
  if (rule.startsWith("Aucune recommandation n'est présentée comme une causalité")) {
    return "Aucune piste n'est présentée comme une cause prouvée.";
  }
  if (rule.startsWith("Le SMIG affiché est la référence statique")) {
    return "Le SMIG affiché est le barème publié pour 2025.";
  }
  return plainText(rule);
}
