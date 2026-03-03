import type {
  AlertDefinition,
  AlertDefinitionUpdate,
  AlertSilence,
  AlertSilenceCreate,
  AlertSilenceUpdate,
  AlertTestResponse,
  JobTriggerResponse,
  MessageTemplate,
  MessageTemplateUpdate,
  NotificationFilters,
  NotificationStats,
  PaginatedNotifications,
  ScheduledJobInfo,
} from '@/types';
import api from './client';

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
