import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocsApi } from '../services/isoDocs';
import type { PageSaveRequest } from '../types/isoDocs';

export function useIsoDocPage(nodeId: string | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.isoDocs.page(nodeId ?? ''),
    queryFn: () => isoDocsApi.getPage(nodeId!),
    enabled: !!nodeId && enabled,
    refetchOnWindowFocus: false,
  });
}

export function useSaveIsoDocPage(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PageSaveRequest) => isoDocsApi.savePage(nodeId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.isoDocs.page(nodeId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.isoDocs.versions(nodeId),
      });
    },
  });
}
