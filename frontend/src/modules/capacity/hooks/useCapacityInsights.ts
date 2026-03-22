import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';

export function useCapacityInsights(
  startDate: string,
  endDate: string,
): UseQueryResult<PeriodInsight[]> {
  return useQuery({
    queryKey: queryKeys.capacity.insights(startDate, endDate),
    queryFn: () => capacityApi.getInsights(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });
}
