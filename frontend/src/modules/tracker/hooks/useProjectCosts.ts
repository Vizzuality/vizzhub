import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';

export function useProjectCostSummary(projectId: string) {
  return useQuery({
    queryKey: queryKeys.tracker.projectCosts.summary(projectId),
    queryFn: () => trackerApi.getProjectCostSummary(projectId),
    enabled: !!projectId,
  });
}

export function useProjectReportParts(projectId: string, periodId?: string) {
  return useQuery({
    queryKey: queryKeys.tracker.projectCosts.parts(projectId, periodId),
    queryFn: () => trackerApi.getProjectReportParts(projectId, periodId),
    enabled: !!projectId,
  });
}

export function useProjectAggregations(projectId: string, groupBy: string) {
  return useQuery({
    queryKey: queryKeys.tracker.projectCosts.aggregations(projectId, groupBy),
    queryFn: () => trackerApi.getProjectAggregations(projectId, groupBy),
    enabled: !!projectId,
  });
}
