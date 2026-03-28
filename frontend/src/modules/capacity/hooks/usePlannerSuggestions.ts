import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { PlannerSuggestionsResponse } from '@/modules/capacity/types/planner';

export function usePlannerSuggestions(
  month: string,
): UseQueryResult<PlannerSuggestionsResponse> {
  return useQuery({
    queryKey: queryKeys.capacity.plannerSuggestions(month),
    queryFn: () => capacityApi.getPlannerSuggestions(month),
    enabled: !!month,
  });
}
