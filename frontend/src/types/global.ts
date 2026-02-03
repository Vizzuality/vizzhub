/**
 * Types for Global Metrics Dashboard.
 *
 * Global metrics aggregate indicators and scores across all projects,
 * with per-indicator project counts to show data coverage.
 */

export interface IndicatorValue {
  value: number | null;
  count: number;
}

export interface ScoreValue {
  value: number | null;
  count: number;
}

export interface GlobalIndicators {
  spi: IndicatorValue;
  cpi: IndicatorValue;
  on_time_milestones: IndicatorValue;
  defect_density: IndicatorValue;
  escaped_rate: IndicatorValue;
  mttr_hours: IndicatorValue;
  governance_compliance: IndicatorValue;
  lead_time_days: IndicatorValue;
  deployment_frequency: IndicatorValue;
  change_failure_rate: IndicatorValue;
  commitment_reliability: IndicatorValue;
  pr_review_ratio: IndicatorValue;
  test_maturity: IndicatorValue;
  arch_checklist: IndicatorValue;
  high_vulns: IndicatorValue;
  okr_impact: IndicatorValue;
  pm_satisfaction: IndicatorValue;
  client_satisfaction: IndicatorValue;
  story_review_ratio: IndicatorValue;
  strategic_impact: IndicatorValue;
}

export interface GlobalScores {
  score: ScoreValue;
  p_time: ScoreValue;
  p_cost: ScoreValue;
  p_quality: ScoreValue;
  p_value: ScoreValue;
  p_satisfaction: ScoreValue;
  p_flow: ScoreValue;
  p_engineering: ScoreValue;
  p_risk: ScoreValue;
}

export interface GlobalMetricsRecord {
  id: string;
  period_year: number;
  period_month: number;
  project_count: number;
  indicators: GlobalIndicators;
  scores: GlobalScores;
  created_at: string;
  updated_at: string;
}

export interface GlobalMetricsHistoryResponse {
  records: GlobalMetricsRecord[];
}

export interface CalculateBatchRequest {
  from_year: number;
  from_month: number;
  to_year: number;
  to_month: number;
}

export interface CalculateBatchResponse {
  months_processed: number;
  records: GlobalMetricsRecord[];
}

export interface AvailableMonth {
  year: number;
  month: number;
}
