import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import type { AccrualGridFilters, AccrualGridResponse } from '@/modules/accrual/types/accrual';

export function useAccrualGrid(filters: AccrualGridFilters) {
  return useQuery<AccrualGridResponse>({
    queryKey: queryKeys.accrual.cells.grid(filters as unknown as Record<string, unknown>),
    queryFn: () => accrualApi.cells.grid(filters),
    staleTime: 30_000,
  });
}
