export type ProjectStatus = 'in_progress' | 'finished';

export interface Project {
  id: string;
  name: string;
  jira_project_key: string | null;
  github_repo: string | null;
  start_date: string | null;
  end_date: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  jira_project_key?: string;
  github_repo?: string;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  jira_project_key?: string;
  github_repo?: string;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
}

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
  score: number;
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

export type StrategicImpact = 'low' | 'medium' | 'high' | 'transformational';

export interface Milestone {
  name: string;
  planned_date: string;
  actual_date?: string;
}

export interface EVMData {
  budget_total: number;
  cost_to_date: number;
  percent_completed: number;
  percent_planned: number;
}

export interface MetricsCreate {
  period_start: string;
  period_end: string;
  evm_data?: EVMData;
  milestones?: Milestone[];
  jira_defects?: {
    bugs_total: number;
    tasks_completed: number;
    escaped_defects: number;
    mttr_hours?: number;
    incidents_count: number;
    post_contract_tasks?: number;
  };
  flow_metrics?: {
    lead_time_days?: number;
    lead_time_sample_size?: number;
    commitment_reliability?: number;
    committed_issues?: number;
    single_sprint_issues?: number;
    multi_sprint_issues?: number;
    total_stories: number;
    stories_with_reviewer: number;
  };
  github_metrics?: {
    prs_without_review: number;
    total_merged_prs: number;
    pr_review_ratio?: number;
    high_severity_vulns: number;
    high_severity_vulns_total?: number;
    pr_size_median?: number;
    review_turnaround_hours?: number;
    deployment_frequency?: number;
    release_count_90d?: number;
    change_failure_rate?: number;
    total_releases?: number;
    failed_releases?: number;
  };
  test_maturity?: {
    e2e?: number;
    unit?: number;
    accessibility?: number;
    security?: number;
    frontend?: number;
  };
  architecture?: {
    docs_up_to_date: boolean;
    iac_implemented: boolean;
    adrs_maintained: boolean;
    diagrams_updated: boolean;
  };
  pm_satisfaction?: {
    delivery_complaints: 'yes' | 'no' | '-';
    design_complaints: 'yes' | 'no' | '-';
    overall_estimation?: number;
  };
  client_survey?: {
    understanding?: number;
    proactivity?: number;
    communication?: number;
    delivery_time?: number;
    response_time?: number;
    quality?: number;
    expectations?: number;
    recommend?: number;
  };
  strategic_impact?: StrategicImpact;
  governance_exceptions?: number;
  sev1_incident: boolean;
}

export interface PMSatisfaction {
  delivery_complaints: 'yes' | 'no' | '-';
  design_complaints: 'yes' | 'no' | '-';
  overall_estimation?: number;
}

export interface TestMaturity {
  e2e?: number;
  unit?: number;
  accessibility?: number;
  security?: number;
  frontend?: number;
}

export interface Architecture {
  docs_up_to_date: boolean;
  iac_implemented: boolean;
  adrs_maintained: boolean;
  diagrams_updated: boolean;
}

export interface ClientSurvey {
  understanding?: number;
  proactivity?: number;
  communication?: number;
  delivery_time?: number;
  response_time?: number;
  quality?: number;
  expectations?: number;
  recommend?: number;
}

export interface Metrics extends MetricsCreate {
  id: string;
  project_id: string;
  created_at: string;
}

// Metrics snapshot types for historical metrics
export type SnapshotType = 'punctual' | 'cumulative';

// MetricsWithScores represents metrics with computed indicators and scores
export interface MetricsWithScores {
  id: string;
  project_id: string;
  period_year: number;
  period_month: number;
  snapshot_type: SnapshotType;
  weights_applied: Record<string, number>;
  targets_applied: Record<string, number>;
  created_at: string;
  indicators: Indicators;
  scores: FinalScore;
}

// Alias for backward compatibility
export type SnapshotWithScores = MetricsWithScores;

// Period capture types (single period with Jira/GitHub collection)
export interface CapturePeriodRequest {
  year?: number;
  month?: number;
  force?: boolean;
}

export interface CapturePeriodResponse {
  punctual: MetricsWithScores;
  cumulative: MetricsWithScores;
}

// Historical capture types (batch capture for multiple periods)
export interface CaptureHistoryRequest {
  from_year: number;
  from_month: number;
  to_year: number;
  to_month: number;
  force: boolean;
}

export interface CaptureResult {
  month: string;
  snapshot_type: SnapshotType;
  status: 'created' | 'skipped' | 'error';
  error_message: string | null;
}

export interface CaptureReport {
  project_id: string;
  requested_range: [string, string];
  summary: {
    total_months: number;
    snapshots_created: number;
    snapshots_skipped: number;
    errors: number;
  };
  details: CaptureResult[];
  errors: CaptureResult[];
}

// Job types for async task tracking
export type JobType = 'capture_history';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobResponse {
  id: string;
  type: JobType;
  status: JobStatus;
  name: string;
  progress: number;
  created_at: string;
}

export interface JobDetailResponse extends JobResponse {
  description: string | null;
  project_id: string | null;
  params: Record<string, unknown>;
  result: CaptureReport | null;
  progress_message: string | null;
  logs: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobSummaryResponse {
  id: string;
  type: JobType;
  status: JobStatus;
  name: string;
  progress: number;
  project_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface CreateCaptureHistoryJobRequest {
  project_id: string;
  from_year: number;
  from_month: number;
  to_year: number;
  to_month: number;
  force?: boolean;
}

export interface ApiErrorResponse {
  detail: string;
}
