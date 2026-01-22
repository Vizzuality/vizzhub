import { useMutation, useQueryClient } from '@tanstack/react-query';
import { collectApi } from '../services/api';

export function useCollectJiraMetrics(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => collectApi.collectJiraMetrics(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
    },
  });
}

export function useCollectGitHubMetrics(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => collectApi.collectGitHubMetrics(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
    },
  });
}
