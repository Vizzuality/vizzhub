import api from '@/core/services/client';
import type {
  AccrualAlias,
  AccrualAliasBulkCreate,
  AccrualAliasCreate,
  AccrualCell,
  AccrualExcelRowsResponse,
  AccrualGridFilters,
  AccrualGridResponse,
  AccrualImportRun,
  AccrualPeriod,
  AccrualPeriodCreate,
  BulkCellUpdate,
  DriftFinding,
  DriftFindingsResponse,
  DriftSummaryResponse,
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
    listByProject: async (projectId: string): Promise<AccrualCell[]> => {
      const r = await api.get<AccrualCell[]>(`/accrual/projects/${projectId}/cells`);
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
  drift: {
    list: async (params: {
      kind?: string[];
      resolved?: boolean;
      project_id?: string;
      excel_code?: string;
      limit?: number;
      offset?: number;
    } = {}): Promise<DriftFindingsResponse> => {
      // FastAPI expects repeated `?kind=a&kind=b` for list query params; axios's
      // default array serialization uses `kind[]=...` which FastAPI ignores.
      // Build a URLSearchParams manually to keep the wire format flat.
      const search = new URLSearchParams();
      params.kind?.forEach((k) => search.append('kind', k));
      if (params.resolved !== undefined) search.append('resolved', String(params.resolved));
      if (params.project_id) search.append('project_id', params.project_id);
      if (params.excel_code) search.append('excel_code', params.excel_code);
      if (params.limit !== undefined) search.append('limit', String(params.limit));
      if (params.offset !== undefined) search.append('offset', String(params.offset));
      const r = await api.get<DriftFindingsResponse>('/accrual/drift', { params: search });
      return r.data;
    },
    summary: async (): Promise<DriftSummaryResponse> => {
      const r = await api.get<DriftSummaryResponse>('/accrual/drift/summary');
      return r.data;
    },
    resolve: async (id: string, resolution: string): Promise<DriftFinding> => {
      const r = await api.post<DriftFinding>(`/accrual/drift/${id}/resolve`, { resolution });
      return r.data;
    },
    reopen: async (id: string): Promise<DriftFinding> => {
      const r = await api.post<DriftFinding>(`/accrual/drift/${id}/reopen`);
      return r.data;
    },
  },
  aliases: {
    list: async (params: { excel_code?: string; project_id?: string } = {}): Promise<AccrualAlias[]> => {
      const r = await api.get<AccrualAlias[]>('/accrual/aliases', { params });
      return r.data;
    },
    create: async (payload: AccrualAliasCreate): Promise<AccrualAlias> => {
      const r = await api.post<AccrualAlias>('/accrual/aliases', payload);
      return r.data;
    },
    bulkCreate: async (payload: AccrualAliasBulkCreate): Promise<AccrualAlias[]> => {
      const r = await api.post<AccrualAlias[]>('/accrual/aliases/bulk', payload);
      return r.data;
    },
    update: async (id: string, payload: { weight?: string; notes?: string }): Promise<AccrualAlias> => {
      const r = await api.patch<AccrualAlias>(`/accrual/aliases/${id}`, payload);
      return r.data;
    },
    remove: async (id: string): Promise<void> => {
      await api.delete(`/accrual/aliases/${id}`);
    },
  },
  excelRows: {
    list: async (params: {
      import_run_id?: string;
      excel_code?: string;
      unmatched_only?: boolean;
      limit?: number;
      offset?: number;
    } = {}): Promise<AccrualExcelRowsResponse> => {
      const r = await api.get<AccrualExcelRowsResponse>('/accrual/excel-rows', { params });
      return r.data;
    },
    runs: async (limit = 20): Promise<AccrualImportRun[]> => {
      const r = await api.get<AccrualImportRun[]>('/accrual/excel-rows/runs', { params: { limit } });
      return r.data;
    },
  },
};
