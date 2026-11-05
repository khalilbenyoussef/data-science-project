export interface Chip {
  provider: string;
  label: string;
  requires_review: boolean;
  review_reasons: string[];
  note: string | null;
}

export interface WhyInfo {
  definition: string;
  source: string;
  source_url: string | null;
  filter: string | null;
  year_used: number | null;
  definition_status: string;
  review_reasons: string[];
  caveat: string | null;
}

export interface Delta {
  value: number;
  unit: string;
  from_year: number;
  to_year: number;
  label: string;
}

export interface Metric {
  id: string;
  label: string;
  value: number | null;
  display: string;
  unit: string;
  year: number | null;
  // annee demandee ; year_basis dit pourquoi year (annee utilisee) peut differer
  year_requested?: number | null;
  year_basis?: "selected" | "survey_wave" | "latest_observed";
  status: string;
  provider: string;
  iso3: string;
  chip: Chip;
  delta: Delta | null;
  evidence_ids: string[];
  why: WhyInfo | null;
  caveat: string | null;
  // indisponible car mesuré seulement à partir d'une vague postérieure
  first_available_year?: number | null;
  unavailable_reason?: string | null;
}

export interface Point {
  year: number;
  value: number | null;
  status: string;
  reason: string | null;
}

export interface Series {
  id: string;
  label: string;
  unit: string;
  points: Point[];
  provider?: string;
  chip?: Chip;
  color?: string | null;
}

export interface ReferenceLine {
  label: string;
  value: number;
  year: number;
  unit: string;
  source: string;
  source_url: string | null;
  provider: string;
  chip: Chip;
}

export interface Bar {
  id: string;
  label: string;
  iso3?: string;
  value: number | null;
  display: string;
  status: string;
  year: number;
  highlight: boolean;
  provider: string;
  chip: Chip;
  evidence_ids: string[];
}

export interface Step {
  id: string;
  label: string;
  value: number | null;
  display: string;
  status: string;
  year: number;
  drop_from_previous_pp: number | null;
  provider: string;
  chip: Chip;
  evidence_ids: string[];
}

export interface DumbbellSide {
  label: string;
  value: number | null;
  display: string;
  status: string;
}

export interface DumbbellRow {
  id: string;
  label: string;
  left: DumbbellSide;
  right: DumbbellSide;
  gap_pp: number;
  status: string;
  year: number;
  provider: string;
  chip: Chip;
  evidence_ids: string[];
}

export interface DumbbellGroup {
  id: string;
  title: string;
  dimension: string;
  rows: DumbbellRow[];
}

export interface GapPoint {
  id: string;
  label: string;
  from_year: number;
  to_year: number;
  gap_from_pp: number;
  gap_to_pp: number;
  change_pp: number;
  status: string;
  evidence_ids: string[];
}

export interface HeatmapCell {
  column: string;
  row: string;
  value: number | null;
  status: string;
  display: string;
  note: string;
}

export interface Chart {
  id: string;
  kind: string;
  title: string;
  subtitle: string | null;
  x_label: string | null;
  y_label: string | null;
  unit: string | null;
  series: Series[];
  bars: Bar[];
  steps: Step[];
  groups: DumbbellGroup[];
  gap_points: GapPoint[];
  columns: string[];
  rows: string[];
  cells: HeatmapCell[];
  reference_lines: ReferenceLine[];
  notes: string[];
  formula: string | null;
  chip: Chip | null;
  // sans valeur du pays : vague postérieure (first_available_year) ou pays jamais observé
  no_data_scope?: "later_wave" | "country" | null;
  first_available_year?: number | null;
}

export interface Insight {
  id: string;
  code: string;
  statement: string;
  severity: string;
  kind: string;
  evidence_ids: string[];
}

export interface XaiCard {
  title: string;
  evidence: Insight[];
  interpretation: Insight[];
  recommendation: Insight;
  caveat: string;
}

export interface ChangeItem {
  metric_id: string;
  label: string;
  previous_value: number | null;
  current_value: number | null;
  delta: number | null;
  unit: string;
  status: string;
}

export interface Changes {
  available: boolean;
  previous_run_id: string | null;
  previous_generated_at: string | null;
  items: ChangeItem[];
}

export interface InfoItem {
  id: string;
  label: string;
  value: string | null;
  unit: string | null;
  status: string;
  provider: string | null;
  chip: Chip | null;
  year: number | null;
  note: string | null;
  source: string | null;
  source_url: string | null;
}

export interface AskPayload {
  suggestions: string[];
  endpoint: string;
  rules: string[];
}

export interface SimulatorPayload {
  default_fee_tnd: number;
  smig_reference: { value: number; year: number; source: string };
  formula: string;
  rules: string[];
}

