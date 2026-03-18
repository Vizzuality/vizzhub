import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { trackerApi } from '../services/tracker';
import { queryKeys } from '@/core/hooks/queryKeys';
import { TIMING } from '@/shared/constants/timing';
import type { Project } from '@/core/types/project';
import type { ProjectCostSummaryLite } from '../types/tracker';

export interface UseProjectCostsMapReturn {
  costsMap: Record<string, ProjectCostSummaryLite | null>;
  isLoading: boolean;
}

export function useProjectCostsMap(
  projects: Project[] | undefined,
): UseProjectCostsMapReturn {
  const projectIds = useMemo(
    () => (projects ?? []).map((p) => p.id),
    [projects],
  );

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.tracker.costs.batch(projectIds),
    queryFn: () => trackerApi.getBatchCosts(projectIds),
    staleTime: TIMING.QUERY_STALE_TIME,
    enabled: projectIds.length > 0,
  });

  const costsMap = useMemo(() => {
    const map: Record<string, ProjectCostSummaryLite | null> = {};
    for (const id of projectIds) {
      map[id] = data?.costs[id] ?? null;
    }
    return map;
  }, [projectIds, data]);

  return { costsMap, isLoading };
}
