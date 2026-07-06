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
  ProgramIndexFilters,
  ProgramIndexResponse,
  ProgramOption,
  ProgramProfile,
  ProgramProfileUpdate,
  ProgramSummary,
  ProgramTermsUpdate,
  ProjectLeaderboard,
  Taxonomy,
  TermChip,
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

  programs: {
    index: async (filters: ProgramIndexFilters = {}): Promise<ProgramIndexResponse> => {
      const params = new URLSearchParams();
      if (filters.search) params.set('search', filters.search);
      if (filters.client_id) params.set('client_id', filters.client_id);
      for (const id of filters.term_ids ?? []) params.append('term_ids', id);
      const response = await api.get<ProgramIndexResponse>('/portfolio/programs', { params });
      return response.data;
    },

    detail: async (id: string): Promise<ProgramSummary> => {
      const response = await api.get<ProgramSummary>(`/portfolio/programs/${id}`);
      return response.data;
    },

    updateProfile: async (id: string, data: ProgramProfileUpdate): Promise<ProgramProfile> => {
      const response = await api.patch<ProgramProfile>(`/portfolio/programs/${id}/profile`, data);
      return response.data;
    },

    replaceTerms: async (id: string, data: ProgramTermsUpdate): Promise<TermChip[]> => {
      const response = await api.put<TermChip[]>(`/portfolio/programs/${id}/terms`, data);
      return response.data;
    },

    options: async (): Promise<ProgramOption[]> => {
      const response = await api.get<ProgramOption[]>('/programs');
      return response.data;
    },

    create: async (name: string): Promise<ProgramOption> => {
      const response = await api.post<ProgramOption>('/programs', { name });
      return response.data;
    },

    rename: async (id: string, name: string): Promise<ProgramOption> => {
      const response = await api.patch<ProgramOption>(`/programs/${id}`, { name });
      return response.data;
    },
  },
};
