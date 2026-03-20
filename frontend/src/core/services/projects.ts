import type {
  PaginatedProjects,
  Project,
  ProjectCreate,
  ProjectListParams,
  ProjectSummary,
  ProjectUpdate,
} from '@/types';
import api from './client';

export const projectsApi = {
  list: async (params: ProjectListParams = {}): Promise<PaginatedProjects> => {
    const response = await api.get<PaginatedProjects>('/projects', { params });
    return response.data;
  },

  listScorecard: async (params: ProjectListParams = {}): Promise<PaginatedProjects> => {
    const response = await api.get<PaginatedProjects>('/projects', {
      params: { ...params, has_scorecard: true },
    });
    return response.data;
  },

  listScorecardSummary: async (): Promise<ProjectSummary[]> => {
    const response = await api.get<ProjectSummary[]>('/projects', {
      params: { lightweight: true, has_scorecard: true },
    });
    return response.data;
  },

  listAllSummary: async (): Promise<ProjectSummary[]> => {
    const response = await api.get<ProjectSummary[]>('/projects', {
      params: { lightweight: true },
    });
    return response.data;
  },

  listActiveSummary: async (): Promise<ProjectSummary[]> => {
    const response = await api.get<ProjectSummary[]>('/projects', {
      params: { lightweight: true, status: 'live' },
    });
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

  replace: async (id: string, data: ProjectCreate): Promise<Project> => {
    const response = await api.put<Project>(`/projects/${id}`, data);
    return response.data;
  },

  update: async (id: string, data: ProjectUpdate): Promise<Project> => {
    const response = await api.patch<Project>(`/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`);
  },

  updateBudget: async (projectId: string, data: {
    milestones?: Array<{
      name: string;
      planned_date: string;
      actual_date?: string;
    }>;
  }): Promise<{
    period_year: number;
    period_month: number;
    milestones: Array<{
      name: string;
      planned_date: string;
      actual_date?: string;
    }>;
  }> => {
    const response = await api.put(`/projects/${projectId}/budget`, data);
    return response.data;
  },

  getLinks: async (projectId: string): Promise<Array<{
    id: string;
    title: string | null;
    url: string | null;
    link_type: string | null;
  }>> => {
    const response = await api.get(`/projects/${projectId}/links`);
    return response.data;
  },

  replaceLinks: async (projectId: string, links: Array<{
    title?: string;
    url?: string;
    link_type?: string;
  }>): Promise<Array<{
    id: string;
    title: string | null;
    url: string | null;
    link_type: string | null;
  }>> => {
    const response = await api.put(`/projects/${projectId}/links`, links);
    return response.data;
  },
};
