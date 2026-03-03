/**
 * Hooks for Global Metrics Dashboard.
 *
 * These hooks provide access to aggregated metrics across all projects,
 * including historical data for trend analysis.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { globalMetricsApi } from '../services';
import { queryKeys } from '@/core/hooks/queryKeys';
import type {
  AvailableMonth,
  CalculateBatchRequest,
  CalculateBatchResponse,
  GlobalMetricsRecord,
} from '../types/global';

/**
 * Hook for fetching global metrics for a specific month.
 * Returns null if no metrics have been calculated for that month.
 */
export function useGlobalMetrics(
  year: number,
  month: number,
): ReturnType<typeof useQuery<GlobalMetricsRecord | null, Error>> {
  return useQuery({
    queryKey: queryKeys.global.record(year, month),
    queryFn: (): Promise<GlobalMetricsRecord | null> =>
      globalMetricsApi.getRecord(year, month),
  });
}

/**
 * Hook for fetching global metrics history.
 * Returns the most recent months first.
 */
export function useGlobalMetricsHistory(
  limit = 12,
): ReturnType<typeof useQuery<GlobalMetricsRecord[], Error>> {
  return useQuery({
    queryKey: queryKeys.global.history(limit),
    queryFn: (): Promise<GlobalMetricsRecord[]> =>
      globalMetricsApi.getHistory(limit),
  });
}

/**
 * Hook for fetching list of months that have calculated global metrics.
 */
export function useAvailableGlobalMonths(): ReturnType<typeof useQuery<AvailableMonth[], Error>> {
  return useQuery({
    queryKey: queryKeys.global.availableMonths,
    queryFn: (): Promise<AvailableMonth[]> =>
      globalMetricsApi.getAvailableMonths(),
  });
}

/**
 * Hook for batch calculating global metrics for a date range.
 * This computes and stores averages for each month in the range.
 */
export function useCalculateGlobalMetrics(): ReturnType<
  typeof useMutation<CalculateBatchResponse, Error, CalculateBatchRequest>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CalculateBatchRequest): Promise<CalculateBatchResponse> =>
      globalMetricsApi.calculate(request),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.global.all });
    },
  });
}

/**
 * Hook for recalculating global metrics with current weights.
 * Use this after changing configuration weights/targets.
 */
export function useRecalculateGlobalMetrics(): ReturnType<
  typeof useMutation<CalculateBatchResponse, Error, CalculateBatchRequest>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CalculateBatchRequest): Promise<CalculateBatchResponse> =>
      globalMetricsApi.recalculate(request),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.global.all });
    },
  });
}
