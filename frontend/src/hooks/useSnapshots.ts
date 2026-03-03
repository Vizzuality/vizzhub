import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { metricsHistoryApi } from '../services/api';
import { queryKeys } from '@/core/hooks/queryKeys';
import type { SnapshotType } from '../types';

export function useProjectMetricsHistory(
  projectId: string,
  limit = 12,
  snapshotType?: SnapshotType,
) {
  return useQuery({
    queryKey: queryKeys.snapshots.history(projectId, limit),
    queryFn: () => metricsHistoryApi.getProjectHistory(projectId, limit, snapshotType),
    enabled: !!projectId,
  });
}

// Alias for backward compatibility
export const useProjectSnapshots = useProjectMetricsHistory;

export function useMetricsByPeriod(
  projectId: string,
  year: number,
  month: number,
  snapshotType?: SnapshotType,
) {
  return useQuery({
    queryKey: queryKeys.snapshots.detail(projectId, year, month),
    queryFn: () => metricsHistoryApi.getByPeriod(projectId, year, month, snapshotType),
    enabled: !!projectId && !!year && !!month,
  });
}

export function useDeleteMetrics(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (metricsId: string) => metricsHistoryApi.deleteMetrics(metricsId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.snapshots.byProject(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.metrics.byProject(projectId),
      });
    },
  });
}

