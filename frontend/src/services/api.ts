import axios from 'axios';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ScoreResponse,
  ScoringConfig,
  MetricsCreate,
} from '../types';

const TOKEN_STORAGE_KEY = 'auth_token';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor: Add JWT token to Authorization header
 *
 * IMPORTANT: Development mode - backend bypasses auth
 * Token is only added if it exists in localStorage
 * Production: All protected routes will require valid JWT
 */
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

/**
 * Response interceptor: Handle authentication errors
 *
 * On 401 Unauthorized:
 * - Clear stored token
 * - Redirect to login page
 * - User must re-authenticate via Google OAuth
 */
api.interceptors.response.use(
  (response) => {
    return response;
  },
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

  validate: async (): Promise<{ valid: boolean; groups: Record<string, boolean> }> => {
    const response = await api.get<{ valid: boolean; groups: Record<string, boolean> }>(
      '/config/validate',
    );
    return response.data;
  },
};

export const collectApi = {
  collectJiraMetrics: async (projectId: string): Promise<MetricsCreate> => {
    const response = await api.post<MetricsCreate>(`/collect/project/${projectId}/jira`);
    return response.data;
  },
};

export default api;
