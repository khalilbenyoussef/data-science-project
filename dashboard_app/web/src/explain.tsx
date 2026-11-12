import { useEffect } from "react";
import { createPortal } from "react-dom";
import type { Chart, Chip, InfoItem, Insight, Metric, XaiCard } from "./types";
import { fmtNumber, fmtPct, fmtSigned, fmtUnit, providerLabel } from "./format";
import {
  HEATMAP_ROW_LABELS, INFO_LABELS, METRIC_LABELS, STEP_LABELS, chipLabel, chipTitle,
  friendlyDefinition, friendlyFilter, friendlySource, plainText,
} from "./copy";
import { t } from "./i18n";
import { getLang } from "./preferences";

/* ------------------------------------------------------------------ contenu
   Les fiches « Pourquoi ? » ne recalculent rien : elles rassemblent la valeur
   publiée, sa définition, sa source et les constats XAI déjà calculés sur les
   mêmes données. Tout est traduit à l'affichage (FR / EN / AR). */

type Triplet = [string, string, string];

function L(fr: string, en: string, ar: string): string {
  const lang = getLang();
  if (lang === "ar") return ar;
  if (lang === "en") return en;
  return fr;
}

const METRIC_STORY: Record<string, { use: Triplet; limit: Triplet }> = {
  account_ownership: {
    use: [
      "Part des adultes qui détiennent un compte dans une banque, une institution financière ou un service d'argent mobile. C'est le point de départ de l'inclusion financière : ce chiffre mesure l'accès, pas l'usage réel du compte.",
      "Share of adults who own an account at a bank, a financial institution or a mobile-money service. It is the starting point of financial inclusion: it measures access, not actual account use.",
      "نسبة البالغين الذين يمتلكون حسابًا في بنك أو مؤسسة مالية أو خدمة أموال عبر الهاتف. هي نقطة انطلاق الإدماج المالي: تقيس الوصول، لا الاستخدام الفعلي للحساب.",
    ],
    limit: [
      "Un compte peut rester inactif. Ce chiffre ne dit rien, à lui seul, sur la fréquence d'utilisation ni sur la qualité des services proposés.",
      "An account may remain inactive. On its own, this figure says nothing about how often it is used or about the quality of the services offered.",
      "قد يبقى الحساب غير نشط. هذا الرقم وحده لا يقول شيئًا عن وتيرة الاستخدام أو جودة الخدمات المتاحة.",
    ],
  },
  digital_payment_rate: {
    use: [
      "Part des adultes ayant effectué ou reçu un paiement numérique au cours de l'année. Il mesure l'usage effectif, au-delà de la simple détention d'un compte.",
      "Share of adults who made or received a digital payment during the year. It measures actual use, beyond simply owning an account.",
      "نسبة البالغين الذين أجروا أو استلموا دفعة رقمية خلال السنة. تقيس الاستخدام الفعلي، وليس مجرد امتلاك حساب.",
    ],
    limit: [
      "Le paiement numérique ne couvre pas tous les usages financiers : l'épargne, le crédit et l'assurance sont mesurés séparément.",
      "Digital payments do not cover every financial use: savings, credit and insurance are measured separately.",
      "الدفع الرقمي لا يغطي كل الاستخدامات المالية: الادخار والائتمان والتأمين تُقاس بشكل منفصل.",
    ],
  },
  saving_rate: {
    use: [
      "Part des adultes ayant épargné ou mis de l'argent de côté, sous n'importe quelle forme, au cours de l'année. L'épargne informelle est incluse.",
      "Share of adults who saved or set money aside, in any form, during the year. Informal savings are included.",
      "نسبة البالغين الذين ادّخروا أو خصّصوا أموالًا، بأي شكل، خلال السنة. ويشمل ذلك الادخار غير الرسمي.",
    ],
    limit: [
      "Épargner ne signifie pas épargner auprès d'une institution financière : les deux indicateurs ne mesurent pas la même chose.",
      "Saving does not mean saving with a financial institution: the two indicators do not measure the same thing.",
      "الادخار لا يعني الادخار لدى مؤسسة مالية: المؤشران لا يقيسان الشيء نفسه.",
    ],
  },
  emergency_money: {
    use: [
      "Part des adultes qui déclarent pouvoir réunir des fonds d'urgence en 30 jours. C'est un indicateur de résilience financière.",
      "Share of adults who say they could raise emergency funds within 30 days. It is an indicator of financial resilience.",
      "نسبة البالغين الذين يقولون إنهم يستطيعون جمع أموال طارئة خلال 30 يومًا. مؤشر على المرونة المالية.",
    ],
    limit: [
      "Il repose sur une déclaration : il ne mesure ni le montant réellement disponible ni la qualité de la protection.",
      "It relies on self-reporting: it measures neither the amount actually available nor the quality of protection.",
      "يعتمد على تصريح ذاتي: لا يقيس المبلغ المتاح فعليًا ولا جودة الحماية.",
    ],
  },
  atm_per_100k: {
    use: [
      "Nombre de distributeurs automatiques pour 100 000 adultes. Il décrit la disponibilité physique des espèces.",
      "Number of automated teller machines per 100,000 adults. It describes the physical availability of cash.",
      "عدد الصرافات الآلية لكل 100 ألف بالغ. يصف التوفر المادي للنقد.",
    ],
    limit: [
      "Un distributeur peut être peu utilisé ou en panne : la densité ne garantit pas un service effectif.",
      "An ATM may be rarely used or out of service: density does not guarantee an effective service.",
      "قد يكون الصراف قليل الاستخدام أو معطلًا: الكثافة لا تضمن خدمة فعلية.",
    ],
  },
  branch_density: {
    use: [
      "Nombre d'agences de banques commerciales pour 100 000 adultes. Il mesure la proximité du réseau bancaire.",
      "Number of commercial bank branches per 100,000 adults. It measures how close the banking network is.",
      "عدد فروع البنوك التجارية لكل 100 ألف بالغ. يقيس قرب الشبكة البنكية.",
    ],
    limit: [
      "La présence d'une agence ne dit pas si les populations pauvres ou rurales y ont réellement accès.",
      "The presence of a branch does not tell whether poor or rural populations can actually use it.",
      "وجود فرع لا يعني أن الفئات الفقيرة أو الريفية تستطيع الوصول إليه فعليًا.",
    ],
  },
  depositors_per_1k: {
    use: [
      "Nombre de déposants auprès des banques commerciales pour 1 000 adultes. Il décrit l'ampleur de la clientèle bancaire.",
      "Number of depositors at commercial banks per 1,000 adults. It describes the size of the banking client base.",
      "عدد المودعين في البنوك التجارية لكل 1000 بالغ. يصف حجم قاعدة عملاء البنوك.",
    ],
    limit: [
      "Une même personne peut détenir plusieurs comptes : ce n'est pas un taux de détention de compte.",
      "One person may hold several accounts: this is not an account ownership rate.",
      "قد يمتلك الشخص نفسه عدة حسابات: هذا ليس معدل امتلاك حساب.",
    ],
  },
  borrowers_per_1k: {
    use: [
      "Nombre d'emprunteurs auprès des banques commerciales pour 1 000 adultes. Il décrit l'accès au crédit bancaire.",
      "Number of borrowers from commercial banks per 1,000 adults. It describes access to bank credit.",
      "عدد المقترضين من البنوك التجارية لكل 1000 بالغ. يصف الوصول إلى الائتمان البنكي.",
    ],
    limit: [
      "Ce chiffre ne dit pas si le crédit est abordable ni s'il bénéficie aux ménages modestes.",
      "This figure does not say whether credit is affordable or whether it reaches lower-income households.",
      "هذا الرقم لا يوضح ما إذا كان الائتمان ميسور التكلفة أو يستفيد منه الأسر محدودة الدخل.",
    ],
  },
  loans_pct_gdp: {
    use: [
      "Encours des crédits accordés par les banques commerciales, rapporté au PIB. Il mesure la profondeur du crédit dans l'économie.",
      "Outstanding loans by commercial banks as a share of GDP. It measures the depth of credit in the economy.",
      "القروض القائمة الممنوحة من البنوك التجارية كنسبة من الناتج المحلي. تقيس عمق الائتمان في الاقتصاد.",
    ],
    limit: [
      "Il porte sur l'ensemble de l'économie : il ne mesure pas directement l'accès des ménages au crédit.",
      "It covers the whole economy: it does not directly measure households' access to credit.",
      "يشمل الاقتصاد ككل: لا يقيس مباشرة وصول الأسر إلى الائتمان.",
    ],
  },
  deposits_pct_gdp: {
    use: [
      "Encours des dépôts dans les banques commerciales, rapporté au PIB. Il mesure la profondeur financière du pays.",
      "Outstanding deposits at commercial banks as a share of GDP. It measures the country's financial depth.",
      "الودائع القائمة في البنوك التجارية كنسبة من الناتج المحلي. تقيس العمق المالي للبلد.",
    ],
    limit: [
      "Des dépôts élevés peuvent coexister avec une faible inclusion : ce n'est pas un indicateur d'accès.",
      "High deposits can coexist with low inclusion: this is not an access indicator.",
      "قد ترتفع الودائع مع انخفاض الإدماج المالي: هذا ليس مؤشر وصول.",
    ],
  },
  urban_account: {
    use: [
      "Part des adultes vivant en ville qui détiennent un compte. À comparer avec le milieu rural pour lire l'écart territorial.",
      "Share of adults living in cities who own an account. Compare it with rural areas to read the territorial gap.",
      "نسبة البالغين المقيمين في المدن الذين يمتلكون حسابًا. تُقارن بالمناطق الريفية لقراءة الفجوة الجغرافية.",
    ],
    limit: [
      "L'écart entre villes et campagnes est une observation : il ne prouve pas, à lui seul, que le lieu de résidence est la cause.",
      "The urban–rural gap is an observation: on its own, it does not prove that place of residence is the cause.",
      "الفجوة بين المدن والأرياف ملاحظة: لا تثبت وحدها أن مكان الإقامة هو السبب.",
    ],
  },
  rural_account: {
    use: [
      "Part des adultes vivant à la campagne qui détiennent un compte. À comparer avec le milieu urbain pour lire l'écart territorial.",
      "Share of adults living in rural areas who own an account. Compare it with urban areas to read the territorial gap.",
      "نسبة البالغين المقيمين في الريف الذين يمتلكون حسابًا. تُقارن بالمناطق الحضرية لقراءة الفجوة الجغرافية.",
    ],
    limit: [
      "L'écart entre villes et campagnes est une observation : il ne prouve pas, à lui seul, que le lieu de résidence est la cause.",
      "The urban–rural gap is an observation: on its own, it does not prove that place of residence is the cause.",
      "الفجوة بين المدن والأرياف ملاحظة: لا تثبت وحدها أن مكان الإقامة هو السبب.",
    ],
  },
};

