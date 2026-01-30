import { useMutation, useQueryClient } from '@tanstack/react-query';
import { snapshotsApi } from '../services/api';
import { queryKeys } from './queryKeys';
import type { CaptureHistoryRequest, CaptureReport } from '../types';

export function useHistoricalCapture(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CaptureHistoryRequest): Promise<CaptureReport> =>
      snapshotsApi.captureHistory(projectId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.snapshots.byProject(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.scores.byProject(projectId),
      });
    },
  });
}