export interface PipelinePayload {
  route1: { id: string; label: string; status: string; detail: string }[];
  route2: { id: string; label: string; status: string; detail: string }[];
  gate: {
    passed: boolean;
    score: number | null;
    threshold: number;
    critical_issues: number;
  };
  sources: {
    name: string;
    path: string;
    rows: number;
    sha256: string | null;
    sha256_match: boolean | null;
    collected_at: string | null;
    rejected: Record<string, number>;
  }[];
  quality: {
    run_id: string | null;
    score: number;
    passed: boolean;
    checks: { source: string; rows: number; cols: number; score: number; gate: boolean }[];
  };
  warehouse: {
    path: string;
    fact_rows: number;
    countries: number;
    by_source: Record<string, number>;
    sha256: string | null;
  };
  last_run: {
    run_id: string;
    created_at: string;
    period: { min_year: number; max_year: number };
  } | null;
  reports: string[];
  history: { run_id: string; generated_at: string; iso3: string; year: number; file: string }[];
  transforms: string[];
  checks: Record<string, unknown>;
}

export interface InfoBlock {
  id: string;
  kind: string;
  title: string;
  subtitle: string | null;
  items: InfoItem[];
  payload: Record<string, unknown>;
}

export interface Notice {
  code: string;
  severity: string;
  message: string;
  kpi_id: string | null;
}

export interface Page {
  id: string;
  title: string;
  subtitle: string | null;
  available: boolean;
  unavailable_reason: string | null;
  metrics: Metric[];
  charts: Chart[];
  insights: Insight[];
  changes: Changes | null;
  xai: XaiCard | null;
  blocks: InfoBlock[];
  notices: Notice[];
}

export interface CountryRef {
  iso3: string;
  name: string;
  region: string | null;
  income_group: string | null;
}

export interface Fact {
  id: string;
  code: string;
  label: string;
  value: number | null;
  display: string;
  unit: string;
  year: number;
  iso3: string;
  provider: string;
  evidence_ids: string[];
}

export interface FindexWave {
  year_requested: number;
  year_used: number | null;
  survey_years: number[];
}

export interface Spec {
  schema_version: string;
  generated_at: string;
  run_id: string;
  country: CountryRef;
  year: number;
  years: number[];
  survey_years?: number[];
  findex_wave?: FindexWave | null;
  countries_available: CountryRef[];
  pages: Page[];
  facts: Fact[];
  notices: Notice[];
  provenance?: Record<string, unknown>;
  reference?: Record<string, unknown>;
  publication_status: string;
}

export interface AskFact {
  id: string;
  label: string;
  display: string;
  year: number;
  unit: string | null;
  iso3?: string | null;
  user_data?: boolean;
  chip?: string;
}

export interface AskResult {
  schema_version: string;
  question: string;
  intent: string;
  answer: string;
  fallback: boolean;
  fact_ids: string[];
  facts: AskFact[];
  caveat: string | null;
  number_check: { passed: boolean; unknown: string[] };
  mode?: "llm" | "deterministic";
  lang?: string;
  suggestions?: string[];
  budget_left?: number;
  user_data_policy?: { llm_allowed: boolean; reason: string | null };
  iso3: string;
  year: number;
  country_name: string;
  generated_at: string | null;
  source: string;
}

// ------------------------------------------------------------ Mes données
export type ColumnRole =
  | "country" | "year" | "indicator" | "value" | "year_column" | "indicator_column" | "ignore";

export interface DetectColumn {
  name: string;
  role: ColumnRole;
  evidence: string;
  origin: string | null;
  samples: string[];
}

export interface DetectResult {
  upload_id: string;
  filename: string;
  size_bytes: number;
  max_file_mb: number;
  rows: number;
  read: { encoding: string; separator: string; decimal: string; header_row: number };
  layout: "long" | "wide_by_year" | "wide_by_indicator" | null;
  layout_evidence: string;
  problem: string | null;
  columns: DetectColumn[];
  country: { column: string; kind: "iso3" | "name"; share: number } | null;
  fingerprint: string;
  reusable: { name: string; confirmed_at: string | null; indicators: Record<string, string> }[];
}

export interface IndicatorChoice {
  label?: string;
  unit?: string | null;
  transform?: "none" | "percent_to_fraction";
  comparable_kpi?: string | null;
  same_definition?: boolean;
}

export interface ComparableKpi {
  id: string;
  name_fr: string;
  unit: string;
  definition: string | null;
  denominator: string | null;
}

export interface ComparisonValue {
  value: number;
  display: string;
  year: number;
  unit: string;
  chip?: string;
  publication_status?: string;
}

