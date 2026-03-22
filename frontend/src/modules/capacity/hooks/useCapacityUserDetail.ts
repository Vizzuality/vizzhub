import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { PeriodProjectInsight } from '@/modules/capacity/types/capacity';

export function useCapacityUserDetail(
  userId: string,
  startDate: string,
  endDate: string,
): UseQueryResult<PeriodProjectInsight[]> {
  return useQuery({
    queryKey: queryKeys.capacity.userDetail(userId, startDate, endDate),
    queryFn: () => capacityApi.getUserDetail(userId, startDate, endDate),
    enabled: !!userId && !!startDate && !!endDate,
  });
}
