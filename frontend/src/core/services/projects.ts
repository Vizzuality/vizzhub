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
    const response = await api.get<PaginatedProjects>('/scorecards', { params });
    return response.data;
  },

  listSummary: async (): Promise<ProjectSummary[]> => {
    const response = await api.get<ProjectSummary[]>('/scorecards', {
      params: { lightweight: true },
    });
    return response.data;
  },

  get: async (id: string): Promise<Project> => {
    const response = await api.get<Project>(`/scorecards/${id}`);
    return response.data;
  },

  create: async (data: ProjectCreate): Promise<Project> => {
    const response = await api.post<Project>('/scorecards', data);
    return response.data;
  },

  update: async (id: string, data: ProjectUpdate): Promise<Project> => {
    const response = await api.patch<Project>(`/scorecards/${id}`, data);
    return response.data;
  },

  replace: async (id: string, data: ProjectCreate): Promise<Project> => {
    const response = await api.put<Project>(`/scorecards/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/scorecards/${id}`);
  },
};
