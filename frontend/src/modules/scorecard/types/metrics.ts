import type { Indicators, FinalScore } from './scores';

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

export type ComplaintAnswer = 'yes' | 'no' | '-';

export interface PMSatisfaction {
  delivery_complaints: ComplaintAnswer;
  design_complaints: ComplaintAnswer;
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
    high_severity_vulns: number | null;
    high_severity_vulns_total: number | null;
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
    delivery_complaints: ComplaintAnswer;
    design_complaints: ComplaintAnswer;
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

export interface Metrics extends MetricsCreate {
  id: string;
  project_id: string;
  created_at: string;
}

export type SnapshotType = 'punctual' | 'cumulative';

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
  evm_data?: EVMData;
  milestones?: Milestone[];
  jira_defects?: NonNullable<MetricsCreate['jira_defects']>;
  flow_metrics?: NonNullable<MetricsCreate['flow_metrics']>;
  github_metrics?: NonNullable<MetricsCreate['github_metrics']>;
  test_maturity?: TestMaturity;
  architecture?: Architecture;
  pm_satisfaction?: PMSatisfaction;
  client_survey?: ClientSurvey;
  strategic_impact?: StrategicImpact;
  governance_exceptions?: number;
  sev1_incident?: boolean;
}

export type SnapshotWithScores = MetricsWithScores;

export interface CapturePeriodRequest {
  year?: number;
  month?: number;
  force?: boolean;
}

export interface CapturePeriodResponse {
  punctual: MetricsWithScores;
  cumulative: MetricsWithScores;
}

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
