import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocsApi } from '../services/isoDocs';

export function useDriveExportStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.isoDocs.driveStatus,
    queryFn: isoDocsApi.getDriveExportStatus,
    refetchOnWindowFocus: false,
    enabled,
  });
}

export function useTriggerDriveExport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: isoDocsApi.triggerDriveExport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.driveStatus });
    },
  });
}

export function useSaveDriveFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: isoDocsApi.saveDriveFolder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.driveStatus });
    },
  });
}
