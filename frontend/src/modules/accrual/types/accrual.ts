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
