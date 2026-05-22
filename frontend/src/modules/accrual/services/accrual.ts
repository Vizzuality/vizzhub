import api from '@/core/services/client';
import type {
  AccrualCell,
  AccrualGridFilters,
  AccrualGridResponse,
  AccrualPeriod,
  AccrualPeriodCreate,
  AccrualPeriodUpdate,
  BulkCellUpdate,
} from '@/modules/accrual/types/accrual';

export const accrualApi = {
  periods: {
    list: async (): Promise<AccrualPeriod[]> => {
      const r = await api.get<AccrualPeriod[]>('/accrual/periods');
      return r.data;
    },
    current: async (): Promise<AccrualPeriod | null> => {
      const r = await api.get<AccrualPeriod | null>('/accrual/periods/current');
      return r.data;
    },
    create: async (payload: AccrualPeriodCreate): Promise<AccrualPeriod> => {
      const r = await api.post<AccrualPeriod>('/accrual/periods', payload);
      return r.data;
    },
    patch: async (id: string, payload: AccrualPeriodUpdate): Promise<AccrualPeriod> => {
      const r = await api.patch<AccrualPeriod>(`/accrual/periods/${id}`, payload);
      return r.data;
    },
    seedRates: async (): Promise<Record<string, string>> => {
      const r = await api.get<Record<string, string>>('/accrual/periods/seed-rates');
      return r.data;
    },
  },
  cells: {
    grid: async (filters: AccrualGridFilters): Promise<AccrualGridResponse> => {
      const params: Record<string, unknown> = { year_from: filters.year_from, year_to: filters.year_to };
      if (filters.status !== undefined) params.status = filters.status;
      if (filters.currency !== undefined) params.currency = filters.currency;
      if (filters.project_manager_id !== undefined) params.project_manager_id = filters.project_manager_id;
      const r = await api.get<AccrualGridResponse>('/accrual/grid', { params });
      return r.data;
    },
    listByProject: async (projectId: string): Promise<AccrualCell[]> => {
      const r = await api.get<AccrualCell[]>(`/accrual/projects/${projectId}/cells`);
      return r.data;
    },
    redistribute: async (
      projectId: string,
      force = false,
    ): Promise<{ cells_updated: number }> => {
      const r = await api.post<{ cells_updated: number }>(
        `/accrual/projects/${projectId}/redistribute`,
        { force },
      );
      return r.data;
    },
    patch: async (cellId: string, amount: string): Promise<AccrualCell> => {
      const r = await api.patch<AccrualCell>(`/accrual/cells/${cellId}`, { amount });
      return r.data;
    },
    clearOverride: async (cellId: string): Promise<AccrualCell> => {
      const r = await api.delete<AccrualCell>(`/accrual/cells/${cellId}/override`);
      return r.data;
    },
    bulk: async (updates: BulkCellUpdate[]): Promise<{ updated: number }> => {
      const r = await api.post<{ updated: number }>('/accrual/cells/bulk', { updates });
      return r.data;
    },
  },
};
