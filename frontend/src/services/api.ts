import axios from 'axios';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ScoreResponse,
  ScoringConfig,
  MetricsCreate,
  MetricsWithScores,
  CapturePeriodRequest,
  CapturePeriodResponse,
  CaptureHistoryRequest,
  CaptureReport,
  SnapshotType,
  JobResponse,
  JobDetailResponse,
  JobSummaryResponse,
  CreateCaptureHistoryJobRequest,
  SlackChannel,
  AlertDefinition,
  AlertDefinitionUpdate,
  AlertTestResponse,
  MessageTemplate,
  MessageTemplateUpdate,
  AlertSilence,
  AlertSilenceCreate,
  AlertSilenceUpdate,
  PaginatedNotifications,
  NotificationFilters,
  NotificationStats,
  ScheduledJobInfo,
  JobTriggerResponse,
} from '../types';

const TOKEN_STORAGE_KEY = 'auth_token';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem('auth_user');
      globalThis.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export const projectsApi = {
  list: async (): Promise<Project[]> => {
    const response = await api.get<Project[]>('/projects');
    return response.data;
  },

  get: async (id: string): Promise<Project> => {
    const response = await api.get<Project>(`/projects/${id}`);
    return response.data;
  },

  create: async (data: ProjectCreate): Promise<Project> => {
    const response = await api.post<Project>('/projects', data);
    return response.data;
  },

  update: async (id: string, data: ProjectUpdate): Promise<Project> => {
    const response = await api.patch<Project>(`/projects/${id}`, data);
    return response.data;
  },

  replace: async (id: string, data: ProjectCreate): Promise<Project> => {
    const response = await api.put<Project>(`/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`);
  },
};

export const scoresApi = {
  getProjectScores: async (
    projectId: string,
    year?: number,
    month?: number,
  ): Promise<ScoreResponse> => {
    const params: Record<string, number> = {};
    if (year !== undefined) params.year = year;
    if (month !== undefined) params.month = month;

    const response = await api.get<ScoreResponse>(
      `/scores/project/${projectId}`,
      { params },
    );
    return response.data;
  },

  getScoreHistory: async (
    projectId: string,
    limit = 10,
  ): Promise<ScoreResponse[]> => {
    const response = await api.get<ScoreResponse[]>(
      `/scores/project/${projectId}/history`,
      { params: { limit } },
    );
    return response.data;
  },

  calculate: async (
    metrics: MetricsCreate,
    sev1Incident = false,
  ): Promise<ScoreResponse> => {
    const response = await api.post<ScoreResponse>('/scores/calculate', {
      metrics,
      sev1_incident: sev1Incident,
    });
    return response.data;
  },
};

export const configApi = {
  get: async (): Promise<ScoringConfig> => {
    const response = await api.get<ScoringConfig>('/config');
    return response.data;
  },

  validate: async (): Promise<{ valid: boolean; groups: Record<string, boolean>; errors?: string[] }> => {
    const response = await api.get<{ valid: boolean; groups: Record<string, boolean>; errors?: string[] }>(
      '/config/validate',
    );
    return response.data;
  },

  updateParameters: async (updates: Array<{ name: string; value: string }>): Promise<void> => {
    await api.patch('/config/parameters', { updates });
  },
};

export const collectApi = {
  collectJiraMetrics: async (projectId: string): Promise<MetricsCreate> => {
    const response = await api.post<MetricsCreate>(`/collect/project/${projectId}/jira`);
    return response.data;
  },

  collectGitHubMetrics: async (projectId: string): Promise<MetricsCreate> => {
    const response = await api.post<MetricsCreate>(
      `/collect/project/${projectId}/github`,
      {},
      { timeout: 60000 },
    );
    return response.data;
  },
};

