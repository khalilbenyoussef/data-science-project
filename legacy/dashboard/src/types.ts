export type Severity = "review" | "warning" | "info";

export interface CountryScope {
  iso3: string;
  name: string;
  region: string | null;
  income_group: string | null;
}

export interface KpiScope {
  kpi_id: string;
  name: string;
  unit: string;
  subgroup: string;
  verification_status: string;
  valid_years: number[];
  dependencies: string[];
}

export interface Scope {
  countries: CountryScope[];
  kpis: KpiScope[];
  mode: string;
  year: number | null;
  reference_iso3: string;
  ranking_rule: string;
}

export interface SourceProvenance {
  source: string;
  path: string | null;
  sha256: string | null;
  rows: number | null;
  observed_sha256: string | null;
  hash_match: boolean | null;
}

export interface Provenance {
  warehouse_path: string;
  warehouse_sha256: string;
  warehouse_size_bytes: number;
  lineage_path: string;
  lineage_sha256: string | null;
  lineage_run_id: string | null;
  lineage_created_at: string | null;
  quality_report_path: string;
  quality_report_sha256: string | null;
  quality_gate_passed: boolean | null;
  quality_score: number | null;
  quality_association_status: string;
  content_binding: string;
  recorded_warehouse_path: string | null;
  recorded_warehouse_sha256: string | null;
  sources: SourceProvenance[];
  issues: string[];
}

export interface Card {
  kpi_id: string;
  kpi_name: string;
  iso3: string;
  country_name: string;
  region: string | null;
  income_group: string | null;
  year: number | null;
  value: number | null;
  unit: string;
  availability_status: string;
  reason: string | null;
  definition_status: string;
  requires_review: boolean;
  review_reasons: string[];
  evidence_id: string;
}

export interface TableRow extends Card {
  selection: string;
  source: string;
  indicator_code: string;
}

export interface SeriesPoint {
  year: number;
  value: number | null;
  availability_status: string;
  reason: string | null;
  requires_review: boolean;
  evidence_id: string;
}

export interface Series {
  kpi_id: string;
  iso3: string;
  unit: string;
  points: SeriesPoint[];
}

export interface RankingRow {
  iso3: string;
  rank: number | null;
  value: number | null;
  unit: string;
  availability_status: string;
  reason: string | null;
  requires_review: boolean;
  review_reasons: string[];
  evidence_id: string;
}

export interface Ranking {
  kpi_id: string;
  year: number | null;
  status: string;
  rule: string;
  rows: RankingRow[];
}

export interface ComparisonRow {
  iso3: string;
  value: number | null;
  reference_value: number | null;
  difference: number | null;
  unit: string;
  comparison_status: string;
  reason: string | null;
  requires_review: boolean;
  review_reasons: string[];
  evidence_id: string;
}

export interface Comparison {
  comparison_id: string;
  kpi_id: string;
  reference_iso3: string;
  year: number | null;
  difference_formula: string;
  status: string;
  rows: ComparisonRow[];
}

export interface Insight {
  id: string | null;
  code: string | null;
  statement: string | null;
  severity: Severity | null;
  evidence_ids: string[];
}

export interface Notice {
  code: string;
  severity: Severity;
  message: string;
  [key: string]: unknown;
}

export interface AnalysisSummary {
  kpis: string[];
  countries: string[];
  mode: string;
  year: number | null;
  selected_observations: number;
  available: number;
  unavailable: number;
  requires_review: number;
  findings: { total: number; review: number; warning: number; info: number };
}

export interface DashboardData {
  schema_version: string;
  generated_at: string;
  run_id: string;
  catalog: { version: string; sha256: string };
  scope: Scope;
  provenance: Provenance;
  cards: Card[];
  table: TableRow[];
  series: Series[];
  rankings: Ranking[];
  comparisons: Comparison[];
  insights: Insight[];
  notices: Notice[];
  summary?: AnalysisSummary | null;
  limitations?: string[];
  publication_status: string;
}