const DEFAULT_METRIC_STORY = {
  use: [
    "Cet indicateur mesure une dimension précise de l'accès ou de l'usage des services financiers. Sa définition complète figure ci-dessous.",
    "This indicator measures one precise dimension of access to or use of financial services. Its full definition is given below.",
    "يقيس هذا المؤشر بُعدًا محددًا من الوصول إلى الخدمات المالية أو استخدامها. التعريف الكامل أدناه.",
  ],
  limit: [
    "Un indicateur isolé ne suffit pas à conclure : il décrit une observation, pas une relation de cause à effet.",
    "A single indicator is not enough to conclude: it describes an observation, not a causal relationship.",
    "لا يكفي مؤشر واحد للاستنتاج: يصف ملاحظة، لا علاقة سببية.",
  ],
} as const;

const INFO_STORY: Record<string, { use: Triplet; limit: Triplet }> = {
  "macro-gdp_pc": {
    use: [
      "Le PIB par habitant résume la richesse produite par habitant. Il sert de contexte économique, pas de mesure d'inclusion financière.",
      "GDP per capita summarises the wealth produced per inhabitant. It provides economic context, not a measure of financial inclusion.",
      "الناتج المحلي للفرد يلخص الثروة المنتجة لكل ساكن. يوفر سياقًا اقتصاديًا، وليس قياسًا للإدماج المالي.",
    ],
    limit: [
      "Il ne dit rien sur la répartition de cette richesse ni sur l'accès effectif aux services financiers.",
      "It says nothing about how that wealth is distributed or about actual access to financial services.",
      "لا يقول شيئًا عن توزيع هذه الثروة ولا عن الوصول الفعلي إلى الخدمات المالية.",
    ],
  },
  fx_tnd_usd_2024: {
    use: [
      "Taux de change officiel moyen de l'année. Il permet de convertir des montants entre devises.",
      "Official average exchange rate for the year. It is used to convert amounts between currencies.",
      "سعر الصرف الرسمي المتوسط للسنة. يُستخدم لتحويل المبالغ بين العملات.",
    ],
    limit: [
      "Ce n'est pas un indicateur d'accès : il sert uniquement de repère de conversion.",
      "It is not an access indicator: it only serves as a conversion reference.",
      "ليس مؤشر وصول: يُستخدم فقط كمرجع للتحويل.",
    ],
  },
  derived_monthly_magnitude: {
    use: [
      "Ordre de grandeur calculé à partir du PIB par habitant et du taux de change. Il aide à se représenter les montants.",
      "Order of magnitude calculated from GDP per capita and the exchange rate. It helps put amounts into perspective.",
      "حجم تقريبي محسوب من الناتج المحلي للفرد وسعر الصرف. يساعد على تصور المبالغ.",
    ],
    limit: [
      "C'est un calcul indicatif, pas une donnée observée : il ne doit pas être cité comme un chiffre officiel.",
      "It is an indicative calculation, not an observed data point: it should not be cited as an official figure.",
      "إنه حساب إرشادي، وليس بيانات ملاحظة: لا ينبغي الاستشهاد به كرقم رسمي.",
    ],
  },
};

