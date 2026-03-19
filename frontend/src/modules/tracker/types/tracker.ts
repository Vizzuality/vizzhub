export interface ReportingPeriod {
  id: string;
  date: string;
  base_rate: number;
  status: 'unstarted' | 'active' | 'finished';
  report_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReportingPeriodCreate {
  date: string;
  base_rate?: number;
}

export interface Report {
  id: string;
  user_id: string;
  reporting_period_id: string;
  estimated: boolean;
  user_name: string | null;
  user_email: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReportWithParts extends Report {
  parts: ReportPart[];
}

export interface ReportCreate {
  reporting_period_id: string;
  estimated?: boolean;
}

export interface ReportPart {
  id: string;
  report_id: string;
  project_id: string;
  project_name: string | null;
  functional_area_id: string | null;
  percentage: number | null;
  days: number | null;
  cost: number | null;
  created_at: string;
  updated_at: string;
}

export interface ReportPartCreate {
  report_id: string;
  project_id: string;
  functional_area_id?: string;
  percentage: number;
}

export interface ReportPartUpdate {
  functional_area_id?: string | null;
  percentage?: number;
}

export interface PeriodCostBreakdown {
  period_id: string;
  date: string;
  staff_cost: number;
  non_staff_cost: number;
  total: number;
  parts_count: number;
}

export interface ProjectCostSummary {
  project_id: string;
  budget: number | null;
  contract_rate: number;
  staff_cost: number;
  non_staff_cost: number;
  total_cost: number;
  burn_percentage: number | null;
  periods: PeriodCostBreakdown[];
}

export interface ProjectReportPart {
  id: string;
  period_date: string;
  user_name: string | null;
  user_email: string | null;
  functional_area: string | null;
  percentage: number | null;
  days: number | null;
  cost: number | null;
  estimated: boolean;
}

export interface ProjectCostSummaryLite {
  budget: number | null;
  total_cost: number;
  staff_cost: number;
  non_staff_cost: number;
  burn_percentage: number | null;
}

export interface BatchCostsResponse {
  costs: Record<string, ProjectCostSummaryLite>;
  errors: Record<string, string>;
}

export interface AggregationPeriod {
  date: string;
  days: number;
  cost: number;
}

export interface AggregationRow {
  name: string;
  email: string | null;
  total_days: number;
  total_cost: number;
  periods: AggregationPeriod[];
}

export interface AggregationResponse {
  group_by: string;
  rows: AggregationRow[];
}

