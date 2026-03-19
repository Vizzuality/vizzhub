import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { trackerApi } from '../services/tracker';
import { queryKeys } from '@/core/hooks/queryKeys';
import { TIMING } from '@/shared/constants/timing';
import type { Project } from '@/core/types/project';
import type { ProgressSummary } from '../types/tracker';

export interface UseProjectProgressMapReturn {
  progressMap: Record<string, ProgressSummary | null>;
  isLoading: boolean;
}

export function useProjectProgressMap(
  projects: Project[] | undefined,
): UseProjectProgressMapReturn {
  const projectIds = useMemo(
    () => (projects ?? []).map((p) => p.id),
    [projects],
  );

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.tracker.progress.batch(projectIds),
    queryFn: () => trackerApi.getBatchProgress(projectIds),
    staleTime: TIMING.QUERY_STALE_TIME,
    enabled: projectIds.length > 0,
  });

  const progressMap = useMemo(() => {
    const map: Record<string, ProgressSummary | null> = {};
    for (const id of projectIds) {
      map[id] = data?.progress[id] ?? null;
    }
    return map;
  }, [projectIds, data]);

  return { progressMap, isLoading };
}
