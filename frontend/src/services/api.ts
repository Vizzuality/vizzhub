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
      window.location.href = '/login';
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
  getProjectScores: async (projectId: string): Promise<ScoreResponse> => {
    const response = await api.get<ScoreResponse>(`/scores/project/${projectId}`);
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
};

export default api;
