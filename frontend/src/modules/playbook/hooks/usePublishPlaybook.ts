import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { playbookApi } from '../services/playbook';
import type { PublishStatus } from '../types/playbook';

export function usePublishPlaybook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => playbookApi.publishPlaybook(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.publishStatus });
    },
  });
}

export function usePublishStatus() {
  return useQuery<PublishStatus | null>({
    queryKey: queryKeys.playbook.publishStatus,
    queryFn: playbookApi.getPublishStatus,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === 'running' ? 3000 : false;
    },
  });
}
