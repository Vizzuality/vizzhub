import { useMutation, useQueryClient } from '@tanstack/react-query';
import { collectApi } from '../services/api';
import { queryKeys } from './queryKeys';

export function useCollectJiraMetrics(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => collectApi.collectJiraMetrics(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
    },
  });
}

export function useCollectGitHubMetrics(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => collectApi.collectGitHubMetrics(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
    },
  });
}