export interface ComparisonRow {
  indicator_code: string;
  label: string;
  unit: string;
  kpi_id: string;
  kpi: string;
  definition: string | null;
  denominator: string | null;
  user: ComparisonValue | null;
  official: ComparisonValue | null;
  status: "ok" | "unit_mismatch" | "unknown_kpi" | "no_user_value" | "no_official_value";
  same_year: boolean;
  notes: string[];
}

export interface ComparisonsResult {
  iso3: string;
  year: number;
  chip: string;
  note: string;
  rows: ComparisonRow[];
}

export interface SourceMappingInput {
  roles?: Record<string, ColumnRole>;
  country_kind?: "iso3" | "name";
  indicators?: Record<string, IndicatorChoice>;
  country_names?: Record<string, string>;
  reuse?: string;
  replace?: boolean;
}

export interface DryRunResult {
  name: string;
  layout: string;
  roles: Record<string, ColumnRole>;
  indicators: { code: string; label: string; unit: string | null; transform: string; comparable_kpi?: string | null }[];
  country_names: Record<string, string>;
  missing_fields: { indicator: string; label: string; field: string }[];
  blocking: string[];
  rows_mapped_pct: number;
  observations: number;
  mapped: number;
  empty_cells: number;
  year_range: [number, number] | null;
  countries: string[];
  unmapped_countries: Record<string, { rows: number; reason: string }>;
  non_numeric: { count: number; examples: { line: number; column: string; text: string }[] };
  invalid_years: { count: number };
  duplicates: { exact_removed: number; conflicting_keys: number };
  preview: {
    iso3: string; year: number; indicator_code: string; indicator_label: string; value: number;
    unit: string; raw_value: string; raw_column: string; line: number;
  }[];
  quality: { gate: boolean; score: number; issues: { code: string; severity: string; message: string | null }[] };
}

export interface SourceJob {
  job_id: string;
  kind: "add" | "delete" | "demo";
  source: string;
  status: "queued" | "running" | "success" | "quality_failed" | "audit_failed" | "error";
  step: string | null;
  steps_done: string[];
  run_id: string | null;
  route2_run_id: string | null;
  message: string | null;
  reasons: string[];
  started_at: string;
  finished_at: string | null;
  seconds: number | null;
  quality_score?: number | null;
  skipped?: string[];
  no_change?: boolean;
}

export interface UserSource {
  name: string;
  file: string;
  confirmed_at: string | null;
  indicators: { code: string; label: string; unit: string }[];
  rows: number;
  years: [number, number] | null;
  countries: string[];
  quality_score: number | null;
  status: "included" | "excluded" | "pending";
  reason: string | null;
  last_job: { job_id: string; kind: string; status: string; finished_at: string | null } | null;
}

export interface SourcesList {
  sources: UserSource[];
  active_job: SourceJob | null;
  max_file_mb: number;
}

export interface SourceData {
  name: string;
  provider: string;
  chip: string;
  indicators: { code: string; label: string; unit: string }[];
  values: { iso3: string; year: number; indicator_code: string; indicator_label: string; value: number | null; unit: string }[];
}

export interface RunSummary {
  run_id: string;
  status: string | null;
  objective: string | null;
  started_at: string | null;
  finished_at: string | null;
  errors: string[];
  spec: boolean;
  route2: Record<string, unknown> | null;
}

// ------------------------------------------------------------ Pistes de recommandation
export interface RecommendationEvidence {
  id: string;
  kpi_id: string;
  kpi: string;
  iso3: string;
  year: number;
  value: number;
  unit: string;
  publication_status: string;
  review_reasons: string[];
}

export interface Recommendation {
  id: string;
  rule_id: string;
  kpi_id: string;
  kpi: string;
  iso3: string;
  year: number;
  country: string;
  target_group: string;
  text: string;
  rule: string;
  review_note: boolean;
  evidence: RecommendationEvidence[];
}

export interface RecommendationsResult {
  iso3: string;
  year: number;
  country: string;
  rules_version: number | null;
  rules_checked: number;
  recommendations: Recommendation[];
  rejected: number;
}

// ------------------------------------------------------------ Agents (page Sources et qualité)
export interface AgentRow {
  id: string;
  route: "Route 1" | "Route 2" | "Interface";
  label: string;
  role: string;
  status: string | null;
  started_at: string | null;
  duration_s: number | null;
  key_output: string | null;
  llm: boolean;
  llm_mode: string;
  llm_measured: string;
  note: string | null;
}

export interface AgentsTimeline {
  route1_run_id: string;
  route2_run_id: string | null;
  snapshot_id: string;
  status: string | null;
  no_change: boolean;
  finished_at: string | null;
  agents: AgentRow[];
  active_job: SourceJob | null;
}