const DEFAULT_INFO_STORY = {
  use: [
    "Cette donnée complète le contexte de la page. Elle est affichée avec son année et sa source.",
    "This data point adds context to the page. It is shown with its year and source.",
    "تكمل هذه المعطيات سياق الصفحة. تُعرض مع سنتها ومصدرها.",
  ],
  limit: [
    "Elle n'entre pas dans le calcul des indicateurs d'inclusion : elle sert de repère de lecture.",
    "It is not used to calculate inclusion indicators: it serves as a reading reference.",
    "لا تدخل في حساب مؤشرات الإدماج المالي: تُستخدم كمرجع للقراءة.",
  ],
} as const;

const CHART_STORY: Record<string, Triplet> = {
  line: [
    "Chaque point est une observation publiée par l'enquête ou la source bancaire. Les années sans observation ne sont pas estimées.",
    "Each point is an observation published by the survey or the banking source. Years without an observation are not estimated.",
    "كل نقطة ملاحظة منشورة من الاستقصاء أو المصدر البنكي. السنوات بلا ملاحظة لا تُقدَّر.",
  ],
  bar: [
    "Les barres comparent des groupes ou des repères observés. Les valeurs manquantes ne sont pas remplacées.",
    "The bars compare observed groups or benchmarks. Missing values are not replaced.",
    "تقارن الأعمدة مجموعات أو مراجع ملاحظة. القيم المفقودة لا تُستبدل.",
  ],
  funnel: [
    "Chaque étape correspond à une question posée séparément : la baisse n'est pas un taux de conversion individuel.",
    "Each step corresponds to a separately asked question: the decline is not an individual conversion rate.",
    "كل مرحلة تقابل سؤالًا يُطرح بشكل منفصل: الانخفاض ليس معدل تحول فردي.",
  ],
  dumbbell: [
    "Chaque ligne compare deux groupes observés. L'écart est exprimé en points de pourcentage.",
    "Each row compares two observed groups. The gap is expressed in percentage points.",
    "كل سطر يقارن مجموعتين ملاحظتين. تُعبَّر الفجوة بنقاط مئوية.",
  ],
  gap: [
    "Chaque ligne indique l'évolution d'un écart entre deux dates. Un écart qui se réduit ne signifie pas que les groupes évoluent de la même façon.",
    "Each row shows how a gap changed between two dates. A narrowing gap does not mean the groups are evolving in the same way.",
    "كل سطر يوضح تطور فجوة بين تاريخين. تضيُّق الفجوة لا يعني أن المجموعتين تتطوران بالطريقة نفسها.",
  ],
  heatmap: [
    "Chaque cellule indique la part d'adultes citant un obstacle. Une cellule vide signifie que la donnée n'est pas disponible, pas qu'elle vaut zéro.",
    "Each cell gives the share of adults reporting a barrier. An empty cell means the data is unavailable, not that it is zero.",
    "كل خلية تعطي نسبة البالغين الذين ذكروا عائقًا. الخلية الفارغة تعني أن البيانات غير متاحة، وليس أنها صفر.",
  ],
};

