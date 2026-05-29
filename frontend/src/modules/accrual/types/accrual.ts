export interface AccrualPeriod {
  id: string;
  start_date: string; // ISO date
  status: 'open' | 'closed';
  closed_at: string | null;
  created_at: string;
  created_by: string | null;
  /** ECB USD/EUR rate effective at start_date (units of USD per 1 EUR). */
  usd_rate: string | null;
}

export interface AccrualPeriodCreate {
  start_date: string;
}

export type AccrualCellSource = 'excel' | 'team_budget' | 'manual';

export interface AccrualCell {
  id: string;
  line_id: string | null;
  project_id: string | null;
  year: number;
  month: number;
  amount: string;
  is_manual_override: boolean;
  is_frozen: boolean;
  frozen_at: string | null;
  frozen_eur_amount: string | null;
  eur_amount: string | null;
  source: AccrualCellSource;
  updated_at: string;
}

export interface BulkCellUpdate {
  line_id: string;
  year: number;
  month: number;
  amount: string;
}

export interface AccrualGridFilters {
  year_from: number;
  year_to: number;
  status?: string;
  currency?: string;
  project_manager_id?: string;
  source?: AccrualLineSource;
}

export type AccrualHealthStatus = 'ok' | 'warning' | 'critical' | 'no_data';

export interface AccrualHealth {
  status: AccrualHealthStatus;
  diff_eur: string | null;
  diff_pct: number | null;
}

export type AccrualLineSource = 'excel' | 'team_budget' | 'manual';

/** A project tag on a line (0..N per line). */
export interface AccrualLineProject {
  id: string;
  code: string | null;
  name: string;
  status: string;
  project_manager_id: string | null;
  project_manager_name: string | null;
}

/** A grid row: one revenue-recognition line. */
export interface AccrualGridLine {
  id: string;
  name: string | null;
  source: AccrualLineSource;
  excel_code: string | null;
  value_eur: string;
  value_orig: string | null;
  currency: string | null;
  window_start: string | null;
  window_end: string | null;
  projects: AccrualLineProject[];
  health: AccrualHealth;
}

export interface AccrualGridMonth {
  year: number;
  month: number;
}

export interface AccrualGridBounds {
  min_year: number;
  max_year: number;
}

export interface AccrualGridResponse {
  lines: AccrualGridLine[];
  cells: AccrualCell[];
  months: AccrualGridMonth[];
  bounds: AccrualGridBounds | null;
  available_currencies: string[];
}

/** Canonical key used for failedCells sets and optimistic-update maps. */
export function buildCellKey(lineId: string, year: number, month: number): string {
  return `${lineId}:${year}:${month}`;
}

export type DriftKind =
  | 'date_extend'
  | 'date_shrink'
  | 'value_drift'
  | 'status_stale'
  | 'missing_excel'
  | 'missing_tracker';

export interface DriftFinding {
  id: string;
  kind: DriftKind;
  project_id: string | null;
  project_name: string | null;
  project_code: string | null;
  excel_code: string | null;
  detected_at: string;
  resolved_at: string | null;
  resolution: string | null;
  resolved_by: string | null;
  payload: Record<string, unknown>;
  import_run_id: string | null;
}

export interface DriftFindingsResponse {
  items: DriftFinding[];
  total: number;
}

export interface DriftSummaryBucket {
  open: number;
  resolved: number;
}

export interface DriftSummaryResponse {
  by_kind: Record<string, DriftSummaryBucket>;
  total_open: number;
  total_resolved: number;
}

export interface AccrualAlias {
  id: string;
  excel_code: string;
  project_id: string;
  project_name: string | null;
  project_code: string | null;
  weight: string;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AccrualAliasCreate {
  excel_code: string;
  project_id: string;
  weight?: string;
  notes?: string;
}

export interface AccrualAliasBulkMapping {
  project_id: string;
  weight?: string;
  notes?: string;
}

export interface AccrualAliasBulkCreate {
  excel_code: string;
  mappings: AccrualAliasBulkMapping[];
  replace_existing?: boolean;
}

export interface AccrualExcelRow {
  id: string;
  import_run_id: string;
  import_run_position: number;
  excel_code: string;
  name: string | null;
  pm_name: string | null;
  client: string | null;
  value_orig: string | null;
  currency: string | null;
  rate: string | null;
  value_eur: string;
  start_date: string | null;
  end_date: string | null;
  months: number | null;
  monthly_cells: { year: number; month: number; eur_amount: string }[];
  alias_project_id: string | null;
  alias_project_name: string | null;
  alias_project_code: string | null;
}

export interface AccrualExcelRowsResponse {
  items: AccrualExcelRow[];
  total: number;
  import_run_id: string | null;
}

export interface AccrualImportRun {
  id: string;
  started_at: string;
  completed_at: string | null;
  source_path: string | null;
  rows_parsed: number;
  rows_mapped: number;
  rows_unmatched: number;
  drift_findings_count: number;
}
