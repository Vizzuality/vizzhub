import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocsApi } from '../services/isoDocs';
import type { NodeCreateRequest, NodeUpdateRequest, ReorderItem } from '../types/isoDocs';

export function useIsoDocTree() {
  return useQuery({
    queryKey: queryKeys.isoDocs.tree,
    queryFn: isoDocsApi.getTree,
  });
}

export function useCreateIsoDocNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: NodeCreateRequest) => isoDocsApi.createNode(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.tree });
    },
  });
}

export function useUpdateIsoDocNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: NodeUpdateRequest }) =>
      isoDocsApi.updateNode(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.tree });
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.page(id) });
    },
  });
}

export function useDeleteIsoDocNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => isoDocsApi.deleteNode(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.tree });
    },
  });
}

export function useReorderIsoDocNodes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: ReorderItem[]) => isoDocsApi.reorderNodes(items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.tree });
    },
  });
}
