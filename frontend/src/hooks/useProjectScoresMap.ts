import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scoresApi } from '../services/api';
import { queryKeys } from '@/core/hooks/queryKeys';
import { TIMING } from '../constants/timing';
import type { Project } from '../types';

export interface UseProjectScoresMapReturn {
  scoresMap: Record<string, number | null>;
  isLoading: boolean;
}

export function useProjectScoresMap(
  projects: Project[] | undefined,
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

  return {
    scoresMap,
    isLoading,
  };
}
