import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { projectContextsApi } from '../services/projectContexts';
import type {
  ProjectContextCreate,
  ProjectContextUpdate,
} from '../types/projectContexts';

export function useProjectContexts() {
  return useQuery({
    queryKey: queryKeys.devstackProjectContexts.list(),
    queryFn: () => projectContextsApi.list(),
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
    mutationFn: (data: ProjectContextCreate) => projectContextsApi.create(data),
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
    mutationFn: (id: string) => projectContextsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}
