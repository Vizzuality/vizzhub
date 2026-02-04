import type {
  CaptureHistoryRequest,
  CapturePeriodRequest,
  CapturePeriodResponse,
  CaptureReport,
  MetricsCreate,
  MetricsWithScores,
  SnapshotType,
} from '../../types';
import api from './client';

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

export const snapshotsApi = metricsHistoryApi;

export const captureApi = {
  capturePeriod: async (
    projectId: string,
    request: CapturePeriodRequest,
  ): Promise<CapturePeriodResponse> => {
    const response = await api.post<CapturePeriodResponse>(
      `/projects/${projectId}/capture-period`,
      request,
      { timeout: 120000 },
    );
    return response.data;
  },
};
