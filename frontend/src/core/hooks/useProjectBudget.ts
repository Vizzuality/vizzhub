import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/core/services/projects';
import { queryKeys } from '@/core/hooks/queryKeys';

interface BudgetPayload {
  milestones?: Array<{
    name: string;
    planned_date: string;
    actual_date?: string;
  }>;
}

export function useCurrentPeriodMetrics(projectId: string) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  return useQuery({
    queryKey: queryKeys.metrics.byPeriod(projectId, year, month),
    queryFn: async () => {
      try {
        const { metricsHistoryApi } = await import(
          '@/modules/scorecard/services/metrics'
        );
        return await metricsHistoryApi.getByPeriod(projectId, year, month);
      } catch {
        return null;
      }
    },
    enabled: !!projectId,
  });
}

export function useUpdateProjectBudget(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BudgetPayload) => projectsApi.updateBudget(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.metrics.byProject(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.scores.byProject(projectId),
      });
    },
  });
}
