import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { scoresApi } from '../services/api';
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
      queryKey: ['scores', project.id],
      queryFn: () => scoresApi.getProjectScores(project.id),
      staleTime: 5 * 60 * 1000,
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
