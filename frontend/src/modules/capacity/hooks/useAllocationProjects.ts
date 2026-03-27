import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { AllocationProjectsResponse } from '@/modules/capacity/types/allocation';

export function useAllocationProjects(
  startDate?: string,
  endDate?: string,
): UseQueryResult<AllocationProjectsResponse> {
  return useQuery({
    queryKey: queryKeys.capacity.allocationProjects(startDate, endDate),
    queryFn: () => capacityApi.getAllocationProjects(startDate, endDate),
  });
}
