import api from '@/core/services/client';
import type {
  DevstackEntry,
  DevstackEntryCreate,
  DevstackEntryListParams,
  DevstackEntryListResponse,
  DevstackEntryUpdate,
} from '../types/devstack';

export const devstackApi = {
  list: async (params: DevstackEntryListParams = {}): Promise<DevstackEntryListResponse> => {
    const response = await api.get<DevstackEntryListResponse>('/devstack', { params });
    return response.data;
  },

  get: async (id: string): Promise<DevstackEntry> => {
    const response = await api.get<DevstackEntry>(`/devstack/${id}`);
    return response.data;
  },

  create: async (data: DevstackEntryCreate): Promise<DevstackEntry> => {
    const response = await api.post<DevstackEntry>('/devstack', data);
    return response.data;
  },

  update: async (id: string, data: DevstackEntryUpdate): Promise<DevstackEntry> => {
    const response = await api.put<DevstackEntry>(`/devstack/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/devstack/${id}`);
  },

};