const CHART_CODES: Record<string, string[]> = {
  account_ownership_history: ["account_ownership"],
  account_ownership_peers: ["account_ownership_peers"],
  inclusion_funnel: ["formal_usage"],
  formal_vs_any: ["formal_usage"],
  account_ownership_groups: ["gap_gender", "gap_income", "gap_education", "gap_laborforce", "gap_urbanicity"],
  gap_change: ["gap_gender", "gap_income", "gap_education", "gap_laborforce", "gap_urbanicity"],
  physical_network: ["atm_per_100k", "branch_density"],
  atm_peers: ["atm_per_100k"],
  supply_demand_index: ["outreach", "banking_depth"],
};

const METRIC_CODES: Record<string, string[]> = {
  depositors_per_1k: ["outreach"],
  borrowers_per_1k: ["outreach"],
  loans_pct_gdp: ["banking_depth"],
  deposits_pct_gdp: ["banking_depth"],
  urban_account: ["gap_urbanicity"],
  rural_account: ["gap_urbanicity"],
};

/* --------------------------------------------------------------- structures */

export interface ExplainXai {
  statements: { text: string; severity: string }[];
  hypothesis: string | null;
}

export interface ExplainSection {
  heading: string;
  body?: string;
  items?: string[];
}

export interface ExplainContent {
  eyebrow: string;
  title: string;
  value?: string;
  meta?: string;
  sections: ExplainSection[];
  chip?: Chip | null;
  sources: string[];
  xai?: ExplainXai;
  askQuestion: string;
}

