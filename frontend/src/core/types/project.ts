import type { PaginatedResponse } from './common';

export type ProjectStatus = 'proposal' | 'live' | 'finished';

export interface Project {
  id: string;
  name: string;
  code: string | null;
  program_id: string | null;
  program_name: string | null;
  is_billable: boolean;
  has_scorecard: boolean;
  has_dependabot_alerts: boolean;
  has_budget_alerts: boolean;
  currency: string;
  budget: number | null;
  notes: string | null;
  summary: string | null;
  jira_project_key: string | null;
  github_repo: string | null;
  slack_channel_id: string | null;
  project_manager_id: string | null;
  project_manager_name: string | null;
  start_date: string | null;
  end_date: string | null;
  status: ProjectStatus;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  code: string;
  program_id?: string | null;
  is_billable?: boolean;
  has_scorecard?: boolean;
  has_dependabot_alerts?: boolean;
  has_budget_alerts?: boolean;
  currency: string;
  budget?: number | null;
  original_budget?: number | null;
  notes?: string | null;
  summary?: string | null;
  jira_project_key?: string;
  github_repo?: string;
  slack_channel_id?: string;
  project_manager_id?: string | null;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  code?: string;
  program_id?: string | null;
  is_billable?: boolean;
  has_scorecard?: boolean;
  has_dependabot_alerts?: boolean;
  has_budget_alerts?: boolean;
  currency?: string;
  budget?: number | null;
  notes?: string | null;
  summary?: string | null;
  jira_project_key?: string;
  github_repo?: string;
  slack_channel_id?: string | null;
  project_manager_id?: string | null;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
  finished_at?: string;
  clear_finished_at?: boolean;
}

export interface SlackChannel {
  id: string;
  name: string;
  is_private: boolean;
}

export type PaginatedProjects = PaginatedResponse<Project>;

export interface ProjectSummary {
  id: string;
  name: string;
  code?: string | null;
  currency?: string | null;
  budget?: number | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface ProjectListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  sort?: string;
  order?: string;
  start_date_from?: string;
  start_date_to?: string;
  project_manager_id?: string;
}

export interface ProgramSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface BudgetPreviewResponse {
  budget_eur: number | null;
}
