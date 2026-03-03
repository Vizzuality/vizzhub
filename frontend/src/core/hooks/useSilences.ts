import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { silencesApi } from '@/core/services/notifications';
import { queryKeys } from './queryKeys';
import type { AlertSilence, AlertSilenceCreate, AlertSilenceUpdate } from '@/types';

/**
 * Hook for fetching alert silences.
 */
export function useSilences(
  projectId?: string,
  includeExpired = false,
): ReturnType<typeof useQuery<AlertSilence[], Error>> {
  return useQuery({
    queryKey: queryKeys.silences.list(projectId),
    queryFn: (): Promise<AlertSilence[]> => silencesApi.list(projectId, includeExpired),
  });
}

/**
 * Hook for creating a silence.
 */
export function useCreateSilence(): ReturnType<
  typeof useMutation<AlertSilence, Error, AlertSilenceCreate>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AlertSilenceCreate): Promise<AlertSilence> => silencesApi.create(data),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.silences.all });
    },
  });
}

/**
 * Hook for updating a silence.
 */
export function useUpdateSilence(): ReturnType<
  typeof useMutation<AlertSilence, Error, { id: number; data: AlertSilenceUpdate }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }): Promise<AlertSilence> => silencesApi.update(id, data),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.silences.all });
    },
  });
}

/**
 * Hook for deleting a silence.
 */
export function useDeleteSilence(): ReturnType<typeof useMutation<void, Error, number>> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number): Promise<void> => silencesApi.delete(id),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.silences.all });
    },
  });
}
