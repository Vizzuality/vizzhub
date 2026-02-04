import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { scoresApi } from '../services/api';
import { queryKeys } from './queryKeys';
import { TIMING } from '../constants/timing';
import type { Project } from '../types';

export interface UseProjectScoresMapReturn {
  scoresMap: Record<string, number | null>;
  isLoading: boolean;
}

export function useProjectScoresMap(
  projects: Project[] | undefined,
): UseProjectScoresMapReturn {
  const scoreQueries = useQueries({
    queries: (projects ?? []).map((project) => ({
      queryKey: queryKeys.scores.byProject(project.id),
      queryFn: () => scoresApi.getProjectScores(project.id),
      staleTime: TIMING.QUERY_STALE_TIME,
      retry: false,
    })),
  });

  const scoresMap = useMemo(() => {
    const map: Record<string, number | null> = {};
    (projects ?? []).forEach((project, index) => {
      const query = scoreQueries[index];
      map[project.id] = query?.data?.scores?.score ?? null;
    });
    return map;
  }, [projects, scoreQueries]);

  const isLoading = scoreQueries.some((q) => q.isLoading);

  return {
    scoresMap,
    isLoading,
  };
}