export const metricsHistoryApi = {
  getProjectHistory: async (
    projectId: string,
    limit = 12,
    snapshotType?: SnapshotType,
  ): Promise<MetricsWithScores[]> => {
    const response = await api.get<MetricsWithScores[]>(
      `/metrics/project/${projectId}/history`,
      { params: { limit, snapshot_type: snapshotType } },
    );
    return response.data;
  },

  getByPeriod: async (
    projectId: string,
    year: number,
    month: number,
    snapshotType?: SnapshotType,
  ): Promise<MetricsWithScores> => {
    const response = await api.get<MetricsWithScores>(
      `/metrics/project/${projectId}/${year}/${month}`,
      { params: { snapshot_type: snapshotType } },
    );
    return response.data;
  },

  deleteMetrics: async (metricsId: string): Promise<void> => {
    await api.delete(`/metrics/${metricsId}`);
  },

  captureHistory: async (
    projectId: string,
    request: CaptureHistoryRequest,
  ): Promise<CaptureReport> => {
    const response = await api.post<CaptureReport>(
      `/projects/${projectId}/capture-history`,
      request,
    );
    return response.data;
  },
};

// Alias for backward compatibility
export const snapshotsApi = metricsHistoryApi;

export const captureApi = {
  capturePeriod: async (
    projectId: string,
    request: CapturePeriodRequest,
  ): Promise<CapturePeriodResponse> => {
    const response = await api.post<CapturePeriodResponse>(
      `/projects/${projectId}/capture-period`,
      request,
      { timeout: 120000 }, // 2 minute timeout for collector calls
    );
    return response.data;
  },
};

export const jobsApi = {
  createCaptureHistory: async (
    request: CreateCaptureHistoryJobRequest,
  ): Promise<JobResponse> => {
    const response = await api.post<JobResponse>('/jobs/capture-history', request);
    return response.data;
  },

  getJob: async (jobId: string): Promise<JobDetailResponse> => {
    const response = await api.get<JobDetailResponse>(`/jobs/${jobId}`);
    return response.data;
  },

  listJobs: async (projectId?: string): Promise<JobSummaryResponse[]> => {
    const params = projectId ? { project_id: projectId } : {};
    const response = await api.get<JobSummaryResponse[]>('/jobs', { params });
    return response.data;
  },

  cancelJob: async (jobId: string): Promise<JobResponse> => {
    const response = await api.post<JobResponse>(`/jobs/${jobId}/cancel`);
    return response.data;
  },

  retryJob: async (jobId: string): Promise<JobResponse> => {
    const response = await api.post<JobResponse>(`/jobs/${jobId}/retry`);
    return response.data;
  },

  deleteJob: async (jobId: string): Promise<void> => {
    await api.delete(`/jobs/${jobId}`);
  },
};

export const globalMetricsApi = {
  getRecord: async (
    year: number,
    month: number,
  ): Promise<import('../types/global').GlobalMetricsRecord | null> => {
    const response = await api.get<import('../types/global').GlobalMetricsRecord | null>(
      `/global/${year}/${month}`,
    );
    return response.data;
  },

  getHistory: async (
    limit = 12,
  ): Promise<import('../types/global').GlobalMetricsRecord[]> => {
    const response = await api.get<import('../types/global').GlobalMetricsHistoryResponse>(
      '/global/history',
      { params: { limit } },
    );
    return response.data.records;
  },

  getAvailableMonths: async (): Promise<import('../types/global').AvailableMonth[]> => {
    const response = await api.get<import('../types/global').AvailableMonth[]>(
      '/global/available-months',
    );
    return response.data;
  },

  calculate: async (
    request: import('../types/global').CalculateBatchRequest,
  ): Promise<import('../types/global').CalculateBatchResponse> => {
    const response = await api.post<import('../types/global').CalculateBatchResponse>(
      '/global/calculate',
      request,
    );
    return response.data;
  },

  recalculate: async (
    request: import('../types/global').CalculateBatchRequest,
  ): Promise<import('../types/global').CalculateBatchResponse> => {
    const response = await api.post<import('../types/global').CalculateBatchResponse>(
      '/global/recalculate',
      request,
    );
    return response.data;
  },
};

