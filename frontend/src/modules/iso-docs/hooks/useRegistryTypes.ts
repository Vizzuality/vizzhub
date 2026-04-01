import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { registriesApi } from '../services/registries';
import type { RegistryTypeCreate, RegistryTypeUpdate } from '../types/registry';

export function useRegistryTypes() {
  return useQuery({
    queryKey: queryKeys.isoDocs.registryTypes,
    queryFn: registriesApi.listTypes,
  });
}

export function useRegistryType(id: string | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.registryType(id ?? ''),
    queryFn: () => registriesApi.getType(id!),
    enabled: !!id,
  });
}

export function useCreateRegistryType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RegistryTypeCreate) => registriesApi.createType(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryTypes });
    },
  });
}

export function useUpdateRegistryType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RegistryTypeUpdate }) =>
      registriesApi.updateType(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryTypes });
    },
  });
}

export function useDeleteRegistryType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => registriesApi.deleteType(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryTypes });
    },
  });
}
