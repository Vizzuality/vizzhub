import type { QueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';

/**
 * Invalidate all project-related data caches.
 *
 * This is the standard pattern used after mutations that affect
 * metrics or scores. Centralizing this logic prevents duplication
 * across multiple hooks.
 */
export function invalidateProjectData(
  queryClient: QueryClient,
  projectId: string,
): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
  queryClient.invalidateQueries({ queryKey: ['scores', 'batch'] });
}

/**
 * Invalidate project data for a specific period.
 *
 * Use this when a mutation affects a specific month's data
 * in addition to the general project cache.
 */
export function invalidateProjectPeriodData(
  queryClient: QueryClient,
  projectId: string,
  year: number,
  month: number,
): void {
  invalidateProjectData(queryClient, projectId);
  queryClient.invalidateQueries({
    queryKey: queryKeys.metrics.byPeriod(projectId, year, month),
  });
  queryClient.invalidateQueries({
    queryKey: queryKeys.scores.byPeriod(projectId, year, month),
  });
}

/**
 * Invalidate project data including snapshots.
 *
 * Use this after capture operations that create new snapshots.
 */
export function invalidateProjectCaptureData(
  queryClient: QueryClient,
  projectId: string,
): void {
  invalidateProjectData(queryClient, projectId);
  queryClient.invalidateQueries({
    queryKey: queryKeys.snapshots.byProject(projectId),
  });
}
