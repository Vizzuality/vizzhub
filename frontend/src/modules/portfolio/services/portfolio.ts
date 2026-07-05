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
  OverviewApplyResult,
  OverviewCurrentBatch,
  OverviewDecisionPatch,
  OverviewImportProject,
  OverviewMatch,
  OverviewUploadResult,
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

  import: {
    upload: async (file: File): Promise<OverviewUploadResult> => {
      const form = new FormData();
      form.append('file', file);
      // axios sets a global application/json Content-Type; undefined lets the
      // browser attach the multipart boundary. (Codebase gotcha.)
      const response = await api.post<OverviewUploadResult>('/portfolio/import/upload', form, {
        headers: { 'Content-Type': undefined },
      });
      return response.data;
    },
    current: async (): Promise<OverviewCurrentBatch | null> => {
      const response = await api.get<OverviewCurrentBatch | null>('/portfolio/import/current');
      return response.data;
    },
    projects: async (): Promise<OverviewImportProject[]> => {
      const response = await api.get<OverviewImportProject[]>('/portfolio/import/projects');
      return response.data;
    },
    matches: async (batchId: string): Promise<OverviewMatch[]> => {
      const response = await api.get<OverviewMatch[]>(`/portfolio/import/${batchId}/matches`);
      return response.data;
    },
    saveDecision: async (
      batchId: string,
      stagingId: string,
      patch: OverviewDecisionPatch,
    ): Promise<void> => {
      await api.patch(`/portfolio/import/${batchId}/decisions/${stagingId}`, patch);
    },
    apply: async (batchId: string): Promise<OverviewApplyResult> => {
      const response = await api.post<OverviewApplyResult>(`/portfolio/import/${batchId}/apply`);
      return response.data;
    },
  },
};
