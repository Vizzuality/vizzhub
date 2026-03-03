import type {
  AvailableMonth,
  CalculateBatchRequest,
  CalculateBatchResponse,
  GlobalMetricsHistoryResponse,
  GlobalMetricsRecord,
} from '../../types';
import api from '@/core/services/client';

export const globalMetricsApi = {
  getRecord: async (
    year: number,
    month: number,
  ): Promise<GlobalMetricsRecord | null> => {
    const response = await api.get<GlobalMetricsRecord | null>(
      `/global/${year}/${month}`,
    );
    return response.data;
  },

  getHistory: async (
    limit = 12,
  ): Promise<GlobalMetricsRecord[]> => {
    const response = await api.get<GlobalMetricsHistoryResponse>(
      '/global/history',
      { params: { limit } },
    );
    return response.data.records;
  },

  getAvailableMonths: async (): Promise<AvailableMonth[]> => {
    const response = await api.get<AvailableMonth[]>(
      '/global/available-months',
    );
    return response.data;
  },

  calculate: async (
    request: CalculateBatchRequest,
  ): Promise<CalculateBatchResponse> => {
    const response = await api.post<CalculateBatchResponse>(
      '/global/calculate',
      request,
    );
    return response.data;
  },

  recalculate: async (
    request: CalculateBatchRequest,
  ): Promise<CalculateBatchResponse> => {
    const response = await api.post<CalculateBatchResponse>(
      '/global/recalculate',
      request,
    );
    return response.data;
  },
};