function uniqueness(values: (string | null | undefined)[]): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value))));
}

function relatedInsights(codes: string[], insights: Insight[], limit = 3): Insight[] {
  if (codes.length === 0) return [];
  const wanted = new Set(codes);
  return insights.filter((item) => wanted.has(item.code)).slice(0, limit);
}

function xaiFrom(insights: Insight[], xai: XaiCard | null | undefined, includeCard: boolean): ExplainXai | undefined {
  const statements = insights.map((item) => ({
    text: plainText(item.statement),
    severity: item.severity,
  }));
  const hypothesis = includeCard && xai ? plainText(xai.recommendation.statement) : null;
  if (statements.length === 0 && !hypothesis) return undefined;
  return { statements, hypothesis };
}

function fallbackXai(
  xai: XaiCard | null | undefined,
  withHypothesis = true,
): ExplainXai | undefined {
  if (!xai) return undefined;
  const pool = [...xai.evidence, ...xai.interpretation].slice(0, 3);
  return {
    statements: pool.map((item) => ({ text: plainText(item.statement), severity: item.severity })),
    hypothesis: withHypothesis ? plainText(xai.recommendation.statement) : null,
  };
}

/* -------------------------------------------------------------------- metric */

export function buildMetricExplanation(
  metric: Metric,
  insights: Insight[],
  xai: XaiCard | null | undefined,
): ExplainContent {
  const story = METRIC_STORY[metric.id] ?? DEFAULT_METRIC_STORY;
  const label = METRIC_LABELS[metric.id] ?? plainText(metric.label);
  const available = metric.status === "available";
  const value = available
    ? plainText(metric.display)
    : metric.unavailable_reason
      ? plainText(metric.unavailable_reason)
      : metric.status === "placeholder"
        ? t("En attente de données")
        : t("Indisponible");
  const year = metric.year ?? metric.year_requested ?? null;

  const sections: ExplainSection[] = [];
  sections.push({
    heading: t("Ce que dit la valeur"),
    body: available
      ? t("{label} : {value} en {year}.", { label, value, year: year ?? "—" })
      : t("Ce chiffre n'est pas disponible pour cette sélection."),
    items: available && metric.delta?.label ? [t("Évolution : {delta}.", { delta: plainText(metric.delta.label) })] : undefined,
  });
  sections.push({
    heading: t("À quoi sert ce chiffre"),
    body: L(...story.use),
  });
  sections.push({
    heading: t("Ce que le chiffre ne dit pas"),
    body: L(...story.limit),
  });
  sections.push({
    heading: t("Source"),
    body: `${friendlyDefinition(metric.id, metric.why?.definition ?? null)} · ${t("Année de référence")} ${year ?? "—"}`,
    items: [
      friendlySource(metric.why?.source ?? null),
      metric.why?.filter ? `${t("Périmètre")} · ${friendlyFilter(metric.why.filter)}` : "",
    ].filter(Boolean),
  });

  const codes = [metric.id, ...(METRIC_CODES[metric.id] ?? [])];
  const matched = relatedInsights(codes, insights);
  const xaiSection = xaiFrom(matched, xai, false) ?? fallbackXai(xai, false);

  return {
    eyebrow: t("Comprendre ce chiffre"),
    title: label,
    value,
    meta: available
      ? t("Année : {year} · {provider}", { year: year ?? "—", provider: providerLabel(metric.provider) })
      : t("Année de référence : {year}", { year: year ?? "—" }),
    sections,
    chip: metric.chip,
    sources: uniqueness([chipLabel(metric.chip), friendlySource(metric.why?.source ?? null)]),
    xai: xaiSection,
    askQuestion: t("Pourquoi {label} est-il à ce niveau ?", { label }),
  };
}

