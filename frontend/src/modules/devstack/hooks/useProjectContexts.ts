import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { projectContextsApi } from '../services/projectContexts';
import type { ProjectContextUpdate } from '../types/projectContexts';

export function useProjectContexts() {
  return useQuery({
    queryKey: queryKeys.devstackProjectContexts.list(),
    queryFn: projectContextsApi.list,
  });
}

export function useProjectContext(id: string) {
  return useQuery({
    queryKey: queryKeys.devstackProjectContexts.detail(id),
    queryFn: () => projectContextsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateProjectContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: projectContextsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}

export function useUpdateProjectContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProjectContextUpdate }) =>
      projectContextsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}

export function useDeleteProjectContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: projectContextsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}
