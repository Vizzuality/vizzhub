import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { ReportableUser } from '@/modules/capacity/types/capacity';

export function useReportableUsers(): UseQueryResult<ReportableUser[]> {
  return useQuery({
    queryKey: queryKeys.capacity.reportableUsers,
    queryFn: capacityApi.getReportableUsers,
  });
}
