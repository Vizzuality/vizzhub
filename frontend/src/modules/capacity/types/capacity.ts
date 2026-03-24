export interface FunctionalAreaInsight {
  short: string;
  billable_pct: number;
  absence_pct: number;
  user_count: number;
}

export interface PeriodInsight {
  period: string;
  functional_areas: FunctionalAreaInsight[];
}

export interface UserInsight {
  user_id: string;
  name: string;
  billable_pct: number;
  absence_pct: number;
  billable_project_count: number;
}

export interface PeriodUserInsight {
  period: string;
  users: UserInsight[];
}

export interface ProjectInsight {
  project_id: string;
  name: string;
  percentage: number;
}

export interface PeriodProjectInsight {
  period: string;
  projects: ProjectInsight[];
  absence_pct: number;
}

export interface ReportableUser {
  id: string;
  name: string;
}

export interface ChartDataPoint {
  month: string;
  [key: string]: number | string;
}
