import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useCallback, useEffect } from 'react';
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

const VISIBILITY_DEBOUNCE_MS = 400;

export function useUpdateColumnVisibility(typeId: string | null): (hiddenColumns: string[]) => void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mutation = useMutation({
    mutationFn: (hiddenColumns: string[]) =>
      registriesApi.updateColumnVisibility(typeId!, hiddenColumns),
  });
  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const debouncedUpdate = useCallback(
    (hiddenColumns: string[]) => {
      if (!typeId) return;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        mutateRef.current(hiddenColumns);
      }, VISIBILITY_DEBOUNCE_MS);
    },
    [typeId],
  );

  return debouncedUpdate;
}
