import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { captureApi } from '../services';
import { invalidateProjectCaptureData } from './cacheUtils';
import type { CapturePeriodRequest, CapturePeriodResponse } from '../types';
import type { ApiErrorResponse } from '@/core/types/common';

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
      invalidateProjectCaptureData(queryClient, projectId);
      options.onSuccess?.(data);
    },
    onError: (error: Error) => {
      const axiosError = error as AxiosError<ApiErrorResponse>;
      const detail = axiosError.response?.data?.detail;
      options.onError?.(error, detail);
    },
  });
}
