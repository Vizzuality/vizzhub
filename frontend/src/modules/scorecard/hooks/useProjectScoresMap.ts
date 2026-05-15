import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scoresApi } from '../services';
import { queryKeys } from '@/core/hooks/queryKeys';
import { TIMING } from '@/shared/constants/timing';
export interface UseProjectScoresMapReturn {
  scoresMap: Record<string, number | null>;
  // Period of the latest captured metrics per project ("YYYY-MM").
  // null when the project has no captured metrics yet.
  latestPeriodMap: Record<string, string | null>;
  isLoading: boolean;
}

export function useProjectScoresMap(
  projects: { id: string }[] | undefined,
): UseProjectScoresMapReturn {
  const projectIds = useMemo(
    () => (projects ?? []).map((p) => p.id),
    [projects],
  );

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.scores.batch(projectIds),
    queryFn: () => scoresApi.getBatchScores(projectIds),
    staleTime: TIMING.QUERY_STALE_TIME,
    enabled: projectIds.length > 0,
  });

  const scoresMap = useMemo(() => {
    const map: Record<string, number | null> = {};
    for (const id of projectIds) {
      map[id] = data?.scores[id]?.scores?.score ?? null;
    }
    return map;
  }, [projectIds, data]);

  const latestPeriodMap = useMemo(() => {
    const map: Record<string, string | null> = {};
    for (const id of projectIds) {
      map[id] = data?.scores[id]?.latest_period ?? null;
    }
    return map;
  }, [projectIds, data]);

  return {
    scoresMap,
    latestPeriodMap,
    isLoading,
  };
}
