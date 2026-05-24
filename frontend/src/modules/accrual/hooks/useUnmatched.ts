import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import type {
  AccrualAlias,
  AccrualAliasBulkCreate,
  AccrualAliasCreate,
  AccrualExcelRowsResponse,
  DriftFinding,
  DriftFindingsResponse,
  DriftSummaryResponse,
} from '@/modules/accrual/types/accrual';

export interface UseDriftFiltersOptions {
  readonly kind?: string[];
  readonly resolved?: boolean;
  readonly project_id?: string;
  readonly excel_code?: string;
  readonly limit?: number;
  readonly offset?: number;
}

export function useDriftFindings(filters: UseDriftFiltersOptions = {}) {
  return useQuery<DriftFindingsResponse>({
    queryKey: queryKeys.accrual.drift.list(filters as Record<string, unknown>),
    queryFn: () => accrualApi.drift.list(filters),
    staleTime: 30_000,
  });
}

export function useDriftSummary() {
  return useQuery<DriftSummaryResponse>({
    queryKey: queryKeys.accrual.drift.summary(),
    queryFn: () => accrualApi.drift.summary(),
    staleTime: 30_000,
  });
}

export function useResolveDrift() {
  const qc = useQueryClient();
  return useMutation<DriftFinding, Error, { id: string; resolution: string }>({
    mutationFn: ({ id, resolution }) => accrualApi.drift.resolve(id, resolution),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.drift.all });
    },
  });
}

export function useReopenDrift() {
  const qc = useQueryClient();
  return useMutation<DriftFinding, Error, string>({
    mutationFn: (id) => accrualApi.drift.reopen(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.drift.all });
    },
  });
}

export function useUnmatchedExcelRows(params: { excel_code?: string } = {}) {
  const filters = { ...params, unmatched_only: true };
  return useQuery<AccrualExcelRowsResponse>({
    queryKey: queryKeys.accrual.excelRows.list(filters as Record<string, unknown>),
    queryFn: () => accrualApi.excelRows.list(filters),
    staleTime: 30_000,
  });
}

export function useAliases(filters: { excel_code?: string; project_id?: string } = {}) {
  return useQuery<AccrualAlias[]>({
    queryKey: queryKeys.accrual.aliases.list(filters as Record<string, unknown>),
    queryFn: () => accrualApi.aliases.list(filters),
    staleTime: 30_000,
  });
}

export function useCreateAlias() {
  const qc = useQueryClient();
  return useMutation<AccrualAlias, Error, AccrualAliasCreate>({
    mutationFn: (payload) => accrualApi.aliases.create(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.aliases.all });
      // New alias may resolve a missing_tracker finding next run, so the
      // unmatched-rows view shouldn't claim it anymore even before re-import.
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.excelRows.all });
    },
  });
}

export function useBulkCreateAliases() {
  const qc = useQueryClient();
  return useMutation<AccrualAlias[], Error, AccrualAliasBulkCreate>({
    mutationFn: (payload) => accrualApi.aliases.bulkCreate(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.aliases.all });
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.excelRows.all });
    },
  });
}

export function useDeleteAlias() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => accrualApi.aliases.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.accrual.aliases.all });
    },
  });
}