/* ---------------------------------------------------------------------- info */

export function buildInfoExplanation(item: InfoItem): ExplainContent {
  const story = INFO_STORY[item.id] ?? DEFAULT_INFO_STORY;
  const label = INFO_LABELS[item.id] ?? plainText(item.label);
  const available = item.status === "available" && Boolean(item.value);
  const value = available
    ? plainText(item.value)
    : item.status === "placeholder"
      ? t("En attente de données")
      : t("Indisponible");
  const sections: ExplainSection[] = [
    {
      heading: t("Ce que dit la valeur"),
      body: available
        ? t("La valeur affichée est {value} pour l'année {year}.", {
            value,
            year: item.year ?? "—",
          })
        : t("Ce chiffre n'est pas disponible pour cette sélection."),
    },
    { heading: t("À quoi sert ce chiffre"), body: L(...story.use) },
    { heading: t("Ce que le chiffre ne dit pas"), body: L(...story.limit) },
    {
      heading: t("Source"),
      body: friendlySource(item.source ?? null),
      items: item.note ? [plainText(item.note)] : undefined,
    },
  ];
  return {
    eyebrow: t("Comprendre cette donnée"),
    title: label,
    value,
    meta: item.year ? t("Année : {year}", { year: item.year }) : undefined,
    sections,
    chip: item.chip,
    sources: uniqueness([friendlySource(item.source ?? null)]),
    askQuestion: t("Que signifie {label} dans ce tableau de bord ?", { label }),
  };
}

/* --------------------------------------------------------------------- chart */

function valueText(value: number | null, unit: string | null): string {
  if (value === null) return "—";
  if (unit === "percent") return fmtPct(value);
  if (unit === "index_2017_100") return fmtNumber(value, 0);
  return fmtUnit(value, unit);
}

