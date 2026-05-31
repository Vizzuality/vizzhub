import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import type { AccrualDashboardSummary } from '@/modules/accrual/types/accrual';

export function useAccrualDashboard(year: number): UseQueryResult<AccrualDashboardSummary> {
  return useQuery({
    queryKey: queryKeys.accrual.dashboard.monthly({ year }),
    queryFn: () => accrualApi.dashboard.summary(year),
    staleTime: 60_000,
  });
}
