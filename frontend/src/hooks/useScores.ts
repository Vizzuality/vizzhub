import { useQuery } from '@tanstack/react-query';
import { scoresApi, configApi } from '../services/api';
import { queryKeys } from './queryKeys';

export function useProjectScores(projectId: string) {
  return useQuery({
    queryKey: queryKeys.scores.byProject(projectId),
    queryFn: () => scoresApi.getProjectScores(projectId),
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