export interface SlackConfigResponse {
  id: number;
  bot_token_configured: boolean;
  leadership_channel_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SlackStatusResponse {
  configured: boolean;
}

export interface SlackTestResult {
  ok: boolean;
  team?: string;
  bot_id?: string;
  error?: string;
}

export const slackApi = {
  getStatus: async (): Promise<SlackStatusResponse> => {
    const response = await api.get<SlackConfigResponse>('/admin/slack/config');
    return {
      configured: response.data.bot_token_configured,
    };
  },

  getConfig: async (): Promise<SlackConfigResponse> => {
    const response = await api.get<SlackConfigResponse>('/admin/slack/config');
    return response.data;
  },

  updateConfig: async (data: {
    bot_token?: string;
    leadership_channel_id?: string;
  }): Promise<SlackConfigResponse> => {
    const response = await api.put<SlackConfigResponse>('/admin/slack/config', data);
    return response.data;
  },

  testConnection: async (): Promise<SlackTestResult> => {
    const response = await api.post<SlackTestResult>('/admin/slack/test');
    return response.data;
  },

  getChannels: async (): Promise<SlackChannel[]> => {
    const response = await api.get<SlackChannel[]>('/admin/slack/channels');
    return response.data;
  },
};

export const notificationsApi = {
  list: async (filters: NotificationFilters = {}): Promise<PaginatedNotifications> => {
    const params: Record<string, string | number> = {};
    if (filters.project_id) params.project_id = filters.project_id;
    if (filters.alert_definition_id) params.alert_definition_id = filters.alert_definition_id;
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;
    if (filters.page) params.page = filters.page;
    if (filters.page_size) params.page_size = filters.page_size;

    const response = await api.get<PaginatedNotifications>('/notifications', { params });
    return response.data;
  },

  getStats: async (): Promise<NotificationStats> => {
    const response = await api.get<NotificationStats>('/notifications/stats');
    return response.data;
  },
};

export const silencesApi = {
  list: async (projectId?: string, includeExpired = false): Promise<AlertSilence[]> => {
    const params: Record<string, string | boolean> = { include_expired: includeExpired };
    if (projectId) params.project_id = projectId;

    const response = await api.get<AlertSilence[]>('/silences', { params });
    return response.data;
  },

  create: async (data: AlertSilenceCreate): Promise<AlertSilence> => {
    const response = await api.post<AlertSilence>('/silences', data);
    return response.data;
  },

  update: async (id: number, data: AlertSilenceUpdate): Promise<AlertSilence> => {
    const response = await api.put<AlertSilence>(`/silences/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/silences/${id}`);
  },
};

export const alertsAdminApi = {
  list: async (): Promise<AlertDefinition[]> => {
    const response = await api.get<AlertDefinition[]>('/admin/alerts');
    return response.data;
  },

  update: async (id: number, data: AlertDefinitionUpdate): Promise<AlertDefinition> => {
    const response = await api.put<AlertDefinition>(`/admin/alerts/${id}`, data);
    return response.data;
  },

  test: async (id: number): Promise<AlertTestResponse> => {
    const response = await api.post<AlertTestResponse>(`/admin/alerts/${id}/test`);
    return response.data;
  },

  getTemplates: async (alertId: number): Promise<MessageTemplate[]> => {
    const response = await api.get<MessageTemplate[]>(`/admin/alerts/${alertId}/templates`);
    return response.data;
  },

  updateTemplate: async (templateId: number, data: MessageTemplateUpdate): Promise<MessageTemplate> => {
    const response = await api.put<MessageTemplate>(`/admin/templates/${templateId}`, data);
    return response.data;
  },
};

export const scheduledJobsApi = {
  list: async (): Promise<ScheduledJobInfo[]> => {
    const response = await api.get<ScheduledJobInfo[]>('/admin/jobs/scheduled');
    return response.data;
  },

  trigger: async (jobName: string): Promise<JobTriggerResponse> => {
    const response = await api.post<JobTriggerResponse>(`/admin/jobs/scheduled/${jobName}/run`);
    return response.data;
  },
};

export default api;
