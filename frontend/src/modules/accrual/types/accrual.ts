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
  name: string;
  currency: string;
  status: string;
  project_manager_id: string | null;
  project_manager_name: string | null;
}

export interface AccrualGridMonth {
  year: number;
  month: number;
}

export interface AccrualGridResponse {
  projects: AccrualGridProject[];
  cells: AccrualCell[];
  months: AccrualGridMonth[];
}
