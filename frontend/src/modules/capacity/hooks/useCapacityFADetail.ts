import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { PeriodUserInsight } from '@/modules/capacity/types/capacity';

export function useCapacityFADetail(
  fa: string,
  startDate: string,
  endDate: string,
): UseQueryResult<PeriodUserInsight[]> {
  return useQuery({
    queryKey: queryKeys.capacity.faDetail(fa, startDate, endDate),
    queryFn: () => capacityApi.getInsightsDetail(fa, startDate, endDate),
    enabled: !!fa && !!startDate && !!endDate,
  });
}
