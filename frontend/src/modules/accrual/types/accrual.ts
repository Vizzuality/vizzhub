export interface AccrualPeriod {
  id: string;
  start_date: string; // ISO date
  status: 'open' | 'closed';
  fx_rates: Record<string, string>; // currency -> Decimal string
  closed_at: string | null;
  created_at: string;
  created_by: string | null;
}

export interface AccrualPeriodCreate {
  start_date: string;
  fx_rates: Record<string, string>;
}

export interface AccrualPeriodUpdate {
  fx_rates?: Record<string, string>;
}

export interface AccrualCell {
  id: string;
  project_id: string;
  year: number;
  month: number;
  amount: string;
  is_manual_override: boolean;
  is_frozen: boolean;
  frozen_at: string | null;
  frozen_rate: string | null;
  frozen_eur_amount: string | null;
  eur_amount: string | null;
  updated_at: string;
}

export interface BulkCellUpdate {
  project_id: string;
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
}

export interface AccrualGridProject {
  id: string;
  code: string | null;
  name: string;
  currency: string;
  budget: string | null; // legacy EUR field, kept for now
  original_budget: string | null; // budget in project's original currency
  budget_eur: string | null; // original_budget converted to EUR at the signing rate
  locked_fx_rate: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  project_manager_id: string | null;
  project_manager_name: string | null;
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
  projects: AccrualGridProject[];
  cells: AccrualCell[];
  months: AccrualGridMonth[];
  bounds: AccrualGridBounds | null;
  available_currencies: string[];
}

/** Canonical key used for failedCells sets and optimistic-update maps. */
export function buildCellKey(projectId: string, year: number, month: number): string {
  return `${projectId}:${year}:${month}`;
}
