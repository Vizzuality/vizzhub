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
