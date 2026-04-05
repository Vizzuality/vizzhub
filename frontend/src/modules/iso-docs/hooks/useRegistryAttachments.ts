import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { registriesApi } from '../services/registries';

export function useUploadAttachment(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rowId, file, fieldKey }: { rowId: string; file: File; fieldKey?: string }) =>
      registriesApi.uploadAttachment(nodeId, rowId, file, fieldKey),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.isoDocs.registryRows(nodeId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.assets.all });
    },
  });
}

export function useDeleteAttachment(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (attachmentId: string) => registriesApi.deleteAttachment(attachmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.isoDocs.registryRows(nodeId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.assets.all });
    },
  });
}
