export interface AccrualPeriod {
  id: string;
  start_date: string; // ISO date
  status: 'open' | 'closed';
  closed_at: string | null;
  created_at: string;
  created_by: string | null;
  /**
   * The CEO's per-currency rate for this period (units of foreign per 1 EUR) —
   * the source of truth for conversion, e.g. `{ USD: '1.08', GBP: '0.87' }`.
   */
  fx_rates: Record<string, string>;
  /** ECB USD/EUR rate at start_date — fallback only, shown when fx_rates lacks USD. */
  usd_rate: string | null;
}

export interface AccrualPeriodCreate {
  start_date: string;
  /** Per-currency CEO rate (foreign per €), e.g. { USD: '1.08', GBP: '0.87' }. */
  fx_rates?: Record<string, string>;
}

export interface AccrualPeriodUpdate {
  fx_rates: Record<string, string>;
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
  data_quality_note: string | null;
  dates_diverged: boolean;
  /** The CEO's per-line Excel rate (foreign per €) — audit + override of the period rate. Display-only. */
  rate: string | null;
}

/** A line with its linked projects — the line-editor detail shape. */
export interface AccrualLineDetail {
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
}

export interface AccrualLineCreate {
  name?: string | null;
  value_eur: string | number;
  value_orig?: string | number | null;
  currency?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  project_ids?: string[];
}

export interface AccrualLineUpdate {
  name?: string | null;
  value_eur?: string | number;
  value_orig?: string | number | null;
  currency?: string | null;
  window_start?: string | null;
  window_end?: string | null;
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

export type MonthStatus = 'recognized' | 'forecast';

export interface DashboardMonth {
  month: number;
  amount_eur: number;
  status: MonthStatus;
  prev_amount_eur: number;
}

export interface DashboardKpis {
  recognized_ytd_eur: number;
  recognized_quarter_eur: number;
  contracted_total_eur: number;
  backlog_eur: number;
  plan_recognized_pct: number;
  recognized_prev_ytd_eur: number;
  yoy_pct: number | null;
}

export interface AccrualDashboardSummary {
  year: number;
  available_years: number[];
  months: DashboardMonth[];
  kpis: DashboardKpis;
}
