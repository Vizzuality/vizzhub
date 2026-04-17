import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { devstackApi } from '../services/devstack';
import type { DevstackEntryCreate, DevstackEntryListParams, DevstackEntryUpdate } from '../types/devstack';

export function useDevstackEntries(params: DevstackEntryListParams = {}) {
  return useQuery({
    queryKey: queryKeys.devstack.list(params as Record<string, unknown>),
    queryFn: () => devstackApi.list(params),
  });
}

export function useDevstackEntry(id: string) {
  return useQuery({
    queryKey: queryKeys.devstack.detail(id),
    queryFn: () => devstackApi.get(id),
    enabled: !!id,
  });
}

export function useCreateDevstackEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DevstackEntryCreate) => devstackApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.all });
    },
  });
}

export function useUpdateDevstackEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DevstackEntryUpdate }) =>
      devstackApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.all });
    },
  });
}

export function useDeleteDevstackEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => devstackApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.all });
    },
  });
}