function chartHighlights(chart: Chart): string[] {
  const items: string[] = [];
  if (chart.kind === "line") {
    for (const series of chart.series.slice(0, 3)) {
      const points = series.points
        .filter((point) => point.value !== null)
        .sort((a, b) => a.year - b.year);
      if (points.length === 0) continue;
      const first = points[0];
      const last = points[points.length - 1];
      const label = plainText(series.label);
      if (first.year === last.year) {
        items.push(t("{label} : {value}.", { label, value: valueText(last.value, series.unit) }));
      } else {
        items.push(
          t("Entre {from} et {to}, {label} passe de {start} à {end}.", {
            from: first.year,
            to: last.year,
            label,
            start: valueText(first.value, series.unit),
            end: valueText(last.value, series.unit),
          }),
        );
      }
    }
  }
  if (chart.kind === "bar") {
    const bars = chart.bars.filter((bar) => bar.value !== null);
    if (bars.length > 0) {
      const sorted = [...bars].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
      const top = sorted[0];
      const bottom = sorted[sorted.length - 1];
      items.push(t("La valeur la plus élevée est {value} ({label}).", {
        value: plainText(top.display),
        label: plainText(top.label),
      }));
      if (bottom.id !== top.id) {
        items.push(t("La valeur la plus basse est {value} ({label}).", {
          value: plainText(bottom.display),
          label: plainText(bottom.label),
        }));
      }
    }
  }
  if (chart.kind === "funnel") {
    for (const step of chart.steps) {
      if (step.status !== "available" || step.value === null) continue;
      items.push(t("{label} : {value}.", {
        label: STEP_LABELS[step.id] ?? plainText(step.label),
        value: plainText(step.display),
      }));
    }
  }
  if (chart.kind === "dumbbell") {
    const rows = chart.groups.flatMap((group) =>
      group.rows.map((row) => ({ group: group.title, row })),
    );
    const top = [...rows].sort((a, b) => (b.row.gap_pp ?? 0) - (a.row.gap_pp ?? 0))[0];
    if (top) {
      items.push(t("L'écart le plus marqué concerne {group} : {value} points.", {
        group: plainText(top.group),
        value: fmtNumber(top.row.gap_pp, 1),
      }));
    }
  }
  if (chart.kind === "gap") {
    for (const point of chart.gap_points.slice(0, 4)) {
      items.push(
        t("{label} : l'écart passe de {start} à {end} points entre {from} et {to}.", {
          label: plainText(point.label),
          from: point.from_year,
          to: point.to_year,
          start: fmtNumber(point.gap_from_pp, 1),
          end: fmtNumber(point.gap_to_pp, 1),
        }),
      );
    }
  }
  if (chart.kind === "heatmap") {
    const cells = chart.cells
      .filter((cell) => cell.status === "available" && cell.value !== null)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    if (cells.length > 0) {
      const top = cells[0];
      items.push(t("Le maximum observé est {value}, pour {label}.", {
        value: fmtPct(top.value),
        label: `${plainText(top.column)} · ${HEATMAP_ROW_LABELS[top.row] ?? top.row}`,
      }));
    }
  }
  return items;
}

export function buildChartExplanation(
  chart: Chart,
  insights: Insight[],
  xai: XaiCard | null | undefined,
): ExplainContent {
  const gapSpan = chart.id === "gap_change" ? chart.gap_points[0] : undefined;
  const title = gapSpan
    ? t("Évolution des écarts entre {from} et {to}", { from: gapSpan.from_year, to: gapSpan.to_year })
    : plainText(chart.title);
  const codes = [chart.id, ...(CHART_CODES[chart.id] ?? [])];
  const matched = relatedInsights(codes, insights, 4);
  const xaiSection = xaiFrom(matched, xai, false) ?? fallbackXai(xai);
  const providers = uniqueness([
    ...chart.series.map((series) => series.provider ?? null),
    ...chart.bars.map((bar) => bar.provider),
    ...chart.steps.map((step) => step.provider),
  ]).map((value) => providerLabel(value));
  const notes = chart.notes.map(plainText).filter(Boolean);
  const highlights = chartHighlights(chart);
  const sections: ExplainSection[] = [
    {
      heading: t("Ce que montre ce graphique"),
      body: chart.subtitle ? plainText(chart.subtitle) : title,
    },
    {
      heading: t("Lecture des données"),
      items: highlights.length ? highlights : [t("Graphique sans donnée pour cette sélection.")],
    },
    {
      heading: t("Lecture simple"),
      body: L(...(CHART_STORY[chart.kind] ?? CHART_STORY.bar)),
    },
    {
      heading: t("Précautions de lecture"),
      items: notes.length
        ? notes
        : [t("Aucune précaution particulière n'est signalée pour ce graphique.")],
    },
  ];
  return {
    eyebrow: t("Comprendre ce graphique"),
    title,
    meta: providers.length
      ? t("Source : {source}", { source: providers.join(" · ") })
      : undefined,
    sections,
    chip: chart.chip,
    sources: providers,
    xai: xaiSection,
    askQuestion: t("Pourquoi ce graphique évolue-t-il ainsi ?"),
  };
}

