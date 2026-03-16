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

export interface ReportingPeriodUpdate {
  date?: string;
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
