export interface DimensionScores {
  p_time: number | null;
  p_cost: number | null;
  p_quality: number | null;
  p_value: number | null;
  p_satisfaction: number | null;
  p_flow: number | null;
  p_engineering: number | null;
  p_risk: number | null;
}

export type Dimension = 'Time' | 'Cost' | 'Quality' | 'Value' | 'Satisfaction' | 'Flow' | 'Engineering' | 'Risk';

export const ALL_DIMENSIONS: Dimension[] = ['Time', 'Cost', 'Quality', 'Value', 'Satisfaction', 'Flow', 'Engineering', 'Risk'];

export interface HistoricalDataPoint {
  period: string;
  value: number | null;
}

export type DoraLevel = 'Elite' | 'High' | 'Medium' | 'Low';

export interface DoraMetricDetail {
  value: number;
  level: DoraLevel;
  score: number;
  no_incidents?: boolean;
}

export interface DoraScore {
  score: number | null;
  classification: DoraLevel | null;
  metrics: {
    deployment_frequency?: DoraMetricDetail;
    lead_time?: DoraMetricDetail;
    change_failure_rate?: DoraMetricDetail;
    mttr?: DoraMetricDetail;
  };
  available_metrics: number;
}

export interface FinalScore {
  score: number | null;
  dimensions: DimensionScores;
  weights_applied: Record<string, number>;
  dora: DoraScore | null;
}

export interface Indicators {
  spi: number | null;
  on_time_milestones: number | null;
  cpi: number | null;
  budget_variance: number | null;
  defect_density: number | null;
  escaped_rate: number | null;
  mttr_hours: number | null;
  governance_compliance: number | null;
  lead_time_days: number | null;
  commitment_reliability: number | null;
  pr_review_ratio: number | null;
  prs_without_review: number | null;
  high_vulns: number | null;
  test_maturity: number | null;
  arch_checklist: number | null;
  story_review_ratio: number | null;
  okr_impact: number | null;
  pm_satisfaction: number | null;
  client_satisfaction: number | null;
  pr_size_median: number | null;
  review_turnaround_hours: number | null;
  deployment_frequency: number | null;
  change_failure_rate: number | null;
  post_contract_tasks: number | null;
}

export interface ScoreResponse {
  indicators: Indicators;
  scores: FinalScore;
}

export interface ScoringConfig {
  targets: {
    defect_density: number;
    escaped_rate: number;
    mttr_hours: number;
    spi: number;
    cpi: number;
    lead_time_days: number;
    high_vuln_count: number;
    gov_exceptions: number;
    pr_no_review_ratio: number;
    story_review_ratio: number;
    client_satisfaction: number;
    architecture: number;
    commitment_reliability: number;
    milestones_on_time: number;
    test_maturity: number;
    pm_satisfaction: number;
    pr_size_lines: number;
    review_turnaround_hours: number;
    deployment_frequency: number;
    change_failure_rate: number;
    post_contract_tasks: number;
    budget_variance: number;
    governance_compliance: number;
    okr_impact: number;
  };
  ideals: {
    spi: number;
    cpi: number;
  };
  global_weights: {
    time: number;
    cost: number;
    quality: number;
    value: number;
    satisfaction: number;
    flow: number;
    engineering: number;
    risk: number;
  };
  constants: {
    sev1_cap: number;
    grace_days: number;
  };
  weight_validation: Record<string, boolean>;
}
