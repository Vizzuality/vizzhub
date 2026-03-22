export interface FunctionalAreaInsight {
  short: string;
  billable_pct: number;
  user_count: number;
}

export interface PeriodInsight {
  period: string;
  functional_areas: FunctionalAreaInsight[];
}
