import { useQuery } from '@tanstack/react-query';
import { scoresApi, configApi } from '../services';
import { queryKeys } from '@/core/hooks/queryKeys';

export function useProjectScores(
  projectId: string,
  year?: number,
  month?: number,
) {
  const hasPeriod = year !== undefined && month !== undefined;

  return useQuery({
    queryKey: hasPeriod
      ? queryKeys.scores.byPeriod(projectId, year, month)
      : queryKeys.scores.byProject(projectId),
    queryFn: () => scoresApi.getProjectScores(projectId, year, month),
    enabled: !!projectId,
  });
}

export function useScoreHistory(projectId: string, limit = 10) {
  return useQuery({
    queryKey: queryKeys.scores.history(projectId, limit),
    queryFn: () => scoresApi.getScoreHistory(projectId, limit),
    enabled: !!projectId,
  });
}

export function useScoringConfig() {
  return useQuery({
    queryKey: queryKeys.config.all,
    queryFn: configApi.get,
  });
}
