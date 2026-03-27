import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { AllocationUsersResponse } from '@/modules/capacity/types/allocation';

export function useAllocationUsers(): UseQueryResult<AllocationUsersResponse> {
  return useQuery({
    queryKey: queryKeys.capacity.allocationUsers,
    queryFn: () => capacityApi.getAllocationUsers(),
  });
}
