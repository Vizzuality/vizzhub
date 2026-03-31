import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { playbookApi } from '../services/playbook';
import type { PageSaveRequest } from '../types/playbook';

export function usePlaybookPage(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.playbook.page(nodeId ?? ''),
    queryFn: () => playbookApi.getPage(nodeId!),
    enabled: !!nodeId,
    refetchOnWindowFocus: false,
  });
}

export function useSavePage(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PageSaveRequest) => playbookApi.savePage(nodeId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.playbook.page(nodeId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.playbook.versions(nodeId),
      });
    },
  });
}

export function useAssetStatus() {
  return useQuery({
    queryKey: queryKeys.playbook.assetStatus,
    queryFn: playbookApi.getAssetStatus,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
