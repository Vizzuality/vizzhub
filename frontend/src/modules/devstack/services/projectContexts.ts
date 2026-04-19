import api from '@/core/services/client';
import type {
  ProjectContext,
  ProjectContextCreate,
  ProjectContextUpdate,
} from '../types/projectContexts';

export const projectContextsApi = {
  list: async (): Promise<ProjectContext[]> => {
    const response = await api.get<ProjectContext[]>(
      '/devstack/project-contexts',
    );
    return response.data;
  },

  get: async (id: string): Promise<ProjectContext> => {
    const response = await api.get<ProjectContext>(
      `/devstack/project-contexts/${id}`,
    );
    return response.data;
  },

  create: async (data: ProjectContextCreate): Promise<ProjectContext> => {
    const response = await api.post<ProjectContext>(
      '/devstack/project-contexts',
      data,
    );
    return response.data;
  },

  update: async (
    id: string,
    data: ProjectContextUpdate,
  ): Promise<ProjectContext> => {
    const response = await api.put<ProjectContext>(
      `/devstack/project-contexts/${id}`,
      data,
    );
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/devstack/project-contexts/${id}`);
  },
};
