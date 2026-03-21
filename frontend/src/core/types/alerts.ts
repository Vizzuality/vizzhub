import type { PaginatedResponse } from './common';

export type AlertCategory = 'business' | 'project';
export type ChannelType = 'leadership' | 'project';
export type AlertSchedule = 'daily_check_monthly_report' | 'daily';
export type TemplateType = 'initial' | 'reminder' | 'escalation';
export type NotificationStatus = 'sent' | 'failed' | 'pending';

export interface AlertDefinition {
  id: number;
  name: string;
  description: string | null;
  category: AlertCategory;
  channel_type: ChannelType;
  schedule: AlertSchedule;
  is_enabled: boolean;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AlertDefinitionUpdate {
  is_enabled?: boolean;
  config_json?: Record<string, unknown>;
}

export interface MessageTemplate {
  id: number;
  alert_definition_id: number;
  template_type: TemplateType;
  message_template: string;
  is_active: boolean;
}

export interface MessageTemplateUpdate {
  message_template?: string;
  is_active?: boolean;
}

export interface AlertSilence {
  id: number;
  project_id: string;
  alert_definition_id: number | null;
  silenced_until: string | null;
  reason: string | null;
  created_by: string | null;
  created_at: string;
  project_name: string | null;
  alert_name: string | null;
}

export interface AlertSilenceCreate {
  project_id: string;
  alert_definition_id: number | null;
  silenced_until: string | null;
  reason: string | null;
}

export interface AlertSilenceUpdate {
  silenced_until?: string | null;
  reason?: string | null;
}

export interface AlertNotification {
  id: number;
  project_id: string;
  alert_definition_id: number;
  channel_id: string;
  message: string;
  status: NotificationStatus;
  error_message: string | null;
  metadata_json: Record<string, unknown> | null;
  sent_at: string;
  project_name: string | null;
  alert_name: string | null;
}

export type PaginatedNotifications = PaginatedResponse<AlertNotification>;

export interface NotificationFilters {
  project_id?: string;
  alert_definition_id?: number;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}

export interface NotificationStats {
  total_this_month: number;
  by_type: Record<string, number>;
  by_project: Array<{ project_name: string; count: number }>;
  avg_vulnerability_resolution_days: number | null;
}

export interface ScheduledJobLastRun {
  id: number;
  started_at: string;
  completed_at: string | null;
  status: string;
  projects_checked: number;
  alerts_sent: number;
  error_message: string | null;
}

export interface ScheduledJobInfo {
  name: string;
  schedule: string;
  description: string;
  last_run: ScheduledJobLastRun | null;
}

export interface JobTriggerResponse {
  success: boolean;
  message: string;
  job_id: string | null;
}

export interface AlertTestResponse {
  ok: boolean;
  message: string;
  channel_id: string | null;
  error: string | null;
}

export interface CustomNotificationRequest {
  slack_user_id: string;
  message: string;
  unfurl_links?: boolean;
}

export interface CustomNotificationResponse {
  ok: boolean;
  message: string;
  error: string | null;
}