/* ------------------------------------------------------------------ dialog */

export function ExplainDialog({
  content,
  onClose,
  onAsk,
}: {
  content: ExplainContent;
  onClose: () => void;
  onAsk?: (question: string) => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const ask = () => {
    onAsk?.(content.askQuestion);
    onClose();
  };

  return createPortal(
    <div className="sheet-overlay explain-overlay" onClick={onClose}>
      <div
        className="sheet explain-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="explain-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sheet-head">
          <div>
            <span className="eyebrow">{content.eyebrow}</span>
            <h3 id="explain-title">{content.title}</h3>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label={t("Fermer")}>
            ×
          </button>
        </div>

        {content.value && (
          <div className="sheet-value">
            <strong>{content.value}</strong>
            {content.meta && <span className="muted">{content.meta}</span>}
          </div>
        )}
        {!content.value && content.meta && <p className="muted small explain-meta">{content.meta}</p>}

        <div className="explain-body">
          {content.sections.map((section) => (
            <section key={section.heading} className="explain-block">
              <h4>{section.heading}</h4>
              {section.body && <p>{section.body}</p>}
              {section.items && section.items.length > 0 && (
                <ul>
                  {section.items.map((item, index) => (
                    <li key={`${section.heading}-${index}`}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}

          {content.xai && (
            <section className="explain-block explain-xai">
              <div className="explain-xai-head">
                <h4>{t("Analyse expliquée")}</h4>
                <span className="chip chip-warning">{t("Lien observé, pas une cause")}</span>
              </div>
              <p>
                {t(
                  "Aucun facteur explicatif n'est déduit : l'analyse relie seulement des observations issues des mêmes données.",
                )}
              </p>
              {content.xai.statements.length > 0 && (
                <ul className="explain-xai-list">
                  {content.xai.statements.map((statement, index) => (
                    <li key={`xai-${index}`}>
                      <span className={`dot ${severityClassSafe(statement.severity)}`} />
                      <span>{statement.text}</span>
                    </li>
                  ))}
                </ul>
              )}
              {content.xai.hypothesis && (
                <div className="explain-hypothesis">
                  <span className="eyebrow">{t("Piste à explorer")}</span>
                  <p>{content.xai.hypothesis}</p>
                </div>
              )}
            </section>
          )}
        </div>

        {content.chip && (
          <p className="explain-chip-line">
            <span className={`chip chip-${content.chip.provider}`} title={chipTitle(content.chip)}>
              {chipLabel(content.chip)}
            </span>
          </p>
        )}

        {onAsk && (
          <div className="explain-actions">
            <button className="primary-btn" onClick={ask}>
              {t("Demander à Finova")}
            </button>
          </div>
        )}
        <p className="muted small">
          {t(
            "Cette explication utilise uniquement les chiffres publiés ; elle ne recalcule rien.",
          )}
        </p>
      </div>
    </div>,
    document.body,
  );
}

function severityClassSafe(severity: string): string {
  if (severity === "review") return "sev-review";
  if (severity === "warning") return "sev-warning";
  return "sev-info";
}
