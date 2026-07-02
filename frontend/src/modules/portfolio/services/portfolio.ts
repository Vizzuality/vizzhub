import api from '@/core/services/client';
import type {
  Client,
  ClientCreate,
  ClientLeaderboard,
  ClientListParams,
  ClientListResponse,
  ClientOption,
  ClientUpdate,
  MergeRequest,
  MergeResponse,
  ProjectLeaderboard,
  Taxonomy,
} from '../types/portfolio';

export const portfolioApi = {
  listClients: async (params: ClientListParams = {}): Promise<ClientListResponse> => {
    const response = await api.get<ClientListResponse>('/clients', { params });
    return response.data;
  },

  listClientOptions: async (): Promise<ClientOption[]> => {
    const response = await api.get<ClientOption[]>('/clients/options');
    return response.data;
  },

  createClient: async (data: ClientCreate): Promise<Client> => {
    const response = await api.post<Client>('/clients', data);
    return response.data;
  },

  updateClient: async (id: string, data: ClientUpdate): Promise<Client> => {
    const response = await api.patch<Client>(`/clients/${id}`, data);
    return response.data;
  },

  mergeClients: async (targetId: string, data: MergeRequest): Promise<MergeResponse> => {
    const response = await api.post<MergeResponse>(`/clients/${targetId}/merge`, data);
    return response.data;
  },

  listTaxonomies: async (): Promise<Taxonomy[]> => {
    const response = await api.get<Taxonomy[]>('/taxonomies');
    return response.data;
  },

  dashboard: {
    projects: async (year?: number): Promise<ProjectLeaderboard> => {
      const response = await api.get<ProjectLeaderboard>('/portfolio/dashboard/projects', {
        params: year ? { year } : {},
      });
      return response.data;
    },
    clients: async (year?: number): Promise<ClientLeaderboard> => {
      const response = await api.get<ClientLeaderboard>('/portfolio/dashboard/clients', {
        params: year ? { year } : {},
      });
      return response.data;
    },
  },
};
