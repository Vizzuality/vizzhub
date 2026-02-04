export type ProjectStatus = 'in_progress' | 'finished';

export interface Project {
  id: string;
  name: string;
  jira_project_key: string | null;
  github_repo: string | null;
  slack_channel_id: string | null;
  start_date: string | null;
  end_date: string | null;
  status: ProjectStatus;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  jira_project_key?: string;
  github_repo?: string;
  slack_channel_id?: string;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  jira_project_key?: string;
  github_repo?: string;
  slack_channel_id?: string | null;
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
