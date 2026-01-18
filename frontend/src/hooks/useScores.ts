import { useQuery } from '@tanstack/react-query';
import { scoresApi, configApi } from '../services/api';

export function useProjectScores(projectId: string) {
  return useQuery({
    queryKey: ['scores', projectId],
    queryFn: () => scoresApi.getProjectScores(projectId),
    enabled: !!projectId,
  });
}

export function useScoreHistory(projectId: string, limit = 10) {
  return useQuery({
    queryKey: ['scores', projectId, 'history', limit],
    queryFn: () => scoresApi.getScoreHistory(projectId, limit),
    enabled: !!projectId,
  });
}

export function useScoringConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: configApi.get,
  });
}

export function useConfigValidation() {
  return useQuery({
    queryKey: ['config', 'validation'],
    queryFn: configApi.validate,
  });
}
