import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

export function useConfigParameters() {
  return useQuery({
    queryKey: ['config', 'parameters'],
    queryFn: configApi.getParameters,
  });
}

export function useUpdateConfigParameters() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (updates: Array<{ name: string; value: string }>) =>
      configApi.updateParameters(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['config', 'parameters'] });
      queryClient.invalidateQueries({ queryKey: ['config', 'validation'] });
    },
  });
}
