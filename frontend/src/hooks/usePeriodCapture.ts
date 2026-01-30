import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { captureApi } from '../services/api';
import { queryKeys } from './queryKeys';
import type { CapturePeriodRequest, CapturePeriodResponse } from '../types';

interface ApiErrorResponse {
  detail: string;
}

interface UseCapturePeriodOptions {
  onSuccess?: (data: CapturePeriodResponse) => void;
  onError?: (error: Error, detail?: string) => void;
}

export function useCapturePeriod(
  projectId: string,
  options: UseCapturePeriodOptions = {},
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CapturePeriodRequest) =>
      captureApi.capturePeriod(projectId, request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.snapshots.byProject(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.metrics.byProject(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.scores.byProject(projectId),
      });
      options.onSuccess?.(data);
    },
    onError: (error: Error) => {
      const axiosError = error as AxiosError<ApiErrorResponse>;
      const detail = axiosError.response?.data?.detail;
      options.onError?.(error, detail);
    },
  });
}

export function getCapturePeriodErrorMessage(error: Error): string {
  const axiosError = error as AxiosError<ApiErrorResponse>;
  if (axiosError.response?.status === 409) {
    return axiosError.response.data?.detail ?? 'Snapshot already exists for this period';
  }
  if (axiosError.response?.status === 400) {
    return axiosError.response.data?.detail ?? 'Invalid capture request';
  }
  return 'Failed to capture period. Verify that the project has Jira or GitHub configured.';
}

/**
 * Simplified hook for collecting metrics from Jira and GitHub.
 * Captures current month data with force=true (always overwrites).
 * Creates both punctual and cumulative snapshots.
 */
export function useCollectMetrics(
  projectId: string,
  options: UseCapturePeriodOptions = {},
) {
  const mutation = useCapturePeriod(projectId, options);

  return {
    ...mutation,
    collectMetrics: () => mutation.mutate({ force: true }),
  };
}
