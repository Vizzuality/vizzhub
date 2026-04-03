import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { registriesApi } from '../services/registries';
import type { RegistryRowCreate, RegistryRowUpdate } from '../types/registry';

function invalidateRows(queryClient: ReturnType<typeof useQueryClient>, nodeId: string): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryRows(nodeId) });
}

export function useRegistryYears(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.registryYears(nodeId ?? ''),
    queryFn: () => registriesApi.listYears(nodeId!),
    enabled: !!nodeId,
  });
}

export function useRegistryRows(nodeId: string | null, year?: number) {
  return useQuery({
    queryKey: queryKeys.isoDocs.registryRows(nodeId ?? '', year),
    queryFn: () => registriesApi.listRows(nodeId!, year),
    enabled: !!nodeId,
  });
}

export function useCreateRegistryRow(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RegistryRowCreate) => registriesApi.createRow(nodeId, body),
    onSuccess: () => invalidateRows(queryClient, nodeId),
  });
}

export function useUpdateRegistryRow(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rowId, data }: { rowId: string; data: RegistryRowUpdate }) =>
      registriesApi.updateRow(nodeId, rowId, data),
    onSuccess: () => invalidateRows(queryClient, nodeId),
  });
}

export function useDeleteRegistryRow(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rowId: string) => registriesApi.deleteRow(nodeId, rowId),
    onSuccess: () => invalidateRows(queryClient, nodeId),
  });
}

export function useReorderRegistryRows(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rowIds: string[]) => registriesApi.reorderRows(nodeId, rowIds),
    onSuccess: () => invalidateRows(queryClient, nodeId),
  });
}

export function useImportCsv(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, year }: { file: File; year?: number }) =>
      registriesApi.importCsv(nodeId, file, year),
    onSuccess: () => {
      invalidateRows(queryClient, nodeId);
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryYears(nodeId) });
    },
  });
}

export function useExportToDrive(nodeId: string) {
  return useMutation({
    mutationFn: (year?: number) => registriesApi.exportToDrive(nodeId, year),
  });
}

export function useExportRegistry(nodeId: string) {
  return useMutation({
    mutationFn: ({ format, year }: { format: 'xlsx' | 'csv'; year?: number }) =>
      registriesApi.exportRegistry(nodeId, format, year),
    onSuccess: (blob, { format }) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `registry.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
}
