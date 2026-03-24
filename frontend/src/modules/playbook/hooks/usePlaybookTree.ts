import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { playbookApi } from '../services/playbook';
import type { NodeCreateRequest, NodeUpdateRequest, ReorderItem } from '../types/playbook';

export function usePlaybookTree() {
  return useQuery({
    queryKey: queryKeys.playbook.tree,
    queryFn: playbookApi.getTree,
  });
}

export function useCreateNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: NodeCreateRequest) => playbookApi.createNode(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.tree });
    },
  });
}

export function useUpdateNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: NodeUpdateRequest }) =>
      playbookApi.updateNode(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.tree });
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.page(id) });
    },
  });
}

export function useDeleteNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => playbookApi.deleteNode(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.tree });
    },
  });
}

export function useReorderNodes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: ReorderItem[]) => playbookApi.reorderNodes(items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.tree });
    },
  });
}
