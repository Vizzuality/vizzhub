export interface FunctionalAreaInsight {
  short: string;
  billable_pct: number;
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
  billable_project_count: number;
}

export interface PeriodUserInsight {
  period: string;
  users: UserInsight[];
}
