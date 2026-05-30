import api from '@/core/services/client';
import type {
  AccrualCell,
  AccrualGridFilters,
  AccrualGridResponse,
  AccrualLineCreate,
  AccrualLineDetail,
  AccrualLineUpdate,
  AccrualPeriod,
  AccrualPeriodCreate,
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
  },
  cells: {
    grid: async (filters: AccrualGridFilters): Promise<AccrualGridResponse> => {
      const params: Record<string, unknown> = { year_from: filters.year_from, year_to: filters.year_to };
      if (filters.status !== undefined) params.status = filters.status;
      if (filters.currency !== undefined) params.currency = filters.currency;
      if (filters.project_manager_id !== undefined) params.project_manager_id = filters.project_manager_id;
      if (filters.source !== undefined) params.source = filters.source;
      const r = await api.get<AccrualGridResponse>('/accrual/grid', { params });
      return r.data;
    },
    patch: async (cellId: string, amount: string): Promise<AccrualCell> => {
      const r = await api.patch<AccrualCell>(`/accrual/cells/${cellId}`, { amount });
      return r.data;
    },
    upsertOnLine: async (
      lineId: string,
      year: number,
      month: number,
      amount: string,
    ): Promise<AccrualCell> => {
      const r = await api.put<AccrualCell>(`/accrual/lines/${lineId}/cells`, {
        year,
        month,
        amount,
      });
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
  lines: {
    get: async (lineId: string): Promise<AccrualLineDetail> => {
      const r = await api.get<AccrualLineDetail>(`/accrual/lines/${lineId}`);
      return r.data;
    },
    create: async (payload: AccrualLineCreate): Promise<AccrualLineDetail> => {
      const r = await api.post<AccrualLineDetail>('/accrual/lines', payload);
      return r.data;
    },
    update: async (lineId: string, payload: AccrualLineUpdate): Promise<AccrualLineDetail> => {
      const r = await api.patch<AccrualLineDetail>(`/accrual/lines/${lineId}`, payload);
      return r.data;
    },
    remove: async (lineId: string): Promise<void> => {
      await api.delete(`/accrual/lines/${lineId}`);
    },
    linkProject: async (lineId: string, projectId: string): Promise<AccrualLineDetail> => {
      const r = await api.post<AccrualLineDetail>(`/accrual/lines/${lineId}/projects`, {
        project_id: projectId,
      });
      return r.data;
    },
    unlinkProject: async (lineId: string, projectId: string): Promise<AccrualLineDetail> => {
      const r = await api.delete<AccrualLineDetail>(
        `/accrual/lines/${lineId}/projects/${projectId}`,
      );
      return r.data;
    },
    redistribute: async (
      lineId: string,
      force = false,
    ): Promise<{ cells_updated: number }> => {
      const r = await api.post<{ cells_updated: number }>(
        `/accrual/lines/${lineId}/redistribute`,
        { force },
      );
      return r.data;
    },
  },
};
